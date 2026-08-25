"""
Central config. Everything sensitive comes from environment variables.
Never hard-code secrets here or anywhere else in this project.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str, allow_empty_in_ci: bool = False) -> str:
    val = os.environ.get(name, "")
    if not val and not allow_empty_in_ci:
        # Don't crash on import for local tooling / linting; callers that
        # actually need the value will get a clear error when they use it.
        pass
    return val


# --- LLM ---
ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

# --- Threads (Meta Graph API) ---
THREADS_ACCESS_TOKEN = _require("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = _require("THREADS_USER_ID")
THREADS_API_BASE = os.environ.get("THREADS_API_BASE", "https://graph.threads.net/v1.0")

# --- Typeform (property requirement form) ---
TYPEFORM_URL = os.environ.get("TYPEFORM_URL", "https://form.typeform.com/to/TJfuvi6E")

# --- Email (approval workflow) ---
EMAIL_SMTP_HOST = os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
EMAIL_USER = _require("EMAIL_USER")
EMAIL_PASSWORD = _require("EMAIL_PASSWORD")
EMAIL_FROM = os.environ.get("EMAIL_FROM", EMAIL_USER)
EMAIL_TO = _require("EMAIL_TO")  # Riyandi's inbox

# --- Approval webhook ---
APPROVAL_SECRET = _require("APPROVAL_SECRET")  # used to sign approval tokens
APPROVAL_BASE_URL = os.environ.get("APPROVAL_BASE_URL", "http://localhost:8080")

# --- Storage ---
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "data", "hoz_agent.db"))

# --- Behaviour ---
WIB_POST_HOUR = int(os.environ.get("WIB_POST_HOUR", "9"))  # 09:00 WIB
NUM_CONCEPTS_MIN = 6
NUM_CONCEPTS_MAX = 8
NUM_SELECTED = 4
APPROVAL_TOKEN_TTL_HOURS = int(os.environ.get("APPROVAL_TOKEN_TTL_HOURS", "72"))
