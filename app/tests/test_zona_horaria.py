"""
Zona horaria del negocio (America/Argentina/Buenos_Aires, UTC-3).

La base guarda instantes en UTC. Un cobro hecho a las 22:30 en Argentina se guarda a las
01:30 UTC del día SIGUIENTE: el "día de caja" tiene que ser el día local, no el UTC.
"""
from datetime import date, datetime, timezone

from app.core import timezone as tz
from app.models.logistica import Movimiento
from app.tests.conftest import crear_cliente_db, login

API = "/api/v1"
UTC = timezone.utc


def mov_en(db, mundo, instante_utc, cobrado=1000.0, total=1000.0, metodo="efectivo", cliente=None):
    m = Movimiento(
        tenant_id=mundo.ta.id,
        cliente_id=(cliente or mundo.cli_a).id,
        repartidor_id=mundo.admin_a.id,
        detalles={},
        monto_total=total,
        monto_cobrado=cobrado,
        metodo_pago=metodo,
        fecha=instante_utc,
    )
    db.add(m)
    db.commit()
    return m


# ─── Funciones del módulo ─────────────────────────────────────────────────────
def test_rango_de_un_dia_local_va_de_3_a_3_utc():
    inicio, fin = tz.rango_dia(date(2026, 11, 19))
    assert inicio == datetime(2026, 11, 19, 3, 0, tzinfo=UTC)
    assert fin == datetime(2026, 11, 20, 3, 0, tzinfo=UTC)


def test_rango_de_mes_y_de_anio_cruzan_bien_el_cambio_de_anio():
    assert tz.rango_mes(2026, 12) == (datetime(2026, 12, 1, 3, 0, tzinfo=UTC), datetime(2027, 1, 1, 3, 0, tzinfo=UTC))
    assert tz.rango_anio(2026) == (datetime(2026, 1, 1, 3, 0, tzinfo=UTC), datetime(2027, 1, 1, 3, 0, tzinfo=UTC))


def test_a_local_convierte_utc_y_asume_utc_si_viene_sin_zona():
    assert tz.a_local(datetime(2026, 11, 20, 1, 30, tzinfo=UTC)).strftime("%d/%m %H:%M") == "19/11 22:30"
    assert tz.a_local(datetime(2026, 11, 20, 1, 30)).strftime("%d/%m %H:%M") == "19/11 22:30"  # naive = UTC (SQLite)


def test_hoy_es_la_fecha_del_negocio_aunque_el_servidor_ya_este_en_el_dia_siguiente(monkeypatch):
    servidor_utc = datetime(2026, 11, 20, 1, 30, tzinfo=UTC)  # en Argentina todavía es 19/11 22:30
    monkeypatch.setattr(tz, "ahora_local", lambda: servidor_utc.astimezone(tz.TZ_NEGOCIO))
    assert tz.hoy_local() == date(2026, 11, 19)


# ─── Historial / cierre de caja diario ────────────────────────────────────────
def test_un_cobro_de_las_22_30_pertenece_al_dia_local_y_no_al_dia_utc(db, mundo):
    mov_en(db, mundo, datetime(2026, 11, 20, 1, 30, tzinfo=UTC))  # 19/11 22:30 en Argentina
    del_19 = mundo.client.get(f"{API}/logistica/historial?fecha=2026-11-19", headers=mundo.h_admin_a).json()
    del_20 = mundo.client.get(f"{API}/logistica/historial?fecha=2026-11-20", headers=mundo.h_admin_a).json()
    assert len(del_19) == 1 and del_19[0]["hora"] == "22:30"
    assert del_20 == []


def test_el_corte_del_dia_es_a_las_00_00_locales(db, mundo):
    mov_en(db, mundo, datetime(2026, 11, 19, 2, 59, 59, tzinfo=UTC), total=1)  # 18/11 23:59:59 local
    mov_en(db, mundo, datetime(2026, 11, 19, 3, 0, 0, tzinfo=UTC), total=2)    # 19/11 00:00:00 local
    dia18 = mundo.client.get(f"{API}/logistica/historial?fecha=2026-11-18", headers=mundo.h_admin_a).json()
    dia19 = mundo.client.get(f"{API}/logistica/historial?fecha=2026-11-19", headers=mundo.h_admin_a).json()
    assert [m["monto_total"] for m in dia18] == [1] and [m["monto_total"] for m in dia19] == [2]


