"""Aislamiento multi-tenant: una empresa nunca ve ni toca datos de otra."""
from app.models.user import UserRole
from app.tests.conftest import (bug, crear_cliente_db, crear_producto, crear_recorrido_db, crear_usuario)

API = "/api/v1"


# ─── Clientes ─────────────────────────────────────────────────────────────────
def test_lista_de_clientes_solo_incluye_la_propia_empresa(mundo):
    res = mundo.client.get(f"{API}/clientes", headers=mundo.h_admin_a)
    assert res.status_code == 200
    ids = [c["id"] for c in res.json()["items"]]
    assert ids == [mundo.cli_a.id]
    assert res.json()["total"] == 1


def test_no_se_puede_ver_cliente_de_otra_empresa_404(mundo):
    assert mundo.client.get(f"{API}/clientes/{mundo.cli_b.id}", headers=mundo.h_admin_a).status_code == 404


def test_no_se_puede_editar_cliente_de_otra_empresa_404(mundo):
    res = mundo.client.put(f"{API}/clientes/{mundo.cli_b.id}", json={"direccion": "Hackeada"}, headers=mundo.h_admin_a)
    assert res.status_code == 404


def test_no_se_puede_borrar_cliente_de_otra_empresa_404(mundo, db):
    assert mundo.client.delete(f"{API}/clientes/{mundo.cli_b.id}", headers=mundo.h_admin_a).status_code == 404
    db.expire_all()
    assert mundo.client.get(f"{API}/clientes/{mundo.cli_b.id}", headers=mundo.h_admin_b).status_code == 200


# ─── Catálogo ─────────────────────────────────────────────────────────────────
def test_catalogo_y_envases_solo_de_la_propia_empresa(mundo):
    productos = mundo.client.get(f"{API}/productos", headers=mundo.h_admin_a).json()
    assert {p["codigo"] for p in productos} == {"AGUA20", "SODA1"}
    envases = mundo.client.get(f"{API}/productos/tipos-envase", headers=mundo.h_admin_a).json()
    assert {e["codigo"] for e in envases} == {"BID20"}


def test_no_se_puede_editar_ni_alternar_producto_de_otra_empresa_404(mundo):
    assert mundo.client.put(f"{API}/productos/{mundo.soda_b.id}", json={"precio_actual": 1}, headers=mundo.h_admin_a).status_code == 404
    assert mundo.client.put(f"{API}/productos/{mundo.soda_b.id}/toggle", headers=mundo.h_admin_a).status_code == 404


def test_no_se_puede_editar_envase_de_otra_empresa_404(mundo):
    assert mundo.client.put(f"{API}/productos/tipos-envase/{mundo.envase_b.id}", json={"nombre": "X"}, headers=mundo.h_admin_a).status_code == 404
    assert mundo.client.put(f"{API}/productos/tipos-envase/{mundo.envase_b.id}/toggle", headers=mundo.h_admin_a).status_code == 404


def test_producto_retornable_no_acepta_envase_de_otra_empresa_400(mundo):
    body = {"nombre": "Pack", "codigo": "PK1", "precio_actual": 100, "es_retornable": True, "tipo_envase_id": mundo.envase_b.id}
    assert mundo.client.post(f"{API}/productos", json=body, headers=mundo.h_admin_a).status_code == 400


def test_mismo_codigo_de_producto_se_permite_en_otra_empresa(mundo, db):
    # AGUA20 ya existe en A; en B debe poder crearse sin conflicto.
    body = {"nombre": "Agua B", "codigo": "AGUA20", "precio_actual": 100}
    assert mundo.client.post(f"{API}/productos", json=body, headers=mundo.h_admin_b).status_code == 200


# ─── Logística ────────────────────────────────────────────────────────────────
def test_recorridos_son_privados_por_empresa(db, mundo):
    ruta_b = crear_recorrido_db(db, mundo.tb.id, "Ruta B", [mundo.cli_b.id])
    assert mundo.client.get(f"{API}/logistica/recorridos", headers=mundo.h_admin_a).json() == []
    assert mundo.client.get(f"{API}/logistica/recorridos/{ruta_b.id}", headers=mundo.h_admin_a).status_code == 404
    assert mundo.client.put(f"{API}/logistica/recorridos/{ruta_b.id}", json={"nombre": "X"}, headers=mundo.h_admin_a).status_code == 404
    assert mundo.client.delete(f"{API}/logistica/recorridos/{ruta_b.id}", headers=mundo.h_admin_a).status_code == 404


