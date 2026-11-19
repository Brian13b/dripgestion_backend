from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str
    SQLALCHEMY_DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    FIRST_SUPERADMIN_USER: str = "gb_soluciones_digitales"
    # Sin valor por defecto: si no se define, NO se crea el superadmin inicial.
    FIRST_SUPERADMIN_PASSWORD: Optional[str] = None

    CLOUDINARY_CLOUD_NAME: Optional[str] = None
    CLOUDINARY_API_KEY: Optional[str] = None
    CLOUDINARY_API_SECRET: Optional[str] = None

    REDIS_URL: Optional[str] = None

    # Zona horaria del negocio: define qué es "hoy" y dónde cortan el día y el mes
    # en historial, caja y dashboard (la base guarda los instantes en UTC).
    APP_TIMEZONE: str = "America/Argentina/Buenos_Aires"

    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,https://dripgestion.vercel.app"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()