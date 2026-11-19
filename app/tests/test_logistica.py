"""
Logística: recorridos, entregas (movimientos), envases retornables, saldos,
cobros manuales, historial y cierre de caja.
"""
from datetime import date

from app.models.cliente import Cliente
from app.models.logistica import Movimiento
from app.tests.conftest import (bug, detalle_para_total, crear_cliente_db, crear_envase, crear_producto, crear_recorrido_db, login)

API = "/api/v1/logistica"


def mov(cliente_id, total=0, cobrado=0, metodo="efectivo", detalles=None, **extra):
    return {"cliente_id": cliente_id, "detalles": detalles or detalle_para_total(total), "monto_total": total, "monto_cobrado": cobrado, "metodo_pago": metodo, **extra}


def estado(db, cliente_id):
    db.expire_all()
    c = db.query(Cliente).filter(Cliente.id == cliente_id).one()
    return c.saldo_dinero, dict(c.stock_envases or {})


# ─── Recorridos ───────────────────────────────────────────────────────────────
def test_admin_crea_recorrido_con_clientes_ordenados(mundo):
    body = {"nombre": "Ruta Norte", "dia_semana": 1, "clientes_orden": [mundo.cli_a.id]}
    res = mundo.client.post(f"{API}/recorridos", json=body, headers=mundo.h_admin_a)
    assert res.status_code == 200
    assert res.json()["clientes_orden"] == [mundo.cli_a.id] and res.json()["tenant_id"] == mundo.ta.id


def test_recorrido_exige_nombre_y_dia_422(mundo):
    assert mundo.client.post(f"{API}/recorridos", json={"nombre": "x"}, headers=mundo.h_admin_a).status_code == 422


def test_admin_edita_nombre_y_orden(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Vieja", [mundo.cli_a.id])
    res = mundo.client.put(f"{API}/recorridos/{ruta.id}", json={"nombre": "Nueva", "clientes_orden": []}, headers=mundo.h_admin_a)
    assert res.status_code == 200 and res.json()["nombre"] == "Nueva" and res.json()["clientes_orden"] == []


def test_recorrido_inexistente_404(mundo):
    assert mundo.client.get(f"{API}/recorridos/999", headers=mundo.h_admin_a).status_code == 404
    assert mundo.client.put(f"{API}/recorridos/999", json={"nombre": "x"}, headers=mundo.h_admin_a).status_code == 404
    assert mundo.client.delete(f"{API}/recorridos/999", headers=mundo.h_admin_a).status_code == 404


def test_repartidor_solo_ve_sus_recorridos(db, mundo):
    propia = crear_recorrido_db(db, mundo.ta.id, "Mía", [], mundo.rep_a.id)
    crear_recorrido_db(db, mundo.ta.id, "Sin asignar", [])
    res = mundo.client.get(f"{API}/recorridos", headers=mundo.h_rep_a).json()
    assert [r["id"] for r in res] == [propia.id]
    assert len(mundo.client.get(f"{API}/recorridos", headers=mundo.h_admin_a).json()) == 2


def test_repartidor_no_puede_ver_recorrido_ajeno_403(db, mundo):
    ajena = crear_recorrido_db(db, mundo.ta.id, "Ajena", [], None)
    assert mundo.client.get(f"{API}/recorridos/{ajena.id}", headers=mundo.h_rep_a).status_code == 403


def test_asignar_repartidor_valido(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "R", [])
    res = mundo.client.patch(f"{API}/recorridos/{ruta.id}/asignar-repartidor", json={"repartidor_id": mundo.rep_a.id}, headers=mundo.h_admin_a)
    assert res.status_code == 200 and res.json()["repartidor_id"] == mundo.rep_a.id


def test_asignar_a_un_admin_o_inexistente_400(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "R", [])
    for rid in (mundo.admin_a.id, 99999):
        res = mundo.client.patch(f"{API}/recorridos/{ruta.id}/asignar-repartidor", json={"repartidor_id": rid}, headers=mundo.h_admin_a)
        assert res.status_code == 400


def test_asignar_a_repartidor_inactivo_400(db, mundo):
    mundo.rep_a.is_active = False
    db.commit()
    ruta = crear_recorrido_db(db, mundo.ta.id, "R", [])
    res = mundo.client.patch(f"{API}/recorridos/{ruta.id}/asignar-repartidor", json={"repartidor_id": mundo.rep_a.id}, headers=mundo.h_admin_a)
    assert res.status_code == 400


def test_eliminar_recorrido_sin_historial(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "R", [])
    assert mundo.client.delete(f"{API}/recorridos/{ruta.id}", headers=mundo.h_admin_a).status_code == 200


@bug("BUG-16", "eliminar un recorrido que tiene movimientos viola la FK: 500")
def test_eliminar_recorrido_con_movimientos_no_rompe(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "R", [mundo.cli_a.id], mundo.rep_a.id)
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 100, 100, recorrido_id=ruta.id), headers=mundo.h_rep_a)
    assert mundo.client.delete(f"{API}/recorridos/{ruta.id}", headers=mundo.h_admin_a).status_code in (200, 400, 409)


