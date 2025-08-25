"""Configuration management for the Bible Q&A API."""
import os
from urllib.parse import urlparse
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # API Configuration
    app_name: str = "Bible Q&A API"
    debug: bool = Field(default=False, env="DEBUG")
    
    # Database Configuration (Heroku compatible)
    database_url: str = Field(default=None, env="DATABASE_URL")
    db_name: str = Field(default=None, env="DB_NAME")
    db_user: str = Field(default=None, env="DB_USER")
    db_password: str = Field(default=None, env="DB_PASSWORD")
    db_host: str = Field(default=None, env="DB_HOST")
    db_port: int = Field(default=5432, env="DB_PORT")
    
    # OpenAI Configuration
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-3.5-turbo", env="OPENAI_MODEL")
    
    # CORS Configuration
    allowed_origins_str: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        env="ALLOWED_ORIGINS"
    )
    
    @property
    def allowed_origins(self) -> list[str]:
        """Parse allowed origins from comma-separated string."""
        return [origin.strip() for origin in self.allowed_origins_str.split(",")]
    
    @property
    def db_config(self) -> dict:
        """Get database configuration, preferring DATABASE_URL for Heroku."""
        if self.database_url:
            # Parse Heroku DATABASE_URL
            parsed = urlparse(self.database_url)
            return {
                'dbname': parsed.path[1:],  # Remove leading slash
                'user': parsed.username,
                'password': parsed.password,
                'host': parsed.hostname,
                'port': parsed.port or 5432
            }
        else:
            # Use individual environment variables
            return {
                'dbname': self.db_name,
                'user': self.db_user,
                'password': self.db_password,
                'host': self.db_host,
                'port': self.db_port
            }
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
