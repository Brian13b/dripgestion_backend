"""
Idempotencia (reintentos que no duplican) y concurrencia (sin perder actualizaciones).

Idempotencia: el celular reintenta por mala señal o por doble toque. Con el header
`Idempotency-Key` el servidor reconoce la operación y devuelve lo ya registrado.

Concurrencia: dos operaciones simultáneas sobre el mismo cliente no deben pisarse.
En producción lo garantiza `SELECT ... FOR UPDATE` (PostgreSQL); SQLite no tiene bloqueo
de fila, así que ese punto se verifica compilando la consulta para PostgreSQL y con
invariantes contables bajo carga.
"""
import threading
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.main import app
from app.models.cliente import Cliente
from app.models.logistica import Movimiento
from app.services import logistica_service
from app.tests.conftest import ES_POSTGRES, crear_cliente_db, crear_producto

API = "/api/v1/logistica"


def clave():
    return str(uuid.uuid4())


def mov(cliente_id, total=0, cobrado=0, metodo="efectivo", detalles=None):
    return {"cliente_id": cliente_id, "detalles": detalles or {}, "monto_total": total, "monto_cobrado": cobrado, "metodo_pago": metodo}


def post_mov(mundo, body, key=None, headers=None):
    h = dict(headers or mundo.h_admin_a)
    if key:
        h["Idempotency-Key"] = key
    return mundo.client.post(f"{API}/movimientos", json=body, headers=h)


def estado(db, cliente_id):
    db.expire_all()
    c = db.get(Cliente, cliente_id)
    return c.saldo_dinero, dict(c.stock_envases or {})


# ─── Idempotencia: entregas ───────────────────────────────────────────────────
def test_reintento_con_la_misma_clave_no_duplica_la_entrega(db, mundo):
    k = clave()
    det = {str(mundo.agua_a.id): {"entregado": 2, "devuelto": 0}}
    body = mov(mundo.cli_a.id, 7000, 2000, detalles=det)
    r1 = post_mov(mundo, body, k)
    r2 = post_mov(mundo, body, k)
    r3 = post_mov(mundo, body, k)
    assert r1.status_code == r2.status_code == r3.status_code == 200
    assert r1.json()["id"] == r2.json()["id"] == r3.json()["id"]
    assert db.query(Movimiento).count() == 1
    assert estado(db, mundo.cli_a.id) == (5000, {str(mundo.envase_a.id): 2})  # deuda y envases UNA vez


def test_sin_clave_cada_pedido_es_una_operacion_nueva_compatibilidad(db, mundo):
    body = mov(mundo.cli_a.id, 100, 0, "cta_corriente")
    post_mov(mundo, body)
    post_mov(mundo, body)
    assert db.query(Movimiento).count() == 2 and estado(db, mundo.cli_a.id)[0] == 200


def test_claves_distintas_son_operaciones_distintas(db, mundo):
    body = mov(mundo.cli_a.id, 100, 0, "cta_corriente")
    post_mov(mundo, body, clave())
    post_mov(mundo, body, clave())
    assert db.query(Movimiento).count() == 2 and estado(db, mundo.cli_a.id)[0] == 200


def test_la_misma_clave_para_otro_cliente_es_conflicto_409(db, mundo):
    otro = crear_cliente_db(db, mundo.ta.id, "Otro", "2615550444")
    k = clave()
    assert post_mov(mundo, mov(mundo.cli_a.id, 100, 0, "cta_corriente"), k).status_code == 200
    res = post_mov(mundo, mov(otro.id, 100, 0, "cta_corriente"), k)
    assert res.status_code == 409
    assert estado(db, otro.id)[0] == 0


def test_la_clave_es_por_empresa_dos_empresas_pueden_usar_la_misma(db, mundo):
    k = clave()
    assert post_mov(mundo, mov(mundo.cli_a.id, 100, 0, "cta_corriente"), k).status_code == 200
    assert post_mov(mundo, mov(mundo.cli_b.id, 100, 0, "cta_corriente"), k, mundo.h_admin_b).status_code == 200
    assert db.query(Movimiento).count() == 2


