from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Values that appear in examples and must never sign real tokens.
PLACEHOLDER_SECRETS = {"change-me", "changeme", "secret", "your-secret-key", "please-change-me"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    app_env: str = "development"
    secret_key: str
    access_token_expire_minutes: int = 60
    # Comma separated browser origins allowed to call the API; "*" allows any.
    cors_origins: str = "*"

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, value: str) -> str:
        # Hosts such as Railway hand out postgres:// or postgresql:// URLs; the app talks through asyncpg.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                value = "postgresql+asyncpg://" + value[len(prefix):]
        # asyncpg spells libpq's sslmode as ssl.
        return value.replace("sslmode=", "ssl=")

    @field_validator("secret_key")
    @classmethod
    def _strong_secret(cls, value: str) -> str:
        # Anyone who knows the key can sign an ADMIN token, so a guessable one is refused outright.
        if value.strip().lower() in PLACEHOLDER_SECRETS or len(value) < 32:
            raise ValueError("SECRET_KEY must be at least 32 random characters (not a placeholder). "
                             "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\"")
        return value

    genai_provider: str = "anthropic"
    genai_api_key: str = ""
    genai_model: str = ""
    # Providers tried, in order, when the primary one fails. Comma separated;
    # empty means the fallback_chain in config/generation.yaml; "none" disables.
    genai_fallback_providers: str = ""
    # Keys for the OpenAI-compatible fallback providers.
    gemini_api_key: str = ""
    gemini_model: str = ""
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    # Local Ollama (docker compose service "ollama"). Ollama itself needs no key;
    # OLLAMA_API_KEY is only sent when it sits behind a proxy that requires one.
    ollama_base_url: str = ""
    ollama_model: str = ""
    ollama_api_key: str = ""

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_upload_mb: int = 25

@lru_cache
def get_settings() -> Settings:
    return Settings()