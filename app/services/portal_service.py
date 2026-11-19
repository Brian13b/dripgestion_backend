from app.core.timezone import a_local
from app.crud import crud_portal
from sqlalchemy.orm import Session

def obtener_datos_mi_cuenta(db: Session, user_id: int, tenant_id: int):
  cliente = crud_portal.get_cliente_por_usuario(db, user_id, tenant_id)
  if not cliente:
    raise ValueError("Perfil de cliente no encontrado")

  tipos_envase = crud_portal.get_tipos_envase_tenant(db, tenant_id)
  mapa_envases = {str(e.id): e for e in tipos_envase}

  total_envases = 0
  envases_detalle = []

  if isinstance(cliente.stock_envases, dict):
    for env_id_str, cant in cliente.stock_envases.items():
      cantidad = int(cant or 0)
      if cantidad <= 0:
        continue
      total_envases += cantidad
      tipo = mapa_envases.get(str(env_id_str))
      if tipo:
        envases_detalle.append({
            "tipo_envase_id": tipo.id,
            "nombre": tipo.nombre,
            "codigo": tipo.codigo,
            "cantidad": cantidad,
        })

  movimientos_db = crud_portal.get_ultimos_movimientos_cliente(
      db, cliente.id, tenant_id
  )
  productos = crud_portal.get_productos_tenant(db, tenant_id)
  mapa_productos = {str(p.id): p.nombre for p in productos}

  ultimos_movimientos = []
  for mov in movimientos_db:
    detalles_texto = []
    if isinstance(mov.detalles, dict):
      for prod_id, cant in mov.detalles.items():
        if prod_id == "_devoluciones_envases" and isinstance(cant, dict):
          for env_id, dev_cant in cant.items():
            if int(dev_cant or 0) > 0:
              nombre_env = (
                  mapa_envases[str(env_id)].nombre
                  if str(env_id) in mapa_envases
                  else "Envase"
              )
              detalles_texto.append(f"Dev. {dev_cant} {nombre_env}")
          continue

        if isinstance(cant, dict):
          entregados = int(cant.get("entregado", 0))
          if entregados > 0:
            nombre_prod = mapa_productos.get(str(prod_id), "Producto")
            detalles_texto.append(f"{entregados} {nombre_prod}")

    texto_productos = (
        " + ".join(detalles_texto) if detalles_texto else "Solo cobro"
    )
    fecha_str = a_local(mov.fecha).strftime("%d/%m/%Y")
    metodo = getattr(mov.metodo_pago, "value", mov.metodo_pago)
    monto_mostrar = (
        mov.monto_total if metodo == "cta_corriente" else mov.monto_cobrado
    )

    ultimos_movimientos.append({
        "fecha": fecha_str,
        "resumen_productos": texto_productos,
        "monto": monto_mostrar,
        "tipo": "Fiado" if metodo == "cta_corriente" else metodo,
    })

  return {
      "nombre_negocio": cliente.nombre_negocio,
      "direccion": cliente.direccion,
      "saldo_dinero": cliente.saldo_dinero,
      "total_envases": total_envases,
      "detalle_envases": cliente.stock_envases,
      "envases_detalle": envases_detalle,
      "ultimos_movimientos": ultimos_movimientos,
  }