def test_una_entrega_rechazada_no_consume_la_clave(db, mundo):
    k = clave()
    malo = mov(mundo.cli_a.id, 100, 0, "cta_corriente", {"99999": {"entregado": 1}})
    assert post_mov(mundo, malo, k).status_code == 400
    assert post_mov(mundo, mov(mundo.cli_a.id, 100, 0, "cta_corriente"), k).status_code == 200
    assert db.query(Movimiento).count() == 1


def test_clave_demasiado_corta_se_rechaza_422(mundo):
    assert post_mov(mundo, mov(mundo.cli_a.id, 1, 0, "cta_corriente"), "abc").status_code == 422


def test_el_movimiento_guarda_la_clave(db, mundo):
    k = clave()
    post_mov(mundo, mov(mundo.cli_a.id, 100, 0, "cta_corriente"), k)
    assert db.query(Movimiento).one().idempotency_key == k


def test_reintento_despues_de_perder_la_respuesta_devuelve_el_mismo_movimiento(db, mundo):
    """Escenario real: el servidor registró la entrega pero el celular no recibió la respuesta."""
    k = clave()
    body = mov(mundo.cli_a.id, 5000, 5000)
    primero = post_mov(mundo, body, k).json()
    # ...el celular no vio la respuesta y vuelve a enviar lo mismo:
    segundo = post_mov(mundo, body, k).json()
    assert primero["id"] == segundo["id"] and db.query(Movimiento).count() == 1


def test_si_otra_peticion_gana_la_carrera_se_devuelve_la_ganadora(db, mundo, monkeypatch):
    """Carrera: dos peticiones pasan el chequeo a la vez; la restricción única en la base decide."""
    k = clave()
    body = mov(mundo.cli_a.id, 300, 0, "cta_corriente")
    ganadora = post_mov(mundo, body, k).json()
    # La 2ª petición "no vio" a la ganadora al chequear (simula la ventana de la carrera):
    monkeypatch.setattr(logistica_service, "_repetido_o_none", lambda *a, **k2: None)
    res = post_mov(mundo, body, k)
    assert res.status_code == 200 and res.json()["id"] == ganadora["id"]
    assert db.query(Movimiento).count() == 1
    assert estado(db, mundo.cli_a.id)[0] == 300  # el saldo de la perdedora se deshizo


