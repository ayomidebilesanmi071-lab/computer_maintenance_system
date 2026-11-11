"""Application configuration for CMIMS.

All secrets and environment-specific settings are read from environment
variables (or a local ``.env`` file loaded by python-dotenv in ``app.py``).
Never hard-code production secrets in source code.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _as_bool(value, default=False):
    """Convert an environment variable into a boolean."""
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Base configuration - suitable for local development."""

    # --- Core Flask ------------------------------------------------------
    # In production ALWAYS set SECRET_KEY through the environment.
    SECRET_KEY = os.environ.get("SECRET_KEY") or "cmims-dev-secret-change-me"

    # The application factory fills this in with
    # <instance>/computer_maintenance.db when the environment does not supply
    # a DATABASE_URL.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or ""
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Secure sessions --------------------------------------------------
    SESSION_COOKIE_HTTPONLY = True       # JavaScript cannot read the session cookie
    SESSION_COOKIE_SAMESITE = "Lax"      # mitigates CSRF from cross-site requests
    SESSION_COOKIE_SECURE = _as_bool(os.environ.get("SESSION_COOKIE_SECURE"))
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

    # --- CSRF protection ---------------------------------------------------
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600           # CSRF tokens expire after 1 hour

    # --- Uploads (optional attachment feature) -------------------------------
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB maximum request/upload size
    ALLOWED_ATTACHMENT_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf", "txt"}
    UPLOAD_FOLDER = str(BASE_DIR / "instance" / "uploads")

    # --- Pagination ---------------------------------------------------------
    PER_PAGE = 15

    # Re-read Jinja templates when they change.  Handy while developing and
    # overridden to False by ProductionConfig.  This never enables the debug
    # server or the Werkzeug debugger.
    TEMPLATES_AUTO_RELOAD = True

    # --- Environment --------------------------------------------------------
    ENV = os.environ.get("FLASK_ENV", "development")
    DEBUG = _as_bool(os.environ.get("FLASK_DEBUG"))


class TestingConfig(Config):
    """Configuration used by the automated test-suite.

    CSRF is disabled so tests can post forms directly; every other security
    control (authentication, authorization, validation) stays active.
    """

    TESTING = True
    WTF_CSRF_ENABLED = False
    WTF_CSRF_TIME_LIMIT = None
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SECRET_KEY = "test-secret-key"


class ProductionConfig(Config):
    """Hardened configuration for a real deployment."""

    ENV = "production"
    DEBUG = False
    TEMPLATES_AUTO_RELOAD = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
