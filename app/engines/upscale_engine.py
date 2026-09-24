"""ALMIGHTY UPSCALE — super-resolution engine (v0.1.0-dev).

MVP backend: high-quality Lanczos resampling + detail recovery pass.
Phase 3 swaps in the trained ALMIGHTY UPSCALE network behind the same call.
"""
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

from . import clamp


def upscale(input_image: Image.Image, scale: float = 2.0, enhance: bool = True) -> Image.Image:
    scale = clamp(scale, 1, 4)
    w, h = input_image.size
    out = input_image.convert("RGB").resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    if enhance:
        out = out.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=3))
        out = ImageEnhance.Contrast(out).enhance(1.05)
        out = ImageEnhance.Color(out).enhance(1.04)
    return out


def upscale_file(input_path: str, scale: float, out_base: Path) -> tuple[str, str]:
    img = Image.open(input_path)
    out = upscale(img, scale)
    out_path = out_base.with_suffix(".png")
    out.save(out_path, optimize=True)
    return str(out_path), "image/png"
