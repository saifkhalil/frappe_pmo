"""Pure math helpers for OKR progress.

No `frappe` import — safe to use from unit tests and other contexts.
"""
from __future__ import annotations


def kr_progress_pct(start: float, current: float, target: float, direction: str) -> float:
    """Return progress percentage 0..100 with clamping.

    - Increase: (current - start) / (target - start)
    - Decrease: (start - current) / (start - target)
    - Maintain: 100 if current == target else 0
    """
    if direction == "Maintain":
        return 100.0 if abs(current - target) < 1e-9 else 0.0

    denom = (target - start) if direction != "Decrease" else (start - target)
    if abs(denom) < 1e-9:
        return 100.0 if abs(current - target) < 1e-9 else 0.0

    numer = (current - start) if direction != "Decrease" else (start - current)
    pct = (numer / denom) * 100.0
    return max(0.0, min(100.0, round(pct, 2)))


def weighted_average(values_weights: list[tuple[float, float]]) -> float:
    """Weighted average of (value, weight) pairs. Falls back to mean if total
    weight is zero. Empty input returns 0."""
    if not values_weights:
        return 0.0
    total = sum(w for _, w in values_weights)
    if total <= 0:
        return round(sum(v for v, _ in values_weights) / len(values_weights), 2)
    return round(sum(v * w for v, w in values_weights) / total, 2)