def test_historial_sin_fecha_usa_el_hoy_del_negocio(db, mundo, monkeypatch):
    from app.api.controllers import logistica as controller

    mov_en(db, mundo, datetime(2026, 11, 20, 1, 30, tzinfo=UTC))
    monkeypatch.setattr(controller, "hoy_local", lambda: date(2026, 11, 19))
    assert len(mundo.client.get(f"{API}/logistica/historial", headers=mundo.h_admin_a).json()) == 1


def test_el_filtro_de_dia_respeta_la_empresa_y_el_chofer(db, mundo):
    mov_en(db, mundo, datetime(2026, 11, 20, 1, 30, tzinfo=UTC))
    assert mundo.client.get(f"{API}/logistica/historial?fecha=2026-11-19", headers=mundo.h_admin_b).json() == []


# ─── Mes y año ────────────────────────────────────────────────────────────────
def test_cobro_de_fin_de_mes_por_la_noche_cuenta_en_ese_mes(db, mundo):
    mov_en(db, mundo, datetime(2026, 12, 1, 2, 0, tzinfo=UTC), cobrado=500, total=500)  # 30/11 23:00 local
    nov = mundo.client.get(f"{API}/dashboard/resumen?mes_a=11&anio_a=2026", headers=mundo.h_admin_a).json()
    dic = mundo.client.get(f"{API}/dashboard/resumen?mes_a=12&anio_a=2026", headers=mundo.h_admin_a).json()
    assert nov["kpis"]["recaudacion_mes"] == 500 and nov["kpis"]["entregas_mes"] == 1
    assert dic["kpis"]["recaudacion_mes"] == 0 and dic["kpis"]["entregas_mes"] == 0


def test_resumen_del_mes_actual_usa_el_mes_local(db, mundo, monkeypatch):
    from app.services import logistica_service

    mov_en(db, mundo, datetime(2026, 12, 1, 2, 0, tzinfo=UTC), cobrado=700, total=700)  # noviembre local
    monkeypatch.setattr(logistica_service, "hoy_local", lambda: date(2026, 11, 30))
    res = mundo.client.get(f"{API}/logistica/historial/mes-actual", headers=mundo.h_admin_a).json()
    assert res["efectivo"] == 700


def test_grafico_diario_asigna_el_cobro_al_dia_local(db, mundo):
    mov_en(db, mundo, datetime(2026, 11, 20, 1, 30, tzinfo=UTC), cobrado=300, total=300)  # día 19 local
    graf = mundo.client.get(f"{API}/dashboard/resumen?mes_a=11&anio_a=2026", headers=mundo.h_admin_a).json()["grafico_comparativo"]
    por_dia = {int(d["dia"]): d["mes_a"] for d in graf}
    assert por_dia[19] == 300 and por_dia[20] == 0


def test_grafico_anual_pone_el_31_de_diciembre_nocturno_en_diciembre(db, mundo):
    mov_en(db, mundo, datetime(2027, 1, 1, 1, 0, tzinfo=UTC), cobrado=900, total=900)  # 31/12/2026 22:00 local
    dash26 = mundo.client.get(f"{API}/dashboard/resumen?mes_a=12&anio_a=2026", headers=mundo.h_admin_a).json()
    dash27 = mundo.client.get(f"{API}/dashboard/resumen?mes_a=1&anio_a=2027", headers=mundo.h_admin_a).json()
    assert dash26["grafico_anual"][11]["total"] == 900          # diciembre de 2026
    assert dash27["grafico_anual"][0]["total"] == 0             # enero de 2027 no la recibe


def test_recaudacion_de_hoy_usa_el_dia_del_negocio(db, mundo, monkeypatch):
    from app.services import dashboard_service

    mov_en(db, mundo, datetime(2026, 11, 20, 1, 30, tzinfo=UTC), cobrado=400, total=400)
    monkeypatch.setattr(dashboard_service, "hoy_local", lambda: date(2026, 11, 19))
    kpis = mundo.client.get(f"{API}/dashboard/resumen?mes_a=11&anio_a=2026", headers=mundo.h_admin_a).json()["kpis"]
    assert kpis["recaudacion_hoy"] == 400


# ─── Portal del cliente ───────────────────────────────────────────────────────
def test_portal_muestra_la_fecha_local_del_movimiento(db, mundo):
    cli = crear_cliente_db(db, mundo.ta.id, "Portal TZ", "2615550123")
    mov_en(db, mundo, datetime(2026, 11, 20, 1, 30, tzinfo=UTC), cliente=cli)
    h = login(mundo.client, "2615550123", mundo.ta.id, password="1234")
    ultimos = mundo.client.get(f"{API}/portal/mi-cuenta", headers=h).json()["ultimos_movimientos"]
    assert ultimos[0]["fecha"] == "19/11/2026"
