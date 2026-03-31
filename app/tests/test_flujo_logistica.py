from fastapi.testclient import TestClient
from app.main import app
from app.api import deps
from app.models.user import User, UserRole

client = TestClient(app)

def override_get_user():
    user = User()
    user.id = 999
    user.tenant_id = 1
    user.role = UserRole.ADMIN
    user.is_active = True
    return user

app.dependency_overrides[deps.get_current_user] = override_get_user
app.dependency_overrides[deps.get_current_admin] = override_get_user

def test_flujo_completo_entrega_y_saldo():
    cliente_data = {
        "nombre_negocio": "Kiosco Test Integracion",
        "direccion": "Calle Falsa 123",
        "telefono": "123456789"
    }
    
    res_cliente = client.post("/api/v1/clientes", json=cliente_data)
    assert res_cliente.status_code == 200, f"Fallo al crear cliente: {res_cliente.text}"
    cliente_id = res_cliente.json()["id"]

    # Registrar una entrega (Compra de $5000, abona $2000 -> Genera deuda de $3000)
    movimiento_data = {
        "cliente_id": cliente_id,
        "detalles": {"1": {"entregado": 2, "devuelto": 0}}, 
        "monto_total": 5000,
        "monto_cobrado": 2000,
        "metodo_pago": "efectivo",
        "observacion": "Prueba de integración atómica"
    }
    
    res_mov = client.post("/api/v1/logistica/movimientos", json=movimiento_data)
    assert res_mov.status_code == 200, f"Fallo al registrar entrega: {res_mov.text}"

    # Verificar que el saldo del cliente se actualizó correctamente a $3000
    res_verify = client.get(f"/api/v1/clientes/{cliente_id}")
    assert res_verify.status_code == 200
    assert res_verify.json()["saldo_dinero"] == 3000

    app.dependency_overrides.clear()