@bug("BUG-16", "no se puede desasignar un repartidor: el schema exige repartidor_id:int aunque el CRUD soporta None")
def test_se_puede_desasignar_repartidor(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "R", [], mundo.rep_a.id)
    res = mundo.client.patch(f"{API}/recorridos/{ruta.id}/asignar-repartidor", json={"repartidor_id": None}, headers=mundo.h_admin_a)
    assert res.status_code == 200


# ─── Entregas: saldo de dinero ────────────────────────────────────────────────
def test_entrega_con_cobro_parcial_genera_deuda(db, mundo):
    res = mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 5000, 2000), headers=mundo.h_admin_a)
    assert res.status_code == 200
    assert estado(db, mundo.cli_a.id)[0] == 3000


def test_entrega_cobrada_completa_no_genera_deuda(db, mundo):
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 5000, 5000), headers=mundo.h_admin_a)
    assert estado(db, mundo.cli_a.id)[0] == 0


def test_entrega_a_cuenta_corriente_suma_toda_la_deuda(db, mundo):
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 4000, 0, "cta_corriente"), headers=mundo.h_admin_a)
    assert estado(db, mundo.cli_a.id)[0] == 4000


def test_cobrar_de_mas_deja_saldo_a_favor(db, mundo):
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 1000, 1500), headers=mundo.h_admin_a)
    assert estado(db, mundo.cli_a.id)[0] == -500


def test_movimiento_registra_repartidor_y_tenant(db, mundo):
    res = mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 100, 100), headers=mundo.h_admin_a).json()
    guardado = db.query(Movimiento).filter(Movimiento.id == res["id"]).one()
    assert guardado.tenant_id == mundo.ta.id and guardado.repartidor_id == mundo.admin_a.id


def test_metodo_de_pago_invalido_422(mundo):
    assert mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 1, 1, "bitcoin"), headers=mundo.h_admin_a).status_code == 422


def test_movimiento_sobre_cliente_inexistente_404(mundo):
    assert mundo.client.post(f"{API}/movimientos", json=mov(99999, 1, 1), headers=mundo.h_admin_a).status_code == 404


def test_movimiento_con_datos_incompletos_422(mundo):
    assert mundo.client.post(f"{API}/movimientos", json={"cliente_id": mundo.cli_a.id}, headers=mundo.h_admin_a).status_code == 422


# ─── Entregas: envases retornables ────────────────────────────────────────────
def test_entrega_de_retornable_suma_envases_al_cliente(db, mundo):
    det = {str(mundo.agua_a.id): {"entregado": 3, "devuelto": 0}}
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 10500, 10500, detalles=det), headers=mundo.h_admin_a)
    assert estado(db, mundo.cli_a.id)[1] == {str(mundo.envase_a.id): 3}


def test_devolucion_en_la_entrega_resta_envases(db, mundo):
    clave = str(mundo.envase_a.id)
    cli = crear_cliente_db(db, mundo.ta.id, "Con stock", "2615550050", stock={clave: 5})
    det = {str(mundo.agua_a.id): {"entregado": 2, "devuelto": 4}}
    mundo.client.post(f"{API}/movimientos", json=mov(cli.id, 7000, 7000, detalles=det), headers=mundo.h_admin_a)
    assert estado(db, cli.id)[1] == {clave: 3}  # 5 + 2 - 4


