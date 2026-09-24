"""ALMIGHTY IMAGE — proprietary image engine (v0.1.0-dev).

MVP backend: a deterministic procedural latent-renderer. Given the same
(prompt, seed, style, character) it always produces the same artwork, which
is what makes character consistency and reproducible generations possible
even before the trained weights exist.

The public entrypoint is `render()`; Phase 3 swaps its internals for the
trained ALMIGHTY IMAGE diffusion model without touching callers.
"""
import colorsys
import math
import random

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from . import clamp, hash01, lerp_color

STYLES = ["cinematic", "vibrant", "anime", "noir", "neon", "watercolor", "fantasy"]

SKIN_TONES = ["#f6d3b6", "#eab98f", "#c98d5f", "#9c6b43", "#6f4a2f", "#4a3223"]
HAIR_COLORS = ["#141414", "#3d2b1f", "#6b4423", "#a86b2d", "#c9a227",
               "#b3b3b3", "#7c5cff", "#ff5d8f", "#22d3ee"]
OUTFIT_COLORS = ["#7c5cff", "#22d3ee", "#ff5d8f", "#f7c948", "#34d399",
                 "#ef4444", "#1f2937", "#f5f5f4"]


def make_palette(prompt: str, style: str, rng: random.Random):
    base = hash01(prompt or "almighty")
    spread = {"noir": 0.03, "watercolor": 0.09}.get(style, 0.14)
    sat, val = {"noir": (0.10, 0.55), "neon": (0.95, 0.95), "anime": (0.72, 0.92),
                "cinematic": (0.55, 0.72), "watercolor": (0.45, 0.9),
                "fantasy": (0.7, 0.85)}.get(style, (0.75, 0.85))
    cols = []
    for i in range(5):
        h = (base + i * spread + rng.uniform(-0.02, 0.02)) % 1.0
        s = clamp(sat + rng.uniform(-0.1, 0.1), 0.05, 1)
        v = clamp(val + rng.uniform(-0.12, 0.12), 0.15, 1)
        cols.append(tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, s, v)))
    return cols


def _vignette(img: Image.Image, strength: float = 0.55) -> Image.Image:
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    steps = 24
    lim = min(w, h) // 2 - 1
    for i in range(steps):
        t = i / steps
        inset = min(int(t * min(w, h) * 0.55), lim)
        d.rectangle([inset, inset, w - inset, h - inset],
                    fill=int(255 * strength * (1 - t)))
    mask = mask.filter(ImageFilter.GaussianBlur(min(w, h) / 6))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(dark, img, mask)


