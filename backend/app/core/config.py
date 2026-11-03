"""Application settings loaded from environment variables.

In production (ENVIRONMENT=production) the app will refuse to start
if any required secret is still unset or at a default value.
"""

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REQUIRED_IN_PRODUCTION = (
    "MODEL_API_KEY",
    "SUPABASE_URL",
    "APP_SIGNING_SECRET",
)

# Sentinel to detect "still a placeholder / default" secrets.
_FORBIDDEN_DEFAULTS = {
    "your_model_api_key_here",
    "changeme",
    "secret",
}


class Settings(BaseSettings):
    # ── Meta ─────────────────────────────────────────────────────────────
    PROJECT_NAME: str = "Pathwise AI Backend"
    API_V1_STR: str = ""
    ENVIRONMENT: str = "development"  # "development" | "production"

    # ── LLM ──────────────────────────────────────────────────────────────
    MODEL_API_KEY: str = ""
    META_BASE_URL: str = "https://api.meta.ai/v1"
    META_MODEL: str = "muse-spark-1.3"
    LLM_TIMEOUT_SECONDS: int = 90

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./pathwise.db"

    # ── CORS ─────────────────────────────────────────────────────────────
    # In production set this to your exact Cloudflare origin, e.g.:
    # CORS_ORIGINS=https://app.pathwise.ai
    CORS_ORIGINS: str | list[str] = [
        "https://pathwise-ai.okizmanofficial.workers.dev",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ]

    # ── Auth (Supabase) ──────────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_JWT_AUDIENCE: str = "authenticated"
    SUPABASE_SERVICE_ROLE_KEY: str = ""  # Server-only! Never in frontend or client!
    SUPABASE_STORAGE_BUCKET: str = "tool-assets"
    APP_SIGNING_SECRET: str = ""

    # ── Beta Allowlist ───────────────────────────────────────────────────
    BETA_ALLOWLIST_ENABLED: bool = False
    BETA_ALLOWED_EMAILS: str = ""  # Comma-separated list of emails

    # ── Monitoring & Jobs ─────────────────────────────────────────────────
    SENTRY_DSN: str = ""
    CRON_SECRET: str = ""
    # Number of reverse proxies in front of the app that append to X-Forwarded-For (Render = 1).
    # 0 = ignore X-Forwarded-For and use the direct peer address.
    TRUSTED_PROXY_COUNT: int = 1

    # ── Quota caps (Slice 3) ──────────────────────────────────────────────
    WORKFLOWS_PER_DAY: int = 2
    INTERVIEW_TURNS_PER_DAY: int = 25
    STEP_ACTIONS_PER_DAY: int = 20

    # Step runs (T9)
    RUN_STEPS_PER_DAY: int = 10
    RUN_MAX_PROMPT_CHARS: int = 6000
    RUN_MAX_OUTPUT_TOKENS: int = 2048
    RUN_TIMEOUT_SECONDS: int = 60

    # ─────────────────────────────────────────────────────────────────────

    @property
    def signing_secret(self) -> str:
        if self.APP_SIGNING_SECRET:
            return self.APP_SIGNING_SECRET
        if self.ENVIRONMENT == "production":
            raise ValueError("APP_SIGNING_SECRET is required in production.")
        return "dev-insecure-signing-secret-pathwise-ai"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_database_url(cls, v: str) -> str:
        if not v:
            return v
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        if v.startswith("postgresql://"):
            try:
                import psycopg  # noqa: F401
            except ImportError:
                try:
                    import psycopg2  # noqa: F401
                    v = v.replace("postgresql://", "postgresql+psycopg2://", 1)
                except ImportError:
                    pass
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @model_validator(mode="after")
    def _infer_supabase_url(self) -> "Settings":
        """If SUPABASE_URL is not set but DATABASE_URL points to Supabase, infer SUPABASE_URL."""
        if not self.SUPABASE_URL and self.DATABASE_URL:
            import re
            match = re.search(r"postgres\.([a-z0-9_-]+):", self.DATABASE_URL)
            if not match:
                match = re.search(r"db\.([a-z0-9_-]+)\.supabase\.co", self.DATABASE_URL)
            if match:
                self.SUPABASE_URL = f"https://{match.group(1)}.supabase.co"
        return self

    @model_validator(mode="after")
    def _production_guard(self) -> "Settings":
        """Refuse to start in production if required secrets are missing or placeholder."""
        if self.ENVIRONMENT != "production":
            return self

        errors: list[str] = []

        if not self.DATABASE_URL or self.DATABASE_URL.startswith("sqlite"):
            errors.append("  DATABASE_URL must be a PostgreSQL connection string in production")

        for name in _REQUIRED_IN_PRODUCTION:
            value = getattr(self, name, "")
            if not value:
                errors.append(f"  {name} is not set")
            elif value.lower() in _FORBIDDEN_DEFAULTS:
                errors.append(f"  {name} is still a placeholder value")

        # In production require SUPABASE_URL, APP_SIGNING_SECRET and either SUPABASE_JWT_SECRET or JWKS URL (via SUPABASE_URL)
        if not self.SUPABASE_JWT_SECRET and not self.SUPABASE_URL:
            errors.append("  Either SUPABASE_JWT_SECRET or a valid SUPABASE_URL (for JWKS) is required in production")
        elif self.SUPABASE_JWT_SECRET and self.SUPABASE_JWT_SECRET.lower() in _FORBIDDEN_DEFAULTS:
            errors.append("  SUPABASE_JWT_SECRET is still a placeholder value")

        # In production CORS must not contain localhost / 127.0.0.1
        for origin in self.CORS_ORIGINS:
            if "localhost" in origin or "127.0.0.1" in origin:
                errors.append(
                    f"  CORS_ORIGINS contains a local origin in production: {origin}"
                )

        if errors:
            raise ValueError(
                "Production startup blocked — fix these configuration problems:\n"
                + "\n".join(errors)
            )

        return self

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
