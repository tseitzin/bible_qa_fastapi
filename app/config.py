"""Configuration management for the Bible Q&A API."""
import os
from urllib.parse import urlparse
from functools import lru_cache
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    # API Configuration
    app_name: str = "Bible Q&A API"
    debug: bool = Field(default=False, env="DEBUG")
    
    # Database Configuration (Heroku compatible)
    database_url: str = Field(default="", env="DATABASE_URL")
    db_name: str = Field(default="", env="DB_NAME")
    db_user: str = Field(default="", env="DB_USER")
    db_password: str = Field(default="", env="DB_PASSWORD")
    db_host: str = Field(default="localhost", env="DB_HOST")
    db_port: int = Field(default=5432, env="DB_PORT")
    
    # OpenAI Configuration
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-3.5-turbo", env="OPENAI_MODEL")
    
    # Authentication Configuration
    secret_key: str = Field(
        default="your-secret-key-change-this-in-production-use-openssl-rand-hex-32",
        env="SECRET_KEY"
    )
    
    # CORS Configuration
    allowed_origins_str: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        env="ALLOWED_ORIGINS"
    )
    
    @computed_field
    @property
    def allowed_origins(self) -> list[str]:
        """Parse allowed origins from comma-separated string."""
        return [origin.strip() for origin in self.allowed_origins_str.split(",")]
    
    @property
    def db_config(self) -> dict:
        """Get database configuration, preferring DATABASE_URL for Heroku."""
        if self.database_url and self.database_url.strip():
            # Parse Heroku DATABASE_URL
            parsed = urlparse(self.database_url)
            return {
                'dbname': parsed.path[1:],  # Remove leading slash
                'user': parsed.username,
                'password': parsed.password,
                'host': parsed.hostname,
                'port': parsed.port or 5432
            }
        elif self.db_name.strip() and self.db_user.strip():
            # Use individual environment variables
            return {
                'dbname': self.db_name,
                'user': self.db_user,
                'password': self.db_password,
                'host': self.db_host,
                'port': self.db_port
            }
        else:
            # Fallback configuration for development
            return {
                'dbname': 'bible_qa',
                'user': 'postgres',
                'password': 'postgres',
                'host': 'localhost',
                'port': 5432
            }
    
    model_config = SettingsConfigDict(
        env_file=".env" if not os.getenv("DYNO") else None,  # Skip .env on Heroku
        case_sensitive=False,
        extra="ignore"
    )

def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
