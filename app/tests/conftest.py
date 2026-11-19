"""
Configuración común de la suite.

IMPORTANTE: las variables de entorno se fijan ANTES de importar `app`, para que
la aplicación use una base SQLite temporal y NUNCA la base del `.env`
(Postgres local de desarrollo). Cada test arranca con tablas vacías.
"""
import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="dripgestion_tests_")
_DB_FILE = os.path.join(_TMP_DIR, "test.db").replace("\\", "/")

# Opcional: correr la suite contra un PostgreSQL REAL y descartable
# (TEST_DATABASE_URL=postgresql://usuario:clave@localhost:5432/dripgestion_test).
# Por seguridad el nombre de la base DEBE terminar en "_test": cada test borra y recrea las tablas.
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
if _TEST_DB_URL:
    assert _TEST_DB_URL.rstrip("/").split("/")[-1].split("?")[0].endswith("_test"), (
        "TEST_DATABASE_URL debe apuntar a una base cuyo nombre termine en '_test'"
    )

# Se pisan siempre (las variables de entorno ganan sobre el .env).
os.environ["SQLALCHEMY_DATABASE_URL"] = _TEST_DB_URL or f"sqlite:///{_DB_FILE}"
os.environ["PROJECT_NAME"] = "DripGestion Tests"
os.environ["SECRET_KEY"] = "clave-solo-para-tests-no-usar-en-produccion"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
os.environ["REDIS_URL"] = ""
os.environ["CLOUDINARY_CLOUD_NAME"] = ""
os.environ["CLOUDINARY_API_KEY"] = ""
os.environ["CLOUDINARY_API_SECRET"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402

from app.core import security  # noqa: E402
from app.core.limiter import limiter  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.cliente import Cliente  # noqa: E402
from app.models.logistica import Movimiento, Recorrido  # noqa: E402
from app.models.producto import Producto, TipoEnvase  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

ES_POSTGRES = engine.url.drivername.startswith("postgresql")
assert engine.url.drivername.startswith("sqlite") or (ES_POSTGRES and bool(_TEST_DB_URL)), (
    "La suite solo corre contra SQLite temporal o contra TEST_DATABASE_URL (base *_test)"
)

if not ES_POSTGRES:
    # Postgres hace cumplir las claves foráneas; SQLite no, salvo que se active.
    # Se activa para que los tests reflejen el comportamiento real en producción.
    @event.listens_for(engine, "connect")
    def _sqlite_fk_on(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# bcrypt con pocas rondas: los tests no necesitan el costo de producción.
security.pwd_context.update(bcrypt__rounds=4)

PASSWORD = "Clave-Test-123"


@pytest.fixture(autouse=True)
def _entorno_limpio():
    """Base vacía, sin overrides y sin rate limit antes de cada test."""
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    limiter.enabled = False
    yield
    app.dependency_overrides.clear()
    limiter.enabled = False


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    # raise_server_exceptions=False: un error no controlado se ve como HTTP 500,
    # igual que en producción, en lugar de cortar el test con una excepción.
    return TestClient(app, raise_server_exceptions=False)


# ─── Fábricas de datos ────────────────────────────────────────────────────────
def crear_tenant(db, nombre="Empresa A", subdominio="empresa-a", activo=True):
    tenant = Tenant(nombre=nombre, subdominio=subdominio, is_active=activo)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def crear_usuario(db, tenant_id, username, rol=UserRole.ADMIN, password=PASSWORD, activo=True, nombre=None):
    user = User(
        tenant_id=tenant_id,
        username=username,
        hashed_password=security.get_password_hash(password),
        role=rol,
        is_active=activo,
        full_name=nombre or username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def crear_envase(db, tenant_id, codigo="BID20", nombre="Bidón 20L", valor=1500.0, activo=True):
    envase = TipoEnvase(tenant_id=tenant_id, codigo=codigo, nombre=nombre, valor_reposicion=valor, activo=activo)
    db.add(envase)
    db.commit()
    db.refresh(envase)
    return envase


def crear_producto(db, tenant_id, codigo="AGUA20", nombre="Agua 20L", precio=3500.0, retornable=False, envase_id=None, activo=True):
    producto = Producto(
        tenant_id=tenant_id,
        codigo=codigo,
        nombre=nombre,
        precio_actual=precio,
        es_retornable=retornable,
        tipo_envase_id=envase_id if retornable else None,
        activo=activo,
    )
    db.add(producto)
    db.commit()
    db.refresh(producto)
    return producto


def crear_cliente_db(db, tenant_id, nombre="Kiosco", telefono="2615550001", saldo=0.0, stock=None):
    user = crear_usuario(db, tenant_id, telefono, rol=UserRole.CLIENTE, password="1234", nombre=nombre)
    cliente = Cliente(
        tenant_id=tenant_id,
        user_id=user.id,
        nombre_negocio=nombre,
        direccion="Calle 123",
        telefono=telefono,
        saldo_dinero=saldo,
        stock_envases=stock or {},
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


def crear_recorrido_db(db, tenant_id, nombre="Ruta Norte", clientes=None, repartidor_id=None, dia=0):
    recorrido = Recorrido(
        tenant_id=tenant_id,
        nombre=nombre,
        dia_semana=dia,
        clientes_orden=clientes or [],
        repartidor_id=repartidor_id,
    )
    db.add(recorrido)
    db.commit()
    db.refresh(recorrido)
    return recorrido


def login(client, username, tenant_id=None, password=PASSWORD):
    headers = {"X-Tenant-ID": str(tenant_id)} if tenant_id is not None else {}
    res = client.post(
        "/api/v1/auth/login/access-token",
        data={"username": username, "password": password},
        headers=headers,
    )
    assert res.status_code == 200, f"Login falló para {username}: {res.status_code} {res.text}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# ─── Escenarios listos para usar ──────────────────────────────────────────────
_CTX = {}


def detalle_para_total(total):
    """Detalle de entrega que respalda `total` con la soda del catalogo de la empresa A
    ($800 c/u, no retornable): desde BUG-18 un total positivo exige items que lo justifiquen."""
    if not total or total <= 0:
        return {}
    cantidad = int(-(-total // 800))
    return {str(_CTX["soda_a_id"]): {"entregado": cantidad}}


class Mundo:
    """Dos empresas, cada una con admin, repartidor y datos propios."""

    pass


@pytest.fixture
def mundo(db, client):
    m = Mundo()
    m.client = client
    m.db = db

    m.ta = crear_tenant(db, "Aguas A", "aguas-a")
    m.tb = crear_tenant(db, "Soda B", "soda-b")

    m.admin_a = crear_usuario(db, m.ta.id, "admin_a", UserRole.ADMIN)
    m.rep_a = crear_usuario(db, m.ta.id, "rep_a", UserRole.REPARTIDOR)
    m.admin_b = crear_usuario(db, m.tb.id, "admin_b", UserRole.ADMIN)
    m.rep_b = crear_usuario(db, m.tb.id, "rep_b", UserRole.REPARTIDOR)
    m.super = crear_usuario(db, None, "super", UserRole.SUPERADMIN)

    m.h_admin_a = login(client, "admin_a", m.ta.id)
    m.h_rep_a = login(client, "rep_a", m.ta.id)
    m.h_admin_b = login(client, "admin_b", m.tb.id)
    m.h_rep_b = login(client, "rep_b", m.tb.id)
    m.h_super = login(client, "super")

    # Catálogo de A
    m.envase_a = crear_envase(db, m.ta.id, "BID20", "Bidón 20L", 1500.0)
    m.agua_a = crear_producto(db, m.ta.id, "AGUA20", "Agua 20L", 3500.0, True, m.envase_a.id)
    m.soda_a = crear_producto(db, m.ta.id, "SODA1", "Soda 1L", 800.0, False)
    _CTX["soda_a_id"] = m.soda_a.id
    # Catálogo de B
    m.envase_b = crear_envase(db, m.tb.id, "SIF", "Sifón", 900.0)
    m.soda_b = crear_producto(db, m.tb.id, "SODAB", "Soda B", 700.0, True, m.envase_b.id)

    # Clientes
    m.cli_a = crear_cliente_db(db, m.ta.id, "Kiosco A", "2615550001")
    m.cli_b = crear_cliente_db(db, m.tb.id, "Kiosco B", "2615550002")
    return m


def bug(codigo, descripcion):
    """
    Marca un test que describe el comportamiento CORRECTO esperado y que hoy falla
    por un bug conocido de la auditoría (ver informe). `strict=True`: cuando el bug
    se corrija, el test pasa y pytest avisa para que se quite la marca.
    """
    return pytest.mark.xfail(reason=f"{codigo}: {descripcion}", strict=True)
