"""Catálogo: tipos de envase y productos (precios, retornables)."""
from app.tests.conftest import bug, crear_envase, crear_producto

API = "/api/v1/productos"


# ─── Tipos de envase ──────────────────────────────────────────────────────────
def test_crear_tipo_envase_normaliza_codigo(mundo):
    res = mundo.client.post(f"{API}/tipos-envase", json={"nombre": " Cajón 12 ", "codigo": " caj12 ", "valor_reposicion": 2500}, headers=mundo.h_admin_a)
    assert res.status_code == 200
    assert res.json()["codigo"] == "CAJ12" and res.json()["nombre"] == "Cajón 12"
    assert res.json()["tenant_id"] == mundo.ta.id


def test_tipo_envase_con_codigo_repetido_400(mundo):
    res = mundo.client.post(f"{API}/tipos-envase", json={"nombre": "Otro", "codigo": "bid20"}, headers=mundo.h_admin_a)
    assert res.status_code == 400


def test_listar_tipos_envase_solo_activos(db, mundo):
    crear_envase(db, mundo.ta.id, "OLD", "Viejo", activo=False)
    todos = mundo.client.get(f"{API}/tipos-envase", headers=mundo.h_admin_a).json()
    activos = mundo.client.get(f"{API}/tipos-envase?solo_activos=true", headers=mundo.h_admin_a).json()
    assert len(todos) == 2 and [e["codigo"] for e in activos] == ["BID20"]


def test_actualizar_y_alternar_tipo_envase(mundo):
    res = mundo.client.put(f"{API}/tipos-envase/{mundo.envase_a.id}", json={"valor_reposicion": 2000}, headers=mundo.h_admin_a)
    assert res.status_code == 200 and res.json()["valor_reposicion"] == 2000
    off = mundo.client.put(f"{API}/tipos-envase/{mundo.envase_a.id}/toggle", headers=mundo.h_admin_a).json()
    assert off["activo"] is False


def test_tipo_envase_inexistente_404(mundo):
    assert mundo.client.put(f"{API}/tipos-envase/9999", json={"nombre": "x"}, headers=mundo.h_admin_a).status_code == 404
    assert mundo.client.put(f"{API}/tipos-envase/9999/toggle", headers=mundo.h_admin_a).status_code == 404


# ─── Productos ────────────────────────────────────────────────────────────────
def test_listar_productos_incluye_su_envase(mundo):
    productos = {p["codigo"]: p for p in mundo.client.get(API, headers=mundo.h_admin_a).json()}
    assert productos["AGUA20"]["tipo_envase"]["codigo"] == "BID20"
    assert productos["SODA1"]["tipo_envase"] is None


def test_crear_producto_normaliza_codigo_y_aplica_unidad(mundo):
    body = {"nombre": "Hielo 5kg", "codigo": "hielo5", "precio_actual": 1200, "unidad_medida": "kg"}
    res = mundo.client.post(API, json=body, headers=mundo.h_admin_a)
    assert res.status_code == 200
    assert res.json()["codigo"] == "HIELO5" and res.json()["unidad_medida"] == "kg"


def test_crear_producto_con_codigo_repetido_400(mundo):
    body = {"nombre": "Dup", "codigo": "agua20", "precio_actual": 1}
    assert mundo.client.post(API, json=body, headers=mundo.h_admin_a).status_code == 400


def test_producto_retornable_exige_tipo_de_envase_400(mundo):
    body = {"nombre": "Pack", "codigo": "PK", "precio_actual": 100, "es_retornable": True}
    res = mundo.client.post(API, json=body, headers=mundo.h_admin_a)
    assert res.status_code == 400 and "tipo de envase" in res.json()["detail"].lower()


def test_producto_retornable_con_envase_inactivo_400(db, mundo):
    inactivo = crear_envase(db, mundo.ta.id, "INA", "Inactivo", activo=False)
    body = {"nombre": "Pack", "codigo": "PK", "precio_actual": 100, "es_retornable": True, "tipo_envase_id": inactivo.id}
    assert mundo.client.post(API, json=body, headers=mundo.h_admin_a).status_code == 400


