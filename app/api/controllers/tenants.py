from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.core import branding
from app.core.security import get_password_hash
from app.db.session import get_db
from app.api import deps
from app.models.user import User, UserRole
from app.models.tenant import Tenant
from app.schemas.tenant import TenantOnboardingCreate, TenantResponse, TenantUpdate
from app.services import tenant_service
from app.services import cloudinary_service

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB
MAGIC_NUMBERS = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpeg": b"\xff\xd8\xff",
    "jpg": b"\xff\xd8\xff",
}


router = APIRouter()

@router.get("/info/{subdominio}", response_model=TenantResponse)
def get_tenant_info(subdominio: str, db: Session = Depends(get_db)):
    try:
        return tenant_service.obtener_info_tenant(db, subdominio)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.put("/config", response_model=TenantResponse)
def update_tenant_config(config_in: TenantUpdate, db: Session = Depends(get_db), current_admin: User = Depends(deps.get_current_admin)):
    try:
        update_data = config_in.dict(exclude_unset=True) 
        return tenant_service.actualizar_config_tenant(db, current_admin.tenant_id, update_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put("/{tenant_id}", response_model=TenantResponse)
def update_tenant(tenant_id: int, tenant_in: TenantUpdate, db: Session = Depends(get_db), superadmin: User = Depends(deps.get_current_superadmin),):
  update_data = tenant_in.model_dump(exclude_unset=True)

  if "subdominio" in update_data:
    nuevo_sub = update_data["subdominio"].lower().strip()
    existe = (
        db.query(Tenant)
        .filter(
            Tenant.subdominio == nuevo_sub,
            Tenant.id != tenant_id,
        )
        .first()
    )
    if existe:
      raise HTTPException(
          status_code=400, detail="Ese subdominio ya está en uso por otra empresa"
      )
    update_data["subdominio"] = nuevo_sub

  try:
    return tenant_service.actualizar_config_tenant(db, tenant_id, update_data)
  except ValueError as e:
    raise HTTPException(status_code=404, detail=str(e))
    
@router.post("/config/logo")
async def upload_tenant_logo(file: UploadFile = File(...), db: Session = Depends(get_db), current_admin: User = Depends(deps.get_current_admin)):

    file.file.seek(0, 2) 
    file_size = file.file.tell() 
    await file.seek(0) 
    
    if file_size > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="El archivo es demasiado grande. Máximo 5MB.")
    
    header = await file.read(20)
    await file.seek(0) 
    
    is_valid_image = any(header.startswith(magic) for magic in MAGIC_NUMBERS.values())
    
    if not is_valid_image:
        raise HTTPException(status_code=400, detail="Formato de imagen no válido o archivo corrupto. Solo JPG/PNG.")
    
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen (PNG, JPG, etc.)")

    tenant = db.query(Tenant).filter(Tenant.id == current_admin.tenant_id).first()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    try:
        upload_result = cloudinary_service.subir_logo(file, current_admin.tenant_id, tenant.logo_public_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error al subir la imagen a la nube")

    tenant.logo_url = upload_result["logo_url"]
    tenant.logo_public_id = upload_result["logo_public_id"]
    
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    return {
        "message": "Logo actualizado correctamente", 
        "logo_url": tenant.logo_url
    }

@router.get("/", response_model=list[TenantResponse])
def listar_todas_las_empresas(db: Session = Depends(get_db), superadmin: User = Depends(deps.get_current_superadmin)):
  return db.query(Tenant).order_by(Tenant.id.desc()).all()


@router.post("/onboarding", response_model=TenantResponse)
def crear_empresa_con_admin(data: TenantOnboardingCreate, db: Session = Depends(get_db), superadmin: User = Depends(deps.get_current_superadmin)):
  if db.query(Tenant).filter(Tenant.subdominio == data.subdominio).first():
    raise HTTPException(
        status_code=400, detail="Ese subdominio ya está registrado"
    )

  nuevo_tenant = Tenant(
      nombre=data.nombre,
      subdominio=data.subdominio.lower().strip(),
      whatsapp=data.whatsapp,
      color_primario=data.color_primario or branding.COLOR_PRIMARIO,
      is_active=True,
  )
  db.add(nuevo_tenant)
  db.flush()
    
  nuevo_admin = User(
      tenant_id=nuevo_tenant.id,
      username=data.admin_username.strip(),
      hashed_password=get_password_hash(data.admin_password),
      full_name=data.admin_full_name,
      role=UserRole.ADMIN,
      is_active=True,
  )
  db.add(nuevo_admin)

  db.commit()
  db.refresh(nuevo_tenant)
  return nuevo_tenant


@router.patch("/{tenant_id}/estado", response_model=TenantResponse)
def cambiar_estado_empresa(tenant_id: int, activo: bool, db: Session = Depends(get_db), superadmin: User = Depends(deps.get_current_superadmin)):
  tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
  if not tenant:
    raise HTTPException(status_code=404, detail="Empresa no encontrada")

  tenant.is_active = activo

  if not activo:
    usuarios_empresa = db.query(User).filter(User.tenant_id == tenant_id).all()
    for u in usuarios_empresa:
      u.token_version += 1

  db.commit()
  db.refresh(tenant)
  return tenant