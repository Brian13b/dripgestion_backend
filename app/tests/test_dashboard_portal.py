"""Dashboard de métricas (admin) y portal del cliente."""
from app.tests.conftest import bug, crear_cliente_db, crear_envase, crear_recorrido_db, login

API = "/api/v1"


def mov(cliente_id, total, cobrado, metodo="efectivo", detalles=None, **extra):
    return {"cliente_id": cliente_id, "detalles": detalles or {}, "monto_total": total, "monto_cobrado": cobrado, "metodo_pago": metodo, **extra}


def dash(mundo, query=""):
    return mundo.client.get(f"{API}/dashboard/resumen{query}", headers=mundo.h_admin_a)


# ─── Dashboard ────────────────────────────────────────────────────────────────
def test_dashboard_empresa_nueva_devuelve_ceros(mundo):
    res = dash(mundo)
    assert res.status_code == 200
    kpis = res.json()["kpis"]
    assert kpis["clientes_activos"] == 1 and kpis["recaudacion_mes"] == 0 and kpis["entregas_mes"] == 0
    assert len(res.json()["grafico_anual"]) == 12 and len(res.json()["grafico_comparativo"]) == 31


def test_dashboard_kpis_reflejan_cobros_deuda_y_envases(db, mundo):
    clave = str(mundo.envase_a.id)
    crear_cliente_db(db, mundo.ta.id, "Deudor", "2615550090", saldo=2500, stock={clave: 4})
    det = {str(mundo.agua_a.id): {"entregado": 2, "devuelto": 0}}
    mundo.client.post(f"{API}/logistica/movimientos", json=mov(mundo.cli_a.id, 7000, 7000, "efectivo", det), headers=mundo.h_admin_a)
    mundo.client.post(f"{API}/logistica/movimientos", json=mov(mundo.cli_a.id, 1000, 0, "cta_corriente"), headers=mundo.h_admin_a)
    kpis = dash(mundo).json()["kpis"]
    assert kpis["clientes_activos"] == 2
    assert kpis["recaudacion_hoy"] == 7000 and kpis["recaudacion_mes"] == 7000
    assert kpis["entregas_mes"] == 2
    assert kpis["deuda_en_calle"] == 3500          # 2500 + 1000 del fiado
    assert kpis["total_envases"] == 6              # 4 + 2 entregados
    assert kpis["valor_envases_calle"] == 9000     # 6 x $1500


def test_dashboard_detalle_de_envases_por_tipo(db, mundo):
    crear_cliente_db(db, mundo.ta.id, "Con envases", "2615550091", stock={str(mundo.envase_a.id): 5})
    envases = dash(mundo).json()["envases_por_tipo"]
    assert envases == [{"tipo_envase_id": mundo.envase_a.id, "nombre": "Bidón 20L", "codigo": "BID20", "cantidad": 5, "valor_total": 7500.0}]


def test_dashboard_grafico_de_metodos(mundo):
    mundo.client.post(f"{API}/logistica/movimientos", json=mov(mundo.cli_a.id, 1000, 1000, "efectivo"), headers=mundo.h_admin_a)
    mundo.client.post(f"{API}/logistica/movimientos", json=mov(mundo.cli_a.id, 600, 600, "transferencia"), headers=mundo.h_admin_a)
    mundo.client.post(f"{API}/logistica/movimientos", json=mov(mundo.cli_a.id, 300, 0, "cta_corriente"), headers=mundo.h_admin_a)
    metodos = {m["name"]: m["value"] for m in dash(mundo).json()["grafico_metodos"]}
    assert metodos == {"Efectivo": 1000, "Transferencias": 600, "A Cuenta": 300}


def test_dashboard_rendimiento_por_recorrido(db, mundo):
    ruta = crear_recorrido_db(db, mundo.ta.id, "Ruta Sur", [mundo.cli_a.id], mundo.rep_a.id)
    mundo.client.post(f"{API}/logistica/movimientos", json=mov(mundo.cli_a.id, 500, 500, recorrido_id=ruta.id), headers=mundo.h_rep_a)
    mundo.client.post(f"{API}/logistica/movimientos", json=mov(mundo.cli_a.id, 200, 200), headers=mundo.h_admin_a)
    rend = {r["nombre"]: (r["recaudado"], r["entregas"]) for r in dash(mundo).json()["grafico_recorridos"]}
    assert rend == {"Ruta Sur": (500, 1), "Sin Recorrido": (200, 1)}


