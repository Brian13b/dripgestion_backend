"""Empresas (tenants): alta por el superadmin, suspensión, branding y logo."""
import io

from app.models.tenant import Tenant
from app.tests.conftest import bug, login

API = "/api/v1/tenants"
ALTA = {
    "nombre": "Hielos del Sur",
    "subdominio": "hielos-sur",
    "whatsapp": "5492615550000",
    "admin_username": "admin_hielos",
    "admin_password": "Clave-Admin-1",
    "admin_full_name": "Ana Admin",
}


# ─── Info pública ─────────────────────────────────────────────────────────────
def test_info_publica_por_subdominio(mundo):
    res = mundo.client.get(f"{API}/info/aguas-a")
    assert res.status_code == 200 and res.json()["nombre"] == "Aguas A"


def test_info_de_subdominio_inexistente_404(mundo):
    assert mundo.client.get(f"{API}/info/no-existe").status_code == 404


# ─── Alta (onboarding) ────────────────────────────────────────────────────────
def test_superadmin_da_de_alta_empresa_con_su_admin(mundo):
    res = mundo.client.post(f"{API}/onboarding", json=ALTA, headers=mundo.h_super)
    assert res.status_code == 200, res.text
    tenant_id = res.json()["id"]
    assert res.json()["is_active"] is True and res.json()["subdominio"] == "hielos-sur"
    # El admin nuevo puede entrar a SU empresa y solo a esa
    h = login(mundo.client, "admin_hielos", tenant_id, password="Clave-Admin-1")
    assert mundo.client.get("/api/v1/auth/me", headers=h).json()["role"] == "admin"
    assert mundo.client.post("/api/v1/auth/login/access-token", data={"username": "admin_hielos", "password": "Clave-Admin-1"}, headers={"X-Tenant-ID": str(mundo.ta.id)}).status_code == 401


def test_alta_con_subdominio_repetido_400(mundo):
    res = mundo.client.post(f"{API}/onboarding", json={**ALTA, "subdominio": "aguas-a"}, headers=mundo.h_super)
    assert res.status_code == 400


def test_alta_permite_el_mismo_username_de_admin_en_otra_empresa(mundo):
    """BUG-10 corregido: el username es único POR EMPRESA, no global."""
    res = mundo.client.post(f"{API}/onboarding", json={**ALTA, "admin_username": "admin_a", "admin_password": "Otra-Clave-77"}, headers=mundo.h_super)
    assert res.status_code == 200, res.text
    nueva = res.json()["id"]
    # Cada admin entra solo a SU empresa, con SU contraseña
    h_nuevo = login(mundo.client, "admin_a", nueva, password="Otra-Clave-77")
    assert mundo.client.get("/api/v1/auth/me", headers=h_nuevo).json()["tenant_id"] == nueva
    h_viejo = login(mundo.client, "admin_a", mundo.ta.id)
    assert mundo.client.get("/api/v1/auth/me", headers=h_viejo).json()["tenant_id"] == mundo.ta.id
    assert mundo.client.post("/api/v1/auth/login/access-token", data={"username": "admin_a", "password": "Otra-Clave-77"}, headers={"X-Tenant-ID": str(mundo.ta.id)}).status_code == 401


def test_username_repetido_dentro_de_la_misma_empresa_sigue_prohibido(db, mundo):
    import pytest
    from sqlalchemy.exc import IntegrityError
    from app.tests.conftest import crear_usuario

    with pytest.raises(IntegrityError):
        crear_usuario(db, mundo.ta.id, "admin_a")
    db.rollback()


def test_username_de_superadmin_no_se_puede_repetir(db, mundo):
    import pytest
    from sqlalchemy.exc import IntegrityError
    from app.models.user import UserRole
    from app.tests.conftest import crear_usuario

    with pytest.raises(IntegrityError):
        crear_usuario(db, None, "super", UserRole.SUPERADMIN)
    db.rollback()


def test_un_usuario_de_empresa_no_puede_loguearse_con_el_nombre_de_otra(mundo):
    res = mundo.client.post("/api/v1/auth/login/access-token", data={"username": "admin_b", "password": "Clave-Test-123"}, headers={"X-Tenant-ID": str(mundo.ta.id)})
    assert res.status_code == 401


