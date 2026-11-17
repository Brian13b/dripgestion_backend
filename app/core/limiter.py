from app.core.config import settings
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL if settings.REDIS_URL else "memory://",
    swallow_errors=True,
    storage_options={
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
        "retry_on_timeout": True,
    },
)