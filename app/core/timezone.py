"""
Zona horaria del negocio.

La base guarda los instantes en UTC (`server_default=now()`), pero "el día de caja"
es el día LOCAL del negocio. Un cobro hecho a las 22:30 en Argentina es de las 01:30
UTC del día siguiente: filtrar por la fecha UTC lo mueve de jornada y descuadra el
cierre. Todo filtro por día/mes/año pasa por este módulo y se hace con rangos
[inicio, fin) en UTC, que funcionan igual en PostgreSQL y SQLite.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings

try:
    TZ_NEGOCIO = ZoneInfo(settings.APP_TIMEZONE)
except ZoneInfoNotFoundError:  # sin base tzdata (Windows sin el paquete `tzdata`)
    # Argentina no tiene horario de verano desde 2009: UTC-3 fijo es equivalente.
    TZ_NEGOCIO = timezone(timedelta(hours=-3), name="ART")


def ahora_local() -> datetime:
    return datetime.now(TZ_NEGOCIO)


def hoy_local() -> date:
    """La fecha de hoy en la zona del negocio (no la del servidor)."""
    return ahora_local().date()


def a_local(instante: datetime) -> datetime:
    """Convierte un instante guardado (UTC; naive en SQLite) a hora local."""
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    return instante.astimezone(TZ_NEGOCIO)


def _a_utc(local_naive: datetime) -> datetime:
    return local_naive.replace(tzinfo=TZ_NEGOCIO).astimezone(timezone.utc)


def rango_dia(dia: date) -> tuple[datetime, datetime]:
    """[00:00 local del día, 00:00 local del día siguiente) expresado en UTC."""
    inicio = datetime.combine(dia, time.min)
    return _a_utc(inicio), _a_utc(inicio + timedelta(days=1))


def rango_mes(anio: int, mes: int) -> tuple[datetime, datetime]:
    inicio = datetime(anio, mes, 1)
    siguiente = datetime(anio + 1, 1, 1) if mes == 12 else datetime(anio, mes + 1, 1)
    return _a_utc(inicio), _a_utc(siguiente)


def rango_anio(anio: int) -> tuple[datetime, datetime]:
    return _a_utc(datetime(anio, 1, 1)), _a_utc(datetime(anio + 1, 1, 1))
