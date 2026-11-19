from collections import defaultdict
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.timezone import a_local, rango_anio, rango_dia, rango_mes
from app.models import cliente, logistica, user as user_model
from app.models.logistica import Recorrido

# Todos los cortes por día / mes / año usan la zona horaria del negocio y rangos
# [inicio, fin) en UTC. Las agrupaciones por mes y por día se hacen en Python
# porque convertir de zona horaria en SQL no es portable (PostgreSQL vs SQLite).


def count_clientes_activos(db: Session, tenant_id: int):
    return db.query(cliente.Cliente).filter(cliente.Cliente.tenant_id == tenant_id).count()

def get_all_clientes_for_envases(db: Session, tenant_id: int):
    return db.query(cliente.Cliente).filter(cliente.Cliente.tenant_id == tenant_id).all()

def get_saldos_pendientes_totales(db: Session, tenant_id: int):
    return db.query(func.sum(cliente.Cliente.saldo_dinero)).filter(
        cliente.Cliente.tenant_id == tenant_id,
        cliente.Cliente.saldo_dinero > 0
    ).scalar() or 0.0

def get_recaudacion_dia(db: Session, fecha: date, tenant_id: int):
    inicio, fin = rango_dia(fecha)
    return db.query(func.sum(logistica.Movimiento.monto_cobrado)).filter(
        logistica.Movimiento.tenant_id == tenant_id,
        logistica.Movimiento.fecha >= inicio,
        logistica.Movimiento.fecha < fin,
    ).scalar() or 0.0

def get_movimientos_mes(db: Session, tenant_id: int, mes: int, anio: int):
    inicio, fin = rango_mes(anio, mes)
    return db.query(logistica.Movimiento).filter(
        logistica.Movimiento.tenant_id == tenant_id,
        logistica.Movimiento.fecha >= inicio,
        logistica.Movimiento.fecha < fin,
    ).all()

def get_recaudacion_anual(db: Session, tenant_id: int, anio: int):
    """[(mes, total_cobrado)] con el mes en hora local del negocio."""
    inicio, fin = rango_anio(anio)
    filas = db.query(logistica.Movimiento.fecha, logistica.Movimiento.monto_cobrado).filter(
        logistica.Movimiento.tenant_id == tenant_id,
        logistica.Movimiento.fecha >= inicio,
        logistica.Movimiento.fecha < fin,
    ).all()
    por_mes = defaultdict(float)
    for fecha, cobrado in filas:
        por_mes[a_local(fecha).month] += cobrado or 0.0
    return sorted(por_mes.items())

def get_rendimiento_choferes(db: Session, tenant_id: int, mes: int, anio: int):
    inicio, fin = rango_mes(anio, mes)
    return db.query(
        user_model.User.full_name,
        func.sum(logistica.Movimiento.monto_cobrado).label('recaudado'),
        func.count(logistica.Movimiento.id).label('entregas')
    ).join(logistica.Movimiento, logistica.Movimiento.repartidor_id == user_model.User.id).filter(
        logistica.Movimiento.tenant_id == tenant_id,
        logistica.Movimiento.fecha >= inicio,
        logistica.Movimiento.fecha < fin,
    ).group_by(user_model.User.full_name).all()

def get_rendimiento_recorridos(db: Session, tenant_id: int, mes: int, anio: int):
    inicio, fin = rango_mes(anio, mes)
    return db.query(
        Recorrido.nombre.label('nombre'),
        func.sum(logistica.Movimiento.monto_cobrado).label('recaudado'),
        func.count(logistica.Movimiento.id).label('entregas')
    ).outerjoin(Recorrido, logistica.Movimiento.recorrido_id == Recorrido.id).filter(
        logistica.Movimiento.tenant_id == tenant_id,
        logistica.Movimiento.fecha >= inicio,
        logistica.Movimiento.fecha < fin,
    ).group_by(Recorrido.nombre).all()

def get_recaudacion_diaria_mes(db: Session, tenant_id: int, mes: int, anio: int):
    """[(dia_del_mes, total_cobrado)] con el día en hora local del negocio."""
    inicio, fin = rango_mes(anio, mes)
    filas = db.query(logistica.Movimiento.fecha, logistica.Movimiento.monto_cobrado).filter(
        logistica.Movimiento.tenant_id == tenant_id,
        logistica.Movimiento.fecha >= inicio,
        logistica.Movimiento.fecha < fin,
    ).all()
    por_dia = defaultdict(float)
    for fecha, cobrado in filas:
        por_dia[a_local(fecha).day] += cobrado or 0.0
    return sorted(por_dia.items())