def test_alta_con_datos_incompletos_422(mundo):
    assert mundo.client.post(f"{API}/onboarding", json={"nombre": "x"}, headers=mundo.h_super).status_code == 422


def test_alta_normaliza_subdominio_a_minusculas(mundo, db):
    mundo.client.post(f"{API}/onboarding", json={**ALTA, "subdominio": "  HIELOS-Sur "}, headers=mundo.h_super)
    assert db.query(Tenant).filter(Tenant.subdominio == "hielos-sur").count() == 1


@bug("BUG-09", "el chequeo de subdominio repetido compara SIN normalizar: 'AGUAS-A' pasa el control y revienta con IntegrityError (500)")
def test_alta_con_subdominio_repetido_en_mayusculas_400(mundo):
    res = mundo.client.post(f"{API}/onboarding", json={**ALTA, "subdominio": "AGUAS-A"}, headers=mundo.h_super)
    assert res.status_code == 400


@bug("BUG-09", "el subdominio no se valida (espacios, puntos, barras): rompe la resolución por hostname")
def test_alta_con_subdominio_invalido_se_rechaza(mundo):
    res = mundo.client.post(f"{API}/onboarding", json={**ALTA, "subdominio": "mi empresa/../x"}, headers=mundo.h_super)
    assert res.status_code in (400, 422)


@bug("BUG-13", "la contraseña inicial del admin no tiene validación de largo/complejidad")
def test_alta_con_password_debil_se_rechaza(mundo):
    res = mundo.client.post(f"{API}/onboarding", json={**ALTA, "admin_password": "1"}, headers=mundo.h_super)
    assert res.status_code in (400, 422)


# ─── Suspensión y reactivación ────────────────────────────────────────────────
def test_suspender_empresa_cierra_sesiones_y_bloquea_login(mundo):
    res = mundo.client.patch(f"{API}/{mundo.ta.id}/estado?activo=false", headers=mundo.h_super)
    assert res.status_code == 200 and res.json()["is_active"] is False
    assert mundo.client.get("/api/v1/auth/me", headers=mundo.h_admin_a).status_code == 401  # token invalidado
    assert mundo.client.post("/api/v1/auth/login/access-token", data={"username": "admin_a", "password": "Clave-Test-123"}, headers={"X-Tenant-ID": str(mundo.ta.id)}).status_code in (400, 401)
    assert mundo.client.get("/api/v1/auth/me", headers=mundo.h_admin_b).status_code == 200  # la otra empresa no se afecta


def test_reactivar_empresa_permite_volver_a_entrar(mundo):
    mundo.client.patch(f"{API}/{mundo.ta.id}/estado?activo=false", headers=mundo.h_super)
    mundo.client.patch(f"{API}/{mundo.ta.id}/estado?activo=true", headers=mundo.h_super)
    login(mundo.client, "admin_a", mundo.ta.id)


def test_cambiar_estado_de_empresa_inexistente_404(mundo):
    assert mundo.client.patch(f"{API}/9999/estado?activo=false", headers=mundo.h_super).status_code == 404


def test_cambiar_estado_exige_el_parametro_activo_422(mundo):
    assert mundo.client.patch(f"{API}/{mundo.ta.id}/estado", headers=mundo.h_super).status_code == 422


# ─── Branding ─────────────────────────────────────────────────────────────────
def test_admin_actualiza_colores_de_su_empresa(mundo):
    res = mundo.client.put(f"{API}/config", json={"color_primario": "#E86A1F", "whatsapp": "5491100001111"}, headers=mundo.h_admin_a)
    assert res.status_code == 200 and res.json()["color_primario"] == "#E86A1F"


def test_superadmin_edita_cualquier_empresa(mundo):
    res = mundo.client.put(f"{API}/{mundo.tb.id}", json={"nombre": "Soda B S.A."}, headers=mundo.h_super)
    assert res.status_code == 200 and res.json()["nombre"] == "Soda B S.A."


def test_superadmin_no_puede_usar_subdominio_de_otra_empresa_400(mundo):
    assert mundo.client.put(f"{API}/{mundo.tb.id}", json={"subdominio": "aguas-a"}, headers=mundo.h_super).status_code == 400


def test_editar_empresa_inexistente_404(mundo):
    assert mundo.client.put(f"{API}/9999", json={"nombre": "x"}, headers=mundo.h_super).status_code == 404


