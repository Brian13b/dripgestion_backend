from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from app.models import cliente, logistica

def count_clientes_activos(db: Session, tenant_id: int):
    return db.query(cliente.Cliente).filter(cliente.Cliente.tenant_id == tenant_id).count()

def get_all_clientes_for_envases(db: Session, tenant_id: int):
    return db.query(cliente.Cliente).filter(cliente.Cliente.tenant_id == tenant_id).all()

def get_saldos_pendientes_totales(db: Session, tenant_id: int):
    return db.query(func.sum(cliente.Cliente.saldo_dinero)).filter(
        cliente.Cliente.tenant_id == tenant_id,
        cliente.Cliente.saldo_dinero > 0
    ).scalar() or 0

def get_recaudacion_dia(db: Session, fecha: date, tenant_id: int):
    return db.query(func.sum(logistica.Movimiento.monto_cobrado)).join(logistica.Recorrido).filter(
        logistica.Recorrido.tenant_id == tenant_id,
        func.date(logistica.Movimiento.fecha) == fecha
    ).scalar() or 0