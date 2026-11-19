"""Clientes: alta con acceso al portal, edición, baja, paginación y validaciones."""
from app.models.cliente import Cliente
from app.models.user import User
from app.tests.conftest import bug, crear_cliente_db, crear_envase, login

API = "/api/v1"
BASE = {"nombre_negocio": "Almacén Don Juan", "direccion": "San Martín 100", "telefono": "2615551234"}


def test_crear_cliente_crea_usuario_de_portal_con_pin_hasheado(db, mundo):
    res = mundo.client.post(f"{API}/clientes", json={**BASE, "pin_acceso": "4321"}, headers=mundo.h_admin_a)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["saldo_dinero"] == 0 and body["envases_detalle"] == []
    assert body["has_pin"] is True
    assert "pin_acceso" not in body  # el PIN nunca se devuelve
    # El cliente puede entrar al portal con ese PIN
    login(mundo.client, "2615551234", mundo.ta.id, password="4321")
    user = db.query(User).filter(User.username == "2615551234").one()
    assert user.hashed_password != "4321"


def test_crear_cliente_sin_telefono_400(mundo):
    body = {"nombre_negocio": "Sin tel", "direccion": "X 1"}
    assert mundo.client.post(f"{API}/clientes", json=body, headers=mundo.h_admin_a).status_code == 400


def test_crear_cliente_con_telefono_repetido_en_la_empresa_400(mundo):
    body = {**BASE, "telefono": mundo.cli_a.telefono}
    assert mundo.client.post(f"{API}/clientes", json=body, headers=mundo.h_admin_a).status_code == 400


def test_crear_cliente_valida_campos_obligatorios_422(mundo):
    assert mundo.client.post(f"{API}/clientes", json={"telefono": "1"}, headers=mundo.h_admin_a).status_code == 422


def test_crear_cliente_con_condicion_iva_invalida_422(mundo):
    res = mundo.client.post(f"{API}/clientes", json={**BASE, "condicion_iva": "Inventada"}, headers=mundo.h_admin_a)
    assert res.status_code == 422


def test_repartidor_puede_dar_de_alta_clientes_en_la_calle(mundo):
    assert mundo.client.post(f"{API}/clientes", json=BASE, headers=mundo.h_rep_a).status_code == 200


def test_listar_clientes_con_paginacion(db, mundo):
    for i in range(5):
        crear_cliente_db(db, mundo.ta.id, f"Cliente {i}", f"26155600{i}")
    res = mundo.client.get(f"{API}/clientes?skip=0&limit=3", headers=mundo.h_admin_a).json()
    assert res["total"] == 6 and len(res["items"]) == 3
    res2 = mundo.client.get(f"{API}/clientes?skip=3&limit=3", headers=mundo.h_admin_a).json()
    assert len(res2["items"]) == 3
    assert not ({c["id"] for c in res["items"]} & {c["id"] for c in res2["items"]})


def test_ficha_de_cliente_incluye_detalle_de_envases_con_valor(db, mundo):
    cli = crear_cliente_db(db, mundo.ta.id, "Con envases", "2615550099", stock={str(mundo.envase_a.id): 3})
    body = mundo.client.get(f"{API}/clientes/{cli.id}", headers=mundo.h_admin_a).json()
    assert body["envases_detalle"] == [
        {"tipo_envase_id": mundo.envase_a.id, "nombre": "Bidón 20L", "codigo": "BID20", "cantidad": 3,
         "valor_reposicion": 1500.0, "subtotal_reposicion": 4500.0}
    ]


def test_cliente_inexistente_404(mundo):
    assert mundo.client.get(f"{API}/clientes/99999", headers=mundo.h_admin_a).status_code == 404
    assert mundo.client.put(f"{API}/clientes/99999", json={"direccion": "x"}, headers=mundo.h_admin_a).status_code == 404
    assert mundo.client.delete(f"{API}/clientes/99999", headers=mundo.h_admin_a).status_code == 404


def test_editar_cliente_actualiza_datos(mundo):
    res = mundo.client.put(f"{API}/clientes/{mundo.cli_a.id}", json={"direccion": "Nueva 456", "observaciones": "Timbre roto"}, headers=mundo.h_admin_a)
    assert res.status_code == 200
    assert res.json()["direccion"] == "Nueva 456" and res.json()["observaciones"] == "Timbre roto"


def test_cambiar_telefono_cambia_el_usuario_de_portal(mundo):
    res = mundo.client.put(f"{API}/clientes/{mundo.cli_a.id}", json={"telefono": "2615557777"}, headers=mundo.h_admin_a)
    assert res.status_code == 200
    login(mundo.client, "2615557777", mundo.ta.id, password="1234")


