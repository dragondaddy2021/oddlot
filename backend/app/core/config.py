from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Locate .env at the project root regardless of the working directory.
# config.py lives at backend/app/core/config.py  →  parents[3] == project root
_ENV_FILE = Path(__file__).parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # Anthropic
    anthropic_api_key: str

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Upstash Redis
    upstash_redis_url: str
    upstash_redis_token: str

    # Auth — JWT is verified via Supabase JWKS (public key), no shared secret needed
    internal_cron_secret: str

    # FinMind
    finmind_api_token: str

    # CORS — comma-separated list of allowed origins
    allowed_origins: str

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