def _grain(img: Image.Image, rng: random.Random, amount: int = 10) -> Image.Image:
    w, h = img.size
    noise = Image.effect_noise((max(2, w // 3), max(2, h // 3)), amount * 2).convert("L")
    noise = noise.resize((w, h))
    rgb_noise = Image.merge("RGB", (noise, noise, noise))
    return Image.blend(img, Image.blend(img, rgb_noise, 0.35), clamp(amount / 40, 0, 0.6))


def draw_character(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float,
                   traits: dict, facing: float = 0.0, pose_phase: float = 0.0) -> None:
    """Render the platform's canonical character rig.

    The same traits dict always draws the same character — this is the
    MVP character-identity system (Phase 3 replaces it with identity
    embeddings from ALMIGHTY IMAGE, same contract).
    """
    skin = traits.get("skin", SKIN_TONES[1])
    hair = traits.get("hair", HAIR_COLORS[0])
    outfit = traits.get("outfit", OUTFIT_COLORS[0])
    accent = traits.get("accent", "#f7c948")
    sway = math.sin(pose_phase) * scale * 0.03 * facing if facing else 0

    s = scale
    # body
    draw.rounded_rectangle([cx - s * 0.22 + sway, cy - s * 0.05,
                            cx + s * 0.22 + sway, cy + s * 0.52],
                           radius=s * 0.12, fill=outfit)
    # accent scarf/belt
    draw.rectangle([cx - s * 0.22 + sway, cy + s * 0.10,
                    cx + s * 0.22 + sway, cy + s * 0.16], fill=accent)
    # head
    hx, hy = cx + sway, cy - s * 0.28
    draw.ellipse([hx - s * 0.16, hy - s * 0.16, hx + s * 0.16, hy + s * 0.16], fill=skin)
    # hair cap
    draw.pieslice([hx - s * 0.185, hy - s * 0.20, hx + s * 0.185, hy + s * 0.10],
                  start=180, end=360, fill=hair)
    # eyes
    ex = s * 0.065
    draw.ellipse([hx - ex - s * 0.025, hy - s * 0.02, hx - ex + s * 0.025, hy + s * 0.03],
                 fill="#1b1b1b")
    draw.ellipse([hx + ex - s * 0.025, hy - s * 0.02, hx + ex + s * 0.025, hy + s * 0.03],
                 fill="#1b1b1b")
    # arms
    draw.line([cx - s * 0.22 + sway, cy + s * 0.02, cx - s * 0.36 + sway, cy + s * 0.30],
              fill=outfit, width=max(2, int(s * 0.09)))
    draw.line([cx + s * 0.22 + sway, cy + s * 0.02, cx + s * 0.36 + sway, cy + s * 0.30],
              fill=outfit, width=max(2, int(s * 0.09)))
    # legs
    draw.line([cx - s * 0.10 + sway, cy + s * 0.52, cx - s * 0.12, cy + s * 0.85],
              fill="#26262b", width=max(2, int(s * 0.10)))
    draw.line([cx + s * 0.10 + sway, cy + s * 0.52, cx + s * 0.12, cy + s * 0.85],
              fill="#26262b", width=max(2, int(s * 0.10)))


def render(width: int = 1024, height: int = 1024, prompt: str = "",
           negative: str = "", style: str = "cinematic", seed: int = 0,
           steps: int = 28, guidance: float = 7.0, character: dict | None = None,
           base_image: Image.Image | None = None, t: float = 0.0,
           motion: float = 0.6, cam_x: float = 0.0, cam_y: float = 0.0,
           zoom: float = 1.0) -> Image.Image:
    """Render one still. All parameters are deterministic in `seed`."""
    rng = random.Random(seed)
    pal = make_palette(prompt, style, rng)
    w, h = int(width), int(height)

    # ---- base gradient sky -------------------------------------------------
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    top, bottom = pal[0], lerp_color(pal[1], (8, 8, 16), 0.55)
    band = 0.45 + 0.2 * math.sin(seed % 7)
    for y in range(h):
        p = y / max(1, h - 1)
        if p < band:
            d.line([(0, y), (w, y)], fill=lerp_color(top, pal[2], p / max(band, 1e-6)))
        else:
            d.line([(0, y), (w, y)],
                   fill=lerp_color(pal[2], bottom, (p - band) / max(1 - band, 1e-6)))

    # ---- luminous blobs (the scene's "subjects") ---------------------------
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    n_blobs = 6 + int(clamp(steps, 10, 50) / 8)
    for i in range(n_blobs):
        r = rng.uniform(0.08, 0.30) * min(w, h)
        bx = rng.uniform(-0.1, 1.1) * w
        by = rng.uniform(-0.05, 0.9) * h
        drift = motion * w * 0.10 * t * rng.choice([-1, 1])
        bx = (bx + drift) % (w + r)
        c = pal[rng.randrange(2, 5)]
        a = rng.randint(50, 120)
        ld.ellipse([bx - r, by - r, bx + r, by + r], fill=(*c, a))
    layer = layer.filter(ImageFilter.GaussianBlur(min(w, h) / 40))
    img.paste(layer, (0, 0), layer)

    # ---- geometric shards --------------------------------------------------
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for _ in range(10 + int(guidance)):
        pts = [(rng.uniform(0, w), rng.uniform(0, h)) for _ in range(rng.choice([3, 3, 4]))]
        c = pal[rng.randrange(0, 5)]
        ld.polygon(pts, fill=(*c, rng.randint(18, 70)), outline=(*c, rng.randint(30, 110)))
    img.paste(layer, (0, 0), layer)

    # ---- light streaks -----------------------------------------------------
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for _ in range(6):
        x0, y0 = rng.uniform(0, w), rng.uniform(0, h * 0.5)
        ang = rng.uniform(-0.6, 0.6) + math.pi / 4
        ln = rng.uniform(0.3, 0.9) * w
        x1, y1 = x0 + math.cos(ang) * ln, y0 + math.sin(ang) * ln
        c = pal[rng.randrange(2, 5)]
        ld.line([x0, y0, x1, y1], fill=(*c, rng.randint(25, 80)),
                width=rng.randint(1, max(2, int(min(w, h) / 120))))
    layer = layer.filter(ImageFilter.GaussianBlur(2))
    img.paste(layer, (0, 0), layer)

    # ---- bokeh / particles ---------------------------------------------------
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for _ in range(40):
        r = rng.uniform(1, max(2, min(w, h) / 60))
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        c = pal[rng.randrange(0, 5)]
        ld.ellipse([x - r, y - r, x + r, y + r], fill=(*c, rng.randint(40, 160)))
    layer = layer.filter(ImageFilter.GaussianBlur(1.5))
    img.paste(layer, (0, 0), layer)

    # ---- optional image-to-image structure --------------------------------
    if base_image is not None:
        ref = base_image.convert("RGB").resize((w, h)).filter(ImageFilter.GaussianBlur(6))
        img = Image.blend(img, ref, 0.45)

    # ---- character identity -------------------------------------------------
    if character:
        traits = character.get("traits", {})
        cscale = min(w, h) * 0.42
        draw_character(ImageDraw.Draw(img), w * 0.5 + cam_x * w * 0.1,
                       h * 0.62 + cam_y * h * 0.05, cscale, traits,
                       facing=1.0, pose_phase=t * 4.0)

    # ---- camera (applied to composition) ------------------------------------
    if abs(cam_x) > 1e-6 or abs(cam_y) > 1e-6 or abs(zoom - 1) > 1e-6:
        zw, zh = int(w / zoom), int(h / zoom)
        crop = img.resize((zw, zh)).crop((0, 0, min(zw, w), min(zh, h)))
        canvas = crop.resize((w, h))
        img = canvas

    # ---- style post-processing ------------------------------------------------
    if style == "anime":
        img = img.quantize(colors=24, method=Image.Quantize.FASTOCTREE,
                           dither=Image.Dither.NONE).convert("RGB")
        edges = img.convert("L").filter(ImageFilter.FIND_EDGES).point(lambda p: 255 - p * 2)
        img = Image.composite(Image.new("RGB", (w, h), (12, 12, 18)), img,
                              edges.filter(ImageFilter.GaussianBlur(1)))
        img = ImageEnhance.Color(img).enhance(1.25)
    elif style == "noir":
        img = img.convert("L").convert("RGB")
        img = ImageEnhance.Contrast(img).enhance(1.45)
        img = _vignette(img, 0.75)
    elif style == "watercolor":
        img = img.filter(ImageFilter.GaussianBlur(1.4))
        img = ImageEnhance.Color(img).enhance(0.85)
        img = ImageEnhance.Brightness(img).enhance(1.06)
    elif style == "neon":
        img = ImageEnhance.Color(img).enhance(1.5)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        img = _vignette(img, 0.6)
    elif style == "fantasy":
        img = ImageEnhance.Color(img).enhance(1.15)
        img = _vignette(img, 0.4)
    else:  # cinematic / vibrant
        img = ImageEnhance.Contrast(img).enhance(1.12)
        img = ImageEnhance.Color(img).enhance(1.25 if style == "vibrant" else 1.05)
        img = _vignette(img, 0.5)

    # negative-prompt soft suppression (MVP heuristic)
    if negative:
        neg = negative.lower()
        if "blur" in neg:
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=60))
        if "dark" in neg:
            img = ImageEnhance.Brightness(img).enhance(1.15)
        if "noisy" in neg or "grain" in neg:
            pass  # skip grain below
        else:
            img = _grain(img, rng, 8)
    else:
        img = _grain(img, rng, 8)

    return img.convert("RGB")
