"""ALMIGHTY VIDEO — proprietary video engine (v0.1.0-dev).

Renders temporally-coherent frame sequences from the same deterministic
scene description used by ALMIGHTY IMAGE (shared seed => consistent world),
then assembles them with ffmpeg (MP4) when available, otherwise GIF.

Phase 3 replaces the frame renderer with the trained ALMIGHTY VIDEO
temporal model; assembly + camera-path code stays.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from .. import config
from . import clamp
from . import image_engine

FFMPEG = shutil.which("ffmpeg")

ASPECTS = {
    "16:9": (640, 360),
    "9:16": (360, 640),
    "1:1": (480, 480),
}


def camera_path(mode: str, t: float):
    """Return (cam_x, cam_y, zoom) at normalized time t in [0,1]."""
    if mode == "pan-left":
        return (-0.6 * t, 0.0, 1.12)
    if mode == "pan-right":
        return (0.6 * t, 0.0, 1.12)
    if mode == "zoom-in":
        return (0.0, 0.0, 1.0 + 0.35 * t)
    if mode == "zoom-out":
        return (0.0, 0.0, 1.35 - 0.35 * t)
    if mode == "orbit":
        import math
        return (0.25 * math.sin(t * 6.283), 0.08 * math.cos(t * 6.283), 1.15)
    if mode == "push-up":
        return (0.0, -0.4 * t, 1.1)
    return (0.0, 0.0, 1.05)


def assemble(frames: list[Image.Image], fps: int, out_base: Path) -> tuple[str, str]:
    """Encode frames -> (file_path, media_type)."""
    if FFMPEG:
        with tempfile.TemporaryDirectory() as tmp:
            for i, f in enumerate(frames):
                f.save(Path(tmp) / f"f_{i:05d}.png")
            out = out_base.with_suffix(".mp4")
            cmd = [FFMPEG, "-y", "-loglevel", "error", "-framerate", str(fps),
                   "-i", str(Path(tmp) / "f_%05d.png"),
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                   str(out)]
            r = subprocess.run(cmd, capture_output=True, timeout=600)
            if r.returncode == 0 and out.exists():
                return str(out), "video/mp4"
    # GIF fallback (also used when ffmpeg is absent)
    out = out_base.with_suffix(".gif")
    dur = max(20, round(1000 / fps))
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=dur, loop=0, optimize=False)
    return str(out), "image/gif"


def render_video(prompt: str, style: str, seed: int, duration: float,
                 aspect: str = "16:9", fps: int = 24, motion: float = 0.8,
                 camera: str = "zoom-in", character: dict | None = None,
                 base_image: Image.Image | None = None,
                 out_base: Path | None = None,
                 resolution_scale: float = 1.0) -> tuple[str, str, list]:
    duration = clamp(duration, 1, config.MAX_VIDEO_SECONDS)
    W, H = ASPECTS.get(aspect, (640, 360))
    W, H = int(W * resolution_scale), int(H * resolution_scale)
    n = min(int(duration * fps), 120)          # hard MVP safety rail
    frames: list[Image.Image] = []
    for i in range(n):
        t = i / max(1, n - 1)
        cx, cy, zoom = camera_path(camera, t)
        frames.append(image_engine.render(
            W, H, prompt=prompt, style=style, seed=seed,
            character=character, base_image=base_image,
            t=t, motion=motion, cam_x=cx, cam_y=cy, zoom=zoom))
    path, mtype = assemble(frames, fps, out_base)
    return path, mtype, frames
