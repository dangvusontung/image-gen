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
ARK_API_KEY = os.getenv("ARK_API_KEY", "").strip()
ARK_API_BASE = os.getenv("ARK_API_BASE", "https://ark.ap-southeast.bytepluses.com/api/v3").rstrip("/")
# ModelArk does not publish per-image prices; set this to bring its jobs under the spend cap.
ARK_PRICE_PER_IMAGE_USD = float(os.getenv("ARK_PRICE_PER_IMAGE_USD", "0"))
ARK_WATERMARK = os.getenv("ARK_WATERMARK", "0") == "1"
# Control-plane (ListModelActivations) credentials: a signed AccessKey/SecretKey pair, separate
# from the Bearer inference key. Without them the adapter falls back to its built-in model list.
ARK_ACCESS_KEY = os.getenv("ARK_ACCESS_KEY", "").strip()
ARK_SECRET_KEY = os.getenv("ARK_SECRET_KEY", "").strip()
ARK_REGION = os.getenv("ARK_REGION", "ap-southeast-1").strip()
ARK_CONTROL_HOST = os.getenv("ARK_CONTROL_HOST", f"ark.{ARK_REGION}.byteplusapi.com").strip()
# Chat model used for concept proposals. Empty means "discover one from the account's catalogue".
ARK_TEXT_MODEL = os.getenv("ARK_TEXT_MODEL", "").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
OPENAI_IMAGE_QUALITY = os.getenv("OPENAI_IMAGE_QUALITY", "high").strip()
# GPT Image is priced per token and varies by quality, so the price is configured, not shipped.
OPENAI_PRICE_PER_IMAGE_USD = float(os.getenv("OPENAI_PRICE_PER_IMAGE_USD", "0"))

JOBS_AUTOSTART = os.getenv("JOBS_AUTOSTART", "1") == "1"
JOB_CONCURRENCY = int(os.getenv("JOB_CONCURRENCY", "3"))
JOB_MAX_ATTEMPTS = int(os.getenv("JOB_MAX_ATTEMPTS", "3"))
JOB_BACKOFF_BASE_SECONDS = float(os.getenv("JOB_BACKOFF_BASE_SECONDS", "2"))
JOB_POLL_INTERVAL_SECONDS = float(os.getenv("JOB_POLL_INTERVAL_SECONDS", "1"))
JOB_POLL_TIMEOUT_SECONDS = float(os.getenv("JOB_POLL_TIMEOUT_SECONDS", "600"))
JOB_TICK_SECONDS = float(os.getenv("JOB_TICK_SECONDS", "1"))
SPEND_LIMIT_USD_PER_DAY = float(os.getenv("SPEND_LIMIT_USD_PER_DAY", "0"))

SECRET_VALUES = tuple(v for v in (GEMINI_API_KEY, BFL_API_KEY, ARK_API_KEY, ARK_SECRET_KEY, OPENAI_API_KEY) if v)
