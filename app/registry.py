"""ALMIGHTY_MODEL_ENGINE — model registry access layer.

Every model row carries: id, version, architecture, capabilities,
resolution limits, duration limits, VRAM requirements, inference config,
safety config. Routing / rollback / monitoring build on this table.
"""
import json

from . import db

KIND_MODEL = {
    "image": "almighty-image",
    "anime": "almighty-anime",
    "video": "almighty-video",
    "2d": "almighty-2d",
    "upscale": "almighty-upscale",
    "story": "almighty-story",
}


def get(model_id: str) -> dict | None:
    return db.q1("SELECT * FROM models WHERE id=?", (model_id,))


def all_models() -> list[dict]:
    return db.q("SELECT * FROM models ORDER BY family")


def route(kind: str) -> dict:
    """Orchestrator routing: pick the registered model for a task kind."""
    model = get(KIND_MODEL.get(kind, ""))
    if not model:
        raise RuntimeError(f"No registered model for task kind '{kind}'")
    return model


def decode(model: dict) -> dict:
    m = dict(model)
    m["capabilities"] = json.loads(m.get("capabilities") or "[]")
    m["config"] = json.loads(m.get("config") or "{}")
    return m
