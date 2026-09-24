"""Admin API — owner/admin only. Every endpoint is guarded server-side via
require_admin(); the frontend merely hides the section from non-admins."""
import os
import shutil

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from . import config, db
from .security import get_current_user, require_admin

router = APIRouter()

SETTING_KEYS = {"daily_free_credits", "quality_threshold", "safety_filter",
                "allow_external_providers", "maintenance_mode"}


def _admin(request: Request) -> dict:
    user = get_current_user(request)
    require_admin(user)
    return user


@router.get("/overview")
def overview(request: Request):
    admin = _admin(request)
    users = db.q1("SELECT COUNT(*) n FROM users")["n"]
    jobs_total = db.q1("SELECT COUNT(*) n FROM jobs")["n"]
    jobs_today = db.q1("SELECT COUNT(*) n FROM jobs WHERE created_at >= date('now')")["n"]
    credits_issued = db.q1("SELECT COALESCE(SUM(CASE WHEN credits>0 THEN credits ELSE 0 END),0) s"
                           " FROM users")["s"]
    storage = sum(f.stat().st_size for f in config.GENERATIONS_DIR.iterdir() if f.is_file())
    try:
        load1, load5, load15 = os.getloadavg()
    except OSError:
        load1 = load5 = load15 = 0.0
    mem = {}
    try:
        for line in open("/proc/meminfo"):
            k, v = line.split(":", 1)
            mem[k] = int(v.strip().split()[0])  # kB
    except OSError:
        pass
    disk = shutil.disk_usage(config.DATA_DIR)
    return {
        "counts": {"users": users, "jobs_total": jobs_total, "jobs_today": jobs_today,
                   "characters": db.q1("SELECT COUNT(*) n FROM characters")["n"],
                   "projects": db.q1("SELECT COUNT(*) n FROM projects")["n"]},
        "credits_issued": credits_issued,
        "storage_bytes": storage,
        "system": {
            "cpu_load": [round(load1, 2), round(load5, 2), round(load15, 2)],
            "memory_total_mb": round(mem.get("MemTotal", 0) / 1024),
            "memory_used_mb": round((mem.get("MemTotal", 0) - mem.get("MemAvailable", 0)) / 1024),
            "disk_free_gb": round(disk.free / 1e9, 1),
            "gpu": ("No GPU attached — the MVP dev engines are CPU-efficient placeholders. "
                    "Phase 3 attaches ALMIGHTY inference GPUs behind this same dashboard."),
        },
        "settings": {k: db.setting(k) for k in sorted(SETTING_KEYS)},
        "app": {"name": config.APP_NAME, "version": config.APP_VERSION},
    }


@router.get("/users")
def users(request: Request, q: str = ""):
    _admin(request)
    sql = "SELECT id,email,name,role,credits,banned,created_at FROM users"
    args: tuple = ()
    if q:
        sql += " WHERE email LIKE ? OR name LIKE ?"
        args = (f"%{q}%", f"%{q}%")
    return db.q(sql + " ORDER BY id", args)


class UserAction(BaseModel):
    action: str            # add_credits | set_credits | set_role | ban | unban
    value: str | int | None = None


@router.post("/users/{uid}")
def user_action(uid: int, body: UserAction, request: Request):
    admin = _admin(request)
    target = db.q1("SELECT * FROM users WHERE id=?", (uid,))
    if not target:
        raise HTTPException(404, "User not found")
    if target["role"] == "owner" and target["email"] != admin["email"]:
        raise HTTPException(403, "The owner account cannot be modified")
    if body.action == "add_credits":
        db.execute("UPDATE users SET credits=credits+? WHERE id=?", (int(body.value or 0), uid))
    elif body.action == "set_credits":
        db.execute("UPDATE users SET credits=? WHERE id=?", (int(body.value or 0), uid))
    elif body.action == "set_role":
        if body.value not in ("user", "admin"):
            raise HTTPException(400, "Role must be user|admin (owner is fixed)")
        db.execute("UPDATE users SET role=? WHERE id=?", (body.value, uid))
    elif body.action == "ban":
        db.execute("UPDATE users SET banned=1 WHERE id=?", (uid,))
    elif body.action == "unban":
        db.execute("UPDATE users SET banned=0 WHERE id=?", (uid,))
    else:
        raise HTTPException(400, "Unknown action")
    db.log("warn", f"admin:{body.action}", admin["email"], f"target user {uid} value={body.value}")
    return {"ok": True}


@router.get("/models")
def models(request: Request):
    _admin(request)
    return db.q("SELECT * FROM models ORDER BY family")


