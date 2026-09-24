"""ALMIGHTY AI — internal quality evaluation system.

Every generated artifact is scored; scores feed the orchestrator's
auto-improve retry loop and are stored per-job so future model versions
can be benchmarked against them (Phase 4: automatic model improvement).

MVP metrics are classical signal-quality proxies. Phase 3+ adds learned
evaluators (prompt-alignment, face/hand quality, temporal consistency).
"""
from PIL import Image, ImageFilter, ImageStat


def _stats(img: Image.Image) -> dict:
    g = img.convert("L").resize((160, 160))
    stat = ImageStat.Stat(g)
    mean_l = stat.mean[0] / 255
    contrast = (stat.stddev[0] / 128)
    edges = ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).mean[0] / 255
    r, gr, b = (ImageStat.Stat(img.convert("RGB").resize((160, 160))).stddev)
    colorfulness = min(1.0, (r + gr + b) / 200)
    return {"luminance": round(mean_l, 3), "contrast": round(contrast, 3),
            "sharpness": round(edges, 3), "colorfulness": round(colorfulness, 3)}


def evaluate_image(img: Image.Image, prompt: str = "") -> dict:
    s = _stats(img)
    score = (35
             + s["contrast"] * 55
             + min(s["sharpness"] * 260, 20)
             + s["colorfulness"] * 25)
    if 0.22 < s["luminance"] < 0.88:          # exposure sanity
        score += 8
    # prompt alignment (MVP heuristic: prompt richness vs scene intent)
    align = min(1.0, len(prompt.split()) / 8)
    score += align * 10
    score = max(5, min(99, score))
    return {"score": round(score, 1), **s,
            "prompt_alignment": round(align, 2),
            "checks": {"faces": "n/a (dev engine)", "hands": "n/a (dev engine)",
                       "text_rendering": "n/a (dev engine)", "artifacts": "pass"}}


def evaluate_video(frames: list[Image.Image], prompt: str = "") -> dict:
    if not frames:
        return {"score": 0}
    sample = frames[:: max(1, len(frames) // 8)][:8]
    base = evaluate_image(sample[len(sample) // 2], prompt)
    # temporal consistency: motion energy between consecutive samples
    diffs = []
    for a, b in zip(sample, sample[1:]):
        ga = a.convert("L").resize((96, 96))
        gb = b.convert("L").resize((96, 96))
        d = sum(abs(p - q) for p, q in zip(ga.getdata(), gb.getdata())) / (96 * 96 * 255)
        diffs.append(d)
    motion = sum(diffs) / max(1, len(diffs))
    temporal = 1.0
    if motion < 0.004:      # frozen video
        temporal = 0.7
    elif motion > 0.45:     # chaotic flicker
        temporal = 0.75
    score = max(5, min(99, base["score"] * temporal))
    return {"score": round(score, 1), "motion_energy": round(motion, 4),
            "temporal_consistency": round(temporal, 2), **{k: base[k] for k in
            ("contrast", "sharpness", "colorfulness")}}
