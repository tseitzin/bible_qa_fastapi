"""Configuration management for the Bible Q&A API."""
import os
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # API Configuration
    app_name: str = "Bible Q&A API"
    debug: bool = Field(default=False, env="DEBUG")
    
    # Database Configuration
    db_name: str = Field(..., env="DB_NAME")
    db_user: str = Field(..., env="DB_USER")
    db_password: str = Field(..., env="DB_PASSWORD")
    db_host: str = Field(..., env="DB_HOST")
    db_port: int = Field(default=5432, env="DB_PORT")
    
    # OpenAI Configuration
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-3.5-turbo", env="OPENAI_MODEL")
    
    # CORS Configuration
    allowed_origins: list[str] = Field(
        default=["http://localhost:5173"],
        env="ALLOWED_ORIGINS"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