def test_producto_no_retornable_no_toca_el_saldo_de_envases(db, mundo):
    det = {str(mundo.soda_a.id): {"entregado": 6, "devuelto": 0}}
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 4800, 4800, detalles=det), headers=mundo.h_admin_a)
    assert estado(db, mundo.cli_a.id)[1] == {}


def test_devolucion_directa_de_envases_sin_compra(db, mundo):
    clave = str(mundo.envase_a.id)
    cli = crear_cliente_db(db, mundo.ta.id, "Devuelve", "2615550051", stock={clave: 4})
    body = mov(cli.id, 0, 0, devoluciones_envases={clave: 3})
    assert mundo.client.post(f"{API}/movimientos", json=body, headers=mundo.h_admin_a).status_code == 200
    assert estado(db, cli.id)[1] == {clave: 1}


def test_devolucion_directa_con_envase_invalido_400_y_sin_cambios(db, mundo):
    clave = str(mundo.envase_a.id)
    cli = crear_cliente_db(db, mundo.ta.id, "Devuelve", "2615550052", saldo=100, stock={clave: 4})
    body = mov(cli.id, 500, 0, devoluciones_envases={"99999": 1})
    assert mundo.client.post(f"{API}/movimientos", json=body, headers=mundo.h_admin_a).status_code == 400
    assert estado(db, cli.id) == (100, {clave: 4})  # nada cambió (rollback)


def test_detalle_con_producto_inexistente_400_y_es_atomico(db, mundo):
    """Si el 2º producto falla, no debe quedar aplicado el 1º ni el saldo."""
    det = {str(mundo.agua_a.id): {"entregado": 2}, "99999": {"entregado": 1}}
    res = mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 9999, 0, detalles=det), headers=mundo.h_admin_a)
    assert res.status_code == 400
    assert estado(db, mundo.cli_a.id) == (0.0, {})
    assert db.query(Movimiento).count() == 0


def test_cantidad_no_numerica_422(mundo):
    det = {str(mundo.agua_a.id): {"entregado": "muchos"}}
    assert mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 1, 1, detalles=det), headers=mundo.h_admin_a).status_code == 422


def test_el_saldo_de_envases_no_baja_de_cero_comportamiento_actual(db, mundo):
    """Caracterización: devolver más de lo que debe deja 0 (se pierde el excedente)."""
    clave = str(mundo.envase_a.id)
    cli = crear_cliente_db(db, mundo.ta.id, "Poco", "2615550053", stock={clave: 1})
    body = mov(cli.id, 0, 0, devoluciones_envases={clave: 5})
    mundo.client.post(f"{API}/movimientos", json=body, headers=mundo.h_admin_a)
    assert estado(db, cli.id)[1] == {clave: 0}


# ─── Permisos del repartidor en la entrega ────────────────────────────────────
def test_repartidor_no_asignado_al_cliente_403(db, mundo):
    res = mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 100, 100), headers=mundo.h_rep_a)
    assert res.status_code == 403 and "permiso" in res.json()["detail"].lower()


def test_repartidor_con_cliente_en_su_ruta_puede_entregar(db, mundo):
    crear_recorrido_db(db, mundo.ta.id, "Mía", [mundo.cli_a.id], mundo.rep_a.id)
    assert mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 100, 100), headers=mundo.h_rep_a).status_code == 200


def test_repartidor_no_puede_usar_recorrido_de_otro_403(db, mundo):
    otro = crear_recorrido_db(db, mundo.ta.id, "Ajena", [mundo.cli_a.id], None)
    res = mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 100, 100, recorrido_id=otro.id), headers=mundo.h_rep_a)
    assert res.status_code == 403


def test_recorrido_inexistente_en_movimiento_404(mundo):
    assert mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 1, 1, recorrido_id=999), headers=mundo.h_admin_a).status_code == 404


# ─── BUG-17: visita excepcional (cliente fuera del recorrido, misma empresa) ──
def _ruta_con_cliente_fuera(db, mundo):
    cli_x = crear_cliente_db(db, mundo.ta.id, "Fuera de ruta", "2615550060")
    mia = crear_recorrido_db(db, mundo.ta.id, "Mía", [mundo.cli_a.id], mundo.rep_a.id)
    return cli_x, mia


