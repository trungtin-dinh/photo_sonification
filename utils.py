from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


# ============================================================
# Domain dataclasses
# ============================================================

@dataclass
class NoteEvent:
    start: float
    duration: float
    midi: int
    velocity: float
    instrument: str
    pan: float = 0.0
    layer: str = "other"


@dataclass
class CompositionInfo:
    tempo: float
    bars: int
    duration: float
    key_name: str
    scale_name: str
    main_instrument: str
    texture_instrument: str
    bass_instrument: str
    pad_instrument: str
    chord_instrument: str
    solo_instrument: str
    mood: str
    mapping_summary: Dict[str, str]


# ============================================================
# Scalar helpers
# ============================================================

def clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


def normalize01(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    lo = float(np.min(x)) if x.size else 0.0
    hi = float(np.max(x)) if x.size else 0.0
    if hi - lo < 1e-12:
        return np.zeros_like(x, dtype=np.float64)
    return (x - lo) / (hi - lo)


def midi_to_freq(midi_note: float) -> float:
    return 440.0 * (2.0 ** ((float(midi_note) - 69.0) / 12.0))


# ============================================================
# Parameter accessors  (safe dict look-ups with range clamping)
# ============================================================

def get_param(params: Optional[Dict[str, object]], key: str, default: object) -> object:
    """Read one optional user parameter with a safe fallback."""
    if not isinstance(params, dict):
        return default
    return params.get(key, default)


def get_float_param(
    params: Optional[Dict[str, object]], key: str, default: float, lo: float, hi: float
) -> float:
    try:
        value = float(get_param(params, key, default))
    except Exception:
        value = default
    return clamp(value, lo, hi)


def get_int_param(
    params: Optional[Dict[str, object]], key: str, default: int, lo: int, hi: int
) -> int:
    try:
        value = int(round(float(get_param(params, key, default))))
    except Exception:
        value = default
    return int(clamp(value, lo, hi))


def arrange_pair(a: float, b: float, lo: float, hi: float, min_gap: float = 0.0) -> Tuple[float, float]:
    """Sort and clamp a min/max pair, preserving a minimum gap when possible."""
    x, y = sorted([float(a), float(b)])
    x = clamp(x, lo, hi)
    y = clamp(y, lo, hi)
    min_gap = max(0.0, float(min_gap))
    if y < x + min_gap:
        mid = clamp(0.5 * (x + y), lo, hi)
        x = clamp(mid - 0.5 * min_gap, lo, hi)
        y = clamp(mid + 0.5 * min_gap, lo, hi)
        if y < x + min_gap:
            x = max(lo, y - min_gap)
            y = min(hi, x + min_gap)
    return float(x), float(y)


def get_range_param(
    params: Optional[Dict[str, object]],
    key: str,
    default: Tuple[float, float],
    lo: float,
    hi: float,
    min_gap: float = 0.0,
) -> Tuple[float, float]:
    raw = get_param(params, key, default)
    try:
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            return arrange_pair(float(raw[0]), float(raw[1]), lo, hi, min_gap)
    except Exception:
        pass
    return arrange_pair(float(default[0]), float(default[1]), lo, hi, min_gap)


def normalize_positive_weights(
    values: Dict[str, float], fallback: Dict[str, float]
) -> Dict[str, float]:
    cleaned = {k: max(0.0, float(v)) for k, v in values.items()}
    total = float(sum(cleaned.values()))
    if total <= 1e-12:
        cleaned = {k: max(0.0, float(v)) for k, v in fallback.items()}
        total = float(sum(cleaned.values()))
    if total <= 1e-12:
        n = max(1, len(cleaned))
        return {k: 1.0 / n for k in cleaned}
    return {k: v / total for k, v in cleaned.items()}


# ============================================================
# Step-callback helper
# ============================================================

def emit_step(step_callback, label: str) -> None:
    if step_callback is not None:
        step_callback(label)


# ============================================================
# Signature helper  (used by UI caching logic)
# ============================================================

def make_signature(**kwargs: object) -> str:
    return hashlib.sha256(
        json.dumps(kwargs, sort_keys=True, default=str).encode()
    ).hexdigest()
