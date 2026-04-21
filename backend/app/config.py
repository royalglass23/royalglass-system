"""
config.py
Loads environment variables from .env via pydantic-settings.
All settings are accessed through the `settings` object imported from here.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    postgres_db: str
    postgres_user: str
    postgres_password: str
    db_host: str = "db"          # Docker service name — matches docker-compose.yml
    db_port: int = 5432

    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480   # 8 hours — reasonable for a work day

    # App
    app_env: str = "development"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.db_host}:{self.db_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"          # Ignore extra vars in .env (like N8N settings)


settings = Settings()
