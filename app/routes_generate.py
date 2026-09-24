"""Generation, jobs, files, characters, projects, uploads."""
import io
import json
import secrets
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from . import config, db, orchestrator
from .security import get_current_user

router = APIRouter()

KINDS = set(config.COSTS)


class GenerateIn(BaseModel):
    kind: str
    prompt: str = ""
    params: dict = {}


def _charge(user: dict, cost: int) -> None:
    if user["role"] in ("admin", "owner") or user["credits"] == -1:
        return
    if user["credits"] < cost:
        raise HTTPException(402, f"Insufficient credits (need {cost}, have {user['credits']}). "
                                 "Credits refresh daily.")
    db.execute("UPDATE users SET credits=credits-? WHERE id=?", (cost, user["id"]))


@router.post("/generate")
def generate(body: GenerateIn, request: Request):
    user = get_current_user(request)
    if db.setting("maintenance_mode", "off") == "on" and user["role"] not in ("admin", "owner"):
        raise HTTPException(503, "Platform is in maintenance mode")
    kind = body.kind.strip().lower()
    if kind not in KINDS:
        raise HTTPException(400, f"Unknown generation kind '{kind}'")
    prompt = body.prompt.strip()[:1500]
    if kind in ("image", "anime", "video", "2d", "story") and not prompt:
        raise HTTPException(400, "Prompt is required")
    cost = config.COSTS[kind]
    _charge(user, cost)
    job_id = db.execute(
        "INSERT INTO jobs (user_id,project_id,kind,model_id,prompt,params,status,step,cost,created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (user["id"], body.params.get("project_id") or None, kind,
         orchestrator.registry.KIND_MODEL[kind], prompt,
         json.dumps(body.params)[:4000], "queued", "queued", cost, db.now()))
    db.log("info", "job-queued", user["email"], f"job {job_id} kind={kind} cost={cost}")
    threading.Thread(target=orchestrator.run_job, args=(job_id,), daemon=True).start()
    return {"job_id": job_id, "status": "queued", "cost": cost}


def _job_or_404(job_id: int, user: dict) -> dict:
    job = db.q1("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not job or (job["user_id"] != user["id"] and user["role"] not in ("admin", "owner")):
        raise HTTPException(404, "Job not found")
    return job


@router.get("/jobs/{job_id}")
def job_status(job_id: int, request: Request):
    user = get_current_user(request)
    job = _job_or_404(job_id, user)
    return {k: job[k] for k in ("id", "kind", "model_id", "prompt", "params", "status", "step",
                                "progress", "media_type", "eval_json", "error", "cost",
                                "created_at", "finished_at", "project_id")}


@router.get("/models/public")
def public_models():
    """Non-sensitive model family status — safe for any visitor."""
    return db.q("SELECT name, family, version, status FROM models ORDER BY family")


@router.get("/jobs")
def jobs_list(request: Request, limit: int = 30, kind: str = ""):
    user = get_current_user(request)
    sql = "SELECT * FROM jobs WHERE user_id=?"
    args: list = [user["id"]]
    if kind and kind in KINDS:
        sql += " AND kind=?"
        args.append(kind)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(max(1, min(limit, 100)))
    rows = db.q(sql, tuple(args))
    return [{k: j[k] for k in ("id", "kind", "prompt", "status", "step", "progress",
                               "media_type", "eval_json", "cost", "created_at", "project_id")}
            for j in rows]


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int, request: Request):
    user = get_current_user(request)
    job = _job_or_404(job_id, user)
    if job["file_path"]:
        try:
            Path(job["file_path"]).unlink(missing_ok=True)
        except OSError:
            pass
    db.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    db.log("info", "job-deleted", user["email"], f"job {job_id}")
    return {"ok": True}


@router.get("/files/{job_id}")
def job_file(job_id: int, request: Request):
    user = get_current_user(request)
    job = _job_or_404(job_id, user)
    p = Path(job["file_path"] or "")
    if not p.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(p, media_type=job["media_type"] or None, filename=p.name)


# ------------------------------------------------------------------ uploads
@router.post("/uploads")
async def upload_file(request: Request, file: UploadFile = File(...)):
    user = get_current_user(request)
    raw = await file.read()
    if len(raw) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 10 MB)")
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
    except UnidentifiedImageError:
        raise HTTPException(400, "Only valid image files are accepted")
    uid = secrets.token_hex(8)
    path = config.UPLOADS_DIR / f"{uid}.png"
    Image.open(io.BytesIO(raw)).convert("RGB").save(path)  # re-encode = sanitize
    up_id = db.execute("INSERT INTO uploads (user_id,path,created_at) VALUES (?,?,?)",
                       (user["id"], str(path), db.now()))
    return {"upload_id": up_id, "name": file.filename or "image"}


# --------------------------------------------------------------- characters
class CharacterIn(BaseModel):
    name: str
    description: str = ""
    traits: dict = {}


@router.post("/characters")
def create_character(body: CharacterIn, request: Request):
    user = get_current_user(request)
    from .engines import hash01
    traits = body.traits or {}
    code = "CHR-" + secrets.token_hex(3).upper()
    seed = int(hash01(body.name + json.dumps(traits, sort_keys=True)) * 999_983)
    cid = db.execute(
        "INSERT INTO characters (user_id,character_code,name,description,traits,seed,created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (user["id"], code, body.name.strip()[:60], body.description.strip()[:400],
         json.dumps(traits), seed, db.now()))
    db.log("info", "character-created", user["email"], code)
    return {"id": cid, "character_code": code, "name": body.name, "seed": seed, "traits": traits}


@router.get("/characters")
def list_characters(request: Request):
    user = get_current_user(request)
    rows = db.q("SELECT * FROM characters WHERE user_id=? ORDER BY id DESC", (user["id"],))
    return [{**r, "traits": json.loads(r["traits"] or "{}")} for r in rows]


@router.delete("/characters/{cid}")
def delete_character(cid: int, request: Request):
    user = get_current_user(request)
    db.execute("DELETE FROM characters WHERE id=? AND user_id=?", (cid, user["id"]))
    return {"ok": True}


# ----------------------------------------------------------------- projects
class ProjectIn(BaseModel):
    name: str


@router.post("/projects")
def create_project(body: ProjectIn, request: Request):
    user = get_current_user(request)
    pid = db.execute("INSERT INTO projects (user_id,name,created_at) VALUES (?,?,?)",
                     (user["id"], body.name.strip()[:80] or "Untitled", db.now()))
    return {"id": pid, "name": body.name.strip()}


@router.get("/projects")
def list_projects(request: Request):
    user = get_current_user(request)
    rows = db.q(
        "SELECT p.*, (SELECT COUNT(*) FROM jobs j WHERE j.project_id=p.id) AS job_count "
        "FROM projects p WHERE p.user_id=? ORDER BY p.id DESC", (user["id"],))
    return rows


@router.delete("/projects/{pid}")
def delete_project(pid: int, request: Request):
    user = get_current_user(request)
    db.execute("UPDATE jobs SET project_id=NULL WHERE project_id=? AND user_id=?",
               (pid, user["id"]))
    db.execute("DELETE FROM projects WHERE id=? AND user_id=?", (pid, user["id"]))
    return {"ok": True}