def test_repartidor_no_puede_entregar_a_cliente_fuera_de_su_ruta_sin_declararlo(db, mundo):
    cli_x, mia = _ruta_con_cliente_fuera(db, mundo)
    res = mundo.client.post(f"{API}/movimientos", json=mov(cli_x.id, 100, 100, recorrido_id=mia.id), headers=mundo.h_rep_a)
    assert res.status_code == 403 and "excepcional" in res.json()["detail"].lower()
    assert db.query(Movimiento).count() == 0 and estado(db, cli_x.id)[0] == 0


def test_visita_excepcional_declarada_se_registra_y_queda_marcada(db, mundo):
    cli_x, mia = _ruta_con_cliente_fuera(db, mundo)
    body = mov(cli_x.id, 800, 300, recorrido_id=mia.id, visita_excepcional=True, observacion="Pidió 1 soda")
    assert mundo.client.post(f"{API}/movimientos", json=body, headers=mundo.h_rep_a).status_code == 200
    guardado = db.query(Movimiento).one()
    assert guardado.visita_excepcional is True and guardado.repartidor_id == mundo.rep_a.id
    assert guardado.observacion.startswith("[Visita excepcional]") and "Pidió 1 soda" in guardado.observacion
    assert estado(db, cli_x.id)[0] == 500  # la deuda y la caja se registran igual


def test_visita_excepcional_es_visible_en_historial_y_en_el_cierre_de_caja(db, mundo):
    cli_x, mia = _ruta_con_cliente_fuera(db, mundo)
    mundo.client.post(f"{API}/movimientos", json=mov(cli_x.id, 800, 800, recorrido_id=mia.id, visita_excepcional=True), headers=mundo.h_rep_a)
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 1600, 1000, recorrido_id=mia.id), headers=mundo.h_rep_a)
    hist = mundo.client.get(f"{API}/historial?recorrido_id={mia.id}", headers=mundo.h_admin_a).json()
    assert {h["cliente"]: h["visita_excepcional"] for h in hist} == {"Fuera de ruta": True, "Kiosco A": False}
    caja = mundo.client.get(f"{API}/historial/mes-actual", headers=mundo.h_admin_a).json()
    assert caja["visitas_excepcionales"] == 1 and caja["cobrado_en_visitas_excepcionales"] == 800
    assert caja["efectivo"] == 1800  # lo cobrado en la excepción suma en la caja general


def test_cliente_de_la_ruta_con_la_marca_no_se_cuenta_como_excepcion(db, mundo):
    _, mia = _ruta_con_cliente_fuera(db, mundo)
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 800, 0, "cta_corriente", recorrido_id=mia.id, visita_excepcional=True), headers=mundo.h_rep_a)
    assert db.query(Movimiento).one().visita_excepcional is False


def test_visita_excepcional_no_cruza_empresas(db, mundo):
    """El cliente de OTRA empresa no existe para este repartidor, aunque declare la excepción."""
    _, mia = _ruta_con_cliente_fuera(db, mundo)
    body = mov(mundo.cli_b.id, 0, 0, recorrido_id=mia.id, visita_excepcional=True)
    res = mundo.client.post(f"{API}/movimientos", json=body, headers=mundo.h_rep_a)
    assert res.status_code == 404 and db.query(Movimiento).count() == 0


def test_recorrido_de_otra_empresa_no_sirve_para_registrar_visitas(db, mundo):
    ruta_b = crear_recorrido_db(db, mundo.tb.id, "Ruta B", [mundo.cli_b.id], mundo.rep_b.id)
    body = mov(mundo.cli_a.id, 0, 0, recorrido_id=ruta_b.id, visita_excepcional=True)
    assert mundo.client.post(f"{API}/movimientos", json=body, headers=mundo.h_rep_a).status_code == 404
    assert mundo.client.post(f"{API}/movimientos", json=body, headers=mundo.h_admin_a).status_code == 404


def test_el_admin_fuera_de_ruta_queda_marcado_aunque_no_lo_declare(db, mundo):
    cli_x, mia = _ruta_con_cliente_fuera(db, mundo)
    assert mundo.client.post(f"{API}/movimientos", json=mov(cli_x.id, 0, 0, recorrido_id=mia.id), headers=mundo.h_admin_a).status_code == 200
    assert db.query(Movimiento).one().visita_excepcional is True


