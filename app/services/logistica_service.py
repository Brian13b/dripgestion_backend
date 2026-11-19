from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional
from app.core.timezone import a_local, hoy_local
from app.crud import crud_logistica
from app.models.cliente import Cliente
from app.models.logistica import Recorrido
from app.models.producto import Producto, TipoEnvase
from app.models.user import UserRole
from app.schemas.logistica import MovimientoCreate, PagoManualCreate
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.logistica import Movimiento


class ClaveIdempotenciaReutilizada(ValueError):
  """La misma Idempotency-Key se usó para otra operación distinta (otro cliente)."""


def _query_cliente_bloqueado(db: Session, cliente_id: int, tenant_id: int):
  """Cliente con BLOQUEO DE FILA (SELECT ... FOR UPDATE en PostgreSQL).

  Dos operaciones simultáneas sobre el mismo cliente (dos repartidores, o un
  repartidor y el admin) se ejecutan una detrás de otra en vez de pisarse:
  `saldo_dinero` y `stock_envases` se leen, modifican y guardan sin perder
  ninguna actualización. El bloqueo se libera con el commit/rollback.
  """
  return (
      db.query(Cliente)
      .filter(Cliente.id == cliente_id, Cliente.tenant_id == tenant_id)
      .populate_existing()
      .with_for_update()
  )


def _movimiento_por_clave(db: Session, tenant_id: int, clave: str):
  return (
      db.query(Movimiento)
      .filter(Movimiento.tenant_id == tenant_id, Movimiento.idempotency_key == clave)
      .first()
  )


def _repetido_o_none(db: Session, tenant_id: int, clave: Optional[str], cliente_id: int):
  """Si la operación con esta clave ya se registró, devuelve el movimiento original."""
  if not clave:
    return None
  existente = _movimiento_por_clave(db, tenant_id, clave)
  if existente is None:
    return None
  if existente.cliente_id != cliente_id:
    raise ClaveIdempotenciaReutilizada(
        "La clave de idempotencia ya se usó para otra operación"
    )
  return existente


