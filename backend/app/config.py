from pydantic_settings import BaseSettings
from typing import List
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Distribution Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    MONGODB_URL: str = os.getenv("MONGODB_URL", "")
    DATABASE_NAME: str = "distribution_management_system"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dms-secret-key-2024")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3002,http://localhost:5173"
    
    # API
    API_V1_PREFIX: str = "/api"
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
