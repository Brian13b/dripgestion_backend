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


def test_alta_con_admin_repetido_400(mundo):
    res = mundo.client.post(f"{API}/onboarding", json={**ALTA, "admin_username": "admin_a"}, headers=mundo.h_super)
    assert res.status_code == 400


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
