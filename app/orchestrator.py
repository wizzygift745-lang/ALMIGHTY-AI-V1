"""ALMIGHTY ORCHESTRATOR — internal task pipeline.

    user request -> prompt understanding -> task classification
                 -> model selection (registry) -> generation
                 -> quality evaluation -> auto-improve (retry) -> result

Runs each job in a worker thread; every stage is recorded on the job row
so the UI can stream progress, and audit logs capture the full trace.
"""
import json
import time
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from . import config, db, evaluation, registry
from .engines import image_engine, story_engine, twod_engine, upscale_engine, video_engine
from .engines import providers


def _set(job_id: int, **fields) -> None:
    sets = ", ".join(f"{k}=?" for k in fields)
    db.execute(f"UPDATE jobs SET {sets} WHERE id=?", (*fields.values(), job_id))


def _finish_ok(job_id: int, path: str, media_type: str, ev: dict) -> None:
    db.execute("UPDATE jobs SET status='done', step='complete', progress=100, file_path=?,"
               " media_type=?, eval_json=?, finished_at=? WHERE id=?",
               (path, media_type, json.dumps(ev), db.now(), job_id))


def _finish_fail(job_id: int, error: str) -> None:
    db.execute("UPDATE jobs SET status='failed', step='failed', error=?, finished_at=? WHERE id=?",
               (error[:500], db.now(), job_id))


