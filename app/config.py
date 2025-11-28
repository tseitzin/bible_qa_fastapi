"""Configuration management for the Bible Q&A API."""
import os
from urllib.parse import urlparse
from functools import lru_cache
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    # API Configuration
    app_name: str = Field(default="Bible Q&A API", env="APP_NAME")
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
    openai_model: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL")
    openai_max_output_tokens: int = Field(default=2000, env="OPENAI_MAX_OUTPUT_TOKENS")
    openai_max_output_tokens_retry: int = Field(default=1500, env="OPENAI_MAX_OUTPUT_TOKENS_RETRY")
    openai_retry_on_truncation: bool = Field(default=True, env="OPENAI_RETRY_ON_TRUNCATION")
    openai_reasoning_effort: str = Field(default="low", env="OPENAI_REASONING_EFFORT")
    openai_request_timeout: int = Field(default=25, env="OPENAI_REQUEST_TIMEOUT")
    openai_max_history_messages: int = Field(default=12, env="OPENAI_MAX_HISTORY_MESSAGES")
    
    # MCP Configuration
    mcp_api_key: str = Field(default="", env="MCP_API_KEY")

    # Authentication Configuration
    secret_key: str = Field(
        default="your-secret-key-change-this-in-production-use-openssl-rand-hex-32",
        env="SECRET_KEY"
    )
    auth_cookie_name: str = Field(default="bible_qa_auth", env="AUTH_COOKIE_NAME")
    auth_cookie_domain: str = Field(default="", env="AUTH_COOKIE_DOMAIN")
    auth_cookie_secure: bool = Field(default=False, env="AUTH_COOKIE_SECURE")
    auth_cookie_samesite: str = Field(default="lax", env="AUTH_COOKIE_SAMESITE")
    auth_cookie_max_age: int = Field(default=60 * 60 * 24 * 7, env="AUTH_COOKIE_MAX_AGE")

    # CSRF Configuration
    csrf_cookie_name: str = Field(default="bible_qa_csrf", env="CSRF_COOKIE_NAME")
    csrf_cookie_secure: bool = Field(default=False, env="CSRF_COOKIE_SECURE")
    csrf_cookie_samesite: str = Field(default="strict", env="CSRF_COOKIE_SAMESITE")
    csrf_cookie_max_age: int = Field(default=60 * 60 * 6, env="CSRF_COOKIE_MAX_AGE")  # 6 hours
    csrf_header_name: str = Field(default="X-CSRF-Token", env="CSRF_HEADER_NAME")
    csrf_protection_enabled: bool = Field(default=True, env="CSRF_PROTECTION_ENABLED")
    
    # CORS Configuration
    @computed_field
    @property
    def allowed_origins(self) -> list[str]:
        """Parse allowed origins from environment variable or use defaults."""
        allowed_origins_str = os.getenv(
            "ALLOWED_ORIGINS",
            "https://www.wordoflifeanswers.com,https://wordoflifeanswers.com,http://localhost:5173,http://localhost:3000"
        )
        origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

        # Automatically add bare/WWW variants when a domain is provided to reduce misconfiguration risk
        normalized = set(origins)
        for origin in list(origins):
            if origin.startswith("https://www."):
                normalized.add(origin.replace("https://www.", "https://", 1))
            elif origin.startswith("https://") and not origin.split("//", 1)[1].startswith("www."):
                host = origin.split("//", 1)[1]
                normalized.add(f"https://www.{host}")

        return sorted(normalized)

    @computed_field
    @property
    def csrf_exempt_paths(self) -> list[str]:
        """List of path prefixes that are exempt from CSRF validation."""
        raw_paths = os.getenv("CSRF_EXEMPT_PATHS", "/api/auth/login,/api/auth/register")
        return [path.strip() for path in raw_paths.split(",") if path.strip()]
    
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
        env_file=None,  # Don't load from .env file
        case_sensitive=False,
        extra="ignore"
    )

def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
