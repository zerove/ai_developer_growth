from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "AI Developer Growth"
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    docs_path: str = "../../../docs"
    knowledge_index_path: str = (
        "../../../examples/ai-navigation/data/knowledge_index.json"
    )

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
