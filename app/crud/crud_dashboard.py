from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from app.models import cliente, logistica, user as user_model
from app.models.logistica import Recorrido

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
    return db.query(func.sum(logistica.Movimiento.monto_cobrado)).filter(
        logistica.Movimiento.tenant_id == tenant_id,
        func.date(logistica.Movimiento.fecha) == fecha
    ).scalar() or 0.0

def get_movimientos_mes(db: Session, tenant_id: int, mes: int, anio: int):
    return db.query(logistica.Movimiento).filter(
        logistica.Movimiento.tenant_id == tenant_id,
        func.extract('month', logistica.Movimiento.fecha) == mes,
        func.extract('year', logistica.Movimiento.fecha) == anio
    ).all()

def get_recaudacion_anual(db: Session, tenant_id: int, anio: int):
    return db.query(
        func.extract('month', logistica.Movimiento.fecha).label('mes'),
        func.sum(logistica.Movimiento.monto_cobrado).label('total_cobrado')
    ).filter(
        logistica.Movimiento.tenant_id == tenant_id,
        func.extract('year', logistica.Movimiento.fecha) == anio
    ).group_by('mes').all()

def get_rendimiento_choferes(db: Session, tenant_id: int, mes: int, anio: int):
    return db.query(
        user_model.User.full_name,
        func.sum(logistica.Movimiento.monto_cobrado).label('recaudado'),
        func.count(logistica.Movimiento.id).label('entregas')
    ).join(logistica.Movimiento, logistica.Movimiento.repartidor_id == user_model.User.id).filter(
        logistica.Movimiento.tenant_id == tenant_id,
        func.extract('month', logistica.Movimiento.fecha) == mes,
        func.extract('year', logistica.Movimiento.fecha) == anio
    ).group_by(user_model.User.full_name).all()

def get_rendimiento_recorridos(db: Session, tenant_id: int, mes: int, anio: int):
    return db.query(
        Recorrido.nombre.label('nombre'),
        func.sum(logistica.Movimiento.monto_cobrado).label('recaudado'),
        func.count(logistica.Movimiento.id).label('entregas')
    ).outerjoin(Recorrido, logistica.Movimiento.recorrido_id == Recorrido.id).filter(
        logistica.Movimiento.tenant_id == tenant_id,
        func.extract('month', logistica.Movimiento.fecha) == mes,
        func.extract('year', logistica.Movimiento.fecha) == anio
    ).group_by(Recorrido.nombre).all()

def get_recaudacion_diaria_mes(db: Session, tenant_id: int, mes: int, anio: int):
    return db.query(
        func.extract('day', logistica.Movimiento.fecha).label('dia'),
        func.sum(logistica.Movimiento.monto_cobrado).label('total')
    ).filter(
        logistica.Movimiento.tenant_id == tenant_id,
        func.extract('month', logistica.Movimiento.fecha) == mes,
        func.extract('year', logistica.Movimiento.fecha) == anio
    ).group_by('dia').all()