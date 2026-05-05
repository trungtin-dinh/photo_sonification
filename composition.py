from __future__ import annotations

import hashlib
import json
import math
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from config import (
    GM_FAMILY_RANGES,
    GM_NAMES,
    GM_PROGRAM_TO_FAMILY,
    GM_PROGRAMS,
    GENERALUSER_GS_DISPLAY_TO_INTERNAL,
    GENERALUSER_GS_INTERNAL_TO_DISPLAY,
    GENERALUSER_GS_LAYER_POOLS,
    KEY_NAMES,
    LAYER_CHANNELS,
    PERCUSSION_NOTES,
    SCALES,
    SIMPLE_DISPLAY_TO_INTERNAL,
    SIMPLE_INTERNAL_TO_DISPLAY,
    SYNTH_GENERALUSER_GS,
    SYNTH_SIMPLE,
)
from utils import (
    NoteEvent,
    CompositionInfo,
    clamp,
    emit_step,
    get_float_param,
    get_int_param,
    get_range_param,
    normalize_positive_weights,
)


# ============================================================
# Instrument label/key conversion helpers
# ============================================================

def get_instrument_choices(synthesizer_type: str) -> List[str]:
    return (
        sorted(GENERALUSER_GS_DISPLAY_TO_INTERNAL.keys())
        if synthesizer_type == SYNTH_GENERALUSER_GS
        else sorted(SIMPLE_DISPLAY_TO_INTERNAL.keys())
    )


def get_instrument_choices_with_none(synthesizer_type: str) -> List[str]:
    return ["None"] + get_instrument_choices(synthesizer_type)


def instrument_key(name: str, synthesizer_type: str) -> str:
    if name == "None":
        return "none"
    if synthesizer_type == SYNTH_GENERALUSER_GS:
        return GENERALUSER_GS_DISPLAY_TO_INTERNAL.get(name, "gm_000")
    return SIMPLE_DISPLAY_TO_INTERNAL.get(name, "soft_piano")


def instrument_label(name: str) -> str:
    if name == "none":
        return "—"
    if name.startswith("gm_"):
        return GENERALUSER_GS_INTERNAL_TO_DISPLAY.get(name, name)
    return SIMPLE_INTERNAL_TO_DISPLAY.get(name, name).lower()


# ============================================================
# Automatic bar-count estimation
# ============================================================

def compute_bar_settings(
    features: Dict[str, float], params: Optional[Dict[str, object]] = None
) -> Tuple[int, int, int]:
    defaults = {"texture": 0.40, "edge": 0.25, "high": 0.20, "peak": 0.15}
    weights = normalize_positive_weights(
        {
            "texture": get_float_param(params, "bar_weight_texture", 0.40, 0.0, 5.0),
            "edge": get_float_param(params, "bar_weight_edge", 0.25, 0.0, 5.0),
            "high": get_float_param(params, "bar_weight_high_frequency", 0.20, 0.0, 5.0),
            "peak": get_float_param(params, "bar_weight_periodicity", 0.15, 0.0, 5.0),
        },
        defaults,
    )
    score = clamp(
        weights["texture"] * features.get("texture_entropy", 0.0)
        + weights["edge"] * features.get("edge_density", 0.0)
        + weights["high"] * features.get("high_frequency_energy", 0.0)
        + weights["peak"] * features.get("periodic_peak_score", 0.0),
        0.0,
        1.0,
    )
    min_lo, min_hi = get_range_param(params, "auto_bar_min_range", (4.0, 8.0), 1.0, 32.0, 1.0)
    max_lo, max_hi = get_range_param(params, "auto_bar_max_range", (12.0, 24.0), 2.0, 64.0, 1.0)
    def_lo, def_hi = get_range_param(params, "auto_bar_default_range", (6.0, 16.0), 1.0, 64.0, 1.0)
    mn = int(round(np.interp(score, [0, 1], [min_lo, min_hi])))
    mx = int(round(np.interp(score, [0, 1], [max_lo, max_hi])))
    if mx <= mn:
        mx = mn + 1
    df = int(round(np.interp(score, [0, 1], [def_lo, def_hi])))
    return int(clamp(mn, 1, 64)), int(clamp(mx, mn + 1, 64)), int(clamp(df, mn, mx))


