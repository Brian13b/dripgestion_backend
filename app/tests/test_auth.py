"""Autenticación, sesiones (token_version) y estados de usuario / empresa."""
from app.models.user import UserRole
from app.tests.conftest import (PASSWORD, bug, crear_tenant, crear_usuario, login)

LOGIN = "/api/v1/auth/login/access-token"


def _login_raw(client, username, password=PASSWORD, tenant_id=None):
    headers = {"X-Tenant-ID": str(tenant_id)} if tenant_id is not None else {}
    return client.post(LOGIN, data={"username": username, "password": password}, headers=headers)


# ─── Login ────────────────────────────────────────────────────────────────────
def test_login_admin_ok_devuelve_token(mundo):
    res = _login_raw(mundo.client, "admin_a", tenant_id=mundo.ta.id)
    assert res.status_code == 200
    assert res.json()["token_type"] == "bearer"
    assert res.json()["access_token"]


def test_login_password_incorrecta_401(mundo):
    assert _login_raw(mundo.client, "admin_a", "mala", mundo.ta.id).status_code == 401


def test_login_usuario_inexistente_401(mundo):
    assert _login_raw(mundo.client, "no_existe", PASSWORD, mundo.ta.id).status_code == 401


def test_login_sin_header_de_empresa_401_para_no_superadmin(mundo):
    assert _login_raw(mundo.client, "admin_a").status_code == 401


def test_login_con_empresa_equivocada_401(mundo):
    assert _login_raw(mundo.client, "admin_a", tenant_id=mundo.tb.id).status_code == 401


def test_login_superadmin_no_necesita_empresa(mundo):
    assert _login_raw(mundo.client, "super").status_code == 200


def test_login_usuario_inactivo_400(db, mundo):
    crear_usuario(db, mundo.ta.id, "inactivo", UserRole.REPARTIDOR, activo=False)
    assert _login_raw(mundo.client, "inactivo", tenant_id=mundo.ta.id).status_code == 400


def test_login_empresa_suspendida_es_rechazado_con_mensaje_claro(db, mundo):
    suspendida = crear_tenant(db, "Susp", "susp", activo=False)
    crear_usuario(db, suspendida.id, "admin_susp")
    res = _login_raw(mundo.client, "admin_susp", tenant_id=suspendida.id)
    assert res.status_code in (400, 401)
    assert "suspendido" in res.json()["detail"]


@bug("BUG-14", "el controller busca 'suspendida' pero el mensaje dice 'suspendido': devuelve 401 en vez de 400")
def test_login_empresa_suspendida_devuelve_400(db, mundo):
    suspendida = crear_tenant(db, "Susp", "susp", activo=False)
    crear_usuario(db, suspendida.id, "admin_susp")
    res = _login_raw(mundo.client, "admin_susp", tenant_id=suspendida.id)
    assert res.status_code == 400


def test_login_rechaza_json_y_exige_form_data_422(mundo):
    res = mundo.client.post(LOGIN, json={"username": "admin_a", "password": PASSWORD})
    assert res.status_code == 422


def test_login_limita_intentos_429(mundo):
    from app.core.limiter import limiter

    limiter.enabled = True
    try:
        limiter.reset()
        codigos = [_login_raw(mundo.client, "admin_a", "mala", mundo.ta.id).status_code for _ in range(7)]
    finally:
        limiter.enabled = False
    assert codigos[:5] == [401] * 5
    assert 429 in codigos[5:]


# ─── Acceso con token ─────────────────────────────────────────────────────────
def test_me_devuelve_el_usuario_logueado(mundo):
    res = mundo.client.get("/api/v1/auth/me", headers=mundo.h_admin_a)
    assert res.status_code == 200
    body = res.json()
    assert body["username"] == "admin_a"
    assert body["role"] == "admin"
    assert body["tenant_id"] == mundo.ta.id
    assert "hashed_password" not in body


def test_ruta_protegida_sin_token_401(mundo):
    assert mundo.client.get("/api/v1/clientes").status_code == 401


@bug("BUG-12", "un token inválido devuelve 403; debería ser 401 para que el front pueda renovar sesión")
def test_token_invalido_devuelve_401(mundo):
    res = mundo.client.get("/api/v1/auth/me", headers={"Authorization": "Bearer basura"})
    assert res.status_code == 401


def test_token_invalido_es_rechazado(mundo):
    res = mundo.client.get("/api/v1/auth/me", headers={"Authorization": "Bearer basura"})
    assert res.status_code in (401, 403)


# ─── Invalidación de sesiones ─────────────────────────────────────────────────
def test_logout_all_invalida_el_token_anterior(mundo):
    assert mundo.client.post("/api/v1/auth/me/logout-all", headers=mundo.h_rep_a).status_code == 200
    assert mundo.client.get("/api/v1/auth/me", headers=mundo.h_rep_a).status_code == 401


def test_cambio_de_password_invalida_tokens_y_permite_login_nuevo(mundo):
    res = mundo.client.put(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "Nueva-Clave-456"},
        headers=mundo.h_admin_a,
    )
    assert res.status_code == 200
    assert mundo.client.get("/api/v1/auth/me", headers=mundo.h_admin_a).status_code == 401
    assert _login_raw(mundo.client, "admin_a", PASSWORD, mundo.ta.id).status_code == 401
    assert _login_raw(mundo.client, "admin_a", "Nueva-Clave-456", mundo.ta.id).status_code == 200


def test_cambio_de_password_con_actual_incorrecta_400(mundo):
    res = mundo.client.put(
        "/api/v1/auth/password",
        json={"current_password": "mala", "new_password": "Nueva-Clave-456"},
        headers=mundo.h_admin_a,
    )
    assert res.status_code == 400


@bug("BUG-13", "no hay política mínima de contraseña: se acepta '1'")
def test_password_nueva_demasiado_corta_se_rechaza(mundo):
    res = mundo.client.put(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "1"},
        headers=mundo.h_admin_a,
    )
    assert res.status_code in (400, 422)


def test_usuario_desactivado_pierde_acceso_aun_con_token_vigente(db, mundo):
    mundo.rep_a.is_active = False
    db.commit()
    assert mundo.client.get("/api/v1/auth/me", headers=mundo.h_rep_a).status_code == 400


def test_empresa_suspendida_corta_el_acceso_con_token_vigente(db, mundo):
    mundo.ta.is_active = False
    db.commit()
    res = mundo.client.get("/api/v1/auth/me", headers=mundo.h_admin_a)
    assert res.status_code == 403
