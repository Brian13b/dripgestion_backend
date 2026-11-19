"""Calendario operativo: turnos con 1 a 3 repartidores, programación en lote y permisos derivados."""
from datetime import date, timedelta

from app.core.timezone import hoy_local
from app.models.logistica import Movimiento, Turno
from app.models.user import UserRole
from app.tests.conftest import crear_cliente_db, crear_recorrido_db, crear_usuario, login

API = "/api/v1/logistica"


def equipo(*pares):
    return [{"user_id": u.id, "rol": rol} for u, rol in pares]


def cuerpo(ruta, fecha, repartidores, desde="08:00", hasta="12:00", **extra):
    return {"recorrido_id": ruta.id, "fecha": str(fecha), "hora_desde": desde, "hora_hasta": hasta, "repartidores": repartidores, **extra}


def mover(mundo, ruta, fecha=None, reps=None, **kw):
    fecha = fecha or hoy_local()
    reps = reps if reps is not None else equipo((mundo.rep_a, "conductor"))
    return mundo.client.post(f"{API}/turnos", json=cuerpo(ruta, fecha, reps, **kw), headers=mundo.h_admin_a)


def nuevo_repartidor(db, mundo, nombre):
    return crear_usuario(db, mundo.ta.id, nombre, UserRole.REPARTIDOR)