def test_cambiar_telefono_a_uno_existente_400(db, mundo):
    crear_cliente_db(db, mundo.ta.id, "Otro", "2615558888")
    res = mundo.client.put(f"{API}/clientes/{mundo.cli_a.id}", json={"telefono": "2615558888"}, headers=mundo.h_admin_a)
    assert res.status_code == 400


def test_cambiar_pin_invalida_sesiones_y_cambia_el_acceso(mundo):
    h_old = login(mundo.client, "2615550001", mundo.ta.id, password="1234")
    assert mundo.client.put(f"{API}/clientes/{mundo.cli_a.id}", json={"pin_acceso": "9999"}, headers=mundo.h_admin_a).status_code == 200
    assert mundo.client.get(f"{API}/auth/me", headers=h_old).status_code == 401
    login(mundo.client, "2615550001", mundo.ta.id, password="9999")


def test_eliminar_cliente_borra_tambien_su_usuario(db, mundo):
    uid = mundo.cli_a.user_id
    assert mundo.client.delete(f"{API}/clientes/{mundo.cli_a.id}", headers=mundo.h_admin_a).status_code == 200
    db.expire_all()
    assert db.query(User).filter(User.id == uid).first() is None


# ─── Bugs ─────────────────────────────────────────────────────────────────────
def test_eliminar_cliente_con_historial_se_rechaza_con_409_y_conserva_todo(db, mundo):
    mov = {"cliente_id": mundo.cli_a.id, "detalles": {}, "monto_total": 100, "monto_cobrado": 0, "metodo_pago": "cta_corriente"}
    assert mundo.client.post(f"{API}/logistica/movimientos", json=mov, headers=mundo.h_admin_a).status_code == 200
    res = mundo.client.delete(f"{API}/clientes/{mundo.cli_a.id}", headers=mundo.h_admin_a)
    assert res.status_code == 409 and "historial" in res.json()["detail"]
    db.expire_all()
    assert db.get(Cliente, mundo.cli_a.id) is not None and db.get(User, mundo.cli_a.user_id) is not None
    assert mundo.client.get("/api/v1/logistica/historial", headers=mundo.h_admin_a).json()[0]["cliente"] == "Kiosco A"


def test_mismo_telefono_puede_ser_cliente_de_dos_empresas(mundo):
    body = {**BASE, "telefono": mundo.cli_a.telefono}  # ya existe en la empresa A
    assert mundo.client.post(f"{API}/clientes", json=body, headers=mundo.h_admin_b).status_code == 200


@bug("BUG-11", "CUIT sin validar: más de 11 caracteres rompe la columna String(11) en Postgres (500)")
def test_cuit_invalido_se_rechaza_con_422(mundo):
    res = mundo.client.post(f"{API}/clientes", json={**BASE, "cuit": "20-33444555-6-EXTRA"}, headers=mundo.h_admin_a)
    assert res.status_code in (400, 422)


@bug("BUG-11", "el CUIT no se valida (largo, dígitos, dígito verificador)")
def test_cuit_con_letras_se_rechaza(mundo):
    res = mundo.client.post(f"{API}/clientes", json={**BASE, "cuit": "abcdefghijk"}, headers=mundo.h_admin_a)
    assert res.status_code in (400, 422)


@bug("BUG-11", "la paginación acepta límites negativos/enormes sin validar")
def test_paginacion_rechaza_limite_negativo(mundo):
    assert mundo.client.get(f"{API}/clientes?limit=-1", headers=mundo.h_admin_a).status_code == 422


@bug("BUG-11", "el PIN por defecto '1234' es débil y se guarda además en texto plano en clientes.pin_acceso")
def test_pin_no_se_guarda_en_texto_plano(db, mundo):
    mundo.client.post(f"{API}/clientes", json={**BASE, "pin_acceso": "4321"}, headers=mundo.h_admin_a)
    cli = db.query(Cliente).filter(Cliente.telefono == "2615551234").one()
    assert cli.pin_acceso != "4321"


@bug("BUG-11", "campos NOT NULL con null explícito (direccion=null) dan 500")
def test_editar_cliente_con_direccion_nula_se_rechaza(mundo):
    res = mundo.client.put(f"{API}/clientes/{mundo.cli_a.id}", json={"direccion": None}, headers=mundo.h_admin_a)
    assert res.status_code in (400, 422)
