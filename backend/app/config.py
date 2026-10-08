import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", REPO_ROOT / "data"))
ASSETS_DIR = Path(os.getenv("ASSETS_DIR", DATA_DIR / "assets"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'image_gen.db'}")
UPLOAD_MAX_SIZE = int(os.getenv("UPLOAD_MAX_SIZE", 20 * 1024 * 1024))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",")
