"""Roles y permisos: quién puede llamar a qué endpoint."""
import pytest

from app.models.user import UserRole
from app.tests.conftest import (bug, crear_cliente_db, crear_recorrido_db, login)

API = "/api/v1"


# ─── Endpoints solo para administrador ────────────────────────────────────────
ENDPOINTS_ADMIN = [
    ("get", "/users"),
    ("get", "/dashboard/resumen"),
    ("get", "/logistica/historial/mes-actual"),
    ("post", "/productos"),
    ("post", "/productos/tipos-envase"),
    ("post", "/logistica/recorridos"),
    ("put", "/tenants/config"),
]


@pytest.mark.parametrize("metodo,ruta", ENDPOINTS_ADMIN)
def test_repartidor_no_puede_usar_endpoints_de_admin_403(mundo, metodo, ruta):
    res = getattr(mundo.client, metodo)(API + ruta, headers=mundo.h_rep_a, **({"json": {}} if metodo in ("post", "put") else {}))
    assert res.status_code == 403, f"{metodo.upper()} {ruta} -> {res.status_code}"


@pytest.mark.parametrize("metodo,ruta", ENDPOINTS_ADMIN)
def test_cliente_no_puede_usar_endpoints_de_admin_403(db, mundo, metodo, ruta):
    crear_cliente_db(db, mundo.ta.id, "Portal", "2615559999")
    h = login(mundo.client, "2615559999", mundo.ta.id, password="1234")
    res = getattr(mundo.client, metodo)(API + ruta, headers=h, **({"json": {}} if metodo in ("post", "put") else {}))
    assert res.status_code == 403, f"{metodo.upper()} {ruta} -> {res.status_code}"


# ─── Endpoints de superadmin ──────────────────────────────────────────────────
def test_admin_de_empresa_no_puede_listar_empresas_403(mundo):
    assert mundo.client.get(f"{API}/tenants/", headers=mundo.h_admin_a).status_code == 403


def test_admin_de_empresa_no_puede_crear_empresas_403(mundo):
    body = {"nombre": "X", "subdominio": "x", "admin_username": "u", "admin_password": "p", "admin_full_name": "U"}
    assert mundo.client.post(f"{API}/tenants/onboarding", json=body, headers=mundo.h_admin_a).status_code == 403


def test_admin_de_empresa_no_puede_suspender_empresas_403(mundo):
    res = mundo.client.patch(f"{API}/tenants/{mundo.tb.id}/estado?activo=false", headers=mundo.h_admin_a)
    assert res.status_code == 403


def test_superadmin_lista_todas_las_empresas(mundo):
    res = mundo.client.get(f"{API}/tenants/", headers=mundo.h_super)
    assert res.status_code == 200
    assert {t["subdominio"] for t in res.json()} == {"aguas-a", "soda-b"}


# ─── Lo que sí permiten los roles operativos ──────────────────────────────────
def test_repartidor_puede_ver_catalogo_y_clientes(mundo):
    assert mundo.client.get(f"{API}/productos", headers=mundo.h_rep_a).status_code == 200
    assert mundo.client.get(f"{API}/clientes", headers=mundo.h_rep_a).status_code == 200


def test_cliente_no_puede_registrar_movimientos_ni_pagos_403(db, mundo):
    crear_cliente_db(db, mundo.ta.id, "Portal", "2615559999")
    h = login(mundo.client, "2615559999", mundo.ta.id, password="1234")
    mov = {"cliente_id": mundo.cli_a.id, "detalles": {}, "monto_total": 100, "monto_cobrado": 100, "metodo_pago": "efectivo"}
    assert mundo.client.post(f"{API}/logistica/movimientos", json=mov, headers=h).status_code == 403
    pago = {"monto": 100, "metodo_pago": "efectivo"}
    assert mundo.client.post(f"{API}/logistica/movimientos/pago/{mundo.cli_a.id}", json=pago, headers=h).status_code == 403
    assert mundo.client.get(f"{API}/logistica/historial", headers=h).status_code == 403


