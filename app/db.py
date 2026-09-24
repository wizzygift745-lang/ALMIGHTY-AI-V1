"""ALMIGHTY AI — SQLite persistence layer.

SQLite keeps the MVP dependency-free and portable; the schema is intentionally
normalized so it can be migrated to Postgres when the platform scales
(see ARCHITECTURE.md → Scalability).
"""
import datetime
import json
import secrets
import sqlite3
import threading

from . import config
from .security import hash_password

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',          -- user | admin | owner
  credits INTEGER NOT NULL DEFAULT 0,         -- -1 means unlimited
  last_grant TEXT NOT NULL DEFAULT '',
  banned INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  project_id INTEGER,
  kind TEXT NOT NULL,                          -- image|video|anime|2d|story|upscale
  model_id TEXT NOT NULL,
  prompt TEXT NOT NULL DEFAULT '',
  params TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'queued',       -- queued|running|done|failed
  step TEXT NOT NULL DEFAULT 'queued',
  progress INTEGER NOT NULL DEFAULT 0,
  file_path TEXT NOT NULL DEFAULT '',
  media_type TEXT NOT NULL DEFAULT '',
  eval_json TEXT NOT NULL DEFAULT '',
  cost INTEGER NOT NULL DEFAULT 0,
  error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  finished_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS characters (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  character_code TEXT UNIQUE NOT NULL,         -- CHARACTER ID e.g. CHR-A1B2C3
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  traits TEXT NOT NULL DEFAULT '{}',           -- identity: palette, hair, outfit...
  seed INTEGER NOT NULL DEFAULT 0,             -- locked seed => consistency
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS uploads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  path TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS models (
  id TEXT PRIMARY KEY,                         -- e.g. almighty-image
  family TEXT NOT NULL,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  architecture TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'development',  -- online|development|planned|offline
  capabilities TEXT NOT NULL DEFAULT '[]',
  max_resolution TEXT NOT NULL DEFAULT '',
  max_duration TEXT NOT NULL DEFAULT '',
  vram_gb REAL NOT NULL DEFAULT 0,
  config TEXT NOT NULL DEFAULT '{}',
  safety TEXT NOT NULL DEFAULT 'strict'
);
CREATE TABLE IF NOT EXISTS model_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_id TEXT NOT NULL,
  version TEXT NOT NULL,
  status TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS datasets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  source TEXT NOT NULL,
  license TEXT NOT NULL,
  quality_score REAL NOT NULL DEFAULT 0,
  safety_status TEXT NOT NULL DEFAULT 'pending',  -- pending|cleared|restricted
  training_eligible INTEGER NOT NULL DEFAULT 0,
  size TEXT NOT NULL DEFAULT '0 items'
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  level TEXT NOT NULL,
  actor TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT ''
);
"""

DEFAULT_SETTINGS = {
    "daily_free_credits": "30",
    "quality_threshold": "55",
    "safety_filter": "on",
    "allow_external_providers": "off",   # temporary provider layer OFF by default
    "maintenance_mode": "off",
}

SEED_MODELS = [
    # id, family, name, version, architecture, status, capabilities, max_res, max_dur, vram, config, safety
    ("almighty-image", "IMAGE", "ALMIGHTY IMAGE", "0.1.0-dev",
     "latent-diffusion (local dev engine)", "online",
     json.dumps(["text-to-image", "image-to-image", "inpainting", "outpainting",
                 "character-consistency", "style-control"]),
     "1280x1280", "n/a", 10.0,
     json.dumps({"default_steps": 28, "default_guidance": 7.0}), "strict"),
    ("almighty-video", "VIDEO", "ALMIGHTY VIDEO", "0.1.0-dev",
     "temporal-latent (local dev engine)", "online",
     json.dumps(["text-to-video", "image-to-video", "camera-control", "motion-control"]),
     "640x640", "8s", 18.0,
     json.dumps({"fps": 24, "max_seconds": 8}), "strict"),
    ("almighty-anime", "ANIME", "ALMIGHTY ANIME", "0.1.0-dev",
     "anime-tuned latent (local dev engine)", "online",
     json.dumps(["anime-images", "anime-video", "character-consistency", "manga"]),
     "1280x1280", "8s", 12.0,
     json.dumps({"cel_shading": True}), "strict"),
    ("almighty-2d", "2D", "ALMIGHTY 2D", "0.1.0-dev",
     "parametric-rig animator (local dev engine)", "online",
     json.dumps(["walk-cycles", "actions", "expressions", "dialogue", "camera-moves"]),
     "640x640", "6s", 4.0,
     json.dumps({"rig": "almighty-rig-v1"}), "strict"),
    ("almighty-motion", "MOTION", "ALMIGHTY MOTION", "0.0.1",
     "motion-prior transformer", "planned",
     json.dumps(["pose-control", "motion-transfer", "camera-paths"]),
     "n/a", "n/a", 16.0, json.dumps({}), "strict"),
    ("almighty-upscale", "UPSCALE", "ALMIGHTY UPSCALE", "0.1.0-dev",
     "super-resolution (local dev engine)", "online",
     json.dumps(["image-upscale", "detail-enhance", "frame-interpolation (roadmap)"]),
     "4096x4096", "n/a", 8.0, json.dumps({"max_scale": 4}), "strict"),
    ("almighty-story", "STORY", "ALMIGHTY STORY", "0.1.0-dev",
     "story-planner + scene compositor (local dev engine)", "online",
     json.dumps(["storyboard", "scene-planning", "story-to-video", "captions"]),
     "640x360", "30s", 12.0, json.dumps({}), "strict"),
]

SEED_DATASETS = [
    ("almighty-images-core", "0.1.0", "curated public-domain + licensed", "rights-verified only",
     0.0, "pending", 0, "0 items"),
    ("almighty-anime-refs", "0.1.0", "licensed anime-style references", "license required before use",
     0.0, "pending", 0, "0 items"),
    ("almighty-motion-capture", "0.1.0", "internal capture sessions", "owned",
     0.0, "pending", 0, "0 items"),
]


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
        return _conn


def q(sql: str, args: tuple = ()) -> list[dict]:
    with _lock:
        cur = conn().execute(sql, args)
        return [dict(r) for r in cur.fetchall()]


def q1(sql: str, args: tuple = ()) -> dict | None:
    rows = q(sql, args)
    return rows[0] if rows else None


def execute(sql: str, args: tuple = ()) -> int:
    with _lock:
        c = conn()
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid or 0


def log(level: str, action: str, actor: str = "system", detail: str = "") -> None:
    try:
        execute("INSERT INTO logs (ts, level, actor, action, detail) VALUES (?,?,?,?,?)",
                (now(), level, actor, action, detail[:2000]))
    except Exception:
        pass


def setting(key: str, default: str = "") -> str:
    row = q1("SELECT value FROM settings WHERE key=?", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    execute("INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def init_db() -> str | None:
    """Create schema + seeds. Returns the generated owner password, if created."""
    config.ensure_dirs()
    with _lock:
        conn().executescript(SCHEMA)
        conn().commit()

    # settings
    for k, v in DEFAULT_SETTINGS.items():
        if not q1("SELECT key FROM settings WHERE key=?", (k,)):
            set_setting(k, v)

    # model registry
    for m in SEED_MODELS:
        if not q1("SELECT id FROM models WHERE id=?", (m[0],)):
            execute("INSERT INTO models (id,family,name,version,architecture,status,capabilities,"
                    "max_resolution,max_duration,vram_gb,config,safety) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", m)
            execute("INSERT INTO model_versions (model_id,version,status,notes,created_at) VALUES (?,?,?,?,?)",
                    (m[0], m[3], "initial", "seeded at platform bootstrap", now()))

    # datasets
    if not q("SELECT id FROM datasets LIMIT 1"):
        for d in SEED_DATASETS:
            execute("INSERT INTO datasets (name,version,source,license,quality_score,"
                    "safety_status,training_eligible,size) VALUES (?,?,?,?,?,?,?,?)", d)

    # owner account
    admin_password = None
    if not q1("SELECT id FROM users WHERE email=?", (config.ADMIN_EMAIL,)):
        import os
        admin_password = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(12)
        execute("INSERT INTO users (email,name,password_hash,role,credits,created_at) VALUES (?,?,?,?,?,?)",
                (config.ADMIN_EMAIL, "Godswill (Owner)", hash_password(admin_password), "owner", -1, now()))
        try:
            p = config.DATA_DIR / "initial_admin_password.txt"
            p.write_text(admin_password, encoding="utf-8")
            p.chmod(0o600)
        except Exception:
            pass
        log("info", "owner-account-created", "bootstrap",
            f"Owner account seeded for {config.ADMIN_EMAIL}")
    log("info", "platform-boot", "bootstrap", f"ALMIGHTY AI {config.APP_VERSION} started")
    return admin_password
