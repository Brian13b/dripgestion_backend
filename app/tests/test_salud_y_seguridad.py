"""Salud del servicio, CORS y credenciales por defecto."""
from app.core.config import settings
from app.db.init_db import init_superadmin
from app.tests.conftest import bug

LOGIN = "/api/v1/auth/login/access-token"


def test_raiz_y_health_responden_ok(client):
    assert client.get("/").json()["estado"] == "Operativo"
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["database"] == "connected" and res.json()["redis"] == "not_configured"


def test_documentacion_openapi_se_genera_sin_errores(client):
    res = client.get("/openapi.json")
    assert res.status_code == 200 and "/api/v1/clientes" in res.json()["paths"]


def test_cors_permite_el_origen_del_front_local(client):
    res = client.options("/api/v1/clientes", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_no_permite_origenes_desconocidos(client):
    res = client.options("/api/v1/clientes", headers={"Origin": "https://sitio-malicioso.com", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in res.headers


@bug("BUG-24", "el regex de CORS acepta CUALQUIER *.vercel.app con credenciales: cualquiera con una cuenta de Vercel puede llamar a la API desde el navegador de un usuario")
def test_cors_no_acepta_cualquier_subdominio_de_vercel(client):
    res = client.options("/api/v1/clientes", headers={"Origin": "https://sitio-ajeno.vercel.app", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in res.headers


def test_superadmin_inicial_se_crea_una_sola_vez(db, monkeypatch):
    from app.models.user import User

    monkeypatch.setattr(settings, "FIRST_SUPERADMIN_PASSWORD", "Clave-Segura-Test-1")
    init_superadmin(db)
    init_superadmin(db)
    assert db.query(User).filter(User.username == settings.FIRST_SUPERADMIN_USER).count() == 1


def test_superadmin_inicial_puede_iniciar_sesion_con_la_clave_configurada(client, db, monkeypatch):
    monkeypatch.setattr(settings, "FIRST_SUPERADMIN_PASSWORD", "Clave-Segura-Test-1")
    init_superadmin(db)
    res = client.post(LOGIN, data={"username": settings.FIRST_SUPERADMIN_USER, "password": "Clave-Segura-Test-1"})
    assert res.status_code == 200


def test_sin_password_configurada_no_se_crea_superadmin(client, db, monkeypatch):
    """BUG-23 corregido: ya no existe una contraseña por defecto en el código."""
    from app.models.user import User

    monkeypatch.setattr(settings, "FIRST_SUPERADMIN_PASSWORD", None)
    init_superadmin(db)
    assert db.query(User).filter(User.username == settings.FIRST_SUPERADMIN_USER).count() == 0
    res = client.post(LOGIN, data={"username": settings.FIRST_SUPERADMIN_USER, "password": "Superadmin123!"})
    assert res.status_code == 401


def test_password_de_superadmin_demasiado_corta_no_crea_usuario(db, monkeypatch):
    from app.models.user import User

    monkeypatch.setattr(settings, "FIRST_SUPERADMIN_PASSWORD", "corta")
    init_superadmin(db)
    assert db.query(User).filter(User.username == settings.FIRST_SUPERADMIN_USER).count() == 0
