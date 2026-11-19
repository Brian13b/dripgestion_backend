from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from app import schemas, models
from app.api import deps
from app.core.timezone import hoy_local
from app.db.session import get_db
from app.schemas.logistica import PagoManualCreate, RecorridoAsignarRepartidor
from app.services import logistica_service, turno_service
from app.services.errores import Conflicto, NoEncontrado, PermisoDenegado
from app.crud import crud_logistica

router = APIRouter()

@router.post("/recorridos", response_model=schemas.RecorridoResponse)
def create_recorrido(recorrido_in: schemas.RecorridoCreate, db: Session = Depends(get_db), current_admin: models.user.User = Depends(deps.get_current_admin)):
    return crud_logistica.create_recorrido(db, recorrido_in.model_dump(), current_admin.tenant_id)

@router.get("/recorridos", response_model=List[schemas.RecorridoResponse])
def get_recorridos(db: Session = Depends(get_db), current_user: models.user.User = Depends(deps.get_current_staff)):
    return crud_logistica.get_recorridos_smart(db, current_user)

@router.get("/recorridos/{recorrido_id}", response_model=schemas.RecorridoResponse)
def get_recorrido_by_id(recorrido_id: int, db: Session = Depends(get_db), current_user: models.user.User = Depends(deps.get_current_staff)):
    recorrido = crud_logistica.get_recorrido(db, recorrido_id, current_user.tenant_id)
    if not recorrido:
        raise HTTPException(status_code=404, detail="Recorrido no encontrado")

    if current_user.role == models.user.UserRole.REPARTIDOR:
        if recorrido.repartidor_id != current_user.id and not turno_service.repartidor_tiene_turno_hoy(
            db, current_user.tenant_id, recorrido.id, current_user.id
        ):
            raise HTTPException(status_code=403, detail="No tenés permiso para ver este recorrido")

    return recorrido

@router.put("/recorridos/{recorrido_id}", response_model=schemas.RecorridoResponse)
def update_recorrido(recorrido_id: int, recorrido_in: schemas.RecorridoUpdate, db: Session = Depends(get_db), current_admin: models.user.User = Depends(deps.get_current_admin)):
    recorrido = crud_logistica.get_recorrido(db, recorrido_id, current_admin.tenant_id)
    if not recorrido:
        raise HTTPException(status_code=404, detail="Recorrido no encontrado")

    if recorrido_in.nombre:
        recorrido.nombre = recorrido_in.nombre
    if recorrido_in.clientes_orden is not None:
        recorrido.clientes_orden = recorrido_in.clientes_orden

    db.commit()
    db.refresh(recorrido)
    return recorrido

@router.patch("/recorridos/{recorrido_id}/asignar-repartidor", response_model=schemas.RecorridoResponse)
def asignar_repartidor(recorrido_id: int, body: RecorridoAsignarRepartidor, db: Session = Depends(get_db), current_admin: models.user.User = Depends(deps.get_current_admin)):
    recorrido = crud_logistica.get_recorrido(db, recorrido_id, current_admin.tenant_id)
    if not recorrido:
        raise HTTPException(status_code=404, detail="Recorrido no encontrado")

    try:
        return crud_logistica.update_recorrido_repartidor(
            db, recorrido, body.repartidor_id, current_admin.tenant_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/recorridos/{recorrido_id}")
def delete_recorrido(recorrido_id: int, db: Session = Depends(get_db), current_admin: models.user.User = Depends(deps.get_current_admin)):
    recorrido = crud_logistica.get_recorrido(db, recorrido_id, current_admin.tenant_id)
    if not recorrido:
        raise HTTPException(status_code=404, detail="Recorrido no encontrado")
    crud_logistica.delete_recorrido(db, recorrido)
    return {"message": "Recorrido eliminado exitosamente"}

@router.post("/movimientos")
def registrar_movimiento(mov_in: schemas.MovimientoCreate, db: Session = Depends(get_db), current_user: models.user.User = Depends(deps.get_current_staff), idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key", min_length=8, max_length=64)):
    """Con el header `Idempotency-Key` (UUID) un reintento NO duplica la entrega."""
    try:
        return logistica_service.registrar_entrega(db, mov_in, current_user, current_user.tenant_id, idempotency_key)
    except logistica_service.ClaveIdempotenciaReutilizada as e:
        raise HTTPException(status_code=409, detail=str(e))
    except logistica_service.PermisoDenegado as e:
        raise HTTPException(status_code=403, detail=str(e))
    except logistica_service.NoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/movimientos/pago/{cliente_id}")
def registrar_pago_manual(cliente_id: int, pago_in: PagoManualCreate, db: Session = Depends(get_db), current_user: models.user.User = Depends(deps.get_current_staff), idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key", min_length=8, max_length=64)):
    """Con el header `Idempotency-Key` (UUID) un reintento NO duplica el pago."""
    try:
        return logistica_service.registrar_pago_manual(db, cliente_id, pago_in, current_user, current_user.tenant_id, idempotency_key)
    except logistica_service.ClaveIdempotenciaReutilizada as e:
        raise HTTPException(status_code=409, detail=str(e))
    except logistica_service.PermisoDenegado as e:
        raise HTTPException(status_code=403, detail=str(e))
    except logistica_service.NoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/historial")
def get_historial_por_fecha(fecha: Optional[date] = None, chofer_id: Optional[int] = None, recorrido_id: Optional[int] = None, db: Session = Depends(get_db), current_user: models.user.User = Depends(deps.get_current_staff)):
    if not fecha:
        fecha = hoy_local()

    if current_user.role == models.user.UserRole.REPARTIDOR:
        chofer_id = current_user.id

    return logistica_service.obtener_historial_dia(db, fecha, current_user.tenant_id, chofer_id, recorrido_id)

@router.get("/historial/mes-actual")
def get_resumen_mes_actual(db: Session = Depends(get_db), current_admin: models.user.User = Depends(deps.get_current_admin)):
    try:
        return logistica_service.obtener_resumen_mes(db, current_admin)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))



# ─── Calendario operativo (turnos) ────────────────────────────────────────────
def _http(e: ValueError) -> HTTPException:
    if isinstance(e, NoEncontrado):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, Conflicto):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, PermisoDenegado):
        return HTTPException(status_code=403, detail=str(e))
    return HTTPException(status_code=400, detail=str(e))


