from dotenv import load_dotenv

load_dotenv()

from pydantic import ValidationError as PydanticValidationError
from pydantic_settings import BaseSettings

from agent.src.exceptions import ConfigError
from agent.src.utils.logging import setup_logging


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    GEMINI_API_KEY: str
    GOOGLE_PLACES_API_KEY: str
    GEMINI_MODEL_PRO: str = "gemini-2.5-pro"
    GEMINI_MODEL_FLASH: str = "gemini-2.5-flash"
    SENDER_NAME: str = "Enrique"
    SENDER_TITLE: str = "CTO, Helios Marketing"
    LOG_LEVEL: str = "INFO"

    # AgentMail
    AGENTMAIL_API_KEY: str
    AGENTMAIL_INBOX_USERNAME: str = "outreach"
    AGENTMAIL_INBOX_DOMAIN: str | None = None

    # FastAPI / Auth
    DASHBOARD_PASSWORD: str
    JWT_SECRET: str
    JWT_EXPIRY_DAYS: int = 30
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Firecrawl fallback (optional; empty disables JS-render fallback)
    FIRECRAWL_API_KEY: str | None = None

    # Calendly webhook signing secret (optional in dev; required in prod)
    CALENDLY_WEBHOOK_SECRET: str | None = None

    # Runtime environment. "prod" enables strict checks:
    # - Calendly webhook signature required
    # - Startup fails if CALENDLY_WEBHOOK_SECRET unset
    APP_ENV: str = "dev"

    # System-wide daily send ceiling across all campaigns.
    # Backstops an autonomous campaign with a bad target/uncapped total.
    HERMES_MAX_DAILY_SENDS: int = 200

    # Unipile (LinkedIn channel). DSN is the per-account host issued by
    # Unipile (e.g. "api3.unipile.com:13344"). Account ID is the LinkedIn
    # account connected through Unipile's hosted-auth flow.
    UNIPILE_API_KEY: str | None = None
    UNIPILE_DSN: str | None = None
    UNIPILE_ACCOUNT_ID: str | None = None

    # LinkedIn cadence + caps. Days until an unanswered email triggers a
    # LinkedIn follow-up; default 4 (long enough that a slow email replier
    # has had a real chance, short enough that the touch still feels related).
    LINKEDIN_FOLLOWUP_DAYS: int = 4
    # Account-safety ceilings. LinkedIn's weekly invite limit is ~100; a
    # daily 50 keeps us comfortably under and leaves room for DMs.
    LINKEDIN_MAX_DAILY_SENDS: int = 50
    LINKEDIN_DRAFT_PER_TICK: int = 5
    LINKEDIN_SEND_PER_TICK: int = 5


try:
    settings = Settings()
except PydanticValidationError as e:
    missing = [str(err["loc"][0]) for err in e.errors() if err["type"] == "missing"]
    if missing:
        raise ConfigError(
            f"Missing required environment variables: {', '.join(missing)}"
        ) from e
    raise ConfigError(f"Configuration error: {e}") from e

if settings.APP_ENV == "prod" and not settings.CALENDLY_WEBHOOK_SECRET:
    raise ConfigError(
        "APP_ENV=prod requires CALENDLY_WEBHOOK_SECRET to be set. "
        "Copy the signing key from your Calendly webhook subscription."
    )

setup_logging(settings.LOG_LEVEL)