def test_no_se_puede_asignar_repartidor_de_otra_empresa_400(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Ruta A")
    res = mundo.client.patch(
        f"{API}/logistica/recorridos/{ruta.id}/asignar-repartidor",
        json={"repartidor_id": mundo.rep_b.id},
        headers=mundo.h_admin_a,
    )
    assert res.status_code == 400


def test_movimiento_sobre_cliente_de_otra_empresa_404(mundo):
    mov = {"cliente_id": mundo.cli_b.id, "detalles": {}, "monto_total": 0, "monto_cobrado": 0, "metodo_pago": "efectivo"}
    res = mundo.client.post(f"{API}/logistica/movimientos", json=mov, headers=mundo.h_admin_a)
    assert res.status_code == 404
    assert "no encontrado" in res.json()["detail"].lower()


def test_movimiento_con_producto_de_otra_empresa_400(mundo):
    mov = {
        "cliente_id": mundo.cli_a.id,
        "detalles": {str(mundo.soda_b.id): {"entregado": 1, "devuelto": 0}},
        "monto_total": 100,
        "monto_cobrado": 0,
        "metodo_pago": "efectivo",
    }
    assert mundo.client.post(f"{API}/logistica/movimientos", json=mov, headers=mundo.h_admin_a).status_code == 400


def test_pago_manual_sobre_cliente_de_otra_empresa_404(mundo):
    res = mundo.client.post(
        f"{API}/logistica/movimientos/pago/{mundo.cli_b.id}", json={"monto": 10, "metodo_pago": "efectivo"}, headers=mundo.h_admin_a
    )
    assert res.status_code == 404


def test_historial_solo_muestra_movimientos_propios(mundo):
    for h, cli, prod in ((mundo.h_admin_a, mundo.cli_a, mundo.soda_a), (mundo.h_admin_b, mundo.cli_b, mundo.soda_b)):
        mov = {"cliente_id": cli.id, "detalles": {str(prod.id): {"entregado": 1}}, "monto_total": 100, "monto_cobrado": 100, "metodo_pago": "efectivo"}
        assert mundo.client.post(f"{API}/logistica/movimientos", json=mov, headers=h).status_code == 200
    res = mundo.client.get(f"{API}/logistica/historial", headers=mundo.h_admin_a).json()
    assert [m["cliente"] for m in res] == ["Kiosco A"]


# ─── Usuarios ─────────────────────────────────────────────────────────────────
def test_equipo_solo_lista_usuarios_de_la_propia_empresa(mundo):
    res = mundo.client.get(f"{API}/users", headers=mundo.h_admin_a)
    assert res.status_code == 200
    assert {u["username"] for u in res.json()} == {"admin_a", "rep_a"}  # sin clientes ni otra empresa


def test_no_se_puede_ver_editar_borrar_ni_desloguear_usuario_de_otra_empresa(mundo):
    uid = mundo.rep_b.id
    assert mundo.client.get(f"{API}/users/{uid}", headers=mundo.h_admin_a).status_code == 404
    assert mundo.client.put(f"{API}/users/{uid}", json={"full_name": "X"}, headers=mundo.h_admin_a).status_code == 400
    assert mundo.client.delete(f"{API}/users/{uid}", headers=mundo.h_admin_a).status_code == 404
    assert mundo.client.post(f"{API}/users/{uid}/logout-all", headers=mundo.h_admin_a).status_code == 404


# ─── Dashboard y portal ───────────────────────────────────────────────────────
def test_dashboard_cuenta_solo_la_propia_empresa(db, mundo):
    crear_cliente_db(db, mundo.tb.id, "Otro B", "2615550077", saldo=999)
    res = mundo.client.get(f"{API}/dashboard/resumen", headers=mundo.h_admin_a)
    assert res.status_code == 200
    kpis = res.json()["kpis"]
    assert kpis["clientes_activos"] == 1
    assert kpis["deuda_en_calle"] == 0


def test_portal_muestra_solo_los_datos_del_propio_cliente(db, mundo):
    from app.tests.conftest import login

    cli2 = crear_cliente_db(db, mundo.ta.id, "Kiosco A2", "2615550003", saldo=50)
    h = login(mundo.client, "2615550003", mundo.ta.id, password="1234")
    res = mundo.client.get(f"{API}/portal/mi-cuenta", headers=h)
    assert res.status_code == 200
    assert res.json()["nombre_negocio"] == "Kiosco A2"
    assert res.json()["saldo_dinero"] == 50


def test_info_publica_de_empresa_inactiva_404(db, mundo):
    mundo.tb.is_active = False
    db.commit()
    assert mundo.client.get(f"{API}/tenants/info/soda-b").status_code == 404
    assert mundo.client.get(f"{API}/tenants/info/aguas-a").status_code == 200


# ─── Referencias cruzadas (bugs) ──────────────────────────────────────────────
@bug("BUG-08", "crear recorrido acepta un repartidor de OTRA empresa (referencia cruzada)")
def test_crear_recorrido_no_acepta_repartidor_de_otra_empresa(mundo):
    body = {"nombre": "Ruta", "dia_semana": 1, "repartidor_id": mundo.rep_b.id, "clientes_orden": []}
    res = mundo.client.post(f"{API}/logistica/recorridos", json=body, headers=mundo.h_admin_a)
    assert res.status_code in (400, 404, 422)


@bug("BUG-08", "crear/editar recorrido acepta IDs de clientes de OTRA empresa")
def test_recorrido_no_acepta_clientes_de_otra_empresa(mundo):
    body = {"nombre": "Ruta", "dia_semana": 1, "clientes_orden": [mundo.cli_b.id]}
    res = mundo.client.post(f"{API}/logistica/recorridos", json=body, headers=mundo.h_admin_a)
    assert res.status_code in (400, 404, 422)


@bug("BUG-09", "el admin puede cambiar su subdominio a uno ya usado: IntegrityError -> 500 (y sin validar formato)")
def test_admin_no_puede_pisar_subdominio_de_otra_empresa(mundo):
    res = mundo.client.put(f"{API}/tenants/config", json={"subdominio": "soda-b"}, headers=mundo.h_admin_a)
    assert res.status_code == 400