def test_producto_no_retornable_ignora_el_envase_enviado(mundo):
    body = {"nombre": "Gaseosa", "codigo": "GAS", "precio_actual": 900, "es_retornable": False, "tipo_envase_id": mundo.envase_a.id}
    res = mundo.client.post(API, json=body, headers=mundo.h_admin_a)
    assert res.status_code == 200 and res.json()["tipo_envase_id"] is None


def test_unidad_de_medida_invalida_422(mundo):
    body = {"nombre": "X", "codigo": "X", "precio_actual": 1, "unidad_medida": "galon"}
    assert mundo.client.post(API, json=body, headers=mundo.h_admin_a).status_code == 422


def test_actualizar_precio(mundo):
    res = mundo.client.put(f"{API}/{mundo.soda_a.id}", json={"precio_actual": 950.5}, headers=mundo.h_admin_a)
    assert res.status_code == 200 and res.json()["precio_actual"] == 950.5


def test_actualizar_codigo_a_uno_existente_400(mundo):
    res = mundo.client.put(f"{API}/{mundo.soda_a.id}", json={"codigo": "agua20"}, headers=mundo.h_admin_a)
    assert res.status_code == 400


def test_actualizar_a_no_retornable_limpia_el_envase(mundo):
    res = mundo.client.put(f"{API}/{mundo.agua_a.id}", json={"es_retornable": False}, headers=mundo.h_admin_a)
    assert res.status_code == 200 and res.json()["tipo_envase_id"] is None


def test_actualizar_a_retornable_sin_envase_400(mundo):
    res = mundo.client.put(f"{API}/{mundo.soda_a.id}", json={"es_retornable": True}, headers=mundo.h_admin_a)
    assert res.status_code == 400


def test_alternar_activo_de_producto(mundo):
    assert mundo.client.put(f"{API}/{mundo.soda_a.id}/toggle", headers=mundo.h_admin_a).json()["activo"] is False


def test_producto_inexistente_404(mundo):
    assert mundo.client.put(f"{API}/9999", json={"nombre": "x"}, headers=mundo.h_admin_a).status_code == 404
    assert mundo.client.put(f"{API}/9999/toggle", headers=mundo.h_admin_a).status_code == 404


def test_campos_obligatorios_422(mundo):
    assert mundo.client.post(API, json={"nombre": "Sin código"}, headers=mundo.h_admin_a).status_code == 422


# ─── Bugs de validación ───────────────────────────────────────────────────────
@bug("BUG-15", "se aceptan precios negativos")
def test_precio_negativo_se_rechaza(mundo):
    body = {"nombre": "Raro", "codigo": "NEG", "precio_actual": -500}
    assert mundo.client.post(API, json=body, headers=mundo.h_admin_a).status_code in (400, 422)


@bug("BUG-15", "se acepta un valor de reposición negativo en los envases")
def test_valor_reposicion_negativo_se_rechaza(mundo):
    body = {"nombre": "Raro", "codigo": "RAR", "valor_reposicion": -10}
    assert mundo.client.post(f"{API}/tipos-envase", json=body, headers=mundo.h_admin_a).status_code in (400, 422)


@bug("BUG-15", "se aceptan nombres y códigos vacíos o solo espacios")
def test_nombre_vacio_se_rechaza(mundo):
    body = {"nombre": "   ", "codigo": "   ", "precio_actual": 10}
    assert mundo.client.post(API, json=body, headers=mundo.h_admin_a).status_code in (400, 422)


@bug("BUG-15", "un producto inactivo puede seguir entregándose (no se valida 'activo' en la entrega)")
def test_no_se_puede_entregar_un_producto_inactivo(db, mundo):
    mundo.client.put(f"{API}/{mundo.soda_a.id}/toggle", headers=mundo.h_admin_a)
    mov = {"cliente_id": mundo.cli_a.id, "detalles": {str(mundo.soda_a.id): {"entregado": 1}}, "monto_total": 800, "monto_cobrado": 800, "metodo_pago": "efectivo"}
    res = mundo.client.post("/api/v1/logistica/movimientos", json=mov, headers=mundo.h_admin_a)
    assert res.status_code == 400
