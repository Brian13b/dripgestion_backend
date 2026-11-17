from datetime import date
from typing import Any
from app.crud import crud_dashboard
from app.models.producto import TipoEnvase
from app.models.user import UserRole
from sqlalchemy.orm import Session

def obtener_metricas_dashboard(
    db: Session, user: Any, mes_a=None, anio_a=None, mes_b=None, anio_b=None
):
  tenant_id = user.tenant_id
  hoy = date.today()

  m_a = int(mes_a) if mes_a else hoy.month
  a_a = int(anio_a) if anio_a else hoy.year

  if mes_b and anio_b:
    m_b, a_b = int(mes_b), int(anio_b)
  else:
    m_b, a_b = (12, a_a - 1) if m_a == 1 else (m_a - 1, a_a)

  total_clientes = crud_dashboard.count_clientes_activos(db, tenant_id)

  todos_los_clientes = crud_dashboard.get_all_clientes_for_envases(
      db, tenant_id
  )
  tipos_envase = (
      db.query(TipoEnvase).filter(TipoEnvase.tenant_id == tenant_id).all()
  )
  mapa_envases = {str(e.id): e for e in tipos_envase}

  acumulado_por_envase: dict[str, int] = {}
  total_envases = 0

  for c in todos_los_clientes:
    if isinstance(c.stock_envases, dict):
      for env_id_str, cant in c.stock_envases.items():
        cantidad = int(cant or 0)
        if cantidad <= 0:
          continue
        total_envases += cantidad
        clave = str(env_id_str)
        acumulado_por_envase[clave] = (
            acumulado_por_envase.get(clave, 0) + cantidad
        )

  envases_por_tipo = []
  valor_envases_calle = 0.0
  for env_id_str, cantidad in acumulado_por_envase.items():
    tipo = mapa_envases.get(env_id_str)
    if tipo:
      valor_total = round(cantidad * tipo.valor_reposicion, 2)
      valor_envases_calle += valor_total
      envases_por_tipo.append({
          "tipo_envase_id": tipo.id,
          "nombre": tipo.nombre,
          "codigo": tipo.codigo,
          "cantidad": cantidad,
          "valor_total": valor_total,
      })

  saldos_pendientes = 0
  recaudacion_hoy = 0
  total_recaudado_mes = 0
  entregas_mes = 0
  grafico_metodos = []
  grafico_anual = []
  grafico_recorridos = []
  grafico_comparativo = []

  if user.role == UserRole.ADMIN:
    saldos_pendientes = crud_dashboard.get_saldos_pendientes_totales(
        db, tenant_id
    )
    recaudacion_hoy = crud_dashboard.get_recaudacion_dia(db, hoy, tenant_id)

    movimientos_a = crud_dashboard.get_movimientos_mes(
        db, tenant_id, m_a, a_a
    )
    total_recaudado_mes = sum(m.monto_cobrado for m in movimientos_a)
    entregas_mes = len(movimientos_a)

    pagos_efectivo = sum(
        m.monto_cobrado
        for m in movimientos_a
        if getattr(m.metodo_pago, "value", m.metodo_pago) == "efectivo"
    )
    pagos_transferencia = sum(
        m.monto_cobrado
        for m in movimientos_a
        if getattr(m.metodo_pago, "value", m.metodo_pago) == "transferencia"
    )
    pagos_fiado = sum(
        m.monto_total
        for m in movimientos_a
        if getattr(m.metodo_pago, "value", m.metodo_pago) == "cta_corriente"
    )

    grafico_metodos = [
        {"name": "Efectivo", "value": pagos_efectivo, "color": "#10b981"},
        {
            "name": "Transferencias",
            "value": pagos_transferencia,
            "color": "#25A7DA",
        },
        {"name": "A Cuenta", "value": pagos_fiado, "color": "#f97316"},
    ]

    datos_anuales = crud_dashboard.get_recaudacion_anual(db, tenant_id, a_a)
    nombres_meses = [
        "Ene",
        "Feb",
        "Mar",
        "Abr",
        "May",
        "Jun",
        "Jul",
        "Ago",
        "Sep",
        "Oct",
        "Nov",
        "Dic",
    ]
    grafico_anual = [{"name": mes, "total": 0} for mes in nombres_meses]

    for mes_num, total in datos_anuales:
      if mes_num:
        grafico_anual[int(mes_num) - 1]["total"] = float(total)

    datos_recorridos = crud_dashboard.get_rendimiento_recorridos(
        db, tenant_id, m_a, a_a
    )
    grafico_recorridos = [
        {
            "nombre": row.nombre or "Sin Recorrido",
            "recaudado": float(row.recaudado),
            "entregas": row.entregas,
        }
        for row in datos_recorridos
    ]

    diario_a = crud_dashboard.get_recaudacion_diaria_mes(
        db, tenant_id, m_a, a_a
    )
    diario_b = crud_dashboard.get_recaudacion_diaria_mes(
        db, tenant_id, m_b, a_b
    )

    dict_a = {int(dia): float(total) for dia, total in diario_a if dia}
    dict_b = {int(dia): float(total) for dia, total in diario_b if dia}

    for d in range(1, 32):
      grafico_comparativo.append({
          "dia": str(d),
          "mes_a": dict_a.get(d, 0.0),
          "mes_b": dict_b.get(d, 0.0),
      })

  nombres = [
      "Ene",
      "Feb",
      "Mar",
      "Abr",
      "May",
      "Jun",
      "Jul",
      "Ago",
      "Sep",
      "Oct",
      "Nov",
      "Dic",
  ]
  label_a = f"{nombres[m_a-1]} {a_a}"
  label_b = f"{nombres[m_b-1]} {a_b}"

  return {
      "kpis": {
          "clientes_activos": total_clientes,
          "total_envases": total_envases,
          "valor_envases_calle": round(valor_envases_calle, 2),
          "deuda_en_calle": float(saldos_pendientes),
          "recaudacion_hoy": float(recaudacion_hoy),
          "recaudacion_mes": float(total_recaudado_mes),
          "entregas_mes": entregas_mes,
      },
      "envases_por_tipo": envases_por_tipo,
      "grafico_comparativo": grafico_comparativo,
      "labels": {"mes_a": label_a, "mes_b": label_b},
      "grafico_metodos": grafico_metodos,
      "grafico_anual": grafico_anual,
      "grafico_recorridos": grafico_recorridos,
      "role": user.role,
  }