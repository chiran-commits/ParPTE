"""Aggregate item scores into PTE-style 10–90 communicative-skill scores.

Pearson converts raw item scores with an IRT model calibrated on millions of test takers; that model is
not public. We use a transparent approximation: a weighted proportion of available points per skill
(using each task's integrated-skill contributions), mapped onto 10–90. `CURVE` can be re-fit once you
have real PTE results to compare against (see docs/SCORING.md).
"""
from __future__ import annotations

import bisect

from ..tasks import MODULES, TASKS

# (proportion of points, PTE score) anchor points — piecewise linear. Slightly convex at the top,
# reflecting that 79+ ("superior") needs near-complete accuracy on integrated items.
CURVE = [(0.0, 10), (0.2, 30), (0.4, 47), (0.55, 58), (0.7, 68), (0.8, 76), (0.88, 82), (0.94, 87), (1.0, 90)]


def to_pte(p: float) -> int:
    p = max(0.0, min(1.0, p))
    xs = [x for x, _ in CURVE]
    i = bisect.bisect_right(xs, p)
    if i >= len(CURVE):
        return 90
    (x0, y0), (x1, y1) = CURVE[i - 1], CURVE[i]
    return round(y0 + (y1 - y0) * (p - x0) / (x1 - x0))


def _ratio(item: dict, trait: str | None) -> float | None:
    if trait:
        t = next((t for t in item.get("traits", []) if t["name"] == trait), None)
        return t["score"] / t["max"] if t and t["max"] else None
    return item["score"] / item["max"] if item.get("max") else None


def aggregate(items: list[dict]) -> dict:
    """items: [{"task": str, "score": float, "max": float, "traits": [...]}, ...]"""
    num = {m: 0.0 for m in MODULES}
    den = {m: 0.0 for m in MODULES}
    profile: dict[str, list[float]] = {}
    for it in items:
        meta = TASKS.get(it["task"])
        if not meta or not meta.get("scored"):
            continue
        for skill, trait, w in meta["skills"]:
            r = _ratio(it, trait)
            if r is None:
                continue
            num[skill] += w * r
            den[skill] += w
        for t in it.get("traits", []):
            if t["max"]:
                profile.setdefault(t["name"], []).append(t["score"] / t["max"])
    skills = {m: (to_pte(num[m] / den[m]) if den[m] else None) for m in MODULES}
    have = [v for v in skills.values() if v is not None]
    overall = round(sum(have) / len(have)) if have else None
    prof = {k: round(100 * sum(v) / len(v)) for k, v in profile.items() if k not in {"Correctness", "Words"}}
    return {"overall": overall, "skills": skills, "profile": prof, "items": len(items)}


def item_band(item: dict) -> int | None:
    return to_pte(item["score"] / item["max"]) if item.get("max") else None