# ─── Alta y validaciones ──────────────────────────────────────────────────────
def test_admin_crea_turno_con_conductor_y_dos_ayudantes(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte")
    a1, a2 = nuevo_repartidor(db, mundo, "ayu1"), nuevo_repartidor(db, mundo, "ayu2")
    res = mover(mundo, ruta, reps=equipo((mundo.rep_a, "conductor"), (a1, "ayudante"), (a2, "ayudante")), nota="Camión 2")
    assert res.status_code == 200, res.text
    t = res.json()
    assert t["recorrido_nombre"] == "Norte" and t["hora_desde"].startswith("08:00") and t["nota"] == "Camión 2"
    assert [r["rol"] for r in t["repartidores"]] == ["conductor", "ayudante", "ayudante"]


def test_un_turno_lleva_de_1_a_3_repartidores_y_un_solo_conductor(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte")
    r = [nuevo_repartidor(db, mundo, f"r{i}") for i in range(3)]
    casos = [
        [],  # ninguno
        equipo((mundo.rep_a, "conductor"), (r[0], "ayudante"), (r[1], "ayudante"), (r[2], "ayudante")),  # 4
        equipo((mundo.rep_a, "ayudante")),  # sin conductor
        equipo((mundo.rep_a, "conductor"), (r[0], "conductor")),  # dos conductores
        equipo((mundo.rep_a, "conductor"), (mundo.rep_a, "ayudante")),  # repetido
    ]
    for reps in casos:
        assert mover(mundo, ruta, reps=reps).status_code == 422
    assert mundo.db.query(Turno).count() == 0


def test_horas_invertidas_o_iguales_se_rechazan(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte")
    assert mover(mundo, ruta, desde="12:00", hasta="08:00").status_code == 422
    assert mover(mundo, ruta, desde="08:00", hasta="08:00").status_code == 422


def test_solo_repartidores_activos_de_la_empresa(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte")
    inactivo = crear_usuario(db, mundo.ta.id, "inactivo", UserRole.REPARTIDOR, activo=False)
    for u in (mundo.rep_b, mundo.admin_a, inactivo):
        assert mover(mundo, ruta, reps=equipo((u, "conductor"))).status_code == 400


def test_ruta_de_otra_empresa_es_404(db, mundo):
    ruta_b = crear_recorrido_db(db, mundo.tb.id, "B")
    assert mover(mundo, ruta_b).status_code == 404


def test_una_ruta_tiene_un_turno_por_dia_409(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte")
    assert mover(mundo, ruta).status_code == 200
    otro = nuevo_repartidor(db, mundo, "otro")
    assert mover(mundo, ruta, reps=equipo((otro, "conductor")), desde="14:00", hasta="18:00").status_code == 409


def test_un_repartidor_no_puede_estar_en_dos_turnos_que_se_superponen(db, mundo):
    r1, r2 = crear_recorrido_db(db, mundo.ta.id, "R1"), crear_recorrido_db(db, mundo.ta.id, "R2")
    assert mover(mundo, r1, desde="08:00", hasta="12:00").status_code == 200
    res = mover(mundo, r2, desde="11:00", hasta="14:00")
    assert res.status_code == 409 and "rep_a" in res.json()["detail"]
    assert mover(mundo, r2, desde="12:00", hasta="14:00").status_code == 200  # justo después: ok


# ─── Consulta ─────────────────────────────────────────────────────────────────
def test_listado_por_rango_ordenado_y_con_tope(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte")
    hoy = hoy_local()
    mover(mundo, ruta, hoy + timedelta(days=2))
    mover(mundo, ruta, hoy)
    res = mundo.client.get(f"{API}/turnos", params={"desde": str(hoy), "hasta": str(hoy + timedelta(days=7))}, headers=mundo.h_admin_a).json()
    assert [t["fecha"] for t in res] == [str(hoy), str(hoy + timedelta(days=2))]
    assert mundo.client.get(f"{API}/turnos", params={"desde": str(hoy), "hasta": str(hoy + timedelta(days=200))}, headers=mundo.h_admin_a).status_code == 400
    assert mundo.client.get(f"{API}/turnos", params={"desde": str(hoy), "hasta": str(hoy - timedelta(days=1))}, headers=mundo.h_admin_a).status_code == 400


def test_el_repartidor_ve_solo_sus_turnos_y_no_los_de_otra_empresa(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte")
    otro = nuevo_repartidor(db, mundo, "otro")
    mover(mundo, ruta, reps=equipo((otro, "conductor")))
    ruta2 = crear_recorrido_db(db, mundo.ta.id, "Sur")
    mover(mundo, ruta2, reps=equipo((mundo.rep_a, "conductor")))
    hoy = str(hoy_local())
    propios = mundo.client.get(f"{API}/turnos", params={"desde": hoy, "hasta": hoy}, headers=mundo.h_rep_a).json()
    assert [t["recorrido_nombre"] for t in propios] == ["Sur"]
    todos_b = mundo.client.get(f"{API}/turnos", params={"desde": hoy, "hasta": hoy}, headers=mundo.h_admin_b).json()
    assert todos_b == []


def test_filtro_por_repartidor_y_ruta(db, mundo):
    r1, r2 = crear_recorrido_db(db, mundo.ta.id, "R1"), crear_recorrido_db(db, mundo.ta.id, "R2")
    otro = nuevo_repartidor(db, mundo, "otro")
    mover(mundo, r1, desde="08:00", hasta="10:00")
    mover(mundo, r2, reps=equipo((otro, "conductor")), desde="08:00", hasta="10:00")
    hoy = str(hoy_local())
    q = {"desde": hoy, "hasta": hoy}
    assert [t["recorrido_nombre"] for t in mundo.client.get(f"{API}/turnos", params={**q, "repartidor_id": otro.id}, headers=mundo.h_admin_a).json()] == ["R2"]
    assert [t["recorrido_nombre"] for t in mundo.client.get(f"{API}/turnos", params={**q, "recorrido_id": r1.id}, headers=mundo.h_admin_a).json()] == ["R1"]


# ─── Edición y baja ───────────────────────────────────────────────────────────
def test_cambiar_horario_y_equipo_de_un_turno(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte")
    tid = mover(mundo, ruta).json()["id"]
    nuevo = nuevo_repartidor(db, mundo, "nuevo")
    res = mundo.client.put(f"{API}/turnos/{tid}", json={"hora_desde": "09:30", "repartidores": equipo((nuevo, "conductor"), (mundo.rep_a, "ayudante"))}, headers=mundo.h_admin_a)
    assert res.status_code == 200, res.text
    t = res.json()
    assert t["hora_desde"].startswith("09:30") and t["hora_hasta"].startswith("12:00")
    assert [(r["nombre"], r["rol"]) for r in t["repartidores"]] == [("nuevo", "conductor"), ("rep_a", "ayudante")]


def test_editar_no_puede_dejar_horas_invertidas_ni_chocar(db, mundo):
    r1, r2 = crear_recorrido_db(db, mundo.ta.id, "R1"), crear_recorrido_db(db, mundo.ta.id, "R2")
    mover(mundo, r1, desde="08:00", hasta="10:00")
    t2 = mover(mundo, r2, desde="10:00", hasta="12:00").json()["id"]
    assert mundo.client.put(f"{API}/turnos/{t2}", json={"hora_desde": "13:00"}, headers=mundo.h_admin_a).status_code == 400
    assert mundo.client.put(f"{API}/turnos/{t2}", json={"hora_desde": "09:00"}, headers=mundo.h_admin_a).status_code == 409


def test_eliminar_turno_y_aislamiento(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte")
    tid = mover(mundo, ruta).json()["id"]
    assert mundo.client.delete(f"{API}/turnos/{tid}", headers=mundo.h_admin_b).status_code == 404
    assert mundo.client.put(f"{API}/turnos/{tid}", json={"nota": "x"}, headers=mundo.h_admin_b).status_code == 404
    assert mundo.client.delete(f"{API}/turnos/{tid}", headers=mundo.h_admin_a).status_code == 200
    assert db.query(Turno).count() == 0


def test_borrar_la_ruta_borra_sus_turnos(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte")
    mover(mundo, ruta)
    assert mundo.client.delete(f"{API}/recorridos/{ruta.id}", headers=mundo.h_admin_a).status_code == 200
    db.expire_all()
    assert db.query(Turno).count() == 0


def test_solo_el_admin_modifica_el_calendario(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte")
    body = cuerpo(ruta, hoy_local(), equipo((mundo.rep_a, "conductor")))
    assert mundo.client.post(f"{API}/turnos", json=body, headers=mundo.h_rep_a).status_code == 403
    assert mundo.client.post(f"{API}/turnos/programar", json={}, headers=mundo.h_rep_a).status_code == 403
    cli = crear_cliente_db(db, mundo.ta.id, "Portal", "2615559999")
    h_cli = login(mundo.client, "2615559999", mundo.ta.id, password="1234")
    hoy = str(hoy_local())
    assert mundo.client.get(f"{API}/turnos", params={"desde": hoy, "hasta": hoy}, headers=h_cli).status_code == 403
    assert cli.id


# ─── Programación en lote (próximos meses) ────────────────────────────────────
def lote(ruta, desde, hasta, dias, reps, **extra):
    return {"recorrido_id": ruta.id, "fecha_desde": str(desde), "fecha_hasta": str(hasta), "dias_semana": dias,
            "hora_desde": "08:00", "hora_hasta": "12:00", "repartidores": reps, **extra}


def test_programar_tres_meses_para_lunes_y_jueves(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte")
    desde = hoy_local()
    hasta = desde + timedelta(days=90)
    res = mundo.client.post(f"{API}/turnos/programar", json=lote(ruta, desde, hasta, [0, 3], equipo((mundo.rep_a, "conductor"))), headers=mundo.h_admin_a)
    assert res.status_code == 200, res.text
    esperados = [desde + timedelta(days=i) for i in range(91) if (desde + timedelta(days=i)).weekday() in (0, 3)]
    assert res.json() == {"creados": len(esperados), "omitidos": []}
    fechas = sorted(t.fecha for t in db.query(Turno).all())
    assert fechas == esperados


def test_programar_omite_lo_ocupado_y_lo_informa(db, mundo):
    ruta, otra = crear_recorrido_db(db, mundo.ta.id, "Norte"), crear_recorrido_db(db, mundo.ta.id, "Sur")
    desde = hoy_local()
    dias = list(range(7))
    mover(mundo, ruta, desde + timedelta(days=1))  # la ruta ya tiene turno mañana
    mover(mundo, otra, desde + timedelta(days=2), desde="09:00", hasta="11:00")  # mismo repartidor, se pisa
    res = mundo.client.post(f"{API}/turnos/programar", json=lote(ruta, desde, desde + timedelta(days=3), dias, equipo((mundo.rep_a, "conductor"))), headers=mundo.h_admin_a).json()
    assert res["creados"] == 2  # hoy y +3
    assert {o["fecha"] for o in res["omitidos"]} == {str(desde + timedelta(days=1)), str(desde + timedelta(days=2))}


def test_programar_validaciones(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte")
    hoy = hoy_local()
    eq = equipo((mundo.rep_a, "conductor"))
    post = lambda body: mundo.client.post(f"{API}/turnos/programar", json=body, headers=mundo.h_admin_a)  # noqa: E731
    assert post(lote(ruta, hoy - timedelta(days=1), hoy, [0], eq)).status_code == 400  # pasado
    assert post(lote(ruta, hoy, hoy + timedelta(days=400), [0], eq)).status_code == 400  # más de 366 días
    assert post(lote(ruta, hoy + timedelta(days=5), hoy, [0], eq)).status_code == 400  # hasta < desde
    assert post(lote(ruta, hoy, hoy + timedelta(days=7), [7], eq)).status_code == 422  # día inválido
    assert post(lote(ruta, hoy, hoy + timedelta(days=7), [], eq)).status_code == 422
    assert post(lote(crear_recorrido_db(db, mundo.tb.id, "B"), hoy, hoy, [0], eq)).status_code == 404


def test_deshacer_una_programacion(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte")
    hoy = hoy_local()
    mundo.client.post(f"{API}/turnos/programar", json=lote(ruta, hoy, hoy + timedelta(days=13), list(range(7)), equipo((mundo.rep_a, "conductor"))), headers=mundo.h_admin_a)
    res = mundo.client.delete(f"{API}/turnos", params={"recorrido_id": ruta.id, "desde": str(hoy), "hasta": str(hoy + timedelta(days=6))}, headers=mundo.h_admin_a)
    assert res.json() == {"eliminados": 7}
    assert db.query(Turno).count() == 7
    assert mundo.client.delete(f"{API}/turnos", params={"recorrido_id": ruta.id, "desde": str(hoy), "hasta": str(hoy)}, headers=mundo.h_admin_b).status_code == 404


# ─── Los turnos habilitan a los repartidores a operar la ruta ese día ─────────
def test_repartidor_con_turno_hoy_ve_la_ruta_y_puede_entregar(db, mundo):
    ayudante = nuevo_repartidor(db, mundo, "ayu")
    h_ayu = login(mundo.client, "ayu", mundo.ta.id)
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte", [mundo.cli_a.id], None)
    # sin turno: no la ve ni opera
    assert mundo.client.get(f"{API}/recorridos", headers=h_ayu).json() == []
    assert mundo.client.get(f"{API}/recorridos/{ruta.id}", headers=h_ayu).status_code == 403
    mover(mundo, ruta, reps=equipo((mundo.rep_a, "conductor"), (ayudante, "ayudante")))
    assert [r["id"] for r in mundo.client.get(f"{API}/recorridos", headers=h_ayu).json()] == [ruta.id]
    assert mundo.client.get(f"{API}/recorridos/{ruta.id}", headers=h_ayu).status_code == 200
    body = {"cliente_id": mundo.cli_a.id, "recorrido_id": ruta.id, "detalles": {}, "monto_total": 0, "monto_cobrado": 0, "metodo_pago": "efectivo"}
    assert mundo.client.post(f"{API}/movimientos", json=body, headers=h_ayu).status_code == 200
    # queda registrado quién la hizo realmente (el ayudante, no el conductor)
    assert db.query(Movimiento).one().repartidor_id == ayudante.id


def test_turno_de_otro_dia_no_habilita(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte", [mundo.cli_a.id], None)
    mover(mundo, ruta, hoy_local() + timedelta(days=1))
    assert mundo.client.get(f"{API}/recorridos", headers=mundo.h_rep_a).json() == []
    body = {"cliente_id": mundo.cli_a.id, "recorrido_id": ruta.id, "detalles": {}, "monto_total": 0, "monto_cobrado": 0, "metodo_pago": "efectivo"}
    assert mundo.client.post(f"{API}/movimientos", json=body, headers=mundo.h_rep_a).status_code == 403


def test_el_turno_tambien_habilita_el_pago_manual_de_los_clientes_de_la_ruta(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Norte", [mundo.cli_a.id], None)
    pago = {"monto": 10, "metodo_pago": "efectivo"}
    assert mundo.client.post(f"{API}/movimientos/pago/{mundo.cli_a.id}", json=pago, headers=mundo.h_rep_a).status_code == 403
    mover(mundo, ruta)
    assert mundo.client.post(f"{API}/movimientos/pago/{mundo.cli_a.id}", json=pago, headers=mundo.h_rep_a).status_code == 200