@bug("BUG-09", "el superadmin no puede editar una empresa SUSPENDIDA (crud filtra is_active=True): responde 404")
def test_superadmin_puede_editar_empresa_suspendida(db, mundo):
    mundo.tb.is_active = False
    db.commit()
    assert mundo.client.put(f"{API}/{mundo.tb.id}", json={"nombre": "Soda B (suspendida)"}, headers=mundo.h_super).status_code == 200


@bug("BUG-09", "los colores/fuente del branding no se validan (valores arbitrarios se inyectan luego en el CSS del front)")
def test_color_con_valor_arbitrario_se_rechaza(mundo):
    res = mundo.client.put(f"{API}/config", json={"color_primario": "red;}</style><script>alert(1)</script>"}, headers=mundo.h_admin_a)
    assert res.status_code in (400, 422)


# ─── Logo ─────────────────────────────────────────────────────────────────────
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


def _subir(mundo, contenido, nombre="logo.png", tipo="image/png", headers=None):
    return mundo.client.post(f"{API}/config/logo", files={"file": (nombre, io.BytesIO(contenido), tipo)}, headers=headers or mundo.h_admin_a)


def test_logo_valido_se_guarda(monkeypatch, db, mundo):
    from app.services import cloudinary_service

    monkeypatch.setattr(cloudinary_service, "subir_logo", lambda f, tid, old: {"logo_url": "https://cdn.test/logo.png", "logo_public_id": "pid"})
    res = _subir(mundo, PNG)
    assert res.status_code == 200 and res.json()["logo_url"] == "https://cdn.test/logo.png"
    db.expire_all()
    assert db.get(Tenant, mundo.ta.id).logo_public_id == "pid"


def test_logo_con_contenido_no_imagen_400(mundo):
    assert _subir(mundo, b"MZ-ejecutable-disfrazado", "logo.png", "image/png").status_code == 400


def test_logo_demasiado_grande_413(mundo):
    assert _subir(mundo, PNG + b"0" * (5 * 1024 * 1024)).status_code == 413


def test_logo_con_content_type_que_no_es_imagen_400(mundo):
    assert _subir(mundo, PNG, "logo.png", "text/plain").status_code == 400


def test_subir_logo_requiere_admin(mundo):
    assert _subir(mundo, PNG, headers=mundo.h_rep_a).status_code == 403


def test_fallo_de_cloudinary_devuelve_500_controlado(monkeypatch, mundo):
    from app.services import cloudinary_service

    def explota(*a, **k):
        raise RuntimeError("cloudinary caído")

    monkeypatch.setattr(cloudinary_service, "subir_logo", explota)
    res = _subir(mundo, PNG)
    assert res.status_code == 500 and "cloudinary" not in res.json()["detail"].lower()


# ─── Paleta por defecto: marca DripGestión (naranja cálido), no el azul anterior ──
PALETA_CALIDA = {
    "color_primario": "#E86A1F",
    "color_primario_light": "#F5A474",
    "color_primario_dark": "#1C1917",
    "color_background": "#F7F4F0",
    "color_success": "#16a34a",
    "color_danger": "#dc2626",
    "color_secondary": "#78716c",
}


def test_empresa_nueva_por_onboarding_nace_con_la_paleta_calida(mundo):
    res = mundo.client.post(f"{API}/onboarding", json=ALTA, headers=mundo.h_super)
    assert res.status_code == 200, res.text
    assert {k: res.json()[k] for k in PALETA_CALIDA} == PALETA_CALIDA


def test_onboarding_respeta_el_color_elegido_y_completa_el_resto_con_la_marca(mundo):
    res = mundo.client.post(f"{API}/onboarding", json={**ALTA, "color_primario": "#123456"}, headers=mundo.h_super)
    assert res.json()["color_primario"] == "#123456" and res.json()["color_primario_light"] == "#F5A474"


def test_empresa_creada_en_base_sin_colores_usa_la_paleta_calida(db):
    from app.tests.conftest import crear_tenant
    t = crear_tenant(db, "Directa", "directa")
    assert {k: getattr(t, k) for k in PALETA_CALIDA} == PALETA_CALIDA


def test_las_migraciones_tienen_una_sola_cabeza():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config("alembic.ini")
    assert ScriptDirectory.from_config(cfg).get_heads() == ["f4b8d2e6a913"]
