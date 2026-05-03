"""
Photo Sonification Lab — Gradio / Hugging Face Space entry point.
Transcribed from app_sl.py (Streamlit version) to Gradio.
All backend logic is identical; only the UI layer is rewritten.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
import urllib.request
import wave
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import gradio as gr
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

APP_TITLE = "Photo Sonification Lab"
DEFAULT_SAMPLE_RATE = 44100
MAX_ANALYSIS_SIDE = int(os.getenv("MAX_ANALYSIS_SIDE", "512"))
MAX_RENDER_SECONDS = 120.0
MASTER_TARGET_PEAK = float(os.getenv("MASTER_TARGET_PEAK", "0.86"))
MASTER_TARGET_RMS = float(os.getenv("MASTER_TARGET_RMS", "0.16"))
FLUIDSYNTH_MASTER_GAIN = float(os.getenv("FLUIDSYNTH_MASTER_GAIN", "0.45"))

DEFAULT_IMAGE_URL = (
    "https://media.mutualart.com/Images/2016_04/28/19/194441798/"
    "8a90ad07-2349-43df-825f-c3ecacc072e2_570.Jpeg"
)
DEFAULT_IMAGE_CAPTION = (
    "Default sample image: Félix De Boeck, *Night lights*, 1954. "
    "Source: MutualArt. Preloaded for testing only; replace with your own photo."
)

SYNTH_SIMPLE = "Simple"
SYNTH_GENERALUSER_GS = "GeneralUser GS"
SYNTHESIZER_OPTIONS = [SYNTH_SIMPLE, SYNTH_GENERALUSER_GS]
SOUNDFONT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd(),
    "soundfonts",
)
SOUNDFONT_CANDIDATES = [
    os.getenv("GENERALUSER_GS_SF2", ""),
    os.path.join(SOUNDFONT_DIR, "GeneralUser-GS.sf2"),
    os.path.join(SOUNDFONT_DIR, "GeneralUser GS.sf2"),
    os.path.join(SOUNDFONT_DIR, "GeneralUser_GS.sf2"),
    os.path.join(os.getcwd(), "GeneralUser-GS.sf2"),
]

KEY_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SCALES = {
    "Major pentatonic": [0, 2, 4, 7, 9],
    "Minor pentatonic": [0, 3, 5, 7, 10],
    "Major": [0, 2, 4, 5, 7, 9, 11],
    "Natural minor": [0, 2, 3, 5, 7, 8, 10],
    "Dorian": [0, 2, 3, 5, 7, 9, 10],
    "Lydian": [0, 2, 4, 6, 7, 9, 11],
}
SCALE_OPTIONS = ["Automatic", *SCALES.keys()]

SIMPLE_DISPLAY_TO_INTERNAL = {
    "Bowed string": "bowed_string", "Bright bell": "bright_bell",
    "Celesta": "celesta", "Cello-like bass": "cello",
    "Clarinet-like reed": "clarinet_like_reed", "Flute-like lead": "flute_like_lead",
    "Glass pad": "glass_pad", "Harp": "harp", "Kalimba": "kalimba",
    "Marimba": "marimba", "Music box": "music_box", "Soft bass": "soft_bass",
    "Soft piano": "soft_piano", "Synth pluck": "synth_pluck", "Warm pad": "warm_pad",
}
SIMPLE_INTERNAL_TO_DISPLAY = {v: k for k, v in SIMPLE_DISPLAY_TO_INTERNAL.items()}

GM_NAMES = [
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet", "Celesta", "Glockenspiel",
    "Music Box", "Vibraphone", "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ", "Reed Organ", "Accordion",
    "Harmonica", "Tango Accordion", "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)",
    "Electric Guitar (jazz)", "Electric Guitar (clean)", "Electric Guitar (muted)", "Overdriven Guitar",
    "Distortion Guitar", "Guitar Harmonics", "Acoustic Bass", "Electric Bass (finger)",
    "Electric Bass (pick)", "Fretless Bass", "Slap Bass 1", "Slap Bass 2", "Synth Bass 1",
    "Synth Bass 2", "Violin", "Viola", "Cello", "Contrabass", "Tremolo Strings",
    "Pizzicato Strings", "Orchestral Harp", "Timpani", "String Ensemble 1", "String Ensemble 2",
    "Synth Strings 1", "Synth Strings 2", "Choir Aahs", "Voice Oohs", "Synth Choir", "Orchestra Hit",
    "Trumpet", "Trombone", "Tuba", "Muted Trumpet", "French Horn", "Brass Section",
    "Synth Brass 1", "Synth Brass 2", "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax",
    "Oboe", "English Horn", "Bassoon", "Clarinet", "Piccolo", "Flute", "Recorder", "Pan Flute",
    "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina", "Lead 1 (square)", "Lead 2 (sawtooth)",
    "Lead 3 (calliope)", "Lead 4 (chiff)", "Lead 5 (charang)", "Lead 6 (voice)",
    "Lead 7 (fifths)", "Lead 8 (bass + lead)", "Pad 1 (new age)", "Pad 2 (warm)",
    "Pad 3 (polysynth)", "Pad 4 (choir)", "Pad 5 (bowed)", "Pad 6 (metallic)",
    "Pad 7 (halo)", "Pad 8 (sweep)", "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)",
    "FX 4 (atmosphere)", "FX 5 (brightness)", "FX 6 (goblins)", "FX 7 (echoes)",
    "FX 8 (sci-fi)", "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Bagpipe",
    "Fiddle", "Shanai", "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock", "Taiko Drum",
    "Melodic Tom", "Synth Drum", "Reverse Cymbal", "Guitar Fret Noise", "Breath Noise",
    "Seashore", "Bird Tweet", "Telephone Ring", "Helicopter", "Applause", "Gunshot",
]
GENERALUSER_GS_DISPLAY_TO_PROGRAM = {name: idx for idx, name in enumerate(GM_NAMES)}
GENERALUSER_GS_DISPLAY_TO_INTERNAL = {
    name: f"gm_{program:03d}" for name, program in GENERALUSER_GS_DISPLAY_TO_PROGRAM.items()
}
GENERALUSER_GS_INTERNAL_TO_DISPLAY = {v: k for k, v in GENERALUSER_GS_DISPLAY_TO_INTERNAL.items()}

GM_FAMILY_RANGES = {
    "piano": range(0, 8), "chromatic_percussion": range(8, 16), "organ": range(16, 24),
    "guitar": range(24, 32), "bass": range(32, 40), "solo_strings": range(40, 48),
    "ensemble": range(48, 56), "brass": range(56, 64), "reed": range(64, 72),
    "pipe": range(72, 80), "synth_lead": range(80, 88), "synth_pad": range(88, 96),
    "synth_fx": range(96, 104), "ethnic": range(104, 112), "percussive": range(112, 120),
    "sound_fx": range(120, 128),
}
GM_PROGRAM_TO_FAMILY = {
    program: family for family, r in GM_FAMILY_RANGES.items() for program in r
}

GENERALUSER_GS_LAYER_POOLS = {
    "main": sorted(set(
        list(GM_FAMILY_RANGES["piano"]) + list(GM_FAMILY_RANGES["chromatic_percussion"]) +
        list(GM_FAMILY_RANGES["organ"]) + list(GM_FAMILY_RANGES["guitar"]) +
        list(GM_FAMILY_RANGES["solo_strings"]) + list(GM_FAMILY_RANGES["brass"]) +
        list(GM_FAMILY_RANGES["reed"]) + list(GM_FAMILY_RANGES["pipe"]) +
        list(GM_FAMILY_RANGES["synth_lead"]) + list(GM_FAMILY_RANGES["ethnic"])
    )),
    "texture": sorted(set(
        list(GM_FAMILY_RANGES["chromatic_percussion"]) + list(GM_FAMILY_RANGES["guitar"]) +
        [45, 46, 47] + list(GM_FAMILY_RANGES["synth_fx"]) +
        list(GM_FAMILY_RANGES["ethnic"]) + list(GM_FAMILY_RANGES["percussive"]) +
        list(GM_FAMILY_RANGES["sound_fx"])
    )),
    "bass": sorted(set(
        list(GM_FAMILY_RANGES["bass"]) + [19, 20, 42, 43, 47, 57, 58, 87, 112, 116, 117, 118]
    )),
    "pad": sorted(set(
        list(GM_FAMILY_RANGES["organ"]) + list(GM_FAMILY_RANGES["solo_strings"]) +
        list(GM_FAMILY_RANGES["ensemble"]) + list(GM_FAMILY_RANGES["synth_pad"]) +
        list(GM_FAMILY_RANGES["synth_fx"]) + [120, 122, 123, 124, 125, 126]
    )),
    "chord": sorted(set(
        list(GM_FAMILY_RANGES["piano"]) + list(GM_FAMILY_RANGES["organ"]) +
        list(GM_FAMILY_RANGES["guitar"]) + list(GM_FAMILY_RANGES["solo_strings"]) +
        list(GM_FAMILY_RANGES["ensemble"]) + list(GM_FAMILY_RANGES["brass"]) +
        list(GM_FAMILY_RANGES["synth_pad"])
    )),
    "solo": sorted(set(
        list(GM_FAMILY_RANGES["chromatic_percussion"]) + list(GM_FAMILY_RANGES["solo_strings"]) +
        list(GM_FAMILY_RANGES["reed"]) + list(GM_FAMILY_RANGES["pipe"]) +
        list(GM_FAMILY_RANGES["synth_lead"]) + list(GM_FAMILY_RANGES["ethnic"]) +
        [22, 23, 27, 28, 30, 31, 46, 56, 59, 60, 61, 63, 98, 99, 100, 101, 102]
    )),
}
_missing = sorted(set(range(128)) - set().union(*[set(v) for v in GENERALUSER_GS_LAYER_POOLS.values()]))
if _missing:
    GENERALUSER_GS_LAYER_POOLS["texture"] = sorted(
        set(GENERALUSER_GS_LAYER_POOLS["texture"] + _missing)
    )

GM_PROGRAMS = {
    "bowed_string": 48, "bright_bell": 14, "celesta": 8, "cello": 42,
    "clarinet_like_reed": 71, "flute_like_lead": 73, "glass_pad": 89,
    "harp": 46, "kalimba": 108, "marimba": 12, "music_box": 10,
    "soft_bass": 32, "soft_piano": 0, "synth_pluck": 84, "warm_pad": 88,
}
GM_PROGRAMS.update({f"gm_{i:03d}": i for i in range(128)})
LAYER_CHANNELS = {"main": 0, "texture": 1, "bass": 2, "pad": 3, "chord": 4, "solo": 5, "other": 6}
PERCUSSION_NOTES = {"texture_tick": 75}

LATEX_DELIMITERS = [
    {"left": "$$", "right": "$$", "display": True},
    {"left": "$", "right": "$", "display": False},
]

# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

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


def image_to_rgb_array(image: Image.Image, max_side: Optional[int] = MAX_ANALYSIS_SIDE) -> np.ndarray:
    img = image.convert("RGB")
    if max_side is not None and max_side > 0:
        w, h = img.size
        scale = min(1.0, float(max_side) / max(w, h))
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    return np.asarray(img).astype(np.float64) / 255.0


def rgb_to_luminance(rgb: np.ndarray) -> np.ndarray:
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def rgb_to_hsv_features(rgb: np.ndarray, luminance: np.ndarray) -> Dict[str, float]:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = np.maximum.reduce([r, g, b])
    mn = np.minimum.reduce([r, g, b])
    diff = mx - mn
    sat = np.where(mx > 1e-12, diff / np.maximum(mx, 1e-12), 0.0)
    hue = np.zeros_like(mx)
    mask = diff > 1e-12
    r_is_max = (mx == r) & mask
    g_is_max = (mx == g) & mask
    b_is_max = (mx == b) & mask
    hue[r_is_max] = ((g[r_is_max] - b[r_is_max]) / diff[r_is_max]) % 6.0
    hue[g_is_max] = ((b[g_is_max] - r[g_is_max]) / diff[g_is_max]) + 2.0
    hue[b_is_max] = ((r[b_is_max] - g[b_is_max]) / diff[b_is_max]) + 4.0
    hue = (hue / 6.0) % 1.0
    weights = sat * (0.25 + luminance)
    weight_sum = float(np.sum(weights))
    if weight_sum <= 1e-12:
        hue_mean = 0.0
    else:
        angle = 2.0 * np.pi * hue
        hue_mean = (
            math.atan2(float(np.sum(weights * np.sin(angle))), float(np.sum(weights * np.cos(angle))))
            / (2.0 * np.pi)
        ) % 1.0
    return {
        "mean_saturation": float(np.mean(sat)),
        "dominant_hue": float(hue_mean),
        "warmth": float(np.mean(rgb[..., 0]) - np.mean(rgb[..., 2])),
    }


def compute_edge_map(luminance: np.ndarray) -> Tuple[np.ndarray, float]:
    gy, gx = np.gradient(luminance)
    mag = np.sqrt(gx * gx + gy * gy)
    norm = normalize01(mag)
    threshold = np.percentile(norm, 75.0)
    return norm, float(np.mean(norm > max(0.08, threshold)))


def normalized_histogram_entropy(values: np.ndarray, bins: int = 64) -> float:
    hist, _ = np.histogram(np.asarray(values).ravel(), bins=bins, range=(0.0, 1.0))
    total = float(np.sum(hist))
    if total <= 1e-12:
        return 0.0
    p = hist.astype(np.float64) / total
    p = p[p > 0]
    if p.size <= 1:
        return 0.0
    return clamp(-float(np.sum(p * np.log2(p))) / math.log2(bins), 0.0, 1.0)


def center_of_mass(weight: np.ndarray) -> Tuple[float, float]:
    w = np.asarray(weight, dtype=np.float64)
    h, width = w.shape
    total = float(np.sum(w))
    if total <= 1e-12:
        return 0.5, 0.5
    yy, xx = np.indices(w.shape)
    return (
        float(np.sum(xx * w) / total) / max(1, width - 1),
        float(np.sum(yy * w) / total) / max(1, h - 1),
    )


def compute_symmetry(luminance: np.ndarray) -> float:
    lr = 1.0 - float(np.mean(np.abs(luminance - np.fliplr(luminance))))
    tb = 1.0 - float(np.mean(np.abs(luminance - np.flipud(luminance))))
    return clamp(0.70 * lr + 0.30 * tb, 0.0, 1.0)


def compute_saliency_map(
    rgb: np.ndarray, luminance: np.ndarray, edge_map: np.ndarray
) -> Tuple[np.ndarray, Dict[str, float]]:
    rgb_mean = np.mean(rgb.reshape(-1, 3), axis=0)
    color_rarity = normalize01(np.sqrt(np.sum((rgb - rgb_mean) ** 2, axis=2)))
    luminance_rarity = normalize01(np.abs(luminance - float(np.mean(luminance))))
    hue_sat = rgb_to_hsv_features(rgb, luminance)["mean_saturation"]
    base = 0.42 * normalize01(edge_map) + 0.34 * color_rarity + 0.24 * luminance_rarity
    h, w = luminance.shape
    yy, xx = np.indices((h, w))
    xn = xx / max(1, w - 1)
    yn = yy / max(1, h - 1)
    center_bias = 1.0 - normalize01(np.sqrt((xn - 0.5) ** 2 + (yn - 0.5) ** 2))
    saliency = normalize01(0.88 * base + 0.12 * center_bias)
    thresh = np.percentile(saliency, 96.0)
    mask = saliency >= max(0.20, thresh)
    weight = np.where(mask, saliency, 0.0)
    cx, cy = center_of_mass(weight)
    if float(np.sum(weight)) <= 1e-12:
        spread = 0.0
    else:
        spread = float(
            np.sqrt(np.sum(weight * ((xn - cx) ** 2 + (yn - cy) ** 2)) / (np.sum(weight) + 1e-12))
        )
    features = {
        "saliency_peak": float(np.max(saliency)) if saliency.size else 0.0,
        "saliency_mean": float(np.mean(saliency)) if saliency.size else 0.0,
        "saliency_area": float(np.mean(mask)) if saliency.size else 0.0,
        "saliency_centroid_x": cx,
        "saliency_centroid_y": cy,
        "saliency_spread": clamp(spread / 0.45, 0.0, 1.0),
        "saliency_colorfulness": float(hue_sat),
    }
    return saliency, features


def analyze_fourier(
    luminance: np.ndarray,
    random_factor: float = 0.0,
    rng: Optional[np.random.Generator] = None,
) -> Dict[str, object]:
    h, w = luminance.shape
    rng = np.random.default_rng() if rng is None else rng
    window = np.outer(
        np.hanning(h) if h > 1 else np.ones(h),
        np.hanning(w) if w > 1 else np.ones(w),
    )
    centered = luminance - float(np.mean(luminance))
    spectrum = np.fft.fftshift(np.fft.fft2(centered * window))
    magnitude = np.abs(spectrum)
    sigma = 0.18 * (clamp(float(random_factor) / 100.0, 0.0, 1.0) ** 2)
    if sigma > 0:
        magnitude *= np.exp(rng.normal(0.0, sigma, size=magnitude.shape))
    power = magnitude ** 2
    fy = np.fft.fftshift(np.fft.fftfreq(h))
    fx = np.fft.fftshift(np.fft.fftfreq(w))
    uu, vv = np.meshgrid(fx, fy)
    radius = np.sqrt(uu * uu + vv * vv)
    r = radius / max(float(np.max(radius)), 1e-12)
    power_no_dc = power.copy()
    power_no_dc[r < 0.025] = 0.0
    total = max(float(np.sum(power_no_dc)), 1e-12)
    low = float(np.sum(power_no_dc[(r >= 0.025) & (r < 0.14)]) / total)
    mid = float(np.sum(power_no_dc[(r >= 0.14) & (r < 0.34)]) / total)
    high = float(np.sum(power_no_dc[r >= 0.34]) / total)
    centroid = float(np.sum(r * power_no_dc) / total)
    bandwidth = float(np.sqrt(np.sum(((r - centroid) ** 2) * power_no_dc) / total))
    theta = np.arctan2(vv, uu)
    horizontal_frequency_energy = float(np.sum(power_no_dc[np.abs(np.sin(theta)) < 0.38]) / total)
    vertical_frequency_energy = float(np.sum(power_no_dc[np.abs(np.cos(theta)) < 0.38]) / total)
    diagonal_frequency_energy = clamp(1.0 - horizontal_frequency_energy - vertical_frequency_energy, 0.0, 1.0)
    valid = power_no_dc[power_no_dc > 0]
    peak_score = (
        0.0 if valid.size == 0
        else clamp(
            math.log1p(float(np.percentile(valid, 99.7)) / (float(np.percentile(valid, 90.0)) + 1e-12)) / 5.0,
            0.0, 1.0,
        )
    )
    return {
        "fft_log_magnitude": normalize01(np.log1p(magnitude)),
        "low_frequency_energy": low,
        "mid_frequency_energy": mid,
        "high_frequency_energy": high,
        "fourier_centroid": centroid,
        "fourier_bandwidth": bandwidth,
        "horizontal_frequency_energy": horizontal_frequency_energy,
        "vertical_frequency_energy": vertical_frequency_energy,
        "diagonal_frequency_energy": diagonal_frequency_energy,
        "periodic_peak_score": peak_score,
        "fourier_noise_sigma": sigma,
    }


def analyze_image(
    image: Image.Image,
    random_factor: float = 0.0,
    rng: Optional[np.random.Generator] = None,
) -> Dict[str, object]:
    rng = np.random.default_rng() if rng is None else rng
    rgb = image_to_rgb_array(image)
    sigma = 0.045 * (clamp(float(random_factor) / 100.0, 0.0, 1.0) ** 2)
    if sigma > 0:
        rgb = np.clip(rgb + rng.normal(0.0, sigma, size=rgb.shape), 0.0, 1.0)
    lum = rgb_to_luminance(rgb)
    p05, p95 = float(np.percentile(lum, 5)), float(np.percentile(lum, 95))
    shadow = lum < max(0.18, p05 + 0.03)
    highlight = lum > min(0.82, p95 - 0.03)
    edge, edge_density = compute_edge_map(lum)
    texture_entropy = normalized_histogram_entropy(edge)
    fourier = analyze_fourier(lum, random_factor=random_factor, rng=rng)
    hsv = rgb_to_hsv_features(rgb, lum)
    saliency, saliency_features = compute_saliency_map(rgb, lum, edge)
    bright_weight = np.maximum(lum - np.mean(lum), 0.0)
    shadow_weight = np.where(shadow, 1.0 - lum, 0.0)
    high_weight = np.where(highlight, lum, 0.0)
    sym = compute_symmetry(lum)
    features: Dict[str, float] = {
        "analysis_width": int(lum.shape[1]),
        "analysis_height": int(lum.shape[0]),
        "mean_brightness": float(np.mean(lum)),
        "contrast": float(np.std(lum)),
        "dynamic_range": float(p95 - p05),
        "shadow_proportion": float(np.mean(shadow)),
        "highlight_proportion": float(np.mean(highlight)),
        "edge_density": float(edge_density),
        "texture_entropy": float(texture_entropy),
        "symmetry_score": float(sym),
        "auto_complexity": clamp(0.25 + 0.65 * texture_entropy, 0.25, 0.90),
        "auto_variation_strength": clamp(0.25 + 0.60 * (1.0 - sym), 0.25, 0.85),
        "bright_centroid_x": center_of_mass(bright_weight)[0],
        "shadow_centroid_x": center_of_mass(shadow_weight)[0],
        "highlight_centroid_x": center_of_mass(high_weight)[0],
        "image_noise_sigma": float(sigma),
        **hsv,
        **saliency_features,
    }
    for k, v in fourier.items():
        if not isinstance(v, np.ndarray):
            features[k] = float(v)
    maps = {
        "rgb": rgb,
        "luminance": lum,
        "edge_map": edge,
        "fft_log_magnitude": fourier["fft_log_magnitude"],
        "shadow_highlight_map": np.dstack([
            highlight.astype(float), np.zeros_like(lum), shadow.astype(float)
        ]),
        "saliency_map": saliency,
    }
    return {"features": features, "maps": maps}


def compute_bar_settings(features: Dict[str, float]) -> Tuple[int, int, int]:
    score = clamp(
        0.40 * features.get("texture_entropy", 0.0) +
        0.25 * features.get("edge_density", 0.0) +
        0.20 * features.get("high_frequency_energy", 0.0) +
        0.15 * features.get("periodic_peak_score", 0.0),
        0.0, 1.0,
    )
    mn = int(round(np.interp(score, [0, 1], [4, 8])))
    mx = int(round(np.interp(score, [0, 1], [12, 24])))
    df = int(round(np.interp(score, [0, 1], [6, 16])))
    return int(clamp(mn, 4, 8)), max(mx, mn + 1), int(clamp(df, mn, mx))


def get_instrument_choices(synthesizer_type: str) -> List[str]:
    if synthesizer_type == SYNTH_GENERALUSER_GS:
        return sorted(GENERALUSER_GS_DISPLAY_TO_PROGRAM.keys())
    return sorted(SIMPLE_DISPLAY_TO_INTERNAL.keys())


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


def find_generaluser_soundfont() -> Optional[str]:
    for p in SOUNDFONT_CANDIDATES:
        if p and os.path.exists(p):
            return p
    return None


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
    b = float(features.get("mean_brightness", 0.5))
    c = float(features.get("contrast", 0.0))
    sat = float(features.get("mean_saturation", 0.0))
    warm = float(features.get("warmth", 0.0))
    sh = float(features.get("shadow_proportion", 0.0))
    h = float(features.get("highlight_proportion", 0.0))
    edge = float(features.get("edge_density", 0.0))
    tex = float(features.get("texture_entropy", 0.0))
    lo = float(features.get("low_frequency_energy", 0.0))
    hi = float(features.get("high_frequency_energy", 0.0))
    peak = float(features.get("periodic_peak_score", 0.0))
    sym = float(features.get("symmetry_score", 0.5))
    sal_peak = float(features.get("saliency_peak", 0.0))
    sal_spread = float(features.get("saliency_spread", 0.0))
    smooth = clamp(lo + 0.35 * (1.0 - hi) + 0.25 * sym, 0.0, 1.0)
    detail = clamp(0.45 * hi + 0.30 * edge + 0.25 * tex, 0.0, 1.0)
    brightness = clamp(0.55 * b + 0.45 * h, 0.0, 1.0)
    darkness = clamp(0.55 * (1.0 - b) + 0.45 * sh, 0.0, 1.0)
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
            "bass": .45 + .50 * lo + .25 * darkness, "organ": .18 + .35 * smooth + .30 * darkness,
            "solo_strings": .20 + .45 * darkness + .25 * smooth, "brass": .12 + .40 * c + .35 * darkness,
            "synth_lead": .08 + .35 * detail + .20 * peak, "percussive": .08 + .45 * edge + .30 * peak,
        }
    elif layer == "pad":
        weights = {
            "organ": .18 + .42 * smooth + .20 * darkness, "solo_strings": .22 + .50 * darkness + .25 * smooth,
            "ensemble": .28 + .55 * smooth + .20 * sym, "synth_pad": .30 + .60 * smooth + .20 * colorfulness,
            "synth_fx": .12 + .35 * detail + .35 * colorfulness, "sound_fx": .04 + .35 * detail + .30 * c,
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
    else:
        weights = {
            "piano": .35 + .35 * smooth + .20 * brightness, "organ": .18 + .35 * smooth + .25 * darkness,
            "guitar": .18 + .35 * colorfulness + .15 * warm, "solo_strings": .16 + .35 * darkness + .25 * smooth,
            "ensemble": .24 + .45 * smooth + .25 * sym, "brass": .10 + .45 * c + .30 * brightness,
            "synth_pad": .18 + .45 * smooth + .25 * colorfulness,
        }
    return float(weights.get(family, 0.05))


def gm_program_affinity(program: int, layer: str, features: Dict[str, float]) -> float:
    family = GM_PROGRAM_TO_FAMILY.get(program, "unknown")
    score = gm_family_weight(layer, family, features)
    h = float(features.get("highlight_proportion", 0.0))
    sh = float(features.get("shadow_proportion", 0.0))
    hi = float(features.get("high_frequency_energy", 0.0))
    lo = float(features.get("low_frequency_energy", 0.0))
    peak = float(features.get("periodic_peak_score", 0.0))
    sal = float(features.get("saliency_peak", 0.0))
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
    features: Dict[str, float], layer: str, avoid: Optional[set] = None
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


def choose_scale(features: Dict[str, float], requested_scale: str) -> str:
    if requested_scale != "Automatic" and requested_scale in SCALES:
        return requested_scale
    b, sat, warm, c = (
        features["mean_brightness"], features["mean_saturation"],
        features["warmth"], features["contrast"],
    )
    if b > 0.60:
        return "Lydian" if warm > 0.06 else "Major pentatonic"
    if b > 0.42:
        return "Dorian" if (warm > 0.06 and sat > 0.38) or c > 0.22 else "Major pentatonic"
    return "Dorian" if warm > 0.05 and sat > 0.30 else "Natural minor"


def choose_instruments(
    features: Dict[str, float], mode: str, synthesizer_type: str,
    main="Soft piano", texture="Harp", bass="Cello-like bass",
    pad="Warm pad", chord="Soft piano", solo="Flute",
) -> Tuple[str, str, str, str, str, str]:
    if mode == "Manual":
        if synthesizer_type == SYNTH_GENERALUSER_GS:
            return tuple(instrument_key(x, synthesizer_type) for x in (main, texture, bass, pad, chord, solo))  # type: ignore
        return (
            instrument_key(main, synthesizer_type), instrument_key(texture, synthesizer_type),
            instrument_key(bass, synthesizer_type), instrument_key(pad, synthesizer_type),
            instrument_key(chord, synthesizer_type), "none",
        )
    b = features["mean_brightness"]
    h = features["highlight_proportion"]
    sh = features["shadow_proportion"]
    hi = features["high_frequency_energy"]
    sat = features["mean_saturation"]
    warm = features["warmth"]
    c = features["contrast"]
    peak = features["periodic_peak_score"]
    if synthesizer_type == SYNTH_GENERALUSER_GS:
        selected: set[int] = set()
        out = []
        for layer in ["main", "texture", "bass", "pad", "chord", "solo"]:
            inst = select_generaluser_instrument(features, layer, selected)
            try:
                selected.add(int(inst.split("_", 1)[1]))
            except Exception:
                pass
            out.append(inst)
        return tuple(out)  # type: ignore
    main_i = (
        "bright_bell" if h > 0.14 and hi > 0.28 else
        "celesta" if b > 0.64 else
        "kalimba" if peak > 0.58 else
        "marimba" if peak > 0.48 else
        "harp" if warm > 0.07 and sat > 0.42 else
        "synth_pluck" if c > 0.25 and hi > 0.28 else
        "soft_piano"
    )
    tex_i = (
        "bright_bell" if hi > 0.44 or h > 0.16 else
        "celesta" if hi > 0.32 else
        "kalimba" if peak > 0.55 else
        "harp" if sat > 0.45 and warm > 0.02 else
        "music_box"
    )
    bass_i = "cello" if sh > 0.26 or b < 0.36 else "soft_bass"
    pad_i = "warm_pad" if (features["low_frequency_energy"] > 0.52 and warm > 0.04) or sh > 0.20 else "glass_pad"
    chord_i = "soft_piano" if main_i != "soft_piano" else "harp"
    return main_i, tex_i, bass_i, pad_i, chord_i, "none"


def describe_mood(features: Dict[str, float]) -> str:
    light = "bright" if features["mean_brightness"] > 0.58 else "dark" if features["mean_brightness"] < 0.40 else "balanced"
    color = "warm" if features["warmth"] > 0.04 else "cool" if features["warmth"] < -0.04 else "neutral"
    contrast = "dynamic" if features["contrast"] > 0.24 else "soft" if features["contrast"] < 0.13 else "moderately dynamic"
    texture = "textured" if features["high_frequency_energy"] > 0.32 else "smooth" if features["high_frequency_energy"] < 0.18 else "moderately textured"
    focus = "focused" if features.get("saliency_area", 0.0) < 0.08 and features.get("saliency_peak", 0.0) > 0.75 else "diffuse"
    return f"{light}, {color}, {contrast}, {texture}, {focus}"


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
        features["dominant_hue"] * 997 +
        features["periodic_peak_score"] * 113 +
        features.get("texture_entropy", 0.0) * 71 +
        features.get("saliency_centroid_x", 0.0) * 53
    )
    if n >= 7:
        pools = [[0, 4, 5, 3], [0, 5, 3, 4], [0, 2, 5, 4], [0, 3, 1, 4]]
    else:
        pools = [[0, 2, 3, 4], [0, 3, 2, 1], [0, 1, 4, 2]]
    return [chord_from_scale_degree(intervals, d % n) for d in pools[seed % len(pools)]]


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


def add_saliency_solo_events(
    events: List[NoteEvent], maps: Dict[str, np.ndarray], features: Dict[str, float],
    melody_notes: List[int], duration: float, beat: float, solo_inst: str, solo_gain_db: float,
) -> None:
    if solo_inst == "none" or not melody_notes:
        return
    sal = np.asarray(maps.get("saliency_map"), dtype=np.float64)
    if sal.size == 0 or float(np.max(sal)) <= 1e-12:
        return
    h, w = sal.shape
    sal_strength = clamp(
        0.55 * features.get("saliency_peak", 0.0) +
        0.25 * features.get("saliency_mean", 0.0) +
        0.20 * (1.0 - features.get("saliency_area", 0.0)),
        0.0, 1.0,
    )
    n_notes = int(clamp(int(round(np.interp(sal_strength, [0.0, 1.0], [3, 18]))), 2, 22))
    candidate_count = min(sal.size, max(64, n_notes * 18))
    flat = np.argpartition(sal.ravel(), -candidate_count)[-candidate_count:]
    coords = [np.unravel_index(int(k), sal.shape) for k in flat]
    coords = sorted(coords, key=lambda rc: float(sal[rc[0], rc[1]]), reverse=True)
    picked: List[Tuple[int, int]] = []
    min_dist = 0.055
    for yy, xx in coords:
        xn = xx / max(1, w - 1)
        yn = yy / max(1, h - 1)
        if all(math.hypot(xn - px / max(1, w - 1), yn - py / max(1, h - 1)) >= min_dist for py, px in picked):
            picked.append((yy, xx))
        if len(picked) >= n_notes:
            break
    picked = sorted(picked, key=lambda rc: rc[1])
    gain = 10.0 ** (float(solo_gain_db) / 20.0)
    for k, (yy, xx) in enumerate(picked):
        x_norm = xx / max(1, w - 1)
        y_norm = yy / max(1, h - 1)
        strength = float(sal[yy, xx])
        t = clamp(x_norm * duration + 0.10 * beat * math.sin(1.7 * k), 0.0, max(0.0, duration - 0.25))
        note = melody_notes[int(round(clamp(1.0 - y_norm, 0.0, 1.0) * (len(melody_notes) - 1)))] + 12
        if k % 5 == 3:
            note += 7
        dur = clamp((0.32 + 0.70 * strength + 0.20 * features.get("saliency_spread", 0.0)) * beat, 0.18 * beat, 1.25 * beat)
        vel = clamp((0.18 + 0.56 * strength) * gain, 0.05, 0.92)
        pan = clamp(-0.82 + 1.64 * x_norm, -0.9, 0.9)
        events.append(NoteEvent(t, dur, int(clamp(note, 48, 112)), vel, solo_inst, pan, "solo"))


def generate_composition(
    analysis: Dict[str, object], bars: int, complexity: float, variation: float,
    requested_scale: str, synthesizer_type: str, instrument_mode: str,
    main_layer: str, texture_layer: str, bass_layer: str, pad_layer: str,
    chord_layer: str, solo_layer: str, mapping_style: str,
    manual_bpm: Optional[float],
    main_gain_db: float, texture_gain_db: float, bass_gain_db: float,
    pad_gain_db: float, chord_gain_db: float, solo_gain_db: float,
) -> Tuple[List[NoteEvent], CompositionInfo]:
    features: Dict[str, float] = analysis["features"]  # type: ignore
    maps: Dict[str, np.ndarray] = analysis["maps"]  # type: ignore
    lum = maps["luminance"]
    b = features["mean_brightness"]
    c = features["contrast"]
    sh = features["shadow_proportion"]
    edge = features["edge_density"]
    sat = features["mean_saturation"]
    warm = features["warmth"]
    lo = features["low_frequency_energy"]
    hi = features["high_frequency_energy"]
    centroid = features["fourier_centroid"]
    bw = features["fourier_bandwidth"]
    peak = features["periodic_peak_score"]
    key_index = int(round(features["dominant_hue"] * 12.0)) % 12
    key_name = KEY_NAMES[key_index]
    scale_name = choose_scale(features, requested_scale)
    intervals = SCALES[scale_name]
    root = int(clamp(48 + key_index + round(np.interp(b, [0, 1], [-5, 7])), 38, 58))
    if mapping_style == "Manual" and manual_bpm is not None:
        tempo = max(1.0, float(manual_bpm))
    elif mapping_style == "Scientific":
        tempo = clamp(50 + 70 * edge + 58 * c + 42 * peak + 34 * hi + 22 * centroid - 20 * sh, 48, 152)
    elif mapping_style == "Musical":
        tempo = clamp(82 + 10 * sat + 8 * b - 6 * sh + 4 * warm, 72, 108)
    else:
        tempo = clamp(62 + 38 * edge + 28 * c + 20 * peak + 10 * hi - 8 * sh, 56, 132)
    beat = 60.0 / tempo
    bars = int(clamp(int(bars), 1, 64))
    duration = min(MAX_RENDER_SECONDS, bars * 4 * beat)
    main_i, tex_i, bass_i, pad_i, chord_i, solo_i = choose_instruments(
        features, instrument_mode, synthesizer_type,
        main_layer, texture_layer, bass_layer, pad_layer, chord_layer, solo_layer,
    )
    if synthesizer_type != SYNTH_GENERALUSER_GS:
        solo_i = "none"
    progression = choose_progression(scale_name, features)
    melody_notes = build_scale_notes(root, intervals, root + 10, root + 31)
    bass_notes = build_scale_notes(root, intervals, root - 18, root + 7)
    events: List[NoteEvent] = []
    pan_bias = np.interp(features["bright_centroid_x"], [0, 1], [-0.45, 0.45])
    shadow_pan = np.interp(features["shadow_centroid_x"], [0, 1], [-0.35, 0.35])
    pad_velocity = clamp(0.07 + 0.18 * lo + 0.04 * (1 - hi), 0.04, 0.28)
    chord_velocity = clamp(0.28 + 0.42 * b + 0.18 * lo, 0.22, 0.78)
    bass_velocity = clamp(0.30 + 0.55 * sh + 0.25 * lo, 0.22, 0.86)
    melody_velocity = clamp(0.30 + 0.30 * features["dynamic_range"] + 0.20 * c + 0.15 * sat, 0.28, 0.90)
    gains = {
        "main": 10 ** (main_gain_db / 20), "texture": 10 ** (texture_gain_db / 20),
        "bass": 10 ** (bass_gain_db / 20), "pad": 10 ** (pad_gain_db / 20),
        "chord": 10 ** (chord_gain_db / 20),
    }
    for bar in range(bars):
        start = bar * 4 * beat
        chord = progression[(bar + (1 if variation > 0.45 and bar >= bars // 2 else 0)) % len(progression)]
        chord_notes = [root + x for x in chord]
        if pad_i != "none":
            for n in chord_notes:
                events.append(NoteEvent(start, 4.05 * beat, int(clamp(n + 12, 36, 88)), clamp(pad_velocity * gains["pad"], 0, 1), pad_i, 0.15 * math.sin(bar * 0.7), "pad"))
        if chord_i != "none":
            for hit in range(2 if hi > 0.22 else 1):
                for n in chord_notes:
                    events.append(NoteEvent(start + hit * 2 * beat, 1.75 * beat, int(clamp(n + 12, 38, 92)), clamp(chord_velocity * (0.92 if hit else 1.0) * gains["chord"], 0, 1), chord_i, pan_bias * 0.45, "chord"))
        if bass_i != "none":
            rb = min(bass_notes, key=lambda x: abs(x - (root - 12))) if bass_notes else root - 12
            events.append(NoteEvent(start, 1.55 * beat, rb, clamp(bass_velocity * gains["bass"], 0, 1), bass_i, shadow_pan, "bass"))
            events.append(NoteEvent(start + 2 * beat, 1.35 * beat, rb + 7, clamp(bass_velocity * 0.82 * gains["bass"], 0, 1), bass_i, shadow_pan * 0.7, "bass"))
    slices = time_slice_statistics(lum, bars * 8)
    step = 1 if complexity > 0.52 else 2
    for i in range(0, len(slices), step):
        sl = slices[i]
        if sl["energy"] < 0.10 and i % 4 != 0:
            continue
        pos = clamp(1 - sl["y_centroid"] + 0.18 * (sl["energy"] - b), 0, 1)
        note = melody_notes[int(round(pos * (len(melody_notes) - 1)))]
        section = min(3, int((i / max(1, len(slices))) * 4))
        note += int(round([0, 2, -2, 5][section] * variation))
        dur = (0.42 + 0.52 * (1 - hi) + 0.25 * sl["energy"]) * beat
        vel = clamp((melody_velocity + 0.25 * sl["contrast"]) * gains["main"], 0, 1)
        events.append(NoteEvent(i * 0.5 * beat, dur, int(clamp(note, 36, 100)), vel, main_i, clamp(pan_bias + 0.20 * math.sin(i * 0.37), -0.75, 0.75), "main"))
    density = clamp(0.20 + 0.80 * complexity + 0.75 * hi + 0.45 * bw, 0, 1)
    if density > 0.28 and tex_i != "none":
        interval = 0.5 * beat if density > 0.55 else beat
        for j in range(int(duration / interval)):
            t = j * interval
            chord = progression[int(t // (4 * beat)) % len(progression)]
            pat = chord + [chord[1] + 12, chord[2] + 12]
            events.append(NoteEvent(t, 0.34 * beat, int(clamp(root + pat[j % len(pat)] + 12, 45, 96)), clamp((0.16 + 0.40 * hi + 0.22 * edge) * gains["texture"], 0, 1), tex_i, clamp(-0.45 + 0.90 * ((j % 8) / 7), -0.65, 0.65), "texture"))
    if density > 0.18:
        sub = 0.5 * beat if density < 0.55 else 0.25 * beat
        for j in range(int(duration / sub)):
            if j % 2 == 1 and density < 0.62:
                continue
            events.append(NoteEvent(j * sub, 0.08 * beat, 76 if j % 4 in [0, 3] else 72, clamp((0.10 + 0.42 * density) * (1.0 if j % 8 == 0 else 0.62), 0.05, 0.55), "texture_tick", 0.55 * math.sin(j * 0.91), "texture"))
    if synthesizer_type == SYNTH_GENERALUSER_GS:
        add_saliency_solo_events(events, maps, features, melody_notes, duration, beat, solo_i, solo_gain_db)
    events = [ev for ev in events if ev.start < duration]
    events.sort(key=lambda ev: (ev.start, ev.layer, ev.midi))
    info = CompositionInfo(
        tempo, bars, duration, key_name, scale_name, main_i, tex_i, bass_i, pad_i, chord_i, solo_i,
        describe_mood(features), {"Saliency": "drives the GeneralUser GS solo/accent layer"},
    )
    return events, info


def adsr_envelope(n: int, sr: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    env = np.ones(max(1, n), dtype=np.float64) * sustain
    a, d, r = int(max(1, attack * sr)), int(max(1, decay * sr)), int(max(1, release * sr))
    env[:min(n, a)] = np.linspace(0, 1, min(n, a), endpoint=False)
    if min(n, a + d) > min(n, a):
        env[min(n, a):min(n, a + d)] = np.linspace(1, sustain, min(n, a + d) - min(n, a), endpoint=False)
    rs = max(0, n - r)
    env[rs:] *= np.linspace(1, 0, n - rs)
    return env


def gm_to_simple(instrument: str) -> str:
    if not instrument.startswith("gm_"):
        return instrument
    try:
        p = int(instrument.split("_", 1)[1])
    except Exception:
        return "soft_piano"
    if p in {8, 9, 10, 11, 14, 98, 112}:
        return "bright_bell"
    if p in {12, 13, 108}:
        return "marimba"
    if p in {46, 104, 105, 106, 107}:
        return "harp"
    if 32 <= p <= 39:
        return "soft_bass"
    if 40 <= p <= 51:
        return "bowed_string"
    if 64 <= p <= 79:
        return "flute_like_lead"
    if 80 <= p <= 87:
        return "synth_pluck"
    if 88 <= p <= 103:
        return "warm_pad"
    return "soft_piano"


def synthesize_note(freq: float, duration: float, sr: int, instrument: str, velocity: float) -> np.ndarray:
    instrument = gm_to_simple(instrument)
    n = max(1, int(round(duration * sr)))
    t = np.arange(n) / sr
    velocity = clamp(velocity, 0, 1)
    if instrument == "none":
        return np.zeros(n)
    if instrument == "soft_piano":
        sig = sum(a * np.sin(2 * np.pi * freq * m * t) for m, a in [(1, 1), (2, .42), (3, .20), (4, .10), (5, .04)])
        env = np.exp(-2.7 * t / max(duration, 1e-6)) * adsr_envelope(n, sr, .008, .12, .20, min(.20, duration * .35))
    elif instrument in {"music_box", "bright_bell", "celesta", "kalimba"}:
        partials = [(1, 1), (2.41, .55), (3.77, .30), (5.93, .16), (8.12, .06)] if instrument == "bright_bell" else [(1, 1), (2.01, .45), (3.02, .24), (4.17, .12)]
        sig = sum(a * np.sin(2 * np.pi * freq * m * t) for m, a in partials)
        env = np.exp(-4.2 * t / max(duration, 1e-6)) * adsr_envelope(n, sr, .002, .07, .08, min(.15, duration * .4))
    elif instrument in {"harp", "synth_pluck", "marimba"}:
        sig = sum((1 / (k ** 1.25)) * np.sin(2 * np.pi * freq * k * t) for k in range(1, 8))
        env = np.exp(-4.8 * t / max(duration, 1e-6)) * adsr_envelope(n, sr, .004, .07, .09, min(.16, duration * .35))
    elif instrument in {"warm_pad", "glass_pad"}:
        phase = 2 * np.pi * freq * np.cumsum(1 + .0025 * np.sin(2 * np.pi * 4.5 * t)) / sr
        sig = .75 * np.sin(phase) + .24 * np.sin(2.01 * phase) + .12 * np.sin(3.98 * phase)
        env = adsr_envelope(n, sr, min(.65, duration * .45), .45, .78, min(.75, duration * .5))
    elif instrument in {"cello", "bowed_string"}:
        phase = 2 * np.pi * freq * np.cumsum(1 + .004 * np.sin(2 * np.pi * 5.1 * t)) / sr
        sig = .75 * np.sin(phase) + .33 * np.sin(2 * phase) + .17 * np.sin(3 * phase)
        env = adsr_envelope(n, sr, .07, .18, .72, min(.35, duration * .4))
    elif instrument == "soft_bass":
        sig = .92 * np.sin(2 * np.pi * freq * t) + .30 * np.sin(2 * np.pi * 2 * freq * t)
        env = adsr_envelope(n, sr, .015, .12, .58, min(.25, duration * .35))
    elif instrument in {"flute_like_lead", "clarinet_like_reed"}:
        if instrument == "clarinet_like_reed":
            sig = np.sin(2 * np.pi * freq * t) - 0.33 * np.sin(6 * np.pi * freq * t) + 0.17 * np.sin(10 * np.pi * freq * t)
        else:
            sig = np.sin(2 * np.pi * freq * t) + 0.08 * np.sin(4 * np.pi * freq * t)
        env = adsr_envelope(n, sr, .04, .15, .80, min(.30, duration * .35))
    else:
        sig = np.sin(2 * np.pi * freq * t)
        env = adsr_envelope(n, sr, .01, .10, .50, min(.20, duration * .4))
    sig = sig * env
    mx = float(np.max(np.abs(sig))) if sig.size else 0
    if mx > 1e-12:
        sig = sig / mx
    return sig * velocity


def normalize_master_audio(
    audio: np.ndarray,
    target_peak: float = MASTER_TARGET_PEAK,
    target_rms: float = MASTER_TARGET_RMS,
) -> np.ndarray:
    audio = np.nan_to_num(np.asarray(audio, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    if audio.size == 0:
        return audio
    if audio.ndim == 1:
        audio = np.column_stack([audio, audio])
    audio = audio - np.mean(audio, axis=0, keepdims=True)
    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms > target_rms and rms > 1e-12:
        audio = audio * (target_rms / rms)
    peak = float(np.max(np.abs(audio)))
    if peak > target_peak and peak > 1e-12:
        audio = audio * (target_peak / peak)
    return np.clip(audio, -0.98, 0.98)


def render_events(
    events: List[NoteEvent],
    duration: float,
    sr: int = DEFAULT_SAMPLE_RATE,
    layer: Optional[str] = None,
    normalize: bool = True,
) -> np.ndarray:
    total = int(round((duration + .8) * sr))
    audio = np.zeros((total, 2))
    for ev in events:
        if layer is not None and ev.layer != layer:
            continue
        if ev.duration <= 0 or ev.instrument == "none":
            continue
        start = int(round(ev.start * sr))
        if start >= total:
            continue
        tone = synthesize_note(midi_to_freq(ev.midi), ev.duration, sr, ev.instrument, ev.velocity)
        end = min(total, start + len(tone))
        tone = tone[:end - start]
        pan = clamp(ev.pan, -1, 1)
        audio[start:end, 0] += tone * math.cos((pan + 1) * math.pi / 4)
        audio[start:end, 1] += tone * math.sin((pan + 1) * math.pi / 4)
    return normalize_master_audio(audio) if normalize else audio


def audio_to_wav_bytes(audio: np.ndarray, sr: int) -> bytes:
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def wav_file_to_audio(path: str) -> Tuple[np.ndarray, int]:
    with wave.open(path, "rb") as wf:
        channels, sr, width = wf.getnchannels(), wf.getframerate(), wf.getsampwidth()
        data = wf.readframes(wf.getnframes())
    if width == 2:
        arr = np.frombuffer(data, dtype=np.int16).astype(np.float64) / 32768.0
    elif width == 4:
        arr = np.frombuffer(data, dtype=np.int32).astype(np.float64) / 2147483648.0
    else:
        arr = (np.frombuffer(data, dtype=np.uint8).astype(np.float64) - 128) / 128
    if channels > 1:
        arr = arr.reshape(-1, channels)[:, :2]
    else:
        arr = np.column_stack([arr, arr])
    return arr, sr


def write_var_len(value: int) -> bytes:
    value = int(max(0, value))
    buffer = value & 0x7F
    value >>= 7
    out = []
    while value:
        out.insert(0, (buffer | 0x80) & 0xFF)
        buffer = value & 0x7F
        value >>= 7
    out.append(buffer & 0xFF)
    return bytes(out)


def midi_channel(ev: NoteEvent) -> int:
    if ev.instrument == "texture_tick":
        return 9
    return LAYER_CHANNELS.get(ev.layer, 6)


def midi_bytes_from_events(events: List[NoteEvent], tempo: float) -> bytes:
    ppq = 480
    tps = ppq * tempo / 60.0
    usq = int(round(60_000_000 / tempo))
    raw: List[Tuple[int, int, bytes]] = [(0, 0, b"\xFF\x51\x03" + usq.to_bytes(3, "big"))]
    seen = set()
    for ev in events:
        if ev.instrument == "none":
            continue
        ch = midi_channel(ev)
        tick = int(round(ev.start * tps))
        if ch != 9:
            program = int(GM_PROGRAMS.get(ev.instrument, 0))
            if (ch, program) not in seen:
                raw.append((max(0, tick - 1), 1, bytes([0xC0 | ch, program])))
                seen.add((ch, program))
    for ev in events:
        if ev.instrument == "none":
            continue
        ch = midi_channel(ev)
        note = PERCUSSION_NOTES.get(ev.instrument, 75) if ch == 9 else int(clamp(ev.midi, 0, 127))
        vel = int(clamp(ev.velocity, .05, 1) * 110)
        s = int(round(ev.start * tps))
        e = int(round((ev.start + max(.05, ev.duration)) * tps))
        raw.append((s, 2, bytes([0x90 | ch, note, vel])))
        raw.append((e, 1, bytes([0x80 | ch, note, 0])))
    raw.sort(key=lambda x: (x[0], x[1]))
    track = bytearray()
    last = 0
    for tick, _, payload in raw:
        track.extend(write_var_len(max(0, tick - last)))
        track.extend(payload)
        last = tick
    track.extend(write_var_len(0))
    track.extend(b"\xFF\x2F\x00")
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq) + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


def render_with_fluidsynth(
    events: List[NoteEvent], duration: float, tempo: float, sr: int
) -> Tuple[Optional[np.ndarray], str]:
    sf2 = find_generaluser_soundfont()
    if sf2 is None:
        return None, "GeneralUser GS selected, but no SoundFont was found. Put GeneralUser-GS.sf2 in ./soundfonts/. Falling back to Simple synthesis."
    exe = shutil.which("fluidsynth")
    if exe is None:
        return None, "GeneralUser GS selected, but the fluidsynth system package is unavailable. Falling back to Simple synthesis."
    with tempfile.TemporaryDirectory() as tmp:
        mid = os.path.join(tmp, "score.mid")
        wav = os.path.join(tmp, "render.wav")
        with open(mid, "wb") as f:
            f.write(midi_bytes_from_events(events, tempo))
        cmd = [exe, "-ni", "-g", f"{FLUIDSYNTH_MASTER_GAIN:.3f}", "-F", wav, "-r", str(sr), sf2, mid]
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=90)
            audio, rendered_sr = wav_file_to_audio(wav)
        except Exception as exc:
            return None, f"GeneralUser GS rendering failed with FluidSynth: {exc}. Falling back to Simple synthesis."
    if rendered_sr != sr:
        return None, f"GeneralUser GS rendered at {rendered_sr} Hz instead of {sr} Hz. Falling back to Simple synthesis."
    target = int(round((duration + .8) * sr))
    audio = audio[:target] if audio.shape[0] >= target else np.vstack([audio, np.zeros((target - audio.shape[0], 2))])
    return normalize_master_audio(audio), f"Audio rendered with GeneralUser GS through FluidSynth (master gain {FLUIDSYNTH_MASTER_GAIN:.2f})."


def render_backend(
    events: List[NoteEvent], info: CompositionInfo, synthesizer_type: str
) -> Tuple[np.ndarray, str]:
    if synthesizer_type == SYNTH_GENERALUSER_GS:
        audio, msg = render_with_fluidsynth(events, info.duration, info.tempo, DEFAULT_SAMPLE_RATE)
        if audio is not None:
            return audio, msg
        return normalize_master_audio(render_events(events, info.duration, DEFAULT_SAMPLE_RATE, normalize=False)), msg
    return normalize_master_audio(render_events(events, info.duration, DEFAULT_SAMPLE_RATE, normalize=False)), "Audio rendered with the Simple procedural synthesizer."


def audio_to_mp3_bytes(audio: np.ndarray, sr: int) -> Tuple[Optional[bytes], str]:
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    lame_error = "lameenc not available"
    try:
        import lameenc  # type: ignore
        enc = lameenc.Encoder()
        enc.set_bit_rate(192)
        enc.set_in_sample_rate(sr)
        enc.set_channels(2)
        enc.set_quality(2)
        data = enc.encode(pcm.tobytes()) + enc.flush()
        if data:
            return bytes(data), "MP3 export generated with lameenc."
    except Exception as exc:
        lame_error = str(exc)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None, f"MP3 export requires lameenc or ffmpeg. lameenc error: {lame_error}"
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "input.wav")
        mp3 = os.path.join(tmp, "output.mp3")
        with open(wav, "wb") as f:
            f.write(audio_to_wav_bytes(audio, sr))
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", wav, "-codec:a", "libmp3lame", "-b:a", "192k", mp3],
            check=True, timeout=45,
        )
        return open(mp3, "rb").read(), "MP3 export generated with ffmpeg."


# ─────────────────────────────────────────────────────────────────────────────
# Plot helpers (return PIL Images, fixed neutral color for dark Gradio theme)
# ─────────────────────────────────────────────────────────────────────────────

PLOT_FG = "#e8e8e8"
PLOT_BG = "#1e1e2e"


def style_ax(fig: plt.Figure, ax: plt.Axes, grid: bool = True) -> None:
    fig.patch.set_facecolor(PLOT_BG)
    ax.set_facecolor(PLOT_BG)
    ax.title.set_color(PLOT_FG)
    ax.xaxis.label.set_color(PLOT_FG)
    ax.yaxis.label.set_color(PLOT_FG)
    ax.tick_params(colors=PLOT_FG)
    for sp in ax.spines.values():
        sp.set_color(PLOT_FG)
    if grid:
        ax.grid(True, color=PLOT_FG, alpha=0.20)


def fig_to_pil(fig: plt.Figure, tight: bool = True) -> Image.Image:
    buf = io.BytesIO()
    kwargs: dict = {"format": "png", "dpi": 110, "facecolor": fig.get_facecolor()}
    if tight:
        kwargs["bbox_inches"] = "tight"
    fig.savefig(buf, **kwargs)
    plt.close(fig)
    buf.seek(0)
    img = Image.open(buf)
    return img.copy()


def mono(audio: np.ndarray) -> np.ndarray:
    return np.mean(audio, axis=1) if audio.ndim == 2 else np.asarray(audio)


def plot_map_pil(data: np.ndarray, title: str, cmap: Optional[str] = "gray") -> Image.Image:
    arr = np.asarray(data)
    h, w = arr.shape[:2]
    aspect = w / max(1, h)
    fw = 4.8
    ih = fw / max(aspect, 1e-6)
    th = 0.42
    fig, ax = plt.subplots(figsize=(fw, ih + th))
    fig.patch.set_facecolor(PLOT_BG)
    ax.set_facecolor(PLOT_BG)
    ax.imshow(arr, cmap=cmap, aspect="equal")
    ax.set_title(title, fontsize=10, color=PLOT_FG, pad=6)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, bottom=0, top=ih / (ih + th))
    return fig_to_pil(fig, tight=False)


def plot_waveform_pil(audio: np.ndarray, sr: int, title: str = "Waveform") -> Image.Image:
    m = mono(audio)
    t = np.arange(len(m)) / sr
    fig, ax = plt.subplots(figsize=(5.0, 2.6))
    style_ax(fig, ax)
    ax.plot(t, m, linewidth=0.7, color="#7eb8f7")
    ax.set_xlabel("Time (s)", color=PLOT_FG)
    ax.set_ylabel("Amplitude", color=PLOT_FG)
    ax.set_title(title, color=PLOT_FG)
    return fig_to_pil(fig)


def plot_frequency_pil(
    audio: np.ndarray, sr: int, title: str = "Fourier magnitude"
) -> Image.Image:
    m = mono(audio)
    fig, ax = plt.subplots(figsize=(5.0, 2.6))
    style_ax(fig, ax)
    if m.size < 2 or float(np.max(np.abs(m))) <= 1e-12:
        ax.text(0.5, 0.5, "No visible spectral energy", ha="center", va="center",
                color=PLOT_FG, transform=ax.transAxes)
    else:
        spec = np.fft.rfft(m * np.hanning(m.size))
        freqs = np.fft.rfftfreq(m.size, 1 / sr)
        mag = np.abs(spec)
        mag = mag / max(float(np.max(mag)), 1e-12)
        ax.plot(freqs, mag, linewidth=0.8, color="#7eb8f7")
        ax.set_xlim(0, min(8000, sr // 2))
    ax.set_xlabel("Frequency (Hz)", color=PLOT_FG)
    ax.set_ylabel("Magnitude", color=PLOT_FG)
    ax.set_title(title, color=PLOT_FG)
    return fig_to_pil(fig)


def format_percent(x: float) -> str:
    return f"{100 * x:.1f}%"


# ─────────────────────────────────────────────────────────────────────────────
# Documentation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _read_md(filename: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    for p in [os.path.join(base, filename), os.path.join(os.getcwd(), filename)]:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    return ""


def split_markdown_by_h2(text: str) -> dict:
    sections: dict = {}
    parts = re.split(r"(?m)^##\s+", text.strip())
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.splitlines()
        title = lines[0].strip()
        if title.lower() in {"table des matières", "table of contents"}:
            continue
        sections[title] = "## " + part
    return sections


DOC_FR_SECTIONS = split_markdown_by_h2(_read_md("documentation_fr.md"))
DOC_EN_SECTIONS = split_markdown_by_h2(_read_md("documentation_en.md"))
DOC_FR_TITLES = list(DOC_FR_SECTIONS.keys())
DOC_EN_TITLES = list(DOC_EN_SECTIONS.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Main run function
# ─────────────────────────────────────────────────────────────────────────────

def run_sonification(
    image: Optional[Image.Image],
    bars: int,
    variation: float,
    complexity: float,
    random_factor: int,
    scale: str,
    mapping_style: str,
    manual_bpm: float,
    synth_type: str,
    instrument_mode: str,
    main_layer: str,
    texture_layer: str,
    bass_layer: str,
    pad_layer: str,
    chord_layer: str,
    solo_layer: str,
    main_gain_db: float,
    texture_gain_db: float,
    bass_gain_db: float,
    pad_gain_db: float,
    chord_gain_db: float,
    solo_gain_db: float,
    # state: tracks whether auto-analysis has already run for this image
    _stored_hash: str,
    _controls_active: bool,
):
    if image is None:
        raise gr.Error("Please upload or select a photo before running.")

    if isinstance(image, np.ndarray):
        pil_image = Image.fromarray(image.astype(np.uint8)).convert("RGB")
    else:
        pil_image = image.convert("RGB")

    # deterministic seed from image content + random factor
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    img_hash = hashlib.sha256(buf.getvalue()).hexdigest()

    # always compute the clean (random=0) analysis for display and auto-defaults
    original_analysis = analyze_image(pil_image, 0.0, np.random.default_rng(0))
    display_maps = original_analysis["maps"]
    display_features = original_analysis["features"]

    # compute image-derived defaults (mirrors Streamlit's compute_bar_settings call)
    bar_min, bar_max, bar_default = compute_bar_settings(display_features)
    variation_default = float(display_features.get("auto_variation_strength", 0.55))
    complexity_default = float(display_features["auto_complexity"])

    # ── Two-phase logic identical to Streamlit ────────────────────────────────
    # Phase 1 (new image / first run): ignore slider values, use auto-derived ones.
    #   This matches Streamlit's "not controls_active" branch.
    # Phase 2 (same image, subsequent runs): use slider values as the user set them.
    #   This matches Streamlit's "controls_active" branch.
    new_image = (img_hash != _stored_hash)
    if new_image or not _controls_active:
        effective_bars = bar_default
        effective_variation = variation_default
        effective_complexity = complexity_default
        effective_random = 0
        analysis = original_analysis
    else:
        effective_bars = int(clamp(int(bars), bar_min, bar_max))
        effective_variation = float(variation)
        effective_complexity = float(complexity)
        effective_random = int(random_factor)
        seed = int(hashlib.sha256(f"{img_hash}:{effective_random}".encode()).hexdigest()[:16], 16)
        analysis = analyze_image(pil_image, float(effective_random), np.random.default_rng(seed))

    events, info = generate_composition(
        analysis, effective_bars, effective_complexity, effective_variation,
        scale, synth_type, instrument_mode,
        main_layer, texture_layer, bass_layer, pad_layer, chord_layer, solo_layer,
        mapping_style, float(manual_bpm) if mapping_style == "Manual" else None,
        float(main_gain_db), float(texture_gain_db), float(bass_gain_db),
        float(pad_gain_db), float(chord_gain_db), float(solo_gain_db),
    )

    audio, synth_msg = render_backend(events, info, synth_type)
    audio = normalize_master_audio(audio)

    # WAV temp file for gr.Audio
    wav_bytes = audio_to_wav_bytes(audio, DEFAULT_SAMPLE_RATE)
    wav_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    wav_tmp.write(wav_bytes)
    wav_tmp.close()

    # MP3 temp file
    mp3_bytes, mp3_msg = audio_to_mp3_bytes(audio, DEFAULT_SAMPLE_RATE)
    mp3_path = None
    if mp3_bytes:
        mp3_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        mp3_tmp.write(mp3_bytes)
        mp3_tmp.close()
        mp3_path = mp3_tmp.name

    # MIDI temp file
    midi_raw = midi_bytes_from_events(events, info.tempo)
    midi_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mid")
    midi_tmp.write(midi_raw)
    midi_tmp.close()

    # composition info markdown
    layers_line = (
        f"Main: {instrument_label(info.main_instrument)} &nbsp;|&nbsp; "
        f"Texture: {instrument_label(info.texture_instrument)} &nbsp;|&nbsp; "
        f"Bass: {instrument_label(info.bass_instrument)} &nbsp;|&nbsp; "
        f"Pad: {instrument_label(info.pad_instrument)} &nbsp;|&nbsp; "
        f"Chord: {instrument_label(info.chord_instrument)}"
    )
    if info.solo_instrument != "none":
        layers_line += f" &nbsp;|&nbsp; Solo: {instrument_label(info.solo_instrument)}"
    info_md = (
        f"**Tempo:** {info.tempo:.1f} BPM &nbsp;&nbsp; "
        f"**Bars / length:** {info.bars} bars / {info.duration:.1f} s  \n"
        f"**Key / scale:** {info.key_name} / {info.scale_name}  \n"
        f"**Mood:** {info.mood}  \n"
        f"**Layers:** {layers_line}  \n"
        f"*{synth_msg}*"
    )

    # photo analysis maps (from clean original_analysis)
    lum_img = plot_map_pil(display_maps["luminance"], "Luminance map", "gray")
    edge_img = plot_map_pil(display_maps["edge_map"], "Edge strength map", "gray")
    fft_img = plot_map_pil(display_maps["fft_log_magnitude"], "2D Fourier log-magnitude", "gray")
    sh_img = plot_map_pil(display_maps["shadow_highlight_map"], "Highlights (red) · shadows (blue)")

    # photo analysis metrics table
    f = display_features
    metrics_md = (
        f"| | |\n|---|---|\n"
        f"| **Brightness** | {f['mean_brightness']:.3f} |\n"
        f"| **Contrast** | {f['contrast']:.3f} |\n"
        f"| **Saturation** | {f['mean_saturation']:.3f} |\n"
        f"| **Shadows** | {format_percent(f['shadow_proportion'])} |\n"
        f"| **Highlights** | {format_percent(f['highlight_proportion'])} |\n"
        f"| **Edge density** | {format_percent(f['edge_density'])} |\n"
        f"| **Texture entropy** | {f['texture_entropy']:.3f} |\n"
        f"| **Symmetry** | {f['symmetry_score']:.3f} |\n"
        f"| **Saliency peak** | {f['saliency_peak']:.3f} |\n"
        f"| **Fourier low** | {format_percent(f['low_frequency_energy'])} |\n"
        f"| **Fourier mid** | {format_percent(f['mid_frequency_energy'])} |\n"
        f"| **Fourier high** | {format_percent(f['high_frequency_energy'])} |\n"
        f"| **Periodic peak score** | {f['periodic_peak_score']:.3f} |"
    )

    # audio analysis plots
    sr = DEFAULT_SAMPLE_RATE
    waveform_img = plot_waveform_pil(audio, sr)
    freq_img = plot_frequency_pil(audio, sr, "Full Fourier magnitude")
    main_freq = plot_frequency_pil(render_events(events, info.duration, sr, layer="main"), sr, "Main layer")
    tex_freq = plot_frequency_pil(render_events(events, info.duration, sr, layer="texture"), sr, "Texture layer")
    bass_freq = plot_frequency_pil(render_events(events, info.duration, sr, layer="bass"), sr, "Bass layer")
    pad_freq = plot_frequency_pil(render_events(events, info.duration, sr, layer="pad"), sr, "Pad layer")
    chord_freq = plot_frequency_pil(render_events(events, info.duration, sr, layer="chord"), sr, "Chord layer")
    solo_freq = None
    if info.solo_instrument != "none":
        solo_freq = plot_frequency_pil(render_events(events, info.duration, sr, layer="solo"), sr, "Solo layer")

    # slider update suggestions based on this image
    bars_update = gr.update(minimum=bar_min, maximum=bar_max, value=bar_default)
    variation_update = gr.update(value=round(variation_default, 2))
    complexity_update = gr.update(value=round(complexity_default, 2))

    status = (
        f"✅ Composition generated — {info.bars} bars, {info.duration:.1f} s, "
        f"{info.tempo:.1f} BPM, key {info.key_name} {info.scale_name}."
    )

    return (
        status, wav_tmp.name, mp3_path, midi_tmp.name, info_md,
        lum_img, edge_img, fft_img, sh_img, metrics_md,
        waveform_img, freq_img, main_freq, tex_freq, bass_freq, pad_freq, chord_freq, solo_freq,
        bars_update, variation_update, complexity_update,
        img_hash, True,   # update stored_hash and controls_active state
    )


# ─────────────────────────────────────────────────────────────────────────────
# Instrument dropdown helpers for dynamic updates
# ─────────────────────────────────────────────────────────────────────────────

_SIMPLE_CHOICES = get_instrument_choices_with_none(SYNTH_SIMPLE)
_GS_CHOICES = get_instrument_choices_with_none(SYNTH_GENERALUSER_GS)
_SIMPLE_DEFAULTS = ["Soft piano", "Harp", "Cello-like bass", "Warm pad", "Soft piano", "None"]
_GS_DEFAULTS = ["Acoustic Grand Piano", "Orchestral Harp", "Cello", "Pad 2 (warm)", "Acoustic Grand Piano", "Flute"]


def on_synth_change(synth_type: str):
    choices = get_instrument_choices_with_none(synth_type)
    defs = _GS_DEFAULTS if synth_type == SYNTH_GENERALUSER_GS else _SIMPLE_DEFAULTS

    def safe(val, ch):
        return val if val in ch else ch[1] if len(ch) > 1 else ch[0]

    solo_vis = synth_type == SYNTH_GENERALUSER_GS
    return (
        gr.update(choices=choices, value=safe(defs[0], choices)),
        gr.update(choices=choices, value=safe(defs[1], choices)),
        gr.update(choices=choices, value=safe(defs[2], choices)),
        gr.update(choices=choices, value=safe(defs[3], choices)),
        gr.update(choices=choices, value=safe(defs[4], choices)),
        gr.update(choices=choices, value=safe(defs[5], choices), visible=solo_vis),
        gr.update(visible=solo_vis),  # solo gain slider
    )


def on_instrument_mode_change(mode: str):
    vis = mode == "Manual"
    return [gr.update(visible=vis)] * 13  # 6 dropdowns + 6 gain sliders + solo row


def on_mapping_change(mapping: str):
    return gr.update(visible=mapping == "Manual")


# ─────────────────────────────────────────────────────────────────────────────
# Gradio UI
# ─────────────────────────────────────────────────────────────────────────────

with gr.Blocks(title=APP_TITLE) as demo:

    # Hidden state: mirrors Streamlit's session_state for two-phase parameter logic.
    # stored_hash: SHA-256 of the last analyzed image (empty = no image analyzed yet).
    # controls_active: True once the image has been run at least once (unlocks slider values).
    stored_hash = gr.State("")
    controls_active = gr.State(False)

    # ── App tab ──────────────────────────────────────────────────────────────
    with gr.Tab("App"):

        with gr.Row():
            # Left column: image input
            with gr.Column(scale=1):
                gr.Markdown("### Input photo")
                input_image = gr.Image(
                    label="Input photo",
                    type="pil",
                    value=DEFAULT_IMAGE_URL,
                )
                gr.Markdown(DEFAULT_IMAGE_CAPTION, elem_classes=["caption"])

            # Right column: composition parameters
            with gr.Column(scale=1):
                gr.Markdown("### Composition parameters")
                with gr.Accordion("Musical structure", open=True):
                    with gr.Row():
                        bars_slider = gr.Slider(
                            label="Number of bars",
                            minimum=4, maximum=24, value=8, step=1,
                        )
                        variation_slider = gr.Slider(
                            label="Variation strength",
                            minimum=0.0, maximum=1.0, value=0.55, step=0.01,
                        )
                    with gr.Row():
                        complexity_slider = gr.Slider(
                            label="Composition complexity",
                            minimum=0.10, maximum=1.00, value=0.72, step=0.01,
                        )
                        random_slider = gr.Slider(
                            label="Random factor",
                            minimum=0, maximum=100, value=0, step=1,
                        )
                    with gr.Row():
                        scale_dd = gr.Dropdown(
                            label="Scale",
                            choices=SCALE_OPTIONS,
                            value="Automatic",
                        )
                        mapping_dd = gr.Dropdown(
                            label="Mapping style (BPM)",
                            choices=["Scientific", "Balanced", "Musical", "Manual"],
                            value="Scientific",
                        )
                    manual_bpm_input = gr.Number(
                        label="Manual BPM",
                        value=90.0,
                        minimum=1.0,
                        precision=1,
                        visible=False,
                    )

                with gr.Accordion("Synthesizer & instruments", open=True):
                    synth_radio = gr.Radio(
                        label="Synthesizer type",
                        choices=SYNTHESIZER_OPTIONS,
                        value=SYNTH_GENERALUSER_GS,
                    )
                    instrument_mode_radio = gr.Radio(
                        label="Instrument layer selection",
                        choices=["Automatic", "Manual"],
                        value="Automatic",
                    )
                    with gr.Group(visible=False) as manual_inst_group:
                        with gr.Row():
                            main_dd = gr.Dropdown(label="Main layer", choices=_GS_CHOICES, value="Acoustic Grand Piano")
                            main_gain = gr.Slider(label="Main gain (dB)", minimum=-24.0, maximum=12.0, value=0.0, step=0.5)
                        with gr.Row():
                            texture_dd = gr.Dropdown(label="Texture layer", choices=_GS_CHOICES, value="Orchestral Harp")
                            texture_gain = gr.Slider(label="Texture gain (dB)", minimum=-24.0, maximum=12.0, value=-2.0, step=0.5)
                        with gr.Row():
                            bass_dd = gr.Dropdown(label="Bass layer", choices=_GS_CHOICES, value="Cello")
                            bass_gain = gr.Slider(label="Bass gain (dB)", minimum=-24.0, maximum=12.0, value=0.0, step=0.5)
                        with gr.Row():
                            pad_dd = gr.Dropdown(label="Pad layer", choices=_GS_CHOICES, value="Pad 2 (warm)")
                            pad_gain = gr.Slider(label="Pad gain (dB)", minimum=-24.0, maximum=12.0, value=-8.0, step=0.5)
                        with gr.Row():
                            chord_dd = gr.Dropdown(label="Chord layer", choices=_GS_CHOICES, value="Acoustic Grand Piano")
                            chord_gain = gr.Slider(label="Chord gain (dB)", minimum=-24.0, maximum=12.0, value=-3.0, step=0.5)
                        with gr.Row(visible=True) as solo_row:
                            solo_dd = gr.Dropdown(label="Solo layer", choices=_GS_CHOICES, value="Flute")
                            solo_gain = gr.Slider(label="Solo gain (dB)", minimum=-24.0, maximum=12.0, value=-1.0, step=0.5)

                run_btn = gr.Button("Run", variant="primary")

        status_md = gr.Markdown()

        # Output tabs
        with gr.Tabs():
            with gr.Tab("Output audio"):
                audio_out = gr.Audio(label="Generated audio", type="filepath")
                info_md = gr.Markdown()
                with gr.Row():
                    mp3_file = gr.File(label="Download MP3", file_types=[".mp3"])
                    midi_file = gr.File(label="Download MIDI", file_types=[".mid"])

            with gr.Tab("Photo analysis"):
                with gr.Row():
                    with gr.Column(scale=2):
                        lum_map = gr.Image(label="Luminance map")
                        edge_map_out = gr.Image(label="Edge strength map")
                        fft_map = gr.Image(label="2D Fourier log-magnitude")
                        sh_map = gr.Image(label="Highlights (red) · shadows (blue)")
                    with gr.Column(scale=1):
                        metrics_md = gr.Markdown(label="Analysis metrics")

            with gr.Tab("Audio analysis"):
                with gr.Row():
                    waveform_out = gr.Image(label="Waveform")
                    full_freq_out = gr.Image(label="Full Fourier magnitude")
                with gr.Row():
                    main_freq_out = gr.Image(label="Main layer")
                    tex_freq_out = gr.Image(label="Texture layer")
                    bass_freq_out = gr.Image(label="Bass layer")
                with gr.Row():
                    pad_freq_out = gr.Image(label="Pad layer")
                    chord_freq_out = gr.Image(label="Chord layer")
                    solo_freq_out = gr.Image(label="Solo layer")

    # ── Documentation FR tab ─────────────────────────────────────────────────
    with gr.Tab("Documentation FR"):
        if DOC_FR_TITLES:
            with gr.Row():
                with gr.Column(scale=1):
                    doc_fr_buttons = []
                    for title in DOC_FR_TITLES:
                        btn = gr.Button(title)
                        doc_fr_buttons.append((btn, title))
                with gr.Column(scale=2):
                    doc_fr_view = gr.Markdown(
                        value=DOC_FR_SECTIONS.get(DOC_FR_TITLES[0], ""),
                        latex_delimiters=LATEX_DELIMITERS,
                    )
            for btn, title in doc_fr_buttons:
                btn.click(
                    fn=lambda t=title: DOC_FR_SECTIONS.get(t, ""),
                    inputs=None,
                    outputs=doc_fr_view,
                )
        else:
            gr.Markdown("Le fichier `documentation_fr.md` est introuvable.")

    # ── Documentation EN tab ─────────────────────────────────────────────────
    with gr.Tab("Documentation EN"):
        if DOC_EN_TITLES:
            with gr.Row():
                with gr.Column(scale=1):
                    doc_en_buttons = []
                    for title in DOC_EN_TITLES:
                        btn = gr.Button(title)
                        doc_en_buttons.append((btn, title))
                with gr.Column(scale=2):
                    doc_en_view = gr.Markdown(
                        value=DOC_EN_SECTIONS.get(DOC_EN_TITLES[0], ""),
                        latex_delimiters=LATEX_DELIMITERS,
                    )
            for btn, title in doc_en_buttons:
                btn.click(
                    fn=lambda t=title: DOC_EN_SECTIONS.get(t, ""),
                    inputs=None,
                    outputs=doc_en_view,
                )
        else:
            gr.Markdown("The file `documentation_en.md` could not be found.")

    # ── Dynamic visibility events ─────────────────────────────────────────────

    # Reset the two-phase state whenever the user swaps the image,
    # so the next Run always re-enters Phase 1 (auto-derived parameters).
    input_image.change(
        fn=lambda _: ("", False),
        inputs=[input_image],
        outputs=[stored_hash, controls_active],
    )

    mapping_dd.change(
        fn=on_mapping_change,
        inputs=[mapping_dd],
        outputs=[manual_bpm_input],
    )

    instrument_mode_radio.change(
        fn=on_instrument_mode_change,
        inputs=[instrument_mode_radio],
        outputs=[
            manual_inst_group,          # group visibility
            main_dd, texture_dd, bass_dd, pad_dd, chord_dd, solo_dd,
            main_gain, texture_gain, bass_gain, pad_gain, chord_gain, solo_gain,
        ],
    )

    synth_radio.change(
        fn=on_synth_change,
        inputs=[synth_radio],
        outputs=[main_dd, texture_dd, bass_dd, pad_dd, chord_dd, solo_dd, solo_gain],
    )

    # ── Run button ────────────────────────────────────────────────────────────

    run_btn.click(
        fn=run_sonification,
        inputs=[
            input_image,
            bars_slider, variation_slider, complexity_slider, random_slider,
            scale_dd, mapping_dd, manual_bpm_input,
            synth_radio, instrument_mode_radio,
            main_dd, texture_dd, bass_dd, pad_dd, chord_dd, solo_dd,
            main_gain, texture_gain, bass_gain, pad_gain, chord_gain, solo_gain,
            stored_hash, controls_active,
        ],
        outputs=[
            status_md, audio_out, mp3_file, midi_file, info_md,
            lum_map, edge_map_out, fft_map, sh_map, metrics_md,
            waveform_out, full_freq_out,
            main_freq_out, tex_freq_out, bass_freq_out, pad_freq_out, chord_freq_out, solo_freq_out,
            bars_slider, variation_slider, complexity_slider,
            stored_hash, controls_active,
        ],
    )


if __name__ == "__main__":
    demo.launch()