@router.get("/turnos", response_model=List[schemas.TurnoResponse])
def listar_turnos(desde: date, hasta: date, recorrido_id: Optional[int] = None, repartidor_id: Optional[int] = None, db: Session = Depends(get_db), current_user: models.user.User = Depends(deps.get_current_staff)):
    """Turnos entre dos fechas (máx. 93 días). El repartidor solo ve los suyos."""
    try:
        return turno_service.listar_turnos(db, current_user, desde, hasta, recorrido_id, repartidor_id)
    except ValueError as e:
        raise _http(e)

@router.post("/turnos", response_model=schemas.TurnoResponse)
def crear_turno(turno_in: schemas.TurnoCreate, db: Session = Depends(get_db), current_admin: models.user.User = Depends(deps.get_current_admin)):
    try:
        return turno_service.crear_turno(db, current_admin.tenant_id, turno_in)
    except ValueError as e:
        raise _http(e)

@router.post("/turnos/programar", response_model=schemas.ProgramarTurnosResponse)
def programar_turnos(data: schemas.ProgramarTurnos, db: Session = Depends(get_db), current_admin: models.user.User = Depends(deps.get_current_admin)):
    """Programa turnos en lote (por ejemplo, los próximos meses). Lo ocupado se omite y se informa."""
    try:
        return turno_service.programar_turnos(db, current_admin.tenant_id, data)
    except ValueError as e:
        raise _http(e)

@router.delete("/turnos")
def eliminar_turnos_en_rango(recorrido_id: int, desde: date, hasta: date, db: Session = Depends(get_db), current_admin: models.user.User = Depends(deps.get_current_admin)):
    """Deshace una programación: borra los turnos futuros de la ruta entre dos fechas."""
    try:
        return {"eliminados": turno_service.eliminar_turnos_en_rango(db, current_admin.tenant_id, recorrido_id, desde, hasta)}
    except ValueError as e:
        raise _http(e)

@router.put("/turnos/{turno_id}", response_model=schemas.TurnoResponse)
def actualizar_turno(turno_id: int, turno_in: schemas.TurnoUpdate, db: Session = Depends(get_db), current_admin: models.user.User = Depends(deps.get_current_admin)):
    try:
        return turno_service.actualizar_turno(db, current_admin.tenant_id, turno_id, turno_in)
    except ValueError as e:
        raise _http(e)

@router.delete("/turnos/{turno_id}")
def eliminar_turno(turno_id: int, db: Session = Depends(get_db), current_admin: models.user.User = Depends(deps.get_current_admin)):
    try:
        turno_service.eliminar_turno(db, current_admin.tenant_id, turno_id)
        return {"message": "Turno eliminado"}
    except ValueError as e:
        raise _http(e)
