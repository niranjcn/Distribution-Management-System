from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
import os
from urllib.parse import urlsplit
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Distribution Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    
    # Server
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = 8080
    
    # Database - MySQL
    DB_HOST: str = os.getenv("DB_HOST", "mysql")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "dms_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "dms_password")
    DB_NAME: str = os.getenv("DB_NAME", "distribution_management_system")

    # Activity log retention
    ACTIVITY_LOG_RETENTION_DAYS: int = int(os.getenv("ACTIVITY_LOG_RETENTION_DAYS", "90"))

    # Database backup
    DB_BACKUP_TIME: str = os.getenv("DB_BACKUP_TIME", "02:00")
    RCLONE_REMOTE: str = os.getenv("RCLONE_REMOTE", "DMS")
    RCLONE_DEST_DIR: str = os.getenv("DMS_RCLONE_DEST_DIR", "dms-db-backups")
    RCLONE_VAULT_DIR: str = os.getenv("DMS_RCLONE_VAULT_DIR", "Backup Document Vault")
    RCLONE_CONFIG_SEED: str = os.getenv("RCLONE_CONFIG_SEED", "/app/rclone/rclone.conf")
    RCLONE_CONFIG: str = os.getenv("RCLONE_CONFIG", "/tmp/rclone.conf")
    
    # Security
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CSRF_COOKIE_NAME: str = "csrftoken"
    CSRF_COOKIE_SECURE: bool = os.getenv(
        "CSRF_COOKIE_SECURE",
        "true" if os.getenv("ENVIRONMENT", "production").lower() == "production" else "false",
    ).lower() == "true"
    ENFORCE_HTTPS: bool = os.getenv("ENFORCE_HTTPS", "false").lower() == "true"
    
    # CORS
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://0.0.0.0:5173,"
        "http://localhost:3002,http://127.0.0.1:3002,http://0.0.0.0:3002"
    )
    CORS_ORIGIN_REGEX: str = r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?$"
    
    # API
    API_V1_PREFIX: str = "/api"
    
    @property
    def cors_origins_list(self) -> List[str]:
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        expanded: List[str] = []

        for origin in origins:
            expanded.append(origin)
            parsed = urlsplit(origin)
            if not parsed.scheme or not parsed.netloc:
                continue

            host = parsed.hostname
            port = parsed.port
            if host not in {"localhost", "127.0.0.1", "0.0.0.0"}:
                continue

            peer_hosts = {"localhost", "127.0.0.1", "0.0.0.0"} - {host}
            for peer in peer_hosts:
                if port is not None:
                    expanded.append(f"{parsed.scheme}://{peer}:{port}")
                else:
                    expanded.append(f"{parsed.scheme}://{peer}")

        # Keep insertion order while removing duplicates.
        return list(dict.fromkeys(expanded))

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "SECRET_KEY is required. Set it in your .env file. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
        if len(value) < 32 or "dms" in value.lower():
            raise ValueError(
                "SECRET_KEY must be at least 32 characters and must not contain default patterns. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
        return value
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