# ─── Control de acceso roto (bugs de la auditoría) ────────────────────────────
@pytest.fixture
def h_cliente(db, mundo):
    crear_cliente_db(db, mundo.ta.id, "Portal", "2615559999")
    return login(mundo.client, "2615559999", mundo.ta.id, password="1234")


def test_cliente_no_puede_listar_clientes_de_la_empresa(mundo, h_cliente):
    assert mundo.client.get(f"{API}/clientes", headers=h_cliente).status_code == 403


def test_cliente_no_puede_ver_ficha_de_otro_cliente(mundo, h_cliente):
    assert mundo.client.get(f"{API}/clientes/{mundo.cli_a.id}", headers=h_cliente).status_code == 403


def test_cliente_no_puede_eliminar_clientes(mundo, h_cliente):
    assert mundo.client.delete(f"{API}/clientes/{mundo.cli_a.id}", headers=h_cliente).status_code == 403


def test_cliente_no_puede_modificar_otros_clientes(mundo, h_cliente):
    res = mundo.client.put(f"{API}/clientes/{mundo.cli_a.id}", json={"pin_acceso": "9999"}, headers=h_cliente)
    assert res.status_code == 403


def test_cliente_no_puede_crear_clientes(mundo, h_cliente):
    body = {"nombre_negocio": "Intruso", "direccion": "X 1", "telefono": "2615558888"}
    assert mundo.client.post(f"{API}/clientes", json=body, headers=h_cliente).status_code == 403


def test_cliente_no_puede_leer_recorridos(db, mundo, h_cliente):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Ruta", [mundo.cli_a.id], mundo.rep_a.id)
    assert mundo.client.get(f"{API}/logistica/recorridos/{ruta.id}", headers=h_cliente).status_code == 403


def test_admin_no_puede_promover_usuario_a_superadmin(mundo):
    res = mundo.client.put(
        f"{API}/users/{mundo.rep_a.id}", json={"role": "superadmin"}, headers=mundo.h_admin_a
    )
    assert res.status_code in (400, 403, 422)


def test_promocion_a_superadmin_no_da_acceso_global(db, mundo):
    """BUG-03 corregido: el intento de promoción falla y el usuario sigue siendo repartidor."""
    mundo.client.put(f"{API}/users/{mundo.rep_a.id}", json={"role": "superadmin"}, headers=mundo.h_admin_a)
    db.expire_all()
    assert db.get(type(mundo.rep_a), mundo.rep_a.id).role == UserRole.REPARTIDOR
    # No puede entrar sin empresa (como superadmin) ni ver las empresas
    assert mundo.client.post(
        "/api/v1/auth/login/access-token", data={"username": "rep_a", "password": "Clave-Test-123"}
    ).status_code == 401
    assert mundo.client.get(f"{API}/tenants/", headers=mundo.h_rep_a).status_code == 403


def test_admin_no_puede_convertir_a_un_cliente_del_portal_en_admin(db, mundo):
    """Los usuarios con rol CLIENTE no forman parte del equipo: no se editan por /users."""
    from app.tests.conftest import crear_cliente_db

    cli = crear_cliente_db(db, mundo.ta.id, "Portal", "2615559998")
    res = mundo.client.put(f"{API}/users/{cli.user_id}", json={"role": "admin"}, headers=mundo.h_admin_a)
    assert res.status_code == 400
    assert mundo.client.delete(f"{API}/users/{cli.user_id}", headers=mundo.h_admin_a).status_code == 404


def test_admin_no_puede_crear_usuarios_con_rol_cliente_o_superadmin(mundo):
    for rol in ("superadmin", "cliente"):
        body = {"username": f"x_{rol}", "password": "Clave-1234567", "role": rol}
        assert mundo.client.post(f"{API}/users", json=body, headers=mundo.h_admin_a).status_code == 400
