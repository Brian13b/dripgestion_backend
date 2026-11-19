"""
Calendario operativo: turnos de recorrido.

Un turno = "esta ruta sale este día, de `hora_desde` a `hora_hasta`, con 1 a 3 repartidores"
(uno conduce y los otros ayudan a descargar). Se programan por fecha concreta, o en lote
para los próximos meses con `programar_turnos`.
"""
from datetime import date, time, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session, selectinload

from app.core.timezone import hoy_local
from app.models.logistica import Recorrido, Turno, TurnoRepartidor
from app.models.user import User, UserRole
from app.schemas.logistica import ProgramarTurnos, TurnoCreate, TurnoRepartidorIn, TurnoUpdate
from app.services.errores import Conflicto, NoEncontrado

MAX_DIAS_PROGRAMACION = 366
MAX_DIAS_CONSULTA = 93


def _validar_equipo(db: Session, tenant_id: int, equipo: List[TurnoRepartidorIn]) -> dict:
  ids = [e.user_id for e in equipo]
  usuarios = (
      db.query(User)
      .filter(User.tenant_id == tenant_id, User.id.in_(ids), User.role == UserRole.REPARTIDOR, User.is_active == True)  # noqa: E712
      .all()
  )
  mapa = {u.id: u for u in usuarios}
  faltan = [i for i in ids if i not in mapa]
  if faltan:
    raise ValueError("Hay repartidores que no existen, están inactivos o no son de esta empresa")
  return mapa


def _se_pisan(d1: time, h1: time, d2: time, h2: time) -> bool:
  return d1 < h2 and d2 < h1


def _conflicto_de_horario(
    db: Session, tenant_id: int, fecha: date, desde: time, hasta: time,
    user_ids: List[int], excluir_turno_id: Optional[int] = None,
) -> Optional[str]:
  """Un repartidor no puede estar en dos turnos que se superponen el mismo día."""
  q = (
      db.query(Turno)
      .join(TurnoRepartidor, TurnoRepartidor.turno_id == Turno.id)
      .filter(Turno.tenant_id == tenant_id, Turno.fecha == fecha, TurnoRepartidor.user_id.in_(user_ids))
  )
  if excluir_turno_id:
    q = q.filter(Turno.id != excluir_turno_id)
  for otro in q.all():
    if _se_pisan(desde, hasta, otro.hora_desde, otro.hora_hasta):
      comunes = {r.user_id for r in otro.repartidores} & set(user_ids)
      nombres = ", ".join(sorted(
          (r.usuario.full_name or r.usuario.username) for r in otro.repartidores if r.user_id in comunes
      ))
      return (
          f"{nombres} ya está en otro turno ese día "
          f"({otro.hora_desde:%H:%M}–{otro.hora_hasta:%H:%M})"
      )
  return None


def _recorrido(db: Session, tenant_id: int, recorrido_id: int) -> Recorrido:
  recorrido = (
      db.query(Recorrido)
      .filter(Recorrido.id == recorrido_id, Recorrido.tenant_id == tenant_id)
      .first()
  )
  if not recorrido:
    raise NoEncontrado("Recorrido no encontrado")
  return recorrido


def _query_base(db: Session):
  return db.query(Turno).options(selectinload(Turno.repartidores).selectinload(TurnoRepartidor.usuario))


def _agregar_equipo(turno: Turno, equipo: List[TurnoRepartidorIn]):
  turno.repartidores = [TurnoRepartidor(user_id=e.user_id, rol=e.rol) for e in equipo]


def serializar(turno: Turno, nombre_recorrido: str) -> dict:
  return {
      "id": turno.id,
      "recorrido_id": turno.recorrido_id,
      "recorrido_nombre": nombre_recorrido,
      "fecha": turno.fecha,
      "hora_desde": turno.hora_desde,
      "hora_hasta": turno.hora_hasta,
      "nota": turno.nota,
      "repartidores": [
          {
              "user_id": r.user_id,
              "nombre": r.usuario.full_name or r.usuario.username,
              "rol": r.rol,
          }
          for r in sorted(turno.repartidores, key=lambda x: (x.rol.value != "conductor", x.id))
      ],
  }


