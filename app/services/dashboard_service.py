from sqlalchemy.orm import Session
from datetime import date
from app.crud import crud_dashboard

def obtener_metricas_dashboard(db: Session, tenant_id: int):
    hoy = date.today()
    
    total_clientes = crud_dashboard.count_clientes_activos(db, tenant_id)
    todos_los_clientes = crud_dashboard.get_all_clientes_for_envases(db, tenant_id)
    
    total_envases = sum(sum(c.stock_envases.values()) for c in todos_los_clientes if isinstance(c.stock_envases, dict))
    saldos_pendientes = crud_dashboard.get_saldos_pendientes_totales(db, tenant_id)
    recaudacion_hoy = crud_dashboard.get_recaudacion_dia(db, hoy, tenant_id)

    return {
        "clientes_activos": total_clientes,
        "total_envases": total_envases,
        "saldos_pendientes": saldos_pendientes,
        "recaudacion_hoy": recaudacion_hoy
    }