def test_el_pago_manual_del_repartidor_sigue_limitado_a_sus_rutas(db, mundo):
    cli_x, _ = _ruta_con_cliente_fuera(db, mundo)
    res = mundo.client.post(f"{API}/movimientos/pago/{cli_x.id}", json={"monto": 10, "metodo_pago": "efectivo"}, headers=mundo.h_rep_a)
    assert res.status_code == 403


# ─── Validaciones de montos (bugs) ────────────────────────────────────────────
def test_monto_total_negativo_se_rechaza(mundo):
    assert mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, -5000, 0, "cta_corriente"), headers=mundo.h_admin_a).status_code in (400, 422)


def test_monto_cobrado_negativo_se_rechaza(mundo):
    assert mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 100, -100), headers=mundo.h_admin_a).status_code in (400, 422)


def test_cantidades_negativas_de_envases_se_rechazan(mundo):
    det = {str(mundo.agua_a.id): {"entregado": -5, "devuelto": 0}}
    assert mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 1, 1, detalles=det), headers=mundo.h_admin_a).status_code in (400, 422)


def test_el_total_no_puede_superar_el_valor_del_catalogo(db, mundo):
    det = {str(mundo.soda_a.id): {"entregado": 10}}  # 10 x $800 = $8000
    res = mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 99999, 0, "cta_corriente", det), headers=mundo.h_admin_a)
    assert res.status_code == 400 and "catálogo" in res.json()["detail"]
    assert estado(db, mundo.cli_a.id)[0] == 0 and db.query(Movimiento).count() == 0


def test_total_positivo_con_detalle_vacio_se_rechaza(db, mundo):
    """BUG-18: sin items que lo respalden, un monto positivo no puede registrarse."""
    for body in (
        {**mov(mundo.cli_a.id, 5000, 0, "cta_corriente"), "detalles": {}},
        {**mov(mundo.cli_a.id, 5000, 5000), "detalles": {}},
        {**mov(mundo.cli_a.id, 5000, 0, "cta_corriente"), "detalles": {str(mundo.soda_a.id): {"entregado": 0}}},
    ):
        res = mundo.client.post(f"{API}/movimientos", json=body, headers=mundo.h_admin_a)
        assert res.status_code == 400
    assert estado(db, mundo.cli_a.id)[0] == 0 and db.query(Movimiento).count() == 0


def test_detalle_vacio_con_total_cero_es_valido_devolucion_o_visita_sin_venta(db, mundo):
    assert mundo.client.post(f"{API}/movimientos", json={**mov(mundo.cli_a.id, 0, 0), "detalles": {}}, headers=mundo.h_admin_a).status_code == 200


def test_el_total_puede_ser_menor_al_catalogo_por_descuento(db, mundo):
    det = {str(mundo.soda_a.id): {"entregado": 10}}
    res = mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 7500, 7500, detalles=det, observacion="Descuento aplicado: -$500"), headers=mundo.h_admin_a)
    assert res.status_code == 200


def test_el_total_exacto_del_catalogo_es_valido(db, mundo):
    det = {str(mundo.soda_a.id): {"entregado": 10}}
    assert mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 8000, 0, "cta_corriente", det), headers=mundo.h_admin_a).status_code == 200


def test_cantidades_con_decimales_o_texto_se_rechazan_422(mundo):
    for cant in ({"entregado": 1.5}, {"entregado": "dos"}, {"entregado": None}, {"devuelto": True}):
        det = {str(mundo.agua_a.id): cant}
        assert mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 0, 0, detalles=det), headers=mundo.h_admin_a).status_code == 422


def test_pago_manual_con_monto_cero_se_rechaza(mundo):
    res = mundo.client.post(f"{API}/movimientos/pago/{mundo.cli_a.id}", json={"monto": 0, "metodo_pago": "efectivo"}, headers=mundo.h_admin_a)
    assert res.status_code == 422


def test_devolucion_directa_negativa_se_rechaza_422(mundo):
    body = mov(mundo.cli_a.id, 0, 0, devoluciones_envases={str(mundo.envase_a.id): -3})
    assert mundo.client.post(f"{API}/movimientos", json=body, headers=mundo.h_admin_a).status_code == 422


def test_los_saldos_se_redondean_a_centavos_y_no_acumulan_error(db, mundo):
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 0.1, 0, "cta_corriente"), headers=mundo.h_admin_a)
    for _ in range(3):
        mundo.client.post(f"{API}/movimientos/pago/{mundo.cli_a.id}", json={"monto": 0.1, "metodo_pago": "efectivo"}, headers=mundo.h_admin_a)
    assert estado(db, mundo.cli_a.id)[0] == -0.2


