"""ALMIGHTY AI — engine shared helpers.

This package hosts ALMIGHTY_MODEL_ENGINE: the internal abstraction every
generation model implements. During MVP the engines are deterministic local
procedural renderers (zero external APIs). In Phase 3 they are replaced,
in-place, by the trained ALMIGHTY weights behind the exact same interface.
"""
import hashlib


def hash01(s: str) -> float:
    """Stable string -> [0,1)."""
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF


def clamp(v, lo, hi):
    try:
        v = float(v)
    except (TypeError, ValueError):
        v = lo
    return max(lo, min(hi, v))


def parse_seed(value, prompt: str = "") -> int:
    """Accept an explicit seed, or derive a stable one from the prompt."""
    try:
        s = int(value)
        if 0 <= s <= 2**31:
            return s
    except (TypeError, ValueError):
        pass
    return int(hash01(prompt or "almighty") * 1_000_000)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))
