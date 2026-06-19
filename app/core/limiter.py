from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings

# Usa Redis si está configurado; en caso contrario cae a memoria local.
# "memory://" es el backend built-in de la librería `limits` — sin red, sin Redis.
_storage = settings.REDIS_URL if settings.REDIS_URL else "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage,
)