def test_el_saldo_vuelve_exactamente_a_cero_con_centavos(db, mundo):
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 0.3, 0, "cta_corriente"), headers=mundo.h_admin_a)
    mundo.client.post(f"{API}/movimientos/pago/{mundo.cli_a.id}", json={"monto": 0.1, "metodo_pago": "efectivo"}, headers=mundo.h_admin_a)
    mundo.client.post(f"{API}/movimientos/pago/{mundo.cli_a.id}", json={"monto": 0.2, "metodo_pago": "efectivo"}, headers=mundo.h_admin_a)
    assert estado(db, mundo.cli_a.id)[0] == 0


# ─── Pago manual de saldo ─────────────────────────────────────────────────────
def test_pago_manual_reduce_el_saldo_y_registra_movimiento(db, mundo):
    cli = crear_cliente_db(db, mundo.ta.id, "Debe", "2615550070", saldo=1000)
    res = mundo.client.post(f"{API}/movimientos/pago/{cli.id}", json={"monto": 400, "metodo_pago": "transferencia", "observacion": "Mercado Pago"}, headers=mundo.h_admin_a)
    assert res.status_code == 200 and res.json()["nuevo_saldo"] == 600
    guardado = db.query(Movimiento).filter(Movimiento.cliente_id == cli.id).one()
    assert guardado.monto_cobrado == 400 and guardado.monto_total == 0 and "Mercado Pago" in guardado.observacion


def test_pago_manual_cliente_inexistente_404(mundo):
    assert mundo.client.post(f"{API}/movimientos/pago/99999", json={"monto": 1, "metodo_pago": "efectivo"}, headers=mundo.h_admin_a).status_code == 404


def test_pago_manual_repartidor_fuera_de_su_ruta_es_rechazado(mundo):
    res = mundo.client.post(f"{API}/movimientos/pago/{mundo.cli_a.id}", json={"monto": 1, "metodo_pago": "efectivo"}, headers=mundo.h_rep_a)
    assert res.status_code == 403


def test_pago_manual_sin_permiso_devuelve_403(mundo):
    res = mundo.client.post(f"{API}/movimientos/pago/{mundo.cli_a.id}", json={"monto": 1, "metodo_pago": "efectivo"}, headers=mundo.h_rep_a)
    assert res.status_code == 403


def test_pago_manual_con_monto_negativo_se_rechaza(db, mundo):
    cli = crear_cliente_db(db, mundo.ta.id, "Debe", "2615550071", saldo=1000)
    res = mundo.client.post(f"{API}/movimientos/pago/{cli.id}", json={"monto": -500, "metodo_pago": "efectivo"}, headers=mundo.h_admin_a)
    assert res.status_code in (400, 422)


def test_pago_manual_con_metodo_invalido_devuelve_422(db, mundo):
    cli = crear_cliente_db(db, mundo.ta.id, "Debe", "2615550072", saldo=1000)
    res = mundo.client.post(f"{API}/movimientos/pago/{cli.id}", json={"monto": 10, "metodo_pago": "bitcoin"}, headers=mundo.h_admin_a)
    assert res.status_code == 422


# ─── Historial y cierre de caja ───────────────────────────────────────────────
def test_historial_del_dia_con_detalle_de_productos_y_devoluciones(mundo):
    clave = str(mundo.envase_a.id)
    det = {str(mundo.agua_a.id): {"entregado": 2, "devuelto": 1}}
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 7000, 7000, detalles=det, devoluciones_envases={clave: 2}), headers=mundo.h_admin_a)
    fila = mundo.client.get(f"{API}/historial", headers=mundo.h_admin_a).json()[0]
    assert fila["cliente"] == "Kiosco A" and fila["monto_total"] == 7000
    assert "2 Agua 20L" in fila["resumen_productos"] and "-2 Bidón 20L" in fila["resumen_productos"]


def test_historial_solo_cobro_dice_solo_cobro(mundo):
    mundo.client.post(f"{API}/movimientos/pago/{mundo.cli_a.id}", json={"monto": 100, "metodo_pago": "efectivo"}, headers=mundo.h_admin_a)
    assert mundo.client.get(f"{API}/historial", headers=mundo.h_admin_a).json()[0]["resumen_productos"] == "Solo cobro / Sin entrega"