def _con_nombre(db: Session, tenant_id: int, turnos: List[Turno]) -> List[dict]:
  ids = {t.recorrido_id for t in turnos}
  nombres = {
      r.id: r.nombre
      for r in db.query(Recorrido.id, Recorrido.nombre).filter(Recorrido.tenant_id == tenant_id, Recorrido.id.in_(ids)).all()
  } if ids else {}
  return [serializar(t, nombres.get(t.recorrido_id, "Ruta eliminada")) for t in turnos]


def listar_turnos(
    db: Session, user: User, desde: date, hasta: date,
    recorrido_id: Optional[int] = None, repartidor_id: Optional[int] = None,
) -> List[dict]:
  if hasta < desde:
    raise ValueError("La fecha 'hasta' no puede ser anterior a 'desde'")
  if (hasta - desde).days > MAX_DIAS_CONSULTA:
    raise ValueError(f"El rango máximo de consulta es de {MAX_DIAS_CONSULTA} días")

  q = _query_base(db).filter(Turno.tenant_id == user.tenant_id, Turno.fecha >= desde, Turno.fecha <= hasta)
  if recorrido_id:
    q = q.filter(Turno.recorrido_id == recorrido_id)
  # El repartidor solo ve los turnos en los que participa.
  if user.role == UserRole.REPARTIDOR:
    repartidor_id = user.id
  if repartidor_id:
    q = q.filter(Turno.repartidores.any(TurnoRepartidor.user_id == repartidor_id))
  turnos = q.order_by(Turno.fecha, Turno.hora_desde, Turno.id).all()
  return _con_nombre(db, user.tenant_id, turnos)


def obtener_turno(db: Session, tenant_id: int, turno_id: int) -> Turno:
  turno = _query_base(db).filter(Turno.id == turno_id, Turno.tenant_id == tenant_id).first()
  if not turno:
    raise NoEncontrado("Turno no encontrado")
  return turno


def crear_turno(db: Session, tenant_id: int, data: TurnoCreate) -> dict:
  recorrido = _recorrido(db, tenant_id, data.recorrido_id)
  _validar_equipo(db, tenant_id, data.repartidores)

  if db.query(Turno.id).filter(Turno.tenant_id == tenant_id, Turno.recorrido_id == recorrido.id, Turno.fecha == data.fecha).first():
    raise Conflicto("Esa ruta ya tiene un turno programado ese día")
  choque = _conflicto_de_horario(db, tenant_id, data.fecha, data.hora_desde, data.hora_hasta, [e.user_id for e in data.repartidores])
  if choque:
    raise Conflicto(choque)

  turno = Turno(
      tenant_id=tenant_id, recorrido_id=recorrido.id, fecha=data.fecha,
      hora_desde=data.hora_desde, hora_hasta=data.hora_hasta, nota=data.nota,
  )
  _agregar_equipo(turno, data.repartidores)
  db.add(turno)
  db.commit()
  return _con_nombre(db, tenant_id, [obtener_turno(db, tenant_id, turno.id)])[0]


def actualizar_turno(db: Session, tenant_id: int, turno_id: int, data: TurnoUpdate) -> dict:
  turno = obtener_turno(db, tenant_id, turno_id)
  desde = data.hora_desde or turno.hora_desde
  hasta = data.hora_hasta or turno.hora_hasta
  if desde >= hasta:
    raise ValueError("La hora de inicio debe ser anterior a la de fin")
  equipo = data.repartidores
  if equipo is not None:
    _validar_equipo(db, tenant_id, equipo)
  ids = [e.user_id for e in equipo] if equipo is not None else [r.user_id for r in turno.repartidores]
  choque = _conflicto_de_horario(db, tenant_id, turno.fecha, desde, hasta, ids, excluir_turno_id=turno.id)
  if choque:
    raise Conflicto(choque)

  turno.hora_desde, turno.hora_hasta = desde, hasta
  if "nota" in data.model_fields_set:
    turno.nota = data.nota
  if equipo is not None:
    turno.repartidores.clear()
    db.flush()
    _agregar_equipo(turno, equipo)
  db.commit()
  return _con_nombre(db, tenant_id, [obtener_turno(db, tenant_id, turno_id)])[0]


