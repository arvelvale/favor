import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve .env relative to the application, independently of the launch directory.
# Values supplied by the deployment environment always take precedence.
load_dotenv(Path(__file__).with_name(".env"))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def require_env(name):
    value = os.environ.get(name)
    if not value or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


DEEPSEEK_API_KEY = require_env("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
SECRET_KEY = require_env("SECRET_KEY")
if len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY must contain at least 32 characters")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")
if PAYPAL_MODE not in ("sandbox", "live"):
    raise RuntimeError("PAYPAL_MODE must be sandbox or live")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_ENABLED = bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET)
FEEDBACK_EMAIL = os.getenv("FEEDBACK_EMAIL", "")

HTTP_PROXY = os.getenv("HTTP_PROXY")
HTTPS_PROXY = os.getenv("HTTPS_PROXY")
API_TIMEOUT = 60.0
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "t")
PORT = int(os.getenv("PORT", "5000"))


def get_proxies():
    proxies = {}
    if HTTP_PROXY:
        proxies["http"] = HTTP_PROXY
    if HTTPS_PROXY:
        proxies["https"] = HTTPS_PROXY
    return proxies or None


db_config = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": require_env("DB_USER"),
    "password": require_env("DB_PASSWORD"),
    "database": os.getenv("DB_NAME", "recipe_app"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "charset": "utf8mb4",
    "use_unicode": True,
}