def _centavos(valor) -> float:
  """Redondea a 2 decimales (mitad hacia arriba) para que los saldos no acumulen
  errores de punto flotante (0.1 + 0.2 != 0.3)."""
  return float(Decimal(str(valor or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _validar_cliente_en_rutas_de_repartidor(
    db: Session, cliente_id: int, repartidor_id: int, tenant_id: int
):
  recorridos = (
      db.query(Recorrido)
      .filter(
          Recorrido.tenant_id == tenant_id,
          Recorrido.repartidor_id == repartidor_id,
      )
      .all()
  )

  for recorrido in recorridos:
    orden = (
        [int(c) for c in recorrido.clientes_orden]
        if recorrido.clientes_orden
        else []
    )
    if cliente_id in orden:
      return

  raise ValueError(
      "No tenés permiso para operar con este cliente. No está asignado en"
      " ninguna de tus rutas."
  )


def registrar_entrega(
    db: Session,
    mov_in: MovimientoCreate,
    current_user: Any,
    tenant_id: int,
    idempotency_key: Optional[str] = None,
):
  cliente = _query_cliente_bloqueado(db, mov_in.cliente_id, tenant_id).first()

  if not cliente:
    raise ValueError("Cliente no encontrado")

  # Reintento (por mala señal, doble toque, etc.): se devuelve lo ya registrado
  # SIN volver a sumar deuda, envases ni movimientos. Se chequea con el cliente
  # bloqueado para que dos reintentos simultáneos se ordenen.
  repetido = _repetido_o_none(db, tenant_id, idempotency_key, mov_in.cliente_id)
  if repetido is not None:
    db.rollback()  # libera el bloqueo
    db.refresh(repetido)  # el rollback expira el objeto: se recarga para serializarlo
    return repetido

  repartidor_id = current_user.id

  if mov_in.recorrido_id:
    recorrido = (
        db.query(Recorrido)
        .filter(
            Recorrido.id == mov_in.recorrido_id,
            Recorrido.tenant_id == tenant_id,
        )
        .first()
    )

    if not recorrido:
      raise ValueError("Recorrido no encontrado")

    if current_user.role != UserRole.ADMIN:
      if recorrido.repartidor_id != current_user.id:
        raise ValueError(
            "No tenés permiso para registrar movimientos en este recorrido"
        )

    repartidor_id = recorrido.repartidor_id or current_user.id
  elif current_user.role != UserRole.ADMIN:
    _validar_cliente_en_rutas_de_repartidor(
        db, mov_in.cliente_id, current_user.id, tenant_id
    )

  try:
    # --- Actualización dinámica de stock de envases por tipo_envase_id ---
    if not isinstance(cliente.stock_envases, dict):
      cliente.stock_envases = {}

    stock_actualizado = {
        str(k): int(v) for k, v in cliente.stock_envases.items()
    }

    # Cargar productos del tenant involucrados en el detalle
    productos_ids = [int(pid) for pid in mov_in.detalles.keys() if str(pid).isdigit()]
    productos_db = (
        db.query(Producto)
        .filter(Producto.tenant_id == tenant_id, Producto.id.in_(productos_ids))
        .all()
        if productos_ids
        else []
    )
    mapa_productos = {str(p.id): p for p in productos_db}

    subtotal_catalogo = 0.0

    for producto_id, cant in mov_in.detalles.items():
      producto = mapa_productos.get(str(producto_id))
      if not producto:
        raise ValueError(f"Producto ID {producto_id} no encontrado en esta empresa")

      if isinstance(cant, dict):
        entregado = int(cant.get("entregado", 0))
        devuelto = int(cant.get("devuelto", 0))
      else:
        entregado = int(cant)
        devuelto = 0

      subtotal_catalogo += (producto.precio_actual or 0.0) * entregado

      # Solo los productos retornables con tipo_envase_id modifican el saldo de envases
      if not producto.es_retornable or not producto.tipo_envase_id:
        continue

      clave_envase = str(producto.tipo_envase_id)
      if clave_envase not in stock_actualizado:
        stock_actualizado[clave_envase] = 0

      nuevo_saldo_envase = stock_actualizado[clave_envase] + (entregado - devuelto)
      stock_actualizado[clave_envase] = max(0, nuevo_saldo_envase)

    # El total nunca puede superar el valor de lo entregado según el catálogo
    # (sí puede ser menor: descuentos). Se valida solo si hay productos en el detalle.
    if mov_in.detalles and mov_in.monto_total > subtotal_catalogo + 0.01:
      raise ValueError(
          "El total no puede superar el valor de los productos entregados según el catálogo"
      )

    # Devoluciones directas por tipo_envase_id (ej. retiro de envases vacíos sin compra)
    if mov_in.devoluciones_envases:
      envases_validos = {
          str(e.id)
          for e in db.query(TipoEnvase.id)
          .filter(TipoEnvase.tenant_id == tenant_id)
          .all()
      }
      for envase_id, cant_devuelta in mov_in.devoluciones_envases.items():
        clave_envase = str(envase_id)
        if clave_envase not in envases_validos:
          raise ValueError(f"Tipo de envase ID {envase_id} no válido")
        actual = stock_actualizado.get(clave_envase, 0)
        stock_actualizado[clave_envase] = max(0, actual - int(cant_devuelta))

    cliente.stock_envases = stock_actualizado

    # --- Actualización de saldo monetario ---
    monto_total = _centavos(mov_in.monto_total)
    monto_cobrado = _centavos(mov_in.monto_cobrado)
    cliente.saldo_dinero = _centavos((cliente.saldo_dinero or 0) + monto_total - monto_cobrado)
    db.add(cliente)

    # --- Persistencia del movimiento ---
    detalles_guardar = dict(mov_in.detalles)
    if mov_in.devoluciones_envases:
      detalles_guardar["_devoluciones_envases"] = mov_in.devoluciones_envases

    mov_data = {
        "tenant_id": tenant_id,
        "cliente_id": mov_in.cliente_id,
        "repartidor_id": repartidor_id,
        "recorrido_id": mov_in.recorrido_id,
        "detalles": detalles_guardar,
        "monto_total": monto_total,
        "monto_cobrado": monto_cobrado,
        "metodo_pago": mov_in.metodo_pago,
        "observacion": mov_in.observacion,
        "idempotency_key": idempotency_key,
    }
    movimiento_creado = crud_logistica.create_movimiento(db, mov_data)
    db.commit()
    db.refresh(movimiento_creado)
    return movimiento_creado

  except ValueError:
    db.rollback()
    raise
  except IntegrityError:
    # Carrera extrema: otra petición con la misma clave ganó justo antes.
    db.rollback()
    ganador = (
        _movimiento_por_clave(db, tenant_id, idempotency_key)
        if idempotency_key
        else None
    )
    if ganador is not None:
      return ganador
    raise ValueError("Error al registrar la entrega: conflicto de datos")
  except Exception as e:
    db.rollback()
    raise ValueError(f"Error al registrar la entrega: {str(e)}")


def registrar_pago_manual(
    db: Session,
    cliente_id: int,
    pago_in: PagoManualCreate,
    current_user: Any,
    tenant_id: int,
    idempotency_key: Optional[str] = None,
):
  cliente = _query_cliente_bloqueado(db, cliente_id, tenant_id).first()
  if not cliente:
    raise ValueError("Cliente no encontrado")

  repetido = _repetido_o_none(db, tenant_id, idempotency_key, cliente_id)
  if repetido is not None:
    nuevo_saldo = cliente.saldo_dinero
    db.rollback()  # libera el bloqueo
    return {"message": "Pago ya registrado", "nuevo_saldo": nuevo_saldo, "repetido": True}

  if current_user.role != UserRole.ADMIN:
    _validar_cliente_en_rutas_de_repartidor(
        db, cliente_id, current_user.id, tenant_id
    )

  monto_pago = _centavos(pago_in.monto)
  cliente.saldo_dinero = _centavos((cliente.saldo_dinero or 0) - monto_pago)
  db.add(cliente)

  mov_data = {
      "tenant_id": tenant_id,
      "cliente_id": cliente_id,
      "repartidor_id": current_user.id,
      "recorrido_id": None,
      "detalles": {},
      "monto_total": 0.0,
      "monto_cobrado": monto_pago,
      "metodo_pago": pago_in.metodo_pago,
      "observacion": f"Pago de saldo. {pago_in.observacion}".strip(),
      "idempotency_key": idempotency_key,
  }

  try:
    crud_logistica.create_movimiento(db, mov_data)
    db.commit()
    return {"message": "Pago registrado", "nuevo_saldo": cliente.saldo_dinero}
  except IntegrityError:
    db.rollback()
    ganador = (
        _movimiento_por_clave(db, tenant_id, idempotency_key)
        if idempotency_key
        else None
    )
    if ganador is not None:
      cli = db.query(Cliente).filter(Cliente.id == cliente_id).first()
      return {"message": "Pago ya registrado", "nuevo_saldo": cli.saldo_dinero, "repetido": True}
    raise ValueError("Error al registrar el pago manual: conflicto de datos")
  except Exception as e:
    db.rollback()
    raise ValueError(f"Error al registrar el pago manual: {str(e)}")


def obtener_historial_dia(
    db: Session,
    fecha: date,
    tenant_id: int,
    chofer_id: Optional[int] = None,
    recorrido_id: Optional[int] = None,
):
  movimientos = crud_logistica.get_movimientos_dia(
      db, fecha, tenant_id, chofer_id, recorrido_id
  )
  productos = db.query(Producto).filter(Producto.tenant_id == tenant_id).all()
  mapa_productos = {str(p.id): p.nombre for p in productos}

  envases = db.query(TipoEnvase).filter(TipoEnvase.tenant_id == tenant_id).all()
  mapa_envases = {str(e.id): e.nombre for e in envases}

  resultados = []

  for mov, nombre_cliente in movimientos:
    detalles_texto = []
    if mov.detalles:
      for prod_id, cant in mov.detalles.items():
        if prod_id == "_devoluciones_envases" and isinstance(cant, dict):
          for env_id, dev_cant in cant.items():
            if int(dev_cant) > 0:
              nombre_env = mapa_envases.get(str(env_id), "Envase")
              detalles_texto.append(f"-{dev_cant} {nombre_env}")
          continue

        if isinstance(cant, dict):
          entregados = cant.get("entregado", 0)
          if entregados > 0:
            nombre_prod = mapa_productos.get(str(prod_id), "Producto")
            detalles_texto.append(f"{entregados} {nombre_prod}")

    texto_productos = (
        " + ".join(detalles_texto)
        if detalles_texto
        else "Solo cobro / Sin entrega"
    )

    resultados.append({
        "id": mov.id,
        "hora": a_local(mov.fecha).strftime("%H:%M"),
        "cliente": nombre_cliente,
        "metodo_pago": mov.metodo_pago,
        "monto_total": mov.monto_total,
        "monto_cobrado": mov.monto_cobrado,
        "resumen_productos": texto_productos,
        "observacion": mov.observacion,
    })

  return resultados


def obtener_resumen_mes(db: Session, user: Any):
  if user.role != UserRole.ADMIN:
    raise ValueError("No tienes permisos para ver el resumen mensual.")

  hoy = hoy_local()
  tenant_id = user.tenant_id

  movimientos = crud_logistica.get_movimientos_mes(
      db, hoy.month, hoy.year, tenant_id
  )

  efectivo = _centavos(sum(
      m.monto_cobrado for m in movimientos if m.metodo_pago == "efectivo"
  ))
  transferencia = _centavos(sum(
      m.monto_cobrado for m in movimientos if m.metodo_pago == "transferencia"
  ))

  deuda_en_calle = (
      db.query(func.sum(Cliente.saldo_dinero))
      .filter(Cliente.tenant_id == tenant_id, Cliente.saldo_dinero > 0)
      .scalar()
      or 0.0
  )

  return {
      "efectivo": efectivo,
      "transferencia": transferencia,
      "fiado": _centavos(deuda_en_calle),
  }