def test_historial_de_otro_dia_esta_vacio(mundo):
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 100, 100), headers=mundo.h_admin_a)
    assert mundo.client.get(f"{API}/historial?fecha=2000-01-01", headers=mundo.h_admin_a).json() == []
    assert len(mundo.client.get(f"{API}/historial?fecha={date.today().isoformat()}", headers=mundo.h_admin_a).json()) == 1


def test_historial_fecha_invalida_422(mundo):
    assert mundo.client.get(f"{API}/historial?fecha=ayer", headers=mundo.h_admin_a).status_code == 422


def test_historial_del_repartidor_solo_muestra_lo_suyo_aunque_pida_otro_chofer(db, mundo):
    crear_recorrido_db(db, mundo.ta.id, "Mía", [mundo.cli_a.id], mundo.rep_a.id)
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 100, 100), headers=mundo.h_rep_a)
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 999, 999), headers=mundo.h_admin_a)
    propios = mundo.client.get(f"{API}/historial?chofer_id={mundo.admin_a.id}", headers=mundo.h_rep_a).json()
    assert [m["monto_total"] for m in propios] == [100]


def test_historial_admin_filtra_por_chofer_y_recorrido(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "R", [mundo.cli_a.id], mundo.rep_a.id)
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 100, 100, recorrido_id=ruta.id), headers=mundo.h_rep_a)
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 999, 999), headers=mundo.h_admin_a)
    por_chofer = mundo.client.get(f"{API}/historial?chofer_id={mundo.rep_a.id}", headers=mundo.h_admin_a).json()
    por_ruta = mundo.client.get(f"{API}/historial?recorrido_id={ruta.id}", headers=mundo.h_admin_a).json()
    assert [m["monto_total"] for m in por_chofer] == [100] == [m["monto_total"] for m in por_ruta]


def test_resumen_del_mes_separa_efectivo_transferencia_y_deuda(db, mundo):
    c2 = crear_cliente_db(db, mundo.ta.id, "Debe", "2615550080")
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 1000, 1000, "efectivo"), headers=mundo.h_admin_a)
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 500, 500, "transferencia"), headers=mundo.h_admin_a)
    mundo.client.post(f"{API}/movimientos", json=mov(c2.id, 700, 0, "cta_corriente"), headers=mundo.h_admin_a)
    res = mundo.client.get(f"{API}/historial/mes-actual", headers=mundo.h_admin_a).json()
    assert (res["efectivo"], res["transferencia"], res["fiado"]) == (1000, 500, 700)
    assert res["visitas_excepcionales"] == 0 and res["cobrado_en_visitas_excepcionales"] == 0


def test_entrega_a_cuenta_corriente_no_admite_cobro_en_el_acto_422(db, mundo):
    """BUG-21 corregido: el cobro parcial debe declararse con su método, así la caja suma todo."""
    res = mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 1000, 400, "cta_corriente"), headers=mundo.h_admin_a)
    assert res.status_code == 422
    assert db.query(Movimiento).count() == 0


def test_cobro_parcial_con_metodo_suma_en_el_cierre_de_caja(mundo):
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_a.id, 1000, 400, "efectivo"), headers=mundo.h_admin_a)
    res = mundo.client.get(f"{API}/historial/mes-actual", headers=mundo.h_admin_a).json()
    assert res["efectivo"] + res["transferencia"] == 400
    assert res["fiado"] == 600


def test_pago_manual_no_acepta_cuenta_corriente_como_metodo(mundo):
    res = mundo.client.post(f"{API}/movimientos/pago/{mundo.cli_a.id}", json={"monto": 10, "metodo_pago": "cta_corriente"}, headers=mundo.h_admin_a)
    assert res.status_code == 422


def test_aislamiento_de_resumen_mes(mundo):
    mundo.client.post(f"{API}/movimientos", json=mov(mundo.cli_b.id, 1000, 1000), headers=mundo.h_admin_b)
    res = mundo.client.get(f"{API}/historial/mes-actual", headers=mundo.h_admin_a).json()
    assert (res["efectivo"], res["transferencia"], res["fiado"], res["visitas_excepcionales"]) == (0, 0, 0, 0)
