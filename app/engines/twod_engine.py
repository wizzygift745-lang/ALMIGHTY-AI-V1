"""ALMIGHTY 2D — proprietary 2D animation engine (v0.1.0-dev).

A parametric rig animator: character (from the character-identity system)
+ background + action + emotion + dialogue + camera => animated scene.

Phase 3 upgrades the rig to learned cel-animation synthesis; the scene
description format (input contract) is final.
"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..fonts import get_font
from . import clamp
from . import video_engine
from .image_engine import draw_character, make_palette

ACTIONS = ["walk", "run", "wave", "dance", "jump", "talk", "fight"]
EMOTIONS = ["happy", "sad", "angry", "surprised", "calm", "determined"]


def _background(w: int, h: int, rng: random.Random, pal, mood: str) -> Image.Image:
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    horizon = int(h * 0.72)
    for y in range(horizon):
        p = y / max(1, horizon)
        d.line([(0, y), (w, y)],
               fill=tuple(int(pal[0][i] * (1 - p) + pal[2][i] * p) for i in range(3)))
    d.rectangle([0, horizon, w, h], fill=tuple(int(c * 0.45) for c in pal[1]))
    # sun/moon
    d.ellipse([w * 0.68, h * 0.12, w * 0.82, h * 0.26], fill=pal[4])
    # hills
    for k, c in enumerate((pal[3], pal[1])):
        pts = [(0, horizon)]
        for x in range(0, w + 8, 8):
            y = horizon - (18 + 26 * math.sin(x / 90 + k * 2 + rng.random())) * (1 - k * 0.4)
            pts.append((x, y))
        pts += [(w, horizon)]
        d.polygon(pts, fill=tuple(int(v * (0.6 + 0.15 * k)) for v in c))
    return img


def _face(d: ImageDraw.ImageDraw, hx, hy, s, emotion: str, talk: float) -> None:
    ex = s * 0.065
    eye_y = hy - s * 0.02
    if emotion == "surprised":
        r = s * 0.045
        d.ellipse([hx - ex - r, eye_y - r, hx - ex + r, eye_y + r], fill="#1b1b1b")
        d.ellipse([hx + ex - r, eye_y - r, hx + ex + r, eye_y + r], fill="#1b1b1b")
    else:
        d.ellipse([hx - ex - s * 0.025, eye_y - s * 0.02, hx - ex + s * 0.025, eye_y + s * 0.03], fill="#1b1b1b")
        d.ellipse([hx + ex - s * 0.025, eye_y - s * 0.02, hx + ex + s * 0.025, eye_y + s * 0.03], fill="#1b1b1b")
    # brows
    tilt = {"angry": -1, "sad": 1, "determined": -0.5}.get(emotion, 0)
    if tilt:
        d.line([hx - ex - s * 0.04, eye_y - s * 0.05 + tilt * s * 0.03,
                hx - ex + s * 0.04, eye_y - s * 0.05 - tilt * s * 0.03], fill="#1b1b1b", width=2)
        d.line([hx + ex - s * 0.04, eye_y - s * 0.05 - tilt * s * 0.03,
                hx + ex + s * 0.04, eye_y - s * 0.05 + tilt * s * 0.03], fill="#1b1b1b", width=2)
    # mouth
    my = hy + s * 0.07
    if talk > 0.05:
        d.ellipse([hx - s * 0.04, my - s * 0.03 * talk, hx + s * 0.04, my + s * 0.05 * talk], fill="#5b2020")
    elif emotion == "happy":
        d.arc([hx - s * 0.06, my - s * 0.05, hx + s * 0.06, my + s * 0.05], 10, 170, fill="#1b1b1b", width=2)
    elif emotion == "sad":
        d.arc([hx - s * 0.06, my, hx + s * 0.06, my + s * 0.08], 190, 350, fill="#1b1b1b", width=2)
    else:
        d.line([hx - s * 0.045, my, hx + s * 0.045, my], fill="#1b1b1b", width=2)


def render_2d(prompt: str, seed: int, duration: float, action: str, emotion: str,
              dialogue: str, camera: str, traits: dict, aspect: str = "16:9",
              fps: int = 24, out_base=None) -> tuple[str, str, list]:
    duration = clamp(duration, 1, 6)
    W, H = video_engine.ASPECTS.get(aspect, (480, 480))
    rng = random.Random(seed)
    pal = make_palette(prompt or "scene", "anime", rng)
    bg = _background(W, H, rng, pal, emotion)
    n = min(int(duration * fps), 144)
    frames: list[Image.Image] = []
    speed = {"walk": 5.0, "run": 9.0, "dance": 7.0, "fight": 10.0}.get(action, 4.0)

    for i in range(n):
        t = i / max(1, n - 1)
        img = bg.copy()
        d = ImageDraw.Draw(img)
        phase = i / fps * speed
        # stage position + camera
        if action in ("walk", "run"):
            cx = W * (0.15 + 0.7 * t)
        else:
            cx = W * 0.5
        cy = H * 0.66
        s = min(W, H) * 0.34
        if camera == "pan-follow":
            shift = -(cx - W * 0.5) * 0.6
            img = img.transform((W, H), Image.AFFINE, (1, 0, shift, 0, 1, 0))
            d = ImageDraw.Draw(img)
            cx -= shift
        elif camera == "zoom-in":
            z = 1 + 0.3 * t
            zw, zh = int(W / z), int(H / z)
            img = img.crop(((W - zw) // 2, (H - zh) // 2, (W - zw) // 2 + zw, (H - zh) // 2 + zh)).resize((W, H))
            d = ImageDraw.Draw(img)
        if action == "jump":
            cy -= abs(math.sin(phase)) * s * 0.5
        elif action == "run":
            cy -= abs(math.sin(phase * 2)) * s * 0.06

        # body via shared rig
        draw_character(d, cx, cy, s, traits, facing=1.0 if action in ("walk", "run") else 0.0,
                       pose_phase=phase if action in ("walk", "run", "dance", "fight") else 0)
        # animated limbs over the rig
        hip_y = cy + s * 0.50
        if action in ("walk", "run"):
            amp = 0.5 if action == "walk" else 0.9
            for side in (-1, 1):
                a = math.sin(phase + (0 if side > 0 else math.pi)) * amp
                d.line([cx + side * s * 0.10, hip_y,
                        cx + side * s * 0.10 + math.sin(a) * s * 0.30,
                        hip_y + math.cos(a) * s * 0.34], fill="#26262b", width=max(2, int(s * 0.10)))
                aa = math.sin(phase + math.pi + (0 if side > 0 else math.pi)) * amp * 0.8
                d.line([cx + side * s * 0.22, cy + s * 0.05,
                        cx + side * s * 0.22 + math.sin(aa) * s * 0.26,
                        cy + s * 0.05 + math.cos(aa) * s * 0.26],
                       fill=traits.get("outfit", "#7c5cff"), width=max(2, int(s * 0.08)))
        elif action == "wave":
            a = math.sin(phase * 2) * 0.6
            d.line([cx + s * 0.22, cy, cx + s * 0.38 + math.sin(a) * s * 0.1,
                    cy - s * 0.30 + math.cos(a) * s * 0.06],
                   fill=traits.get("outfit", "#7c5cff"), width=max(2, int(s * 0.09)))
        elif action == "dance":
            for side in (-1, 1):
                a = math.sin(phase * 2 + side) * 0.9
                d.line([cx + side * s * 0.22, cy,
                        cx + side * (s * 0.3 + math.sin(a) * s * 0.14),
                        cy - s * 0.2 + math.cos(a) * s * 0.16],
                       fill=traits.get("outfit", "#7c5cff"), width=max(2, int(s * 0.08)))
        elif action == "fight":
            a = math.sin(phase * 2)
            d.line([cx + s * 0.22, cy, cx + s * (0.42 + 0.22 * max(0, a)), cy - s * 0.05 * a],
                   fill=traits.get("outfit", "#7c5cff"), width=max(2, int(s * 0.09)))
            if a > 0.7:
                d.line([cx + s * 0.66, cy - s * 0.1, cx + s * 0.8, cy - s * 0.2],
                       fill="#ffd76a", width=3)

        # face (re-draw over rig head for expressions + lip sync)
        sway = math.sin(phase) * s * 0.03 if action in ("walk", "run", "dance") else 0
        hx, hy = cx + sway, cy - s * 0.28
        talk = abs(math.sin(i / fps * 10)) if (action == "talk" or dialogue) else 0.0
        _face(d, hx, hy, s, emotion, talk)

        # dialogue bubble
        if dialogue and 0.15 < t < 0.9:
            font = get_font(max(13, int(s * 0.13)))
            text = dialogue[:120]
            bx, by = min(cx + s * 0.5, W * 0.55), max(s * 0.2, cy - s * 0.9)
            bw = min(W - bx - 10, max(90, font.getlength(text) + 24))
            d.rounded_rectangle([bx, by, bx + bw, by + s * 0.34], radius=10,
                                fill=(250, 250, 250), outline=(20, 20, 25), width=2)
            d.text((bx + 12, by + s * 0.07), text, fill="#111", font=font)

        frames.append(img.filter(ImageFilter.SMOOTH_MORE))
    path, mtype = video_engine.assemble(frames, fps, out_base)
    return path, mtype, frames