def run_job(job_id: int) -> None:
    job = db.q1("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not job:
        return
    actor = f"user:{job['user_id']}"
    try:
        params = json.loads(job["params"] or "{}")
        prompt = job["prompt"]

        # ---- 1. prompt understanding -------------------------------------
        _set(job_id, status="running", step="Prompt understanding", progress=6)
        words = [w for w in prompt.lower().split() if len(w) > 3]
        style = params.get("style") or ("anime" if any(
            w in words for w in ("anime", "manga")) else "cinematic")
        time.sleep(0.15)

        # ---- 2. task classification + 3. model selection -------------------
        _set(job_id, step="Task classification & model routing", progress=14)
        model = registry.decode(registry.route(job["kind"]))
        if model["status"] not in ("online",):
            raise RuntimeError(f"Model {model['name']} is '{model['status']}' — routed task cannot run.")
        db.log("info", "model-routed", actor, f"{model['id']} v{model['version']} <- job {job_id}")
        time.sleep(0.1)

        # ---- temporary provider check (default: none) ----------------------
        provider = providers.active_provider()
        engine_note = ("temporary external provider" if provider
                       else f"proprietary dev engine ({model['architecture']})")
        _set(job_id, step=f"Generation on {model['name']} — {engine_note}", progress=30)

        # ---- character identity -------------------------------------------
        character = None
        if params.get("character_id"):
            ch = db.q1("SELECT * FROM characters WHERE id=? AND user_id=?",
                       (params["character_id"], job["user_id"]))
            if ch:
                character = {"traits": json.loads(ch["traits"] or "{}"),
                             "seed": ch["seed"], "name": ch["name"]}
        base_img = None
        if params.get("upload_id"):
            up = db.q1("SELECT * FROM uploads WHERE id=? AND user_id=?",
                       (params["upload_id"], job["user_id"]))
            if up:
                try:
                    base_img = Image.open(up["path"]).convert("RGB")
                except UnidentifiedImageError:
                    base_img = None

        out_base = config.GENERATIONS_DIR / f"job_{job_id}"
        seed = int(params.get("seed") or 0) or character_seed_or_prompt(character, prompt, job_id)

        # ---- 4. generation (per kind) ---------------------------------------
        path = mtype = None
        frames: list = []
        extra: dict = {}
        kind = job["kind"]

        if kind in ("image", "anime"):
            if kind == "anime":
                style = "anime"
            w, h = _dims(params.get("aspect", "1:1"), int(params.get("resolution", 1024)))
            img = image_engine.render(w, h, prompt=prompt, negative=params.get("negative", ""),
                                      style=style, seed=seed,
                                      steps=int(params.get("steps", 28)),
                                      guidance=float(params.get("guidance", 7)),
                                      character=character, base_image=base_img)
            path, mtype = str(out_base.with_suffix(".png")), "image/png"
            img.save(path, optimize=True)
            ev = evaluation.evaluate_image(img, prompt)
            # auto-improve loop
            threshold = float(db.setting("quality_threshold", "55"))
            if ev["score"] < threshold:
                _set(job_id, step=f"Quality {ev['score']} < {threshold} — auto-improving (new seed)",
                     progress=62)
                img2 = image_engine.render(w, h, prompt=prompt, negative=params.get("negative", ""),
                                           style=style, seed=seed + 7919,
                                           steps=int(params.get("steps", 28)) + 6,
                                           guidance=float(params.get("guidance", 7)) + 1,
                                           character=character, base_image=base_img)
                ev2 = evaluation.evaluate_image(img2, prompt)
                if ev2["score"] >= ev["score"]:
                    img2.save(path, optimize=True)
                    ev = ev2
                db.log("info", "auto-improve", actor, f"job {job_id}: {ev['score']}")

        elif kind == "video":
            path, mtype, frames = video_engine.render_video(
                prompt=prompt, style=style, seed=seed,
                duration=float(params.get("duration", 4)),
                aspect=params.get("aspect", "16:9"), fps=config.VIDEO_FPS,
                motion=float(params.get("motion", 0.8)),
                camera=params.get("camera", "zoom-in"),
                character=character, base_image=base_img, out_base=out_base)
            ev = evaluation.evaluate_video(frames, prompt)

        elif kind == "2d":
            ch_traits = (character or {}).get("traits") or {
                "skin": "#eab98f", "hair": "#2b2118", "outfit": "#7c5cff", "accent": "#f7c948"}
            path, mtype, frames = twod_engine.render_2d(
                prompt=prompt, seed=seed, duration=float(params.get("duration", 3)),
                action=params.get("action", "walk"), emotion=params.get("emotion", "happy"),
                dialogue=params.get("dialogue", ""), camera=params.get("camera", "static"),
                traits=ch_traits, aspect=params.get("aspect", "16:9"),
                fps=config.VIDEO_FPS, out_base=out_base)
            ev = evaluation.evaluate_video(frames, prompt)

        elif kind == "story":
            path, mtype, frames, plan = story_engine.render_story(
                prompt=prompt, seed=seed, duration=float(params.get("duration", 20)),
                aspect=params.get("aspect", "16:9"), character=character, out_base=out_base)
            ev = evaluation.evaluate_video(frames, prompt) if frames else {"score": 60}
            extra = {"plan": plan}

        elif kind == "upscale":
            up_path = _upload_path(params, job)
            if not up_path:
                raise RuntimeError("Upscale requires an input image upload.")
            path, mtype = upscale_engine.upscale_file(up_path, float(params.get("scale", 2)), out_base)
            ev = evaluation.evaluate_image(Image.open(path), prompt)

        else:
            raise RuntimeError(f"Unknown task kind '{kind}'")

        # ---- 5. finalize -----------------------------------------------------
        _set(job_id, step="Quality evaluation", progress=88)
        if extra:
            db.execute("UPDATE jobs SET params=? WHERE id=?",
                       (json.dumps({**params, **extra}), job_id))
        _set(job_id, step="Finalizing", progress=96)
        _finish_ok(job_id, path, mtype, ev)
        db.log("info", "generation-complete", actor,
               f"job {job_id} ({kind}) score={ev.get('score')} file={Path(path).name}")

    except Exception as exc:  # noqa: BLE001 — job-level catch-all by design
        _finish_fail(job_id, str(exc))
        # refund the credits: failures must never cost users
        j2 = db.q1("SELECT * FROM jobs WHERE id=?", (job_id,))
        if j2 and j2["cost"]:
            db.execute("UPDATE users SET credits=credits+? WHERE id=? AND credits>=0",
                       (j2["cost"], j2["user_id"]))
        db.log("error", "generation-failed", actor, f"job {job_id}: {exc}")


def character_seed_or_prompt(character, prompt: str, job_id: int) -> int:
    if character and character.get("seed"):
        return int(character["seed"])
    return (job_id * 2654435761) % 1_000_000


def _dims(aspect: str, long_side: int) -> tuple[int, int]:
    long_side = max(256, min(int(long_side), config.MAX_IMAGE_SIDE))
    if aspect == "16:9":
        return long_side, int(long_side * 9 / 16 // 8 * 8)
    if aspect == "9:16":
        return int(long_side * 9 / 16 // 8 * 8), long_side
    return long_side, long_side


def _upload_path(params: dict, job: dict) -> str:
    up = db.q1("SELECT * FROM uploads WHERE id=? AND user_id=?",
               (params.get("upload_id"), job["user_id"]))
    return up["path"] if up else ""
