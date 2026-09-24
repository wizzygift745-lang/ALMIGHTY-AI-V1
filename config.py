"""ALMIGHTY AI — global configuration.

Everything is overridable via environment variables so the same codebase can
run in a dev sandbox, on a GPU server, or in a container fleet.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("ALMIGHTY_DATA_DIR", BASE_DIR / "data"))
GENERATIONS_DIR = DATA_DIR / "generations"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "almighty.db"
SECRET_PATH = DATA_DIR / "secret.key"

# Platform owner. This account is seeded on first boot with the OWNER role.
# The password is generated server-side on first boot (or taken from the
# ADMIN_PASSWORD env var) and is NEVER shipped in frontend code.
ADMIN_EMAIL = os.environ.get("ALMIGHTY_ADMIN_EMAIL", "amulukugodswill11@gmail.com")

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))

APP_NAME = "ALMIGHTY AI"
APP_TAGLINE = "Independent AI. Infinite creation."
APP_VERSION = "0.1.0-mvp"

# Generation safety rails (MVP caps — raised as inference infra matures)
MAX_IMAGE_SIDE = 1280
VIDEO_FPS = 24
MAX_VIDEO_SECONDS = 8
STORY_FPS = 12
MAX_STORY_SECONDS = 30
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Job cost table (credits)
COSTS = {
    "image": 2,
    "anime": 2,
    "upscale": 1,
    "2d": 6,
    "video": 8,
    "story": 15,
}


def ensure_dirs() -> None:
    for d in (DATA_DIR, GENERATIONS_DIR, UPLOADS_DIR):
        d.mkdir(parents=True, exist_ok=True)
