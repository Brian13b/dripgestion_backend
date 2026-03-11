from sqlalchemy.orm import Session
from app.crud import crud_portal

def obtener_datos_mi_cuenta(db: Session, user_id: int, tenant_id: int):
    cliente = crud_portal.get_cliente_por_usuario(db, user_id)
    if not cliente:
        raise ValueError("Perfil de cliente no encontrado")

    total_envases = sum(cliente.stock_envases.values()) if isinstance(cliente.stock_envases, dict) else 0

    movimientos_db = crud_portal.get_ultimos_movimientos_cliente(db, cliente.id)
    productos = crud_portal.get_productos_tenant(db, tenant_id)
    mapa_productos = {str(p.id): p.nombre for p in productos}

    ultimos_movimientos = []
    for mov in movimientos_db:
        detalles_texto = []
        if mov.detalles:
            for prod_id, cant in mov.detalles.items():
                entregados = cant.get("entregado", 0)
                if entregados > 0:
                    nombre_prod = mapa_productos.get(str(prod_id), "Producto")
                    detalles_texto.append(f"{entregados} {nombre_prod}")
        
        texto_productos = " + ".join(detalles_texto) if detalles_texto else "Solo cobro"
        fecha_str = mov.fecha.strftime("%d/%m/%Y")
        monto_mostrar = mov.monto_total if mov.metodo_pago == 'cta_corriente' else mov.monto_cobrado

        ultimos_movimientos.append({
            "fecha": fecha_str,
            "resumen_productos": texto_productos,
            "monto": monto_mostrar,
            "tipo": "Fiado" if mov.metodo_pago == 'cta_corriente' else mov.metodo_pago
        })

    return {
        "nombre_negocio": cliente.nombre_negocio,
        "direccion": cliente.direccion,
        "saldo_dinero": cliente.saldo_dinero,
        "total_envases": total_envases,
        "detalle_envases": cliente.stock_envases,
        "ultimos_movimientos": ultimos_movimientos
    }