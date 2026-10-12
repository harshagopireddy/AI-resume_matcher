"""Central configuration for AI-resume_matcher."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "resume_matcher.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

# --- Database backend --------------------------------------------------
# "mysql"  -> your device's MySQL server (database resume_matcher1)   DEFAULT
# "sqlite" -> single portable file data/resume_matcher.db
DB_BACKEND = os.environ.get("DB_BACKEND", "mysql").lower()

MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DB = os.environ.get("MYSQL_DB", "resume_matcher1")

# --- Security ----------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-ai-resume-matcher-2026")
SESSION_HOURS = 12
DEFAULT_PASSWORD = "password123"

# --- Matching engine weights (must sum to 1.0) ------------------------
WEIGHTS = {
    "tfidf": 0.35,
    "embedding": 0.25,
    "skill": 0.30,
    "experience": 0.10,
}

USE_EMBEDDINGS = os.environ.get("USE_EMBEDDINGS", "0") == "1"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Email notifications (shortlist / interview invitations) -----------
# Fill these in to send real emails. For Gmail use an "App password".
# When left empty, emails are logged to the console and saved to the
# email_log table so you can still see exactly what was sent.
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")          # e.g. you@gmail.com
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")  # app password
SMTP_FROM = os.environ.get("SMTP_FROM", "")          # defaults to SMTP_USER
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "HireMatch Recruitment")
SMTP_TLS = os.environ.get("SMTP_TLS", "1") == "1"

# Saved-at-runtime overrides (set from the admin UI, takes priority over the
# values above). This file is created automatically when you save settings.
MAIL_SETTINGS_PATH = os.path.join(DATA_DIR, "mail_settings.json")

# --- Uploads -----------------------------------------------------------
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".md", ".csv"}
MAX_CONTENT_LENGTH = 8 * 1024 * 1024   # 8 MB

# Flask
HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "5000"))
DEBUG = os.environ.get("DEBUG", "0") == "1"

# --- Local overrides ---------------------------------------------------
# Optional, git-ignored file with machine-specific secrets (DB password,
# secret key, SMTP credentials). Create `config_local.py` containing
# UPPERCASE name/value pairs. Environment variables still win.
try:
    import config_local as _local
    for _name in dir(_local):
        if _name.isupper():
            globals()[_name] = getattr(_local, _name)
except ImportError:
    pass
