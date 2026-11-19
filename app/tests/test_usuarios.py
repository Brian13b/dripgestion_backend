"""Gestión de equipo (/users)."""
from app.models.user import User, UserRole
from app.tests.conftest import PASSWORD, bug, crear_usuario, login

API = "/api/v1"
NUEVO = {"username": "chofer_nuevo", "full_name": "Chofer Nuevo", "password": "Clave-Chofer-1", "role": "repartidor", "tenant_id": 1}


def test_listar_equipo_excluye_clientes(db, mundo):
    from app.tests.conftest import crear_cliente_db

    crear_cliente_db(db, mundo.ta.id, "Portal", "2615559999")
    nombres = {u["username"] for u in mundo.client.get(f"{API}/users", headers=mundo.h_admin_a).json()}
    assert "2615559999" not in nombres


def test_obtener_usuario_del_equipo(mundo):
    res = mundo.client.get(f"{API}/users/{mundo.rep_a.id}", headers=mundo.h_admin_a)
    assert res.status_code == 200
    assert res.json()["username"] == "rep_a"


def test_obtener_usuario_inexistente_404(mundo):
    assert mundo.client.get(f"{API}/users/99999", headers=mundo.h_admin_a).status_code == 404


def test_crear_usuario_del_equipo_ok(mundo):
    res = mundo.client.post(f"{API}/users", json={**NUEVO, "tenant_id": mundo.ta.id}, headers=mundo.h_admin_a)
    assert res.status_code == 200, res.text
    assert res.json()["tenant_id"] == mundo.ta.id


def test_usuario_creado_puede_iniciar_sesion(mundo):
    mundo.client.post(f"{API}/users", json={**NUEVO, "tenant_id": mundo.ta.id}, headers=mundo.h_admin_a)
    login(mundo.client, "chofer_nuevo", mundo.ta.id, password="Clave-Chofer-1")


def test_crear_usuario_como_lo_manda_el_front_sin_tenant_id_y_con_la_empresa_del_admin(db, mundo):
    """El front no envía tenant_id: la empresa sale siempre del admin autenticado."""
    body = {"username": "chofer_front", "full_name": "Chofer", "password": "Clave-Chofer-1", "role": "repartidor"}
    res = mundo.client.post(f"{API}/users", json=body, headers=mundo.h_admin_a)
    assert res.status_code == 200, res.text
    assert res.json()["tenant_id"] == mundo.ta.id and res.json()["role"] == "repartidor"
    assert db.query(User).filter(User.username == "chofer_front").one().hashed_password != "Clave-Chofer-1"


def test_el_tenant_id_del_body_se_ignora_y_no_permite_crear_en_otra_empresa(mundo):
    body = {"username": "intruso", "password": "Clave-Chofer-1", "role": "repartidor", "tenant_id": mundo.tb.id}
    res = mundo.client.post(f"{API}/users", json=body, headers=mundo.h_admin_a)
    assert res.status_code == 200 and res.json()["tenant_id"] == mundo.ta.id


def test_crear_usuario_con_username_repetido_en_la_empresa_400(mundo):
    body = {**NUEVO, "username": "rep_a", "tenant_id": mundo.ta.id}
    res = mundo.client.post(f"{API}/users", json=body, headers=mundo.h_admin_a)
    assert res.status_code == 400


def test_crear_usuario_con_datos_incompletos_422(mundo):
    assert mundo.client.post(f"{API}/users", json={"username": "x"}, headers=mundo.h_admin_a).status_code == 422


def test_editar_nombre_de_usuario(mundo):
    res = mundo.client.put(f"{API}/users/{mundo.rep_a.id}", json={"full_name": "Juan Pérez"}, headers=mundo.h_admin_a)
    assert res.status_code == 200
    assert res.json()["full_name"] == "Juan Pérez"


def test_editar_usuario_con_username_ya_usado_400(mundo):
    res = mundo.client.put(f"{API}/users/{mundo.rep_a.id}", json={"username": "admin_a"}, headers=mundo.h_admin_a)
    assert res.status_code == 400


def test_desactivar_usuario_le_quita_el_acceso(db, mundo):
    res = mundo.client.put(f"{API}/users/{mundo.rep_a.id}", json={"is_active": False}, headers=mundo.h_admin_a)
    assert res.status_code == 200
    assert mundo.client.get(f"{API}/auth/me", headers=mundo.h_rep_a).status_code == 400


def test_admin_puede_resetear_password_de_un_repartidor(mundo):
    res = mundo.client.put(f"{API}/users/{mundo.rep_a.id}", json={"password": "Reset-Clave-9"}, headers=mundo.h_admin_a)
    assert res.status_code == 200
    login(mundo.client, "rep_a", mundo.ta.id, password="Reset-Clave-9")


def test_reseteo_de_password_cierra_las_sesiones_abiertas(mundo):
    mundo.client.put(f"{API}/users/{mundo.rep_a.id}", json={"password": "Reset-Clave-9"}, headers=mundo.h_admin_a)
    assert mundo.client.get(f"{API}/auth/me", headers=mundo.h_rep_a).status_code == 401


@bug("BUG-05", "username=null explícito en PUT viola NOT NULL: error 500 en lugar de 422")
def test_editar_usuario_con_username_nulo_se_rechaza(mundo):
    res = mundo.client.put(f"{API}/users/{mundo.rep_a.id}", json={"username": None}, headers=mundo.h_admin_a)
    assert res.status_code in (400, 422)


def test_eliminar_usuario_sin_historial(mundo):
    res = mundo.client.delete(f"{API}/users/{mundo.rep_a.id}", headers=mundo.h_admin_a)
    assert res.status_code == 200
    assert mundo.client.get(f"{API}/users/{mundo.rep_a.id}", headers=mundo.h_admin_a).status_code == 404


def test_eliminar_usuario_inexistente_404(mundo):
    assert mundo.client.delete(f"{API}/users/99999", headers=mundo.h_admin_a).status_code == 404


@bug("BUG-06", "eliminar un repartidor con recorridos/movimientos viola la FK: 500 (sin baja lógica)")
def test_eliminar_repartidor_con_historial_no_rompe(db, mundo):
    from app.tests.conftest import crear_recorrido_db

    crear_recorrido_db(db, mundo.ta.id, "Ruta", [mundo.cli_a.id], mundo.rep_a.id)
    res = mundo.client.delete(f"{API}/users/{mundo.rep_a.id}", headers=mundo.h_admin_a)
    assert res.status_code in (200, 400, 409)


@bug("BUG-06", "un admin puede eliminarse a sí mismo y dejar la empresa sin administrador")
def test_admin_no_puede_eliminarse_a_si_mismo(mundo):
    res = mundo.client.delete(f"{API}/users/{mundo.admin_a.id}", headers=mundo.h_admin_a)
    assert res.status_code in (400, 403)


def test_cerrar_sesiones_de_un_empleado(mundo):
    res = mundo.client.post(f"{API}/users/{mundo.rep_a.id}/logout-all", headers=mundo.h_admin_a)
    assert res.status_code == 200
    assert mundo.client.get(f"{API}/auth/me", headers=mundo.h_rep_a).status_code == 401


def test_no_se_puede_usar_logout_remoto_sobre_uno_mismo_400(mundo):
    res = mundo.client.post(f"{API}/users/{mundo.admin_a.id}/logout-all", headers=mundo.h_admin_a)
    assert res.status_code == 400