# ============================================================
# Deterministic scoring helpers for instrument selection
# ============================================================

def feature_seed(features: Dict[str, float], layer: str, salt: str = "") -> int:
    values = [
        layer, salt,
        round(float(features.get("dominant_hue", 0.0)), 4),
        round(float(features.get("mean_brightness", 0.0)), 4),
        round(float(features.get("contrast", 0.0)), 4),
        round(float(features.get("mean_saturation", 0.0)), 4),
        round(float(features.get("warmth", 0.0)), 4),
        round(float(features.get("edge_density", 0.0)), 4),
        round(float(features.get("texture_entropy", 0.0)), 4),
        round(float(features.get("low_frequency_energy", 0.0)), 4),
        round(float(features.get("high_frequency_energy", 0.0)), 4),
        round(float(features.get("periodic_peak_score", 0.0)), 4),
        round(float(features.get("shadow_proportion", 0.0)), 4),
        round(float(features.get("highlight_proportion", 0.0)), 4),
        round(float(features.get("symmetry_score", 0.0)), 4),
        round(float(features.get("saliency_peak", 0.0)), 4),
        round(float(features.get("saliency_centroid_x", 0.0)), 4),
        round(float(features.get("saliency_centroid_y", 0.0)), 4),
    ]
    digest = hashlib.sha256(json.dumps(values, sort_keys=True).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def deterministic_unit(seed: int, program: int, layer: str) -> float:
    digest = hashlib.sha256(f"{seed}:{program}:{layer}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(16 ** 12 - 1)


def gm_family_weight(layer: str, family: str, features: Dict[str, float]) -> float:
    b    = float(features.get("mean_brightness", 0.5))
    c    = float(features.get("contrast", 0.0))
    sat  = float(features.get("mean_saturation", 0.0))
    warm = float(features.get("warmth", 0.0))
    sh   = float(features.get("shadow_proportion", 0.0))
    h    = float(features.get("highlight_proportion", 0.0))
    edge = float(features.get("edge_density", 0.0))
    tex  = float(features.get("texture_entropy", 0.0))
    lo   = float(features.get("low_frequency_energy", 0.0))
    hi   = float(features.get("high_frequency_energy", 0.0))
    peak = float(features.get("periodic_peak_score", 0.0))
    sym  = float(features.get("symmetry_score", 0.5))
    sal_peak   = float(features.get("saliency_peak", 0.0))
    sal_spread = float(features.get("saliency_spread", 0.0))

    smooth      = clamp(lo + 0.35 * (1.0 - hi) + 0.25 * sym, 0.0, 1.0)
    detail      = clamp(0.45 * hi + 0.30 * edge + 0.25 * tex, 0.0, 1.0)
    brightness  = clamp(0.55 * b + 0.45 * h, 0.0, 1.0)
    darkness    = clamp(0.55 * (1.0 - b) + 0.45 * sh, 0.0, 1.0)
    colorfulness = clamp(0.65 * sat + 0.35 * abs(warm), 0.0, 1.0)

    if layer == "main":
        weights = {
            "piano": .35 + .35 * smooth, "chromatic_percussion": .18 + .65 * brightness + .25 * detail,
            "organ": .18 + .35 * smooth + .20 * darkness, "guitar": .16 + .35 * colorfulness + .22 * warm,
            "solo_strings": .20 + .35 * darkness + .20 * smooth, "brass": .12 + .50 * c + .35 * brightness,
            "reed": .18 + .28 * darkness + .20 * detail, "pipe": .18 + .45 * brightness + .20 * smooth,
            "synth_lead": .10 + .55 * detail + .30 * c, "ethnic": .12 + .42 * colorfulness + .45 * peak,
        }
    elif layer == "texture":
        weights = {
            "chromatic_percussion": .25 + .70 * brightness + .45 * hi,
            "guitar": .18 + .30 * colorfulness + .25 * edge,
            "solo_strings": .12 + .40 * peak + .25 * detail,
            "synth_fx": .12 + .55 * detail + .30 * c,
            "ethnic": .18 + .55 * peak + .25 * colorfulness,
            "percussive": .14 + .55 * edge + .35 * peak,
            "sound_fx": .04 + .50 * detail + .35 * c,
        }
    elif layer == "bass":
        weights = {
            "bass": .45 + .50 * lo + .25 * darkness,
            "organ": .18 + .35 * smooth + .30 * darkness,
            "solo_strings": .20 + .45 * darkness + .25 * smooth,
            "brass": .12 + .40 * c + .35 * darkness,
            "synth_lead": .08 + .35 * detail + .20 * peak,
            "percussive": .08 + .45 * edge + .30 * peak,
        }
    elif layer == "pad":
        weights = {
            "organ": .18 + .42 * smooth + .20 * darkness,
            "solo_strings": .22 + .50 * darkness + .25 * smooth,
            "ensemble": .28 + .55 * smooth + .20 * sym,
            "synth_pad": .30 + .60 * smooth + .20 * colorfulness,
            "synth_fx": .12 + .35 * detail + .35 * colorfulness,
            "sound_fx": .04 + .35 * detail + .30 * c,
        }
    elif layer == "solo":
        weights = {
            "chromatic_percussion": .24 + .52 * brightness + .30 * sal_peak,
            "solo_strings": .22 + .30 * darkness + .26 * sal_spread,
            "reed": .20 + .36 * sal_peak + .20 * detail,
            "pipe": .22 + .42 * brightness + .30 * sal_peak,
            "synth_lead": .16 + .50 * detail + .30 * c,
            "ethnic": .18 + .42 * colorfulness + .30 * peak,
            "guitar": .14 + .35 * colorfulness,
            "brass": .10 + .38 * c + .25 * brightness,
            "synth_fx": .08 + .35 * detail + .35 * sal_spread,
        }
    else:  # chord
        weights = {
            "piano": .35 + .35 * smooth + .20 * brightness,
            "organ": .18 + .35 * smooth + .25 * darkness,
            "guitar": .18 + .35 * colorfulness + .15 * warm,
            "solo_strings": .16 + .35 * darkness + .25 * smooth,
            "ensemble": .24 + .45 * smooth + .25 * sym,
            "brass": .10 + .45 * c + .30 * brightness,
            "synth_pad": .18 + .45 * smooth + .25 * colorfulness,
        }
    return float(weights.get(family, 0.05))


def gm_program_affinity(program: int, layer: str, features: Dict[str, float]) -> float:
    family = GM_PROGRAM_TO_FAMILY.get(program, "unknown")
    score = gm_family_weight(layer, family, features)
    h    = float(features.get("highlight_proportion", 0.0))
    sh   = float(features.get("shadow_proportion", 0.0))
    hi   = float(features.get("high_frequency_energy", 0.0))
    lo   = float(features.get("low_frequency_energy", 0.0))
    peak = float(features.get("periodic_peak_score", 0.0))
    sal  = float(features.get("saliency_peak", 0.0))
    if program in {8, 9, 10, 11, 14, 98, 112}:
        score += 0.18 * h + 0.15 * hi + 0.12 * sal
    if program in {12, 13, 108, 114, 115}:
        score += 0.16 * peak + 0.12 * hi
    if program in {32, 33, 34, 35, 36, 37, 38, 39, 42, 43, 58}:
        score += 0.22 * sh + 0.20 * lo
    if program in {48, 49, 50, 51, 52, 53, 54, 88, 89, 90, 91, 92, 93, 94, 95}:
        score += 0.18 * lo + 0.10 * (1.0 - hi)
    if program in {72, 73, 74, 75, 76, 77, 78, 79, 104, 105, 106, 107, 109, 110, 111}:
        score += 0.16 * sal
    return score


def select_generaluser_instrument(
    features: Dict[str, float], layer: str, avoid: Optional[Set[int]] = None
) -> str:
    avoid = set() if avoid is None else set(avoid)
    pool = GENERALUSER_GS_LAYER_POOLS.get(layer, list(range(128)))
    seed = feature_seed(features, layer, "generaluser_gs")
    best_program = pool[0]
    best_score = -1e9
    for program in pool:
        if program in avoid and len(pool) > len(avoid):
            continue
        jitter = 0.42 * deterministic_unit(seed, program, layer)
        score = gm_program_affinity(program, layer, features) + jitter
        if score > best_score:
            best_score = score
            best_program = program
    return GENERALUSER_GS_DISPLAY_TO_INTERNAL.get(GM_NAMES[best_program], f"gm_{best_program:03d}")


# ============================================================
# Scale and instrument selection
# ============================================================

def choose_scale(features: Dict[str, float], requested_scale: str) -> str:
    if requested_scale != "Automatic" and requested_scale in SCALES:
        return requested_scale
    b, sat, warm, c = (
        features["mean_brightness"],
        features["mean_saturation"],
        features["warmth"],
        features["contrast"],
    )
    if b > 0.60:
        return "Lydian" if warm > 0.06 else "Major pentatonic"
    if b > 0.42:
        return "Dorian" if (warm > 0.06 and sat > 0.38) or c > 0.22 else "Major pentatonic"
    return "Dorian" if warm > 0.05 and sat > 0.30 else "Natural minor"


def choose_instruments(
    features: Dict[str, float],
    mode: str,
    synthesizer_type: str,
    main: str = "Soft piano",
    texture: str = "Harp",
    bass: str = "Cello-like bass",
    pad: str = "Warm pad",
    chord: str = "Soft piano",
    solo: str = "Flute",
) -> Tuple[str, str, str, str, str, str]:
    if mode == "Manual":
        if synthesizer_type == SYNTH_GENERALUSER_GS:
            return tuple(instrument_key(x, synthesizer_type) for x in (main, texture, bass, pad, chord, solo))  # type: ignore[return-value]
        return (
            instrument_key(main, synthesizer_type),
            instrument_key(texture, synthesizer_type),
            instrument_key(bass, synthesizer_type),
            instrument_key(pad, synthesizer_type),
            instrument_key(chord, synthesizer_type),
            "none",
        )
    b, h, sh = features["mean_brightness"], features["highlight_proportion"], features["shadow_proportion"]
    hi, lo, peak, sat, warm, c = (
        features["high_frequency_energy"],
        features["low_frequency_energy"],
        features["periodic_peak_score"],
        features["mean_saturation"],
        features["warmth"],
        features["contrast"],
    )
    if synthesizer_type == SYNTH_GENERALUSER_GS:
        selected: Set[int] = set()
        out = []
        for layer in ["main", "texture", "bass", "pad", "chord", "solo"]:
            inst = select_generaluser_instrument(features, layer, selected)
            try:
                selected.add(int(inst.split("_", 1)[1]))
            except Exception:
                pass
            out.append(inst)
        return tuple(out)  # type: ignore[return-value]
    main_i  = "bright_bell" if h > 0.14 and hi > 0.28 else "celesta" if b > 0.64 else "kalimba" if peak > 0.58 else "marimba" if peak > 0.48 else "harp" if warm > 0.07 and sat > 0.42 else "synth_pluck" if c > 0.25 and hi > 0.28 else "soft_piano"
    tex_i   = "bright_bell" if hi > 0.44 or h > 0.16 else "celesta" if hi > 0.32 else "kalimba" if peak > 0.55 else "harp" if sat > 0.45 and warm > 0.02 else "music_box"
    bass_i  = "cello" if sh > 0.26 or b < 0.36 else "soft_bass"
    pad_i   = "warm_pad" if (lo > 0.52 and warm > 0.04) or sh > 0.20 else "glass_pad"
    chord_i = "soft_piano" if main_i != "soft_piano" else "harp"
    return main_i, tex_i, bass_i, pad_i, chord_i, "none"


def describe_mood(features: Dict[str, float]) -> str:
    light    = "bright" if features["mean_brightness"] > 0.58 else "dark" if features["mean_brightness"] < 0.40 else "balanced"
    color    = "warm" if features["warmth"] > 0.04 else "cool" if features["warmth"] < -0.04 else "neutral"
    contrast = "dynamic" if features["contrast"] > 0.24 else "soft" if features["contrast"] < 0.13 else "moderately dynamic"
    texture  = "textured" if features["high_frequency_energy"] > 0.32 else "smooth" if features["high_frequency_energy"] < 0.18 else "moderately textured"
    focus    = "focused" if features.get("saliency_area", 0.0) < 0.08 and features.get("saliency_peak", 0.0) > 0.75 else "diffuse"
    return f"{light}, {color}, {contrast}, {texture}, {focus}"


# ============================================================
# Scale and chord helpers
# ============================================================

def build_scale_notes(root: int, intervals: List[int], low: int, high: int) -> List[int]:
    out = []
    for octave in range(-3, 7):
        for interval in intervals:
            n = root + 12 * octave + interval
            if low <= n <= high:
                out.append(n)
    return sorted(set(out))


def chord_from_scale_degree(intervals: List[int], degree: int) -> List[int]:
    n = len(intervals)
    def at(step: int) -> int:
        return intervals[step % n] + 12 * (step // n)
    return [at(degree), at(degree + 2), at(degree + 4)]


def choose_progression(scale_name: str, features: Dict[str, float]) -> List[List[int]]:
    intervals = SCALES.get(scale_name, SCALES["Major pentatonic"])
    n = len(intervals)
    seed = int(
        features["dominant_hue"] * 997
        + features["periodic_peak_score"] * 113
        + features.get("texture_entropy", 0.0) * 71
        + features.get("saliency_centroid_x", 0.0) * 53
    )
    if n >= 7:
        pools = [[0, 4, 5, 3], [0, 5, 3, 4], [0, 2, 5, 4], [0, 3, 1, 4]]
    else:
        pools = [[0, 2, 3, 4], [0, 3, 2, 1], [0, 1, 4, 2]]
    return [chord_from_scale_degree(intervals, d % n) for d in pools[seed % len(pools)]]


# ============================================================
# Time-slice statistics for melody generation
# ============================================================

def time_slice_statistics(luminance: np.ndarray, n_slices: int) -> List[Dict[str, float]]:
    h, w = luminance.shape
    stats = []
    for i in range(n_slices):
        x0 = int(round(i * w / n_slices))
        x1 = max(1, int(round((i + 1) * w / n_slices)))
        sl = luminance[:, x0:max(x0 + 1, x1)]
        weights = np.maximum(sl - np.percentile(sl, 35), 0.0)
        if float(np.sum(weights)) <= 1e-12:
            yc = 0.5
        else:
            yy = np.arange(h).reshape(-1, 1)
            yc = float(np.sum(yy * weights) / np.sum(weights)) / max(1, h - 1)
        stats.append({"energy": float(np.mean(sl)), "contrast": float(np.std(sl)), "y_centroid": yc})
    return stats


# ============================================================
# Saliency-driven solo layer
# ============================================================

def add_saliency_solo_events(
    events: List[NoteEvent],
    maps: Dict[str, np.ndarray],
    features: Dict[str, float],
    melody_notes: List[int],
    duration: float,
    beat: float,
    solo_inst: str,
    solo_gain_db: float,
    params: Optional[Dict[str, object]] = None,
) -> None:
    if solo_inst == "none" or not melody_notes:
        return
    sal = np.asarray(maps.get("saliency_map"), dtype=np.float64)
    if sal.size == 0 or float(np.max(sal)) <= 1e-12:
        return
    h, w = sal.shape
    strength_defaults = {"peak": 0.55, "mean": 0.25, "area_inverse": 0.20}
    strength_weights = normalize_positive_weights(
        {
            "peak": get_float_param(params, "solo_saliency_peak_weight", 0.55, 0.0, 5.0),
            "mean": get_float_param(params, "solo_saliency_mean_weight", 0.25, 0.0, 5.0),
            "area_inverse": get_float_param(params, "solo_saliency_area_inverse_weight", 0.20, 0.0, 5.0),
        },
        strength_defaults,
    )
    sal_strength = clamp(
        strength_weights["peak"] * features.get("saliency_peak", 0.0)
        + strength_weights["mean"] * features.get("saliency_mean", 0.0)
        + strength_weights["area_inverse"] * (1.0 - features.get("saliency_area", 0.0)),
        0.0,
        1.0,
    )
    note_lo, note_hi = get_range_param(params, "solo_note_count_range", (3.0, 18.0), 1.0, 48.0, 1.0)
    note_cap = get_int_param(params, "solo_note_cap", 22, 1, 64)
    n_notes = int(round(np.interp(sal_strength, [0.0, 1.0], [note_lo, note_hi])))
    n_notes = int(clamp(n_notes, 1, note_cap))
    candidate_multiplier = get_int_param(params, "solo_candidate_multiplier", 18, 4, 64)
    candidate_count = min(sal.size, max(64, n_notes * candidate_multiplier))
    flat = np.argpartition(sal.ravel(), -candidate_count)[-candidate_count:]
    coords = [np.unravel_index(int(k), sal.shape) for k in flat]
    coords = sorted(coords, key=lambda rc: float(sal[rc[0], rc[1]]), reverse=True)
    picked: List[Tuple[int, int]] = []
    min_dist = get_float_param(params, "solo_min_distance", 0.055, 0.0, 0.50)
    for yy, xx in coords:
        xn = xx / max(1, w - 1)
        yn = yy / max(1, h - 1)
        if all(math.hypot(xn - px / max(1, w - 1), yn - py / max(1, h - 1)) >= min_dist for py, px in picked):
            picked.append((yy, xx))
        if len(picked) >= n_notes:
            break
    picked = sorted(picked, key=lambda rc: rc[1])
    gain = 10.0 ** (float(solo_gain_db) / 20.0)
    dur_min, dur_max = get_range_param(params, "solo_duration_beats_range", (0.18, 1.25), 0.05, 4.0, 0.05)
    for k, (yy, xx) in enumerate(picked):
        x_norm  = xx / max(1, w - 1)
        y_norm  = yy / max(1, h - 1)
        strength = float(sal[yy, xx])
        t = clamp(x_norm * duration + 0.10 * beat * math.sin(1.7 * k), 0.0, max(0.0, duration - 0.25))
        note = melody_notes[int(round(clamp(1.0 - y_norm, 0.0, 1.0) * (len(melody_notes) - 1)))] + 12
        if k % 5 == 3:
            note += 7
        dur = clamp(
            (0.32 + 0.70 * strength + 0.20 * features.get("saliency_spread", 0.0)) * beat,
            dur_min * beat,
            dur_max * beat,
        )
        vel = clamp((0.18 + 0.56 * strength) * gain, 0.05, 0.92)
        pan = clamp(-0.82 + 1.64 * x_norm, -0.9, 0.9)
        events.append(NoteEvent(t, dur, int(clamp(note, 48, 112)), vel, solo_inst, pan, "solo"))


# ============================================================
# Main composition generator
# ============================================================

def generate_composition(
    analysis: Dict[str, object],
    bars: int,
    complexity: float,
    variation: float,
    requested_scale: str,
    synthesizer_type: str,
    instrument_mode: str,
    main_layer: str,
    texture_layer: str,
    bass_layer: str,
    pad_layer: str,
    chord_layer: str,
    solo_layer: str,
    mapping_style: str,
    manual_bpm: Optional[float],
    main_gain_db: float,
    texture_gain_db: float,
    bass_gain_db: float,
    pad_gain_db: float,
    chord_gain_db: float,
    solo_gain_db: float,
    params: Optional[Dict[str, object]] = None,
    step_callback=None,
) -> Tuple[List[NoteEvent], CompositionInfo]:
    from config import MAX_RENDER_SECONDS  # local import to avoid circular at module level

    features: Dict[str, float] = analysis["features"]  # type: ignore[assignment]
    maps: Dict[str, np.ndarray] = analysis["maps"]  # type: ignore[assignment]
    lum = maps["luminance"]
    b, c, sh = features["mean_brightness"], features["contrast"], features["shadow_proportion"]
    edge, sat, warm = features["edge_density"], features["mean_saturation"], features["warmth"]
    lo, hi, centroid, bw, peak = (
        features["low_frequency_energy"],
        features["high_frequency_energy"],
        features["fourier_centroid"],
        features["fourier_bandwidth"],
        features["periodic_peak_score"],
    )

    emit_step(step_callback, "Tonal mapping: key, scale and tempo")
    key_index = int(round(features["dominant_hue"] * 12.0)) % 12
    key_name  = KEY_NAMES[key_index]
    scale_name = choose_scale(features, requested_scale)
    intervals  = SCALES[scale_name]
    root = int(clamp(48 + key_index + round(np.interp(b, [0, 1], [-5, 7])), 38, 58))

    sci_lo, sci_hi = get_range_param(params, "tempo_scientific_range", (48.0, 152.0), 1.0, 240.0, 1.0)
    bal_lo, bal_hi = get_range_param(params, "tempo_balanced_range", (56.0, 132.0), 1.0, 240.0, 1.0)
    mus_lo, mus_hi = get_range_param(params, "tempo_musical_range", (72.0, 108.0), 1.0, 240.0, 1.0)
    manual_min = get_float_param(params, "manual_bpm_min", 1.0, 1.0, 240.0)
    if mapping_style == "Manual" and manual_bpm is not None:
        tempo = max(manual_min, float(manual_bpm))
    elif mapping_style == "Scientific":
        tempo = clamp(50 + 70 * edge + 58 * c + 42 * peak + 34 * hi + 22 * centroid - 20 * sh, sci_lo, sci_hi)
    elif mapping_style == "Musical":
        tempo = clamp(82 + 10 * sat + 8 * b - 6 * sh + 4 * warm, mus_lo, mus_hi)
    else:
        tempo = clamp(62 + 38 * edge + 28 * c + 20 * peak + 10 * hi - 8 * sh, bal_lo, bal_hi)
    beat  = 60.0 / tempo
    bars  = int(clamp(int(bars), 1, 64))
    max_render_seconds = get_float_param(params, "max_render_seconds", MAX_RENDER_SECONDS, 8.0, 240.0)
    duration = min(max_render_seconds, bars * 4 * beat)

    emit_step(step_callback, "Instrument scoring and layer assignment")
    main_i, tex_i, bass_i, pad_i, chord_i, solo_i = choose_instruments(
        features, instrument_mode, synthesizer_type,
        main_layer, texture_layer, bass_layer, pad_layer, chord_layer, solo_layer,
    )
    if synthesizer_type != SYNTH_GENERALUSER_GS:
        solo_i = "none"

    emit_step(step_callback, "Chord progression and scale-note lattice")
    progression  = choose_progression(scale_name, features)
    melody_notes = build_scale_notes(root, intervals, root + 10, root + 31)
    bass_notes   = build_scale_notes(root, intervals, root - 18, root + 7)
    events: List[NoteEvent] = []
    pan_bias   = np.interp(features["bright_centroid_x"], [0, 1], [-0.45, 0.45])
    shadow_pan = np.interp(features["shadow_centroid_x"], [0, 1], [-0.35, 0.35])
    pad_velocity   = clamp(0.07 + 0.18 * lo + 0.04 * (1 - hi), 0.04, 0.28)
    chord_velocity = clamp(0.28 + 0.42 * b + 0.18 * lo, 0.22, 0.78)
    bass_velocity  = clamp(0.30 + 0.55 * sh + 0.25 * lo, 0.22, 0.86)
    melody_velocity = clamp(0.30 + 0.30 * features["dynamic_range"] + 0.20 * c + 0.15 * sat, 0.28, 0.90)
    gains = {
        "main":    10 ** (main_gain_db / 20),
        "texture": 10 ** (texture_gain_db / 20),
        "bass":    10 ** (bass_gain_db / 20),
        "pad":     10 ** (pad_gain_db / 20),
        "chord":   10 ** (chord_gain_db / 20),
    }
    double_hit_threshold = get_float_param(params, "chord_double_hit_high_freq_threshold", 0.22, 0.0, 1.0)

    emit_step(step_callback, "Pad, chord and bass event generation")
    for bar in range(bars):
        start = bar * 4 * beat
        chord = progression[
            (bar + (1 if variation > 0.45 and bar >= bars // 2 else 0)) % len(progression)
        ]
        chord_notes = [root + x for x in chord]
        if pad_i != "none":
            for n in chord_notes:
                events.append(NoteEvent(
                    start, 4.05 * beat, int(clamp(n + 12, 36, 88)),
                    clamp(pad_velocity * gains["pad"], 0, 1),
                    pad_i, 0.15 * math.sin(bar * 0.7), "pad",
                ))
        if chord_i != "none":
            for hit in range(2 if hi > double_hit_threshold else 1):
                for n in chord_notes:
                    events.append(NoteEvent(
                        start + hit * 2 * beat, 1.75 * beat,
                        int(clamp(n + 12, 38, 92)),
                        clamp(chord_velocity * (0.92 if hit else 1.0) * gains["chord"], 0, 1),
                        chord_i, pan_bias * 0.45, "chord",
                    ))
        if bass_i != "none":
            rb = min(bass_notes, key=lambda x: abs(x - (root - 12))) if bass_notes else root - 12
            events.append(NoteEvent(start, 1.55 * beat, rb, clamp(bass_velocity * gains["bass"], 0, 1), bass_i, shadow_pan, "bass"))
            events.append(NoteEvent(start + 2 * beat, 1.35 * beat, rb + 7, clamp(bass_velocity * 0.82 * gains["bass"], 0, 1), bass_i, shadow_pan * 0.7, "bass"))

    emit_step(step_callback, "Time-slice melody extraction")
    slices = time_slice_statistics(lum, bars * 8)
    complexity_step_threshold = get_float_param(params, "complexity_step_threshold", 0.52, 0.0, 1.0)
    melody_energy_gate = get_float_param(params, "melody_energy_gate", 0.10, 0.0, 1.0)
    step = 1 if complexity > complexity_step_threshold else 2
    for i in range(0, len(slices), step):
        sl = slices[i]
        if sl["energy"] < melody_energy_gate and i % 4 != 0:
            continue
        pos  = clamp(1 - sl["y_centroid"] + 0.18 * (sl["energy"] - b), 0, 1)
        note = melody_notes[int(round(pos * (len(melody_notes) - 1)))]
        section = min(3, int((i / max(1, len(slices))) * 4))
        note += int(round([0, 2, -2, 5][section] * variation))
        dur = (0.42 + 0.52 * (1 - hi) + 0.25 * sl["energy"]) * beat
        vel = clamp((melody_velocity + 0.25 * sl["contrast"]) * gains["main"], 0, 1)
        events.append(NoteEvent(
            i * 0.5 * beat, dur, int(clamp(note, 36, 100)), vel,
            main_i, clamp(pan_bias + 0.20 * math.sin(i * 0.37), -0.75, 0.75), "main",
        ))

    emit_step(step_callback, "Texture arpeggios and percussion ticks")
    density = clamp(0.20 + 0.80 * complexity + 0.75 * hi + 0.45 * bw, 0, 1)
    texture_density_threshold   = get_float_param(params, "texture_density_threshold", 0.28, 0.0, 1.0)
    texture_fast_threshold      = get_float_param(params, "texture_fast_threshold", 0.55, 0.0, 1.0)
    percussion_density_threshold = get_float_param(params, "percussion_density_threshold", 0.18, 0.0, 1.0)
    percussion_fast_threshold   = get_float_param(params, "percussion_fast_threshold", 0.55, 0.0, 1.0)
    percussion_skip_threshold   = get_float_param(params, "percussion_skip_threshold", 0.62, 0.0, 1.0)
    if density > texture_density_threshold and tex_i != "none":
        interval = 0.5 * beat if density > texture_fast_threshold else beat
        for j in range(int(duration / interval)):
            t = j * interval
            chord = progression[int(t // (4 * beat)) % len(progression)]
            pat = chord + [chord[1] + 12, chord[2] + 12]
            events.append(NoteEvent(
                t, 0.34 * beat, int(clamp(root + pat[j % len(pat)] + 12, 45, 96)),
                clamp((0.16 + 0.40 * hi + 0.22 * edge) * gains["texture"], 0, 1),
                tex_i, clamp(-0.45 + 0.90 * ((j % 8) / 7), -0.65, 0.65), "texture",
            ))
    if density > percussion_density_threshold:
        sub = 0.5 * beat if density < percussion_fast_threshold else 0.25 * beat
        for j in range(int(duration / sub)):
            if j % 2 == 1 and density < percussion_skip_threshold:
                continue
            events.append(NoteEvent(
                j * sub, 0.08 * beat,
                76 if j % 4 in [0, 3] else 72,
                clamp((0.10 + 0.42 * density) * (1.0 if j % 8 == 0 else 0.62), 0.05, 0.55),
                "texture_tick", 0.55 * math.sin(j * 0.91), "texture",
            ))

    if synthesizer_type == SYNTH_GENERALUSER_GS:
        emit_step(step_callback, "Saliency-driven solo/accent events")
        add_saliency_solo_events(events, maps, features, melody_notes, duration, beat, solo_i, solo_gain_db, params=params)

    events = [ev for ev in events if ev.start < duration]
    events.sort(key=lambda ev: (ev.start, ev.layer, ev.midi))
    info = CompositionInfo(
        tempo, bars, duration, key_name, scale_name,
        main_i, tex_i, bass_i, pad_i, chord_i, solo_i,
        describe_mood(features),
        {"Saliency": "drives the GeneralUser GS solo/accent layer"},
    )
    return events, info