def test_dashboard_compara_con_mes_anterior_y_etiquetas(mundo):
    res = dash(mundo, "?mes_a=3&anio_a=2026&mes_b=2&anio_b=2026").json()
    assert res["labels"] == {"mes_a": "Mar 2026", "mes_b": "Feb 2026"}


def test_dashboard_enero_compara_contra_diciembre_del_anio_anterior(mundo):
    assert dash(mundo, "?mes_a=1&anio_a=2026").json()["labels"] == {"mes_a": "Ene 2026", "mes_b": "Dic 2025"}


def test_dashboard_requiere_admin(mundo):
    assert mundo.client.get(f"{API}/dashboard/resumen", headers=mundo.h_rep_a).status_code == 403
    assert mundo.client.get(f"{API}/dashboard/resumen").status_code == 401


@bug("BUG-22", "mes fuera de rango (13) provoca IndexError -> 500 con el texto interno del error")
def test_dashboard_mes_invalido_se_rechaza(mundo):
    assert dash(mundo, "?mes_a=13&anio_a=2026").status_code in (400, 422)


@bug("BUG-22", "mes_a=-1 o años absurdos se toman como válidos (mes negativo indexa la lista desde el final)")
def test_dashboard_mes_negativo_se_rechaza(mundo):
    assert dash(mundo, "?mes_a=-1&anio_a=2026").status_code in (400, 422)


# ─── Portal del cliente ───────────────────────────────────────────────────────
def test_portal_muestra_saldo_envases_y_ultimos_movimientos(db, mundo):
    clave = str(mundo.envase_a.id)
    cli = crear_cliente_db(db, mundo.ta.id, "Mi Kiosco", "2615550095", stock={clave: 2})
    det = {str(mundo.agua_a.id): {"entregado": 3, "devuelto": 1}}
    mundo.client.post(f"{API}/logistica/movimientos", json=mov(cli.id, 10500, 5000, "efectivo", det), headers=mundo.h_admin_a)
    mundo.client.post(f"{API}/logistica/movimientos", json=mov(cli.id, 800, 0, "cta_corriente"), headers=mundo.h_admin_a)
    h = login(mundo.client, "2615550095", mundo.ta.id, password="1234")
    res = mundo.client.get(f"{API}/portal/mi-cuenta", headers=h).json()
    assert res["nombre_negocio"] == "Mi Kiosco"
    assert res["saldo_dinero"] == 6300          # (10500-5000) + 800
    assert res["total_envases"] == 4            # 2 + 3 - 1
    assert res["envases_detalle"][0]["cantidad"] == 4
    assert len(res["ultimos_movimientos"]) == 2
    tipos = {m["tipo"] for m in res["ultimos_movimientos"]}
    assert tipos == {"efectivo", "Fiado"}


def test_portal_limita_a_diez_movimientos(db, mundo):
    cli = crear_cliente_db(db, mundo.ta.id, "Habitual", "2615550096")
    for _ in range(12):
        mundo.client.post(f"{API}/logistica/movimientos", json=mov(cli.id, 10, 10), headers=mundo.h_admin_a)
    h = login(mundo.client, "2615550096", mundo.ta.id, password="1234")
    assert len(mundo.client.get(f"{API}/portal/mi-cuenta", headers=h).json()["ultimos_movimientos"]) == 10


def test_portal_de_un_usuario_que_no_es_cliente_404(mundo):
    assert mundo.client.get(f"{API}/portal/mi-cuenta", headers=mundo.h_admin_a).status_code == 404


def test_portal_requiere_login(mundo):
    assert mundo.client.get(f"{API}/portal/mi-cuenta").status_code == 401


def test_portal_tras_eliminar_al_cliente_el_acceso_deja_de_funcionar(db, mundo):
    cli = crear_cliente_db(db, mundo.ta.id, "Baja", "2615550097")
    h = login(mundo.client, "2615550097", mundo.ta.id, password="1234")
    assert mundo.client.delete(f"{API}/clientes/{cli.id}", headers=mundo.h_admin_a).status_code == 200
    assert mundo.client.get(f"{API}/portal/mi-cuenta", headers=h).status_code in (401, 403, 404)