class ModelStatus(BaseModel):
    status: str


@router.post("/models/{model_id}/status")
def model_status(model_id: str, body: ModelStatus, request: Request):
    admin = _admin(request)
    if body.status not in ("online", "development", "planned", "offline"):
        raise HTTPException(400, "Invalid status")
    if not db.q1("SELECT id FROM models WHERE id=?", (model_id,)):
        raise HTTPException(404, "Model not found")
    db.execute("UPDATE models SET status=? WHERE id=?", (body.status, model_id))
    version = db.q1("SELECT version FROM models WHERE id=?", (model_id,))["version"]
    db.execute("INSERT INTO model_versions (model_id,version,status,notes,created_at) VALUES (?,?,?,?,?)",
               (model_id, version, body.status, f"status changed by {admin['email']}", db.now()))
    db.log("warn", "model-status-changed", admin["email"], f"{model_id} -> {body.status}")
    return {"ok": True}


@router.get("/model_versions")
def model_versions(request: Request, model_id: str = ""):
    _admin(request)
    if model_id:
        return db.q("SELECT * FROM model_versions WHERE model_id=? ORDER BY id DESC", (model_id,))
    return db.q("SELECT * FROM model_versions ORDER BY id DESC LIMIT 100")


@router.get("/datasets")
def datasets(request: Request):
    _admin(request)
    return db.q("SELECT * FROM datasets ORDER BY id")


class DatasetIn(BaseModel):
    name: str
    version: str = "0.1.0"
    source: str = ""
    license: str = "rights-verified only"


@router.post("/datasets")
def add_dataset(body: DatasetIn, request: Request):
    admin = _admin(request)
    did = db.execute("INSERT INTO datasets (name,version,source,license) VALUES (?,?,?,?)",
                     (body.name.strip(), body.version.strip(), body.source.strip(),
                      body.license.strip()))
    db.log("info", "dataset-registered", admin["email"], body.name)
    return {"id": did}


class DatasetStatus(BaseModel):
    safety_status: str | None = None
    training_eligible: int | None = None
    quality_score: float | None = None


@router.post("/datasets/{did}/review")
def review_dataset(did: int, body: DatasetStatus, request: Request):
    admin = _admin(request)
    if body.safety_status and body.safety_status not in ("pending", "cleared", "restricted"):
        raise HTTPException(400, "Invalid safety status")
    if body.safety_status:
        db.execute("UPDATE datasets SET safety_status=? WHERE id=?", (body.safety_status, did))
    if body.training_eligible is not None:
        db.execute("UPDATE datasets SET training_eligible=? WHERE id=?",
                   (1 if body.training_eligible else 0, did))
    if body.quality_score is not None:
        db.execute("UPDATE datasets SET quality_score=? WHERE id=?", (body.quality_score, did))
    db.log("info", "dataset-reviewed", admin["email"], f"dataset {did}")
    return {"ok": True}


@router.get("/jobs")
def all_jobs(request: Request, limit: int = 50):
    _admin(request)
    return db.q("SELECT j.*, u.email FROM jobs j LEFT JOIN users u ON u.id=j.user_id "
                "ORDER BY j.id DESC LIMIT ?", (max(1, min(limit, 200)),))


@router.get("/logs")
def logs(request: Request, limit: int = 100):
    _admin(request)
    return db.q("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (max(1, min(limit, 500)),))


@router.get("/settings")
def get_settings(request: Request):
    _admin(request)
    return {k: db.setting(k) for k in sorted(SETTING_KEYS)}


class SettingsIn(BaseModel):
    values: dict


@router.post("/settings")
def save_settings(body: SettingsIn, request: Request):
    admin = _admin(request)
    for k, v in body.values.items():
        if k not in SETTING_KEYS:
            continue
        db.set_setting(k, str(v).strip()[:100])
        db.log("warn", "setting-changed", admin["email"], f"{k}={v}")
    return {"ok": True}


@router.get("/analytics")
def analytics(request: Request):
    _admin(request)
    by_day = db.q("SELECT date(created_at) d, COUNT(*) n FROM jobs "
                  "GROUP BY d ORDER BY d DESC LIMIT 14")
    by_kind = db.q("SELECT kind, COUNT(*) n FROM jobs GROUP BY kind ORDER BY n DESC")
    users_day = db.q("SELECT date(created_at) d, COUNT(*) n FROM users "
                     "GROUP BY d ORDER BY d DESC LIMIT 14")
    return {"jobs_by_day": list(reversed(by_day)), "jobs_by_kind": by_kind,
            "users_by_day": list(reversed(users_day))}
