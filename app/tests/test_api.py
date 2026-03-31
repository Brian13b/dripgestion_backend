from fastapi.testclient import TestClient
from app.main import app
from app.api import deps
from app.models.user import User, UserRole
from app.models.tenant import Tenant
from app.db.session import SessionLocal

client = TestClient(app)

# 1. Verificar que no hay errores fatales
def test_server_arranca_bien():
    response = client.get("/")

    assert response.status_code != 500 # Error de servidor
    assert response.status_code != 404 # Ruta no encontrada

# 2. Proteccion de rutas
def test_rutas_protegidas_requieren_token():
    payload = {
        "nombre_negocio": "Kiosco Test",
        "direccion": "Calle Falsa 123",
        "telefono": "12345678"
    }

    response = client.post("/api/v1/clientes", json=payload, headers={"X-Tennt-ID": "1"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

# 3. Login con formato correcto
def test_login_rechaza_json_espera_form_data():
    response = client.post(
        "/api/v1/auth/login/access-token",
        json={"username": "admin", "password": "123"},
        headers={"X-Tenant_ID": "1"}
    )

    assert response.status_code == 422

# 4. Aislamiento multi-tenant 
def test_aislamiento_de_empresa_tenant_requerido():
    headers = {"Authorization": "Bearer fake_token"}

    response = client.get("/api/v1/clientes", headers=headers)

    assert response.status_code == 403

def test_flujo_completo_entrega_y_saldo():
    db = SessionLocal()
    try:
        # 1. Configurar Entorno de Prueba Real en BD
        tenant = db.query(Tenant).filter(Tenant.id == 1).first()
        if not tenant:
            tenant = Tenant(id=1, subdominio="test-tenant", nombre="Test Tenant")
            db.add(tenant)
            db.commit()

        user = db.query(User).filter(User.username == "admin_test_integration").first()
        if not user:
            user = User(
                username="admin_test_integration",
                full_name="Admin Test",
                hashed_password="fake_hash",
                role=UserRole.ADMIN,
                tenant_id=1,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # 2. Inyectar el usuario para saltar la autenticación
        def override_get_user():
            return user
            
        app.dependency_overrides[deps.get_current_user] = override_get_user
        app.dependency_overrides[deps.get_current_admin] = override_get_user
        
        # 3. EJECUTAR EL FLUJO
        # A: Crear cliente
        cliente_data = {
            "nombre_negocio": "Kiosco Test Integracion",
            "direccion": "Calle Falsa 123",
            "telefono": "123456789"
        }
        res_cliente = client.post("/api/v1/clientes", json=cliente_data)
        assert res_cliente.status_code == 200, f"Fallo crear cliente: {res_cliente.text}"
        cliente_id = res_cliente.json()["id"]

        # B: Registrar entrega
        movimiento_data = {
            "cliente_id": cliente_id,
            "detalles": {"1": {"entregado": 2, "devuelto": 0}}, 
            "monto_total": 5000,
            "monto_cobrado": 2000,
            "metodo_pago": "efectivo",
            "observacion": "Prueba de integración atómica"
        }
        res_mov = client.post("/api/v1/logistica/movimientos", json=movimiento_data)
        assert res_mov.status_code == 200, f"Fallo registrar entrega: {res_mov.text}"

        # C: Verificar saldo
        res_verify = client.get(f"/api/v1/clientes/{cliente_id}")
        assert res_verify.status_code == 200
        assert res_verify.json()["saldo_dinero"] == 3000

    finally:
        # 4. LIMPIEZA ABSOLUTA (Crucial para que los otros tests no fallen)
        db.close()
        app.dependency_overrides.clear()