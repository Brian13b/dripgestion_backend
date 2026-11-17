from fastapi import FastAPI, status
from fastapi.concurrency import asynccontextmanager
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import redis
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from SaaS_Backend.app.db.init_db import init_superadmin

from app.api.api import api_router
from app.core.config import settings
from app.core.limiter import limiter
from app.db.base import Base
from app.db.session import SessionLocal, engine

@asynccontextmanager
async def lifespan(app: FastAPI):
  db = SessionLocal()
  try:
    init_superadmin(db)
  finally:
    db.close()
  yield

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

origenes_permitidos = [
    o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origenes_permitidos,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {
        "sistema": "Drip Gestión API v1.5.1",
        "estado": "Operativo",
        "multitenant": True
    }

@app.get("/health", tags=["Health"])
def health_check():
  status_report = {
      "status": "ok",
      "database": "disconnected",
      "redis": "disconnected",
  }
  is_healthy = True

  try:
    db = SessionLocal()
    db.execute(text("SELECT 1"))
    db.close()
    status_report["database"] = "connected"
  except Exception as e:
    status_report["database"] = f"error: {str(e)}"
    is_healthy = False

  if settings.REDIS_URL:
    try:
      r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
      if r.ping():
        status_report["redis"] = "connected"
    except Exception as e:
      status_report["redis"] = f"error: {str(e)}"
  else:
    status_report["redis"] = "not_configured"

  code = (
      status.HTTP_200_OK
      if is_healthy
      else status.HTTP_503_SERVICE_UNAVAILABLE
  )
  return JSONResponse(status_code=code, content=status_report)