def test_peticiones_simultaneas_con_la_misma_clave_registran_una_sola_vez(db, mundo):
    k = clave()
    body = mov(mundo.cli_a.id, 100, 0, "cta_corriente")
    codigos = []

    def enviar():
        c = TestClient(app, raise_server_exceptions=False)
        codigos.append(c.post(f"{API}/movimientos", json=body, headers={**mundo.h_admin_a, "Idempotency-Key": k}).status_code)

    hilos = [threading.Thread(target=enviar) for _ in range(6)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert 200 in codigos
    assert db.query(Movimiento).count() == 1
    assert estado(db, mundo.cli_a.id)[0] == 100


# ─── Idempotencia: pagos manuales ─────────────────────────────────────────────
def test_pago_manual_reintentado_no_se_descuenta_dos_veces(db, mundo):
    cli = crear_cliente_db(db, mundo.ta.id, "Debe", "2615550445", saldo=1000)
    k = clave()
    h = {**mundo.h_admin_a, "Idempotency-Key": k}
    r1 = mundo.client.post(f"{API}/movimientos/pago/{cli.id}", json={"monto": 400, "metodo_pago": "efectivo"}, headers=h)
    r2 = mundo.client.post(f"{API}/movimientos/pago/{cli.id}", json={"monto": 400, "metodo_pago": "efectivo"}, headers=h)
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["nuevo_saldo"] == 600 and r2.json()["nuevo_saldo"] == 600 and r2.json().get("repetido") is True
    assert estado(db, cli.id)[0] == 600
    assert db.query(Movimiento).filter(Movimiento.cliente_id == cli.id).count() == 1


def test_pago_manual_con_la_clave_de_otro_cliente_es_409(db, mundo):
    a = crear_cliente_db(db, mundo.ta.id, "A", "2615550446", saldo=500)
    b = crear_cliente_db(db, mundo.ta.id, "B", "2615550447", saldo=500)
    h = {**mundo.h_admin_a, "Idempotency-Key": clave()}
    assert mundo.client.post(f"{API}/movimientos/pago/{a.id}", json={"monto": 100, "metodo_pago": "efectivo"}, headers=h).status_code == 200
    assert mundo.client.post(f"{API}/movimientos/pago/{b.id}", json={"monto": 100, "metodo_pago": "efectivo"}, headers=h).status_code == 409
    assert estado(db, b.id)[0] == 500


# ─── Concurrencia ─────────────────────────────────────────────────────────────
def test_la_consulta_del_cliente_pide_bloqueo_de_fila_en_postgres(db, mundo):
    sql = str(
        logistica_service._query_cliente_bloqueado(db, mundo.cli_a.id, mundo.ta.id)
        .statement.compile(dialect=postgresql.dialect())
    )
    assert "FOR UPDATE" in sql


def test_entrega_y_pago_manual_usan_la_consulta_bloqueada(db, mundo, monkeypatch):
    llamadas = []
    original = logistica_service._query_cliente_bloqueado

    def espiar(*a, **k):
        llamadas.append(a[1])
        return original(*a, **k)

    monkeypatch.setattr(logistica_service, "_query_cliente_bloqueado", espiar)
    post_mov(mundo, mov(mundo.cli_a.id, 10, 0, "cta_corriente"))
    mundo.client.post(f"{API}/movimientos/pago/{mundo.cli_a.id}", json={"monto": 5, "metodo_pago": "efectivo"}, headers=mundo.h_admin_a)
    assert llamadas == [mundo.cli_a.id, mundo.cli_a.id]


def test_muchas_entregas_seguidas_suman_exacto(db, mundo):
    for _ in range(25):
        post_mov(mundo, mov(mundo.cli_a.id, 0.1, 0, "cta_corriente"))
    assert estado(db, mundo.cli_a.id)[0] == 2.5


@pytest.mark.skipif(
    not ES_POSTGRES,
    reason="SQLite no tiene bloqueo de fila (FOR UPDATE): acá SÍ se pierden actualizaciones en paralelo. "
           "Correr con TEST_DATABASE_URL=postgresql://.../dripgestion_test para verificarlo de verdad.",
)
def test_el_saldo_siempre_coincide_con_los_movimientos_bajo_carga_paralela(db, mundo):
    """Invariante contable: saldo == suma(total - cobrado) de lo REALMENTE registrado.
    Si se perdiera una actualización, el saldo quedaría por debajo de esa suma."""
    cli = crear_cliente_db(db, mundo.ta.id, "Concurrido", "2615550448")
    det = {str(mundo.agua_a.id): {"entregado": 1, "devuelto": 0}}

    def enviar(i):
        c = TestClient(app, raise_server_exceptions=False)
        c.post(f"{API}/movimientos", json=mov(cli.id, 3500, 1000, detalles=det), headers={**mundo.h_admin_a, "Idempotency-Key": clave()})

    hilos = [threading.Thread(target=enviar, args=(i,)) for i in range(10)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]

    db.expire_all()
    movs = db.query(Movimiento).filter(Movimiento.cliente_id == cli.id).all()
    assert len(movs) >= 1
    esperado = round(sum(m.monto_total - m.monto_cobrado for m in movs), 2)
    saldo, stock = estado(db, cli.id)
    assert saldo == esperado
    assert stock.get(str(mundo.envase_a.id), 0) == len(movs)  # un envase por entrega registrada