def eliminar_turno(db: Session, tenant_id: int, turno_id: int) -> None:
  db.delete(obtener_turno(db, tenant_id, turno_id))
  db.commit()


def eliminar_turnos_en_rango(db: Session, tenant_id: int, recorrido_id: int, desde: date, hasta: date) -> int:
  """Deshace una programación: borra los turnos de la ruta entre dos fechas (desde hoy en adelante)."""
  _recorrido(db, tenant_id, recorrido_id)
  if hasta < desde:
    raise ValueError("La fecha 'hasta' no puede ser anterior a 'desde'")
  turnos = (
      db.query(Turno)
      .filter(Turno.tenant_id == tenant_id, Turno.recorrido_id == recorrido_id, Turno.fecha >= max(desde, hoy_local()), Turno.fecha <= hasta)
      .all()
  )
  for t in turnos:
    db.delete(t)
  db.commit()
  return len(turnos)


def programar_turnos(db: Session, tenant_id: int, data: ProgramarTurnos) -> dict:
  """Crea turnos para todos los días de la semana elegidos entre dos fechas (próximos meses).

  Lo que ya está ocupado (la ruta ya tiene turno ese día, o un repartidor está en otro
  turno que se superpone) se omite y se informa; el resto se crea.
  """
  recorrido = _recorrido(db, tenant_id, data.recorrido_id)
  _validar_equipo(db, tenant_id, data.repartidores)
  if data.fecha_hasta < data.fecha_desde:
    raise ValueError("La fecha 'hasta' no puede ser anterior a 'desde'")
  if data.fecha_desde < hoy_local():
    raise ValueError("Solo se pueden programar turnos desde hoy en adelante")
  if (data.fecha_hasta - data.fecha_desde).days + 1 > MAX_DIAS_PROGRAMACION:
    raise ValueError(f"Se puede programar hasta {MAX_DIAS_PROGRAMACION} días por vez")

  ocupadas = {
      f for (f,) in db.query(Turno.fecha).filter(
          Turno.tenant_id == tenant_id, Turno.recorrido_id == recorrido.id,
          Turno.fecha >= data.fecha_desde, Turno.fecha <= data.fecha_hasta,
      ).all()
  }
  user_ids = [e.user_id for e in data.repartidores]
  creados, omitidos = 0, []
  dia = data.fecha_desde
  while dia <= data.fecha_hasta:
    if dia.weekday() in data.dias_semana:
      if dia in ocupadas:
        omitidos.append({"fecha": dia, "motivo": "La ruta ya tenía un turno ese día"})
      else:
        choque = _conflicto_de_horario(db, tenant_id, dia, data.hora_desde, data.hora_hasta, user_ids)
        if choque:
          omitidos.append({"fecha": dia, "motivo": choque})
        else:
          turno = Turno(
              tenant_id=tenant_id, recorrido_id=recorrido.id, fecha=dia,
              hora_desde=data.hora_desde, hora_hasta=data.hora_hasta, nota=data.nota,
          )
          _agregar_equipo(turno, data.repartidores)
          db.add(turno)
          db.flush()
          creados += 1
    dia += timedelta(days=1)
  db.commit()
  return {"creados": creados, "omitidos": omitidos}


# ─── Permisos de operación (usado por logistica_service / crud) ───────────────
def repartidor_tiene_turno_hoy(db: Session, tenant_id: int, recorrido_id: int, user_id: int) -> bool:
  return (
      db.query(Turno.id)
      .join(TurnoRepartidor, TurnoRepartidor.turno_id == Turno.id)
      .filter(
          Turno.tenant_id == tenant_id, Turno.recorrido_id == recorrido_id,
          Turno.fecha == hoy_local(), TurnoRepartidor.user_id == user_id,
      )
      .first()
      is not None
  )


def recorridos_con_turno_hoy(db: Session, tenant_id: int, user_id: int) -> List[int]:
  return [
      rid for (rid,) in (
          db.query(Turno.recorrido_id)
          .join(TurnoRepartidor, TurnoRepartidor.turno_id == Turno.id)
          .filter(Turno.tenant_id == tenant_id, Turno.fecha == hoy_local(), TurnoRepartidor.user_id == user_id)
          .all()
      )
  ]
