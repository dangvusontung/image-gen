import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", REPO_ROOT / "data"))
ASSETS_DIR = Path(os.getenv("ASSETS_DIR", DATA_DIR / "assets"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'image_gen.db'}")
UPLOAD_MAX_SIZE = int(os.getenv("UPLOAD_MAX_SIZE", 20 * 1024 * 1024))
GENERATED_MAX_SIZE = int(os.getenv("GENERATED_MAX_SIZE", 60 * 1024 * 1024))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_API_BASE = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
BFL_API_KEY = os.getenv("BFL_API_KEY", "").strip()
BFL_API_BASE = os.getenv("BFL_API_BASE", "https://api.bfl.ai").rstrip("/")
# FLUX.2 docs only show URL inputs; inline encoding is configurable until verified with a live key.
BFL_IMAGE_ENCODING = os.getenv("BFL_IMAGE_ENCODING", "base64")  # "base64" | "data_url"

JOBS_AUTOSTART = os.getenv("JOBS_AUTOSTART", "1") == "1"
JOB_CONCURRENCY = int(os.getenv("JOB_CONCURRENCY", "3"))
JOB_MAX_ATTEMPTS = int(os.getenv("JOB_MAX_ATTEMPTS", "3"))
JOB_BACKOFF_BASE_SECONDS = float(os.getenv("JOB_BACKOFF_BASE_SECONDS", "2"))
JOB_POLL_INTERVAL_SECONDS = float(os.getenv("JOB_POLL_INTERVAL_SECONDS", "1"))
JOB_POLL_TIMEOUT_SECONDS = float(os.getenv("JOB_POLL_TIMEOUT_SECONDS", "600"))
JOB_TICK_SECONDS = float(os.getenv("JOB_TICK_SECONDS", "1"))
SPEND_LIMIT_USD_PER_DAY = float(os.getenv("SPEND_LIMIT_USD_PER_DAY", "5"))

SECRET_VALUES = tuple(v for v in (GEMINI_API_KEY, BFL_API_KEY) if v)
