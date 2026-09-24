"""ALMIGHTY STORY — story-to-video planner + compositor (v0.1.0-dev).

Pipeline:  story prompt
        -> genre detection
        -> scene planning (storyboard)
        -> per-scene image generation (shared universe seed)
        -> Ken Burns animation + burned subtitles
        -> final assembled video

Phase 3 replaces the planner with ALMIGHTY STORY (script-understanding
model) and the renderer with ALMIGHTY VIDEO scenes. Contracts stay.
"""
import math
import re

from PIL import Image, ImageDraw, ImageFilter

from .. import config
from ..fonts import get_font
from . import clamp
from . import image_engine, video_engine

GENRES = {
    "horror": {"style": "noir", "tone": "dark, unsettling shadows, cold atmosphere"},
    "fantasy": {"style": "fantasy", "tone": "epic light, magical atmosphere"},
    "anime": {"style": "anime", "tone": "anime key visual, dramatic lighting"},
    "scifi": {"style": "neon", "tone": "futuristic neon, high technology"},
    "romance": {"style": "watercolor", "tone": "soft warm light, tender mood"},
    "comedy": {"style": "vibrant", "tone": "bright playful colors"},
}
GENRE_KEYWORDS = {
    "horror": ["horror", "scary", "ghost", "haunt", "demon", "monster", "creep", "dark", "blood", "nightmare", "reflection"],
    "fantasy": ["fantasy", "dragon", "magic", "wizard", "kingdom", "quest", "sword"],
    "anime": ["anime", "manga", "shonen", "senpai"],
    "scifi": ["sci-fi", "scifi", "space", "robot", "alien", "cyber", "future"],
    "romance": ["love", "romance", "heart", "kiss", "crush"],
    "comedy": ["comedy", "funny", "joke", "silly"],
}

BEATS = [
    ("the world is revealed", "establishing wide shot"),
    ("the heart of the story", "intimate close-up"),
    ("tension rises", "rising tension, ominous framing"),
    ("the turning point", "dramatic turning point, dynamic angle"),
    ("the moment of truth", "climactic high-contrast framing"),
    ("what remains after", "quiet resolution shot, soft focus"),
]


def detect_genre(prompt: str) -> str:
    low = prompt.lower()
    best, hits = "cinematic", 0
    for genre, words in GENRE_KEYWORDS.items():
        n = sum(1 for w in words if w in low)
        if n > hits:
            best, hits = genre, n
    return best


def plan_story(prompt: str, duration: float) -> list[dict]:
    """Storyboard: list of scenes with caption + generation prompt."""
    duration = clamp(duration, 6, config.MAX_STORY_SECONDS)
    n_scenes = max(3, min(8, round(duration / 5)))
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", prompt) if len(s.strip()) > 8]
    genre = detect_genre(prompt)
    tone = GENRES.get(genre, {"tone": ""})["tone"]
    if len(sentences) >= n_scenes:
        picks = sentences[:n_scenes]
        scenes = [{"caption": s[:110], "prompt": f"{s}. {tone}"} for s in picks]
    else:
        core = sentences[0] if sentences else prompt[:140]
        scenes = []
        for suffix, shot in BEATS[:n_scenes]:
            scenes.append({"caption": f"{core} — {suffix}"[:110],
                           "prompt": f"{core}. {shot}. {tone}"})
    return scenes, genre


def _fit_text(d, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if d.textlength(cur + " " + w, font=font) <= max_w:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3]


def render_story(prompt: str, seed: int, duration: float, aspect: str = "16:9",
                 character: dict | None = None, out_base=None) -> tuple[str, str, list, dict]:
    duration = clamp(duration, 6, config.MAX_STORY_SECONDS)
    scenes, genre = plan_story(prompt, duration)
    style = GENRES.get(genre, {}).get("style", "cinematic")
    # story resolution is tuned for memory-safe long sequences on CPU
    W, H = {"16:9": (512, 288), "9:16": (288, 512), "1:1": (384, 384)}.get(aspect, (512, 288))
    fps = config.STORY_FPS

    # 1. generate storyboard frames (consistent universe: seed-locked)
    boards = []
    for i, sc in enumerate(scenes):
        boards.append(image_engine.render(
            W, H, prompt=sc["prompt"], style=style, seed=seed + i * 17,
            character=character if i % 2 == 0 else None, t=i / max(1, len(scenes) - 1),
            motion=0.2))

    # 2. title card
    def title_card(text, sub):
        card = Image.new("RGB", (W, H), (6, 6, 10))
        d = ImageDraw.Draw(card)
        f = get_font(int(H * 0.09))
        fs = get_font(int(H * 0.045))
        tw = d.textlength(text, font=f)
        if tw > W * 0.9:
            text = text[: int(len(text) * W * 0.9 / tw)] + "…"
            tw = d.textlength(text, font=f)
        d.text(((W - tw) / 2, H * 0.40), text, font=f, fill=(247, 201, 72))
        sw = d.textlength(sub, font=fs)
        d.text(((W - sw) / 2, H * 0.56), sub, font=fs, fill=(180, 180, 190))
        return card

    story_title = prompt.split(".")[0][:48] or "An ALMIGHTY Story"
    frames: list[Image.Image] = []
    title_frames = fps  # 1s title
    frames += [title_card(story_title.upper(), "an ALMIGHTY AI story")] * title_frames

    # 3. Ken Burns per scene + subtitles
    scene_frames = int((duration * fps - title_frames - fps) / len(scenes))
    sub_font = get_font(max(14, int(H * 0.05)))
    for idx, board in enumerate(boards):
        cap = scenes[idx]["caption"]
        grow = idx % 2 == 0
        for i in range(scene_frames):
            t = i / max(1, scene_frames - 1)
            z = (1.0 + 0.10 * t) if grow else (1.10 - 0.10 * t)
            zw, zh = int(W / z), int(H / z)
            ox = int((W - zw) * (0.5 + 0.25 * math.sin(idx + t * 2)))
            oy = int((H - zh) * 0.5)
            ox = max(0, min(W - zw, ox))
            frame = board.crop((ox, oy, ox + zw, oy + zh)).resize((W, H))
            d = ImageDraw.Draw(frame)
            # subtitle band
            lines = _fit_text(d, cap, sub_font, W * 0.86)
            lh = int(H * 0.062)
            band_h = lh * len(lines) + 14
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.rectangle([0, H - band_h, W, H], fill=(0, 0, 0, 150))
            frame = Image.alpha_composite(frame.convert("RGBA"), overlay).convert("RGB")
            d = ImageDraw.Draw(frame)
            for li, line in enumerate(lines):
                lw = d.textlength(line, font=sub_font)
                x, y = (W - lw) / 2, H - band_h + 7 + li * lh
                d.text((x - 1.5, y), line, font=sub_font, fill=(0, 0, 0))
                d.text((x + 1.5, y), line, font=sub_font, fill=(0, 0, 0))
                d.text((x, y), line, font=sub_font, fill=(250, 250, 250))
            frames.append(frame)

    frames += [title_card("CREATED WITH", "ALMIGHTY AI")] * fps

    path, mtype = video_engine.assemble(frames, fps, out_base)
    plan = {"genre": genre, "style": style,
            "storyboard": [{"scene": i + 1, "caption": s["caption"]} for i, s in enumerate(scenes)]}
    sample = frames[:: max(1, len(frames) // 8)][:8]   # eval sample, keeps memory flat
    return path, mtype, sample, plan
