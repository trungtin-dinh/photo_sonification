from __future__ import annotations

import hashlib
import html
import io
import json
import math
import os
import shutil
import struct
import subprocess
import tempfile
import urllib.request
import wave
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.mlab as mlab
import numpy as np
import streamlit as st
from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_SUPPORT = True
except Exception:
    HEIF_SUPPORT = False

APP_TITLE = "Photo Sonification"
DEFAULT_SAMPLE_RATE = 44100
MAX_ANALYSIS_SIDE = int(os.getenv("MAX_ANALYSIS_SIDE", "512"))
MAX_RENDER_SECONDS = 120.0
MASTER_TARGET_PEAK = float(os.getenv("MASTER_TARGET_PEAK", "0.86"))
MASTER_TARGET_RMS = float(os.getenv("MASTER_TARGET_RMS", "0.16"))
FLUIDSYNTH_MASTER_GAIN = float(os.getenv("FLUIDSYNTH_MASTER_GAIN", "0.45"))

DEFAULT_IMAGE_URL = "https://media.mutualart.com/Images/2016_04/28/19/194441798/8a90ad07-2349-43df-825f-c3ecacc072e2_570.Jpeg"
DEFAULT_IMAGE_SOURCE_PAGE = "https://www.mutualart.com/Artwork/Night-lights/171ACA7174BEDBD6"
DEFAULT_IMAGE_CAPTION = (
    "Default sample image: Félix De Boeck, Night lights, 1954. "
    "Source image: MutualArt. This image is preloaded only to let users test the app; "
    "it is not presented as open-source/licensed material. You can upload your own photo "
    "to replace this default image."
)
DEFAULT_IMAGE_NAME = "Félix De Boeck, Night lights, 1954"
SUPPORTED_IMAGE_TYPES = ["png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff", "heic", "heif", "hif"]
HEIF_IMAGE_TYPES = {"heic", "heif", "hif"}

PORTFOLIO_LINKS = [
    {
        "platform": "Streamlit",
        "label": "trungtin-dinh",
        "url": "https://share.streamlit.io/user/trungtin-dinh",
        "icon_url": "https://cdn.simpleicons.org/streamlit/FF4B4B",
    },
    {
        "platform": "GitHub",
        "label": "trungtin-dinh",
        "url": "https://github.com/trungtin-dinh",
        "icon_url": "https://cdn.simpleicons.org/github/FFFFFF",
    },
    {
        "platform": "LinkedIn",
        "label": "Trung-Tin Dinh",
        "url": "https://www.linkedin.com/in/trung-tin-dinh/",
        "icon_url": "https://upload.wikimedia.org/wikipedia/commons/8/81/LinkedIn_icon.svg",
    },
    {
        "platform": "Hugging Face",
        "label": "trungtindinh",
        "url": "https://huggingface.co/trungtindinh",
        "icon_url": "https://cdn.simpleicons.org/huggingface/FFD21E",
    },
    {
        "platform": "Medium",
        "label": "@trungtin.dinh",
        "url": "https://medium.com/@trungtin.dinh",
        "icon_url": "https://cdn.simpleicons.org/medium/FFFFFF",
    },
    {
        "platform": "CV FR",
        "label": "CV FR",
        "url": "https://e.pcloud.link/publink/show?code=XZX81iZss7g3iD9fGJXmPRRGSi7LBTvLcgX",
        "icon_url": "https://upload.wikimedia.org/wikipedia/commons/8/87/PDF_file_icon.svg",        
    },
    {
        "platform": "CV EN",
        "label": "CV EN",
        "url": "https://e.pcloud.link/publink/show?code=XZ581iZBQvbu1mFKjziunF9lblghze8OXkk",
        "icon_url": "https://upload.wikimedia.org/wikipedia/commons/8/87/PDF_file_icon.svg",        
    },
]


def render_portfolio_links() -> None:
    links_html_parts = []

    for item in PORTFOLIO_LINKS:
        show_label = item["platform"] in {"CV FR", "CV EN"}
        link_class = "portfolio-link with-label" if show_label else "portfolio-link icon-only"
        title = f"Open {item['platform']}"
        if not show_label:
            title = f"Open {item['platform']}: {item['label']}"

        label_html = ""
        if show_label:
            label_html = f'<span class="portfolio-label">{html.escape(item["label"])}</span>'

        links_html_parts.append(
            f'<a class="{link_class}" '
            f'href="{html.escape(item["url"], quote=True)}" '
            f'target="_blank" '
            f'rel="noopener noreferrer" '
            f'title="{html.escape(title, quote=True)}" '
            f'aria-label="{html.escape(title, quote=True)}">'
            f'<img class="portfolio-icon" '
            f'src="{html.escape(item["icon_url"], quote=True)}" '
            f'alt="{html.escape(item["platform"], quote=True)} icon">'
            f'{label_html}'
            f'</a>'
        )

    st.markdown(
        f'<div class="portfolio-link-row">{"".join(links_html_parts)}</div>',
        unsafe_allow_html=True,
    )

SYNTH_SIMPLE = "Simple"
SYNTH_GENERALUSER_GS = "GeneralUser GS"
SYNTHESIZER_OPTIONS = [SYNTH_SIMPLE, SYNTH_GENERALUSER_GS]
SOUNDFONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd(), "soundfonts")
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
    "Bowed string": "bowed_string",
    "Bright bell": "bright_bell",
    "Celesta": "celesta",
    "Cello-like bass": "cello",
    "Clarinet-like reed": "clarinet_like_reed",
    "Flute-like lead": "flute_like_lead",
    "Glass pad": "glass_pad",
    "Harp": "harp",
    "Kalimba": "kalimba",
    "Marimba": "marimba",
    "Music box": "music_box",
    "Soft bass": "soft_bass",
    "Soft piano": "soft_piano",
    "Synth pluck": "synth_pluck",
    "Warm pad": "warm_pad",
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
GENERALUSER_GS_DISPLAY_TO_INTERNAL = {name: f"gm_{program:03d}" for name, program in GENERALUSER_GS_DISPLAY_TO_PROGRAM.items()}
GENERALUSER_GS_INTERNAL_TO_DISPLAY = {v: k for k, v in GENERALUSER_GS_DISPLAY_TO_INTERNAL.items()}

GM_FAMILY_RANGES = {
    "piano": range(0, 8),
    "chromatic_percussion": range(8, 16),
    "organ": range(16, 24),
    "guitar": range(24, 32),
    "bass": range(32, 40),
    "solo_strings": range(40, 48),
    "ensemble": range(48, 56),
    "brass": range(56, 64),
    "reed": range(64, 72),
    "pipe": range(72, 80),
    "synth_lead": range(80, 88),
    "synth_pad": range(88, 96),
    "synth_fx": range(96, 104),
    "ethnic": range(104, 112),
    "percussive": range(112, 120),
    "sound_fx": range(120, 128),
}
GM_PROGRAM_TO_FAMILY = {program: family for family, program_range in GM_FAMILY_RANGES.items() for program in program_range}

GENERALUSER_GS_LAYER_POOLS = {
    "main": sorted(set(list(GM_FAMILY_RANGES["piano"]) + list(GM_FAMILY_RANGES["chromatic_percussion"]) + list(GM_FAMILY_RANGES["organ"]) + list(GM_FAMILY_RANGES["guitar"]) + list(GM_FAMILY_RANGES["solo_strings"]) + list(GM_FAMILY_RANGES["brass"]) + list(GM_FAMILY_RANGES["reed"]) + list(GM_FAMILY_RANGES["pipe"]) + list(GM_FAMILY_RANGES["synth_lead"]) + list(GM_FAMILY_RANGES["ethnic"]))),
    "texture": sorted(set(list(GM_FAMILY_RANGES["chromatic_percussion"]) + list(GM_FAMILY_RANGES["guitar"]) + [45, 46, 47] + list(GM_FAMILY_RANGES["synth_fx"]) + list(GM_FAMILY_RANGES["ethnic"]) + list(GM_FAMILY_RANGES["percussive"]) + list(GM_FAMILY_RANGES["sound_fx"]))),
    "bass": sorted(set(list(GM_FAMILY_RANGES["bass"]) + [19, 20, 42, 43, 47, 57, 58, 87, 112, 116, 117, 118])),
    "pad": sorted(set(list(GM_FAMILY_RANGES["organ"]) + list(GM_FAMILY_RANGES["solo_strings"]) + list(GM_FAMILY_RANGES["ensemble"]) + list(GM_FAMILY_RANGES["synth_pad"]) + list(GM_FAMILY_RANGES["synth_fx"]) + [120, 122, 123, 124, 125, 126])),
    "chord": sorted(set(list(GM_FAMILY_RANGES["piano"]) + list(GM_FAMILY_RANGES["organ"]) + list(GM_FAMILY_RANGES["guitar"]) + list(GM_FAMILY_RANGES["solo_strings"]) + list(GM_FAMILY_RANGES["ensemble"]) + list(GM_FAMILY_RANGES["brass"]) + list(GM_FAMILY_RANGES["synth_pad"]))),
    "solo": sorted(set(list(GM_FAMILY_RANGES["chromatic_percussion"]) + list(GM_FAMILY_RANGES["solo_strings"]) + list(GM_FAMILY_RANGES["reed"]) + list(GM_FAMILY_RANGES["pipe"]) + list(GM_FAMILY_RANGES["synth_lead"]) + list(GM_FAMILY_RANGES["ethnic"]) + [22, 23, 27, 28, 30, 31, 46, 56, 59, 60, 61, 63, 98, 99, 100, 101, 102])),
}
_missing_gm_programs = sorted(set(range(128)) - set().union(*[set(v) for v in GENERALUSER_GS_LAYER_POOLS.values()]))
if _missing_gm_programs:
    GENERALUSER_GS_LAYER_POOLS["texture"] = sorted(set(GENERALUSER_GS_LAYER_POOLS["texture"] + _missing_gm_programs))

GM_PROGRAMS = {
    "bowed_string": 48, "bright_bell": 14, "celesta": 8, "cello": 42, "clarinet_like_reed": 71,
    "flute_like_lead": 73, "glass_pad": 89, "harp": 46, "kalimba": 108, "marimba": 12,
    "music_box": 10, "soft_bass": 32, "soft_piano": 0, "synth_pluck": 84, "warm_pad": 88,
}
GM_PROGRAMS.update({f"gm_{i:03d}": i for i in range(128)})
LAYER_CHANNELS = {"main": 0, "texture": 1, "bass": 2, "pad": 3, "chord": 4, "solo": 5, "other": 6}
PERCUSSION_NOTES = {"texture_tick": 75}


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


def clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


def get_param(params: Optional[Dict[str, object]], key: str, default: object) -> object:
    """Read one optional user parameter with a safe fallback."""
    if not isinstance(params, dict):
        return default
    return params.get(key, default)


def get_float_param(params: Optional[Dict[str, object]], key: str, default: float, lo: float, hi: float) -> float:
    try:
        value = float(get_param(params, key, default))
    except Exception:
        value = default
    return clamp(value, lo, hi)


def get_int_param(params: Optional[Dict[str, object]], key: str, default: int, lo: int, hi: int) -> int:
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


def normalize_positive_weights(values: Dict[str, float], fallback: Dict[str, float]) -> Dict[str, float]:
    cleaned = {k: max(0.0, float(v)) for k, v in values.items()}
    total = float(sum(cleaned.values()))
    if total <= 1e-12:
        cleaned = {k: max(0.0, float(v)) for k, v in fallback.items()}
        total = float(sum(cleaned.values()))
    if total <= 1e-12:
        n = max(1, len(cleaned))
        return {k: 1.0 / n for k in cleaned}
    return {k: v / total for k, v in cleaned.items()}


def emit_step(step_callback, label: str) -> None:
    if step_callback is not None:
        step_callback(label)


def normalize01(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    lo = float(np.min(x)) if x.size else 0.0
    hi = float(np.max(x)) if x.size else 0.0
    if hi - lo < 1e-12:
        return np.zeros_like(x, dtype=np.float64)
    return (x - lo) / (hi - lo)


def midi_to_freq(midi_note: float) -> float:
    return 440.0 * (2.0 ** ((float(midi_note) - 69.0) / 12.0))


def load_image_bytes_from_url(url: str, timeout: float = 20.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def open_image_from_bytes(image_bytes: bytes, filename: str = "") -> Image.Image:
    extension = os.path.splitext(filename or "")[1].lower().lstrip(".")
    if extension in HEIF_IMAGE_TYPES and not HEIF_SUPPORT:
        raise RuntimeError(
            "HEIC/HEIF support requires the optional dependency `pillow-heif`. "
            "Add `pillow-heif` to requirements.txt and redeploy the app."
        )
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)
        return image.convert("RGB")
    except Exception as exc:
        if extension in HEIF_IMAGE_TYPES:
            raise RuntimeError(
                "Could not decode this HEIC/HEIF image. Make sure `pillow-heif` is installed "
                "and listed in requirements.txt."
            ) from exc
        raise RuntimeError(f"Could not decode this image file: {exc}") from exc


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
        hue_mean = (math.atan2(float(np.sum(weights * np.sin(angle))), float(np.sum(weights * np.cos(angle)))) / (2.0 * np.pi)) % 1.0
    return {"mean_saturation": float(np.mean(sat)), "dominant_hue": float(hue_mean), "warmth": float(np.mean(rgb[..., 0]) - np.mean(rgb[..., 2]))}


def compute_edge_map(luminance: np.ndarray, params: Optional[Dict[str, object]] = None) -> Tuple[np.ndarray, float]:
    gy, gx = np.gradient(luminance)
    mag = np.sqrt(gx * gx + gy * gy)
    norm = normalize01(mag)
    percentile = get_float_param(params, "edge_threshold_percentile", 75.0, 0.0, 100.0)
    minimum = get_float_param(params, "edge_threshold_minimum", 0.08, 0.0, 1.0)
    threshold = np.percentile(norm, percentile)
    return norm, float(np.mean(norm > max(minimum, threshold)))


def normalized_histogram_entropy(values: np.ndarray, bins: int = 64) -> float:
    bins = max(4, int(bins))
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
    return float(np.sum(xx * w) / total) / max(1, width - 1), float(np.sum(yy * w) / total) / max(1, h - 1)


def compute_symmetry(luminance: np.ndarray) -> float:
    lr = 1.0 - float(np.mean(np.abs(luminance - np.fliplr(luminance))))
    tb = 1.0 - float(np.mean(np.abs(luminance - np.flipud(luminance))))
    return clamp(0.70 * lr + 0.30 * tb, 0.0, 1.0)


def compute_saliency_map(
    rgb: np.ndarray,
    luminance: np.ndarray,
    edge_map: np.ndarray,
    params: Optional[Dict[str, object]] = None,
) -> Tuple[np.ndarray, Dict[str, float]]:
    rgb_mean = np.mean(rgb.reshape(-1, 3), axis=0)
    color_rarity = normalize01(np.sqrt(np.sum((rgb - rgb_mean) ** 2, axis=2)))
    luminance_rarity = normalize01(np.abs(luminance - float(np.mean(luminance))))
    hue_sat = rgb_to_hsv_features(rgb, luminance)["mean_saturation"]

    feature_defaults = {"edge": 0.42, "color": 0.34, "luminance": 0.24}
    feature_weights = normalize_positive_weights(
        {
            "edge": get_float_param(params, "saliency_edge_weight", 0.42, 0.0, 5.0),
            "color": get_float_param(params, "saliency_color_weight", 0.34, 0.0, 5.0),
            "luminance": get_float_param(params, "saliency_luminance_weight", 0.24, 0.0, 5.0),
        },
        feature_defaults,
    )
    base = (
        feature_weights["edge"] * normalize01(edge_map)
        + feature_weights["color"] * color_rarity
        + feature_weights["luminance"] * luminance_rarity
    )

    h, w = luminance.shape
    yy, xx = np.indices((h, w))
    xn = xx / max(1, w - 1)
    yn = yy / max(1, h - 1)
    center_bias = 1.0 - normalize01(np.sqrt((xn - 0.5) ** 2 + (yn - 0.5) ** 2))

    center_weight = get_float_param(params, "saliency_center_bias_weight", 0.12, 0.0, 1.0)
    saliency = normalize01((1.0 - center_weight) * base + center_weight * center_bias)
    percentile = get_float_param(params, "saliency_threshold_percentile", 96.0, 0.0, 100.0)
    minimum = get_float_param(params, "saliency_threshold_minimum", 0.20, 0.0, 1.0)
    thresh = np.percentile(saliency, percentile)
    mask = saliency >= max(minimum, thresh)
    weight = np.where(mask, saliency, 0.0)
    cx, cy = center_of_mass(weight)
    if float(np.sum(weight)) <= 1e-12:
        spread = 0.0
    else:
        spread = float(np.sqrt(np.sum(weight * ((xn - cx) ** 2 + (yn - cy) ** 2)) / (np.sum(weight) + 1e-12)))
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
    params: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    h, w = luminance.shape
    rng = np.random.default_rng() if rng is None else rng
    window = np.outer(np.hanning(h) if h > 1 else np.ones(h), np.hanning(w) if w > 1 else np.ones(w))
    centered = luminance - float(np.mean(luminance))
    spectrum = np.fft.fftshift(np.fft.fft2(centered * window))
    magnitude = np.abs(spectrum)
    sigma_coeff = get_float_param(params, "fourier_noise_sigma_coeff", 0.18, 0.0, 1.0)
    sigma = sigma_coeff * (clamp(float(random_factor) / 100.0, 0.0, 1.0) ** 2)
    if sigma > 0:
        magnitude *= np.exp(rng.normal(0.0, sigma, size=magnitude.shape))
    power = magnitude ** 2
    fy = np.fft.fftshift(np.fft.fftfreq(h))
    fx = np.fft.fftshift(np.fft.fftfreq(w))
    uu, vv = np.meshgrid(fx, fy)
    radius = np.sqrt(uu * uu + vv * vv)
    r = radius / max(float(np.max(radius)), 1e-12)

    dc_radius = get_float_param(params, "fourier_dc_radius", 0.025, 0.0, 0.20)
    low_cut, high_cut = get_range_param(params, "fourier_band_limits", (0.14, 0.34), 0.03, 0.95, 0.02)

    power_no_dc = power.copy()
    power_no_dc[r < dc_radius] = 0.0
    total = max(float(np.sum(power_no_dc)), 1e-12)
    low = float(np.sum(power_no_dc[(r >= dc_radius) & (r < low_cut)]) / total)
    mid = float(np.sum(power_no_dc[(r >= low_cut) & (r < high_cut)]) / total)
    high = float(np.sum(power_no_dc[r >= high_cut]) / total)
    centroid = float(np.sum(r * power_no_dc) / total)
    bandwidth = float(np.sqrt(np.sum(((r - centroid) ** 2) * power_no_dc) / total))
    theta = np.arctan2(vv, uu)
    orientation_width = get_float_param(params, "fourier_orientation_width", 0.38, 0.05, 0.95)
    horizontal_frequency_energy = float(np.sum(power_no_dc[np.abs(np.sin(theta)) < orientation_width]) / total)
    vertical_frequency_energy = float(np.sum(power_no_dc[np.abs(np.cos(theta)) < orientation_width]) / total)
    diagonal_frequency_energy = clamp(1.0 - horizontal_frequency_energy - vertical_frequency_energy, 0.0, 1.0)
    valid = power_no_dc[power_no_dc > 0]
    peak_lo, peak_hi = get_range_param(params, "fourier_peak_percentiles", (90.0, 99.7), 0.0, 100.0, 0.1)
    peak_divisor = get_float_param(params, "fourier_peak_log_divisor", 5.0, 0.5, 20.0)
    peak_score = 0.0 if valid.size == 0 else clamp(
        math.log1p(float(np.percentile(valid, peak_hi)) / (float(np.percentile(valid, peak_lo)) + 1e-12)) / peak_divisor,
        0.0,
        1.0,
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
    params: Optional[Dict[str, object]] = None,
    step_callback=None,
) -> Dict[str, object]:
    rng = np.random.default_rng() if rng is None else rng

    emit_step(step_callback, "Image resize and RGB normalization")
    max_side = get_int_param(params, "analysis_max_side", MAX_ANALYSIS_SIDE, 128, 2048)
    rgb = image_to_rgb_array(image, max_side=max_side)

    sigma_coeff = get_float_param(params, "image_noise_sigma_coeff", 0.045, 0.0, 0.25)
    sigma = sigma_coeff * (clamp(float(random_factor) / 100.0, 0.0, 1.0) ** 2)
    if sigma > 0:
        emit_step(step_callback, "Spatial noise perturbation")
        rgb = np.clip(rgb + rng.normal(0.0, sigma, size=rgb.shape), 0.0, 1.0)

    emit_step(step_callback, "Luminance and shadow/highlight thresholds")
    lum = rgb_to_luminance(rgb)
    lum_p_low, lum_p_high = get_range_param(params, "luminance_percentile_range", (5.0, 95.0), 0.0, 100.0, 0.1)
    p_low, p_high = float(np.percentile(lum, lum_p_low)), float(np.percentile(lum, lum_p_high))
    shadow_floor = get_float_param(params, "shadow_dark_floor", 0.18, 0.0, 1.0)
    highlight_floor = get_float_param(params, "highlight_bright_floor", 0.82, 0.0, 1.0)
    shadow_offset = get_float_param(params, "shadow_offset", 0.03, 0.0, 0.50)
    highlight_offset = get_float_param(params, "highlight_offset", 0.03, 0.0, 0.50)
    shadow = lum < max(shadow_floor, p_low + shadow_offset)
    highlight = lum > min(highlight_floor, p_high - highlight_offset)

    emit_step(step_callback, "Gradient edge map and entropy")
    edge, edge_density = compute_edge_map(lum, params=params)
    entropy_bins = get_int_param(params, "entropy_histogram_bins", 64, 8, 256)
    texture_entropy = normalized_histogram_entropy(edge, bins=entropy_bins)

    emit_step(step_callback, "2D FFT and Fourier band energies")
    fourier = analyze_fourier(lum, random_factor=random_factor, rng=rng, params=params)

    emit_step(step_callback, "HSV color statistics")
    hsv = rgb_to_hsv_features(rgb, lum)

    emit_step(step_callback, "Saliency map and centroid extraction")
    saliency, saliency_features = compute_saliency_map(rgb, lum, edge, params=params)

    emit_step(step_callback, "Symmetry and automatic music defaults")
    bright_weight = np.maximum(lum - np.mean(lum), 0.0)
    shadow_weight = np.where(shadow, 1.0 - lum, 0.0)
    high_weight = np.where(highlight, lum, 0.0)
    sym = compute_symmetry(lum)
    auto_complexity_lo, auto_complexity_hi = get_range_param(params, "auto_complexity_range", (0.25, 0.90), 0.05, 1.0, 0.01)
    auto_variation_lo, auto_variation_hi = get_range_param(params, "auto_variation_range", (0.25, 0.85), 0.0, 1.0, 0.01)
    auto_complexity = clamp(auto_complexity_lo + (auto_complexity_hi - auto_complexity_lo) * texture_entropy, auto_complexity_lo, auto_complexity_hi)
    auto_variation = clamp(auto_variation_lo + (auto_variation_hi - auto_variation_lo) * (1.0 - sym), auto_variation_lo, auto_variation_hi)

    features: Dict[str, float] = {
        "analysis_width": int(lum.shape[1]),
        "analysis_height": int(lum.shape[0]),
        "mean_brightness": float(np.mean(lum)),
        "contrast": float(np.std(lum)),
        "dynamic_range": float(p_high - p_low),
        "shadow_proportion": float(np.mean(shadow)),
        "highlight_proportion": float(np.mean(highlight)),
        "edge_density": float(edge_density),
        "texture_entropy": float(texture_entropy),
        "symmetry_score": float(sym),
        "auto_complexity": auto_complexity,
        "auto_variation_strength": auto_variation,
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
        "shadow_highlight_map": np.dstack([highlight.astype(float), np.zeros_like(lum), shadow.astype(float)]),
        "saliency_map": saliency,
    }
    return {"features": features, "maps": maps}


def compute_bar_settings(features: Dict[str, float], params: Optional[Dict[str, object]] = None) -> Tuple[int, int, int]:
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


def get_instrument_choices(synthesizer_type: str) -> List[str]:
    return sorted(GENERALUSER_GS_DISPLAY_TO_PROGRAM.keys()) if synthesizer_type == SYNTH_GENERALUSER_GS else sorted(SIMPLE_DISPLAY_TO_INTERNAL.keys())


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
        weights = {"piano": .35 + .35 * smooth, "chromatic_percussion": .18 + .65 * brightness + .25 * detail, "organ": .18 + .35 * smooth + .20 * darkness, "guitar": .16 + .35 * colorfulness + .22 * warm, "solo_strings": .20 + .35 * darkness + .20 * smooth, "brass": .12 + .50 * c + .35 * brightness, "reed": .18 + .28 * darkness + .20 * detail, "pipe": .18 + .45 * brightness + .20 * smooth, "synth_lead": .10 + .55 * detail + .30 * c, "ethnic": .12 + .42 * colorfulness + .45 * peak}
    elif layer == "texture":
        weights = {"chromatic_percussion": .25 + .70 * brightness + .45 * hi, "guitar": .18 + .30 * colorfulness + .25 * edge, "solo_strings": .12 + .40 * peak + .25 * detail, "synth_fx": .12 + .55 * detail + .30 * c, "ethnic": .18 + .55 * peak + .25 * colorfulness, "percussive": .14 + .55 * edge + .35 * peak, "sound_fx": .04 + .50 * detail + .35 * c}
    elif layer == "bass":
        weights = {"bass": .45 + .50 * lo + .25 * darkness, "organ": .18 + .35 * smooth + .30 * darkness, "solo_strings": .20 + .45 * darkness + .25 * smooth, "brass": .12 + .40 * c + .35 * darkness, "synth_lead": .08 + .35 * detail + .20 * peak, "percussive": .08 + .45 * edge + .30 * peak}
    elif layer == "pad":
        weights = {"organ": .18 + .42 * smooth + .20 * darkness, "solo_strings": .22 + .50 * darkness + .25 * smooth, "ensemble": .28 + .55 * smooth + .20 * sym, "synth_pad": .30 + .60 * smooth + .20 * colorfulness, "synth_fx": .12 + .35 * detail + .35 * colorfulness, "sound_fx": .04 + .35 * detail + .30 * c}
    elif layer == "solo":
        weights = {"chromatic_percussion": .24 + .52 * brightness + .30 * sal_peak, "solo_strings": .22 + .30 * darkness + .26 * sal_spread, "reed": .20 + .36 * sal_peak + .20 * detail, "pipe": .22 + .42 * brightness + .30 * sal_peak, "synth_lead": .16 + .50 * detail + .30 * c, "ethnic": .18 + .42 * colorfulness + .30 * peak, "guitar": .14 + .35 * colorfulness, "brass": .10 + .38 * c + .25 * brightness, "synth_fx": .08 + .35 * detail + .35 * sal_spread}
    else:
        weights = {"piano": .35 + .35 * smooth + .20 * brightness, "organ": .18 + .35 * smooth + .25 * darkness, "guitar": .18 + .35 * colorfulness + .15 * warm, "solo_strings": .16 + .35 * darkness + .25 * smooth, "ensemble": .24 + .45 * smooth + .25 * sym, "brass": .10 + .45 * c + .30 * brightness, "synth_pad": .18 + .45 * smooth + .25 * colorfulness}
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


def select_generaluser_instrument(features: Dict[str, float], layer: str, avoid: Optional[set] = None) -> str:
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
    b, sat, warm, c = features["mean_brightness"], features["mean_saturation"], features["warmth"], features["contrast"]
    if b > 0.60:
        return "Lydian" if warm > 0.06 else "Major pentatonic"
    if b > 0.42:
        return "Dorian" if (warm > 0.06 and sat > 0.38) or c > 0.22 else "Major pentatonic"
    return "Dorian" if warm > 0.05 and sat > 0.30 else "Natural minor"


def choose_instruments(features: Dict[str, float], mode: str, synthesizer_type: str, main="Soft piano", texture="Harp", bass="Cello-like bass", pad="Warm pad", chord="Soft piano", solo="Flute") -> Tuple[str, str, str, str, str, str]:
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
    hi, lo, peak, sat, warm, c = features["high_frequency_energy"], features["low_frequency_energy"], features["periodic_peak_score"], features["mean_saturation"], features["warmth"], features["contrast"]
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
        return tuple(out)  # type: ignore[return-value]
    main_i = "bright_bell" if h > 0.14 and hi > 0.28 else "celesta" if b > 0.64 else "kalimba" if peak > 0.58 else "marimba" if peak > 0.48 else "harp" if warm > 0.07 and sat > 0.42 else "synth_pluck" if c > 0.25 and hi > 0.28 else "soft_piano"
    tex_i = "bright_bell" if hi > 0.44 or h > 0.16 else "celesta" if hi > 0.32 else "kalimba" if peak > 0.55 else "harp" if sat > 0.45 and warm > 0.02 else "music_box"
    bass_i = "cello" if sh > 0.26 or b < 0.36 else "soft_bass"
    pad_i = "warm_pad" if (lo > 0.52 and warm > 0.04) or sh > 0.20 else "glass_pad"
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
    seed = int(features["dominant_hue"] * 997 + features["periodic_peak_score"] * 113 + features.get("texture_entropy", 0.0) * 71 + features.get("saliency_centroid_x", 0.0) * 53)
    if n >= 7:
        pools = [[0, 4, 5, 3], [0, 5, 3, 4], [0, 2, 5, 4], [0, 3, 1, 4]]
    else:
        pools = [[0, 2, 3, 4], [0, 3, 2, 1], [0, 1, 4, 2]]
    return [chord_from_scale_degree(intervals, d % n) for d in pools[seed % len(pools)]]


def time_slice_statistics(luminance: np.ndarray, n_slices: int) -> List[Dict[str, float]]:
    h, w = luminance.shape
    stats = []
    for i in range(n_slices):
        x0, x1 = int(round(i * w / n_slices)), max(1, int(round((i + 1) * w / n_slices)))
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
        x_norm = xx / max(1, w - 1)
        y_norm = yy / max(1, h - 1)
        strength = float(sal[yy, xx])
        t = clamp(x_norm * duration + 0.10 * beat * math.sin(1.7 * k), 0.0, max(0.0, duration - 0.25))
        note = melody_notes[int(round(clamp(1.0 - y_norm, 0.0, 1.0) * (len(melody_notes) - 1)))] + 12
        if k % 5 == 3:
            note += 7
        dur = clamp((0.32 + 0.70 * strength + 0.20 * features.get("saliency_spread", 0.0)) * beat, dur_min * beat, dur_max * beat)
        vel = clamp((0.18 + 0.56 * strength) * gain, 0.05, 0.92)
        pan = clamp(-0.82 + 1.64 * x_norm, -0.9, 0.9)
        events.append(NoteEvent(t, dur, int(clamp(note, 48, 112)), vel, solo_inst, pan, "solo"))


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
    features: Dict[str, float] = analysis["features"]  # type: ignore[assignment]
    maps: Dict[str, np.ndarray] = analysis["maps"]  # type: ignore[assignment]
    lum = maps["luminance"]
    b, c, sh = features["mean_brightness"], features["contrast"], features["shadow_proportion"]
    edge, sat, warm = features["edge_density"], features["mean_saturation"], features["warmth"]
    lo, hi, centroid, bw, peak = features["low_frequency_energy"], features["high_frequency_energy"], features["fourier_centroid"], features["fourier_bandwidth"], features["periodic_peak_score"]

    emit_step(step_callback, "Tonal mapping: key, scale and tempo")
    key_index = int(round(features["dominant_hue"] * 12.0)) % 12
    key_name = KEY_NAMES[key_index]
    scale_name = choose_scale(features, requested_scale)
    intervals = SCALES[scale_name]
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
    beat = 60.0 / tempo
    bars = int(clamp(int(bars), 1, 64))
    max_render_seconds = get_float_param(params, "max_render_seconds", MAX_RENDER_SECONDS, 8.0, 240.0)
    duration = min(max_render_seconds, bars * 4 * beat)

    emit_step(step_callback, "Instrument scoring and layer assignment")
    main_i, tex_i, bass_i, pad_i, chord_i, solo_i = choose_instruments(features, instrument_mode, synthesizer_type, main_layer, texture_layer, bass_layer, pad_layer, chord_layer, solo_layer)
    if synthesizer_type != SYNTH_GENERALUSER_GS:
        solo_i = "none"

    emit_step(step_callback, "Chord progression and scale-note lattice")
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
    gains = {"main": 10 ** (main_gain_db / 20), "texture": 10 ** (texture_gain_db / 20), "bass": 10 ** (bass_gain_db / 20), "pad": 10 ** (pad_gain_db / 20), "chord": 10 ** (chord_gain_db / 20)}
    double_hit_threshold = get_float_param(params, "chord_double_hit_high_freq_threshold", 0.22, 0.0, 1.0)

    emit_step(step_callback, "Pad, chord and bass event generation")
    for bar in range(bars):
        start = bar * 4 * beat
        chord = progression[(bar + (1 if variation > 0.45 and bar >= bars // 2 else 0)) % len(progression)]
        chord_notes = [root + x for x in chord]
        if pad_i != "none":
            for n in chord_notes:
                events.append(NoteEvent(start, 4.05 * beat, int(clamp(n + 12, 36, 88)), clamp(pad_velocity * gains["pad"], 0, 1), pad_i, 0.15 * math.sin(bar * 0.7), "pad"))
        if chord_i != "none":
            for hit in range(2 if hi > double_hit_threshold else 1):
                for n in chord_notes:
                    events.append(NoteEvent(start + hit * 2 * beat, 1.75 * beat, int(clamp(n + 12, 38, 92)), clamp(chord_velocity * (0.92 if hit else 1.0) * gains["chord"], 0, 1), chord_i, pan_bias * 0.45, "chord"))
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
        pos = clamp(1 - sl["y_centroid"] + 0.18 * (sl["energy"] - b), 0, 1)
        note = melody_notes[int(round(pos * (len(melody_notes) - 1)))]
        section = min(3, int((i / max(1, len(slices))) * 4))
        note += int(round([0, 2, -2, 5][section] * variation))
        dur = (0.42 + 0.52 * (1 - hi) + 0.25 * sl["energy"]) * beat
        vel = clamp((melody_velocity + 0.25 * sl["contrast"]) * gains["main"], 0, 1)
        events.append(NoteEvent(i * 0.5 * beat, dur, int(clamp(note, 36, 100)), vel, main_i, clamp(pan_bias + 0.20 * math.sin(i * 0.37), -0.75, 0.75), "main"))

    emit_step(step_callback, "Texture arpeggios and percussion ticks")
    density = clamp(0.20 + 0.80 * complexity + 0.75 * hi + 0.45 * bw, 0, 1)
    texture_density_threshold = get_float_param(params, "texture_density_threshold", 0.28, 0.0, 1.0)
    texture_fast_threshold = get_float_param(params, "texture_fast_threshold", 0.55, 0.0, 1.0)
    percussion_density_threshold = get_float_param(params, "percussion_density_threshold", 0.18, 0.0, 1.0)
    percussion_fast_threshold = get_float_param(params, "percussion_fast_threshold", 0.55, 0.0, 1.0)
    percussion_skip_threshold = get_float_param(params, "percussion_skip_threshold", 0.62, 0.0, 1.0)
    if density > texture_density_threshold and tex_i != "none":
        interval = 0.5 * beat if density > texture_fast_threshold else beat
        for j in range(int(duration / interval)):
            t = j * interval
            chord = progression[int(t // (4 * beat)) % len(progression)]
            pat = chord + [chord[1] + 12, chord[2] + 12]
            events.append(NoteEvent(t, 0.34 * beat, int(clamp(root + pat[j % len(pat)] + 12, 45, 96)), clamp((0.16 + 0.40 * hi + 0.22 * edge) * gains["texture"], 0, 1), tex_i, clamp(-0.45 + 0.90 * ((j % 8) / 7), -0.65, 0.65), "texture"))
    if density > percussion_density_threshold:
        sub = 0.5 * beat if density < percussion_fast_threshold else 0.25 * beat
        for j in range(int(duration / sub)):
            if j % 2 == 1 and density < percussion_skip_threshold:
                continue
            events.append(NoteEvent(j * sub, 0.08 * beat, 76 if j % 4 in [0, 3] else 72, clamp((0.10 + 0.42 * density) * (1.0 if j % 8 == 0 else 0.62), 0.05, 0.55), "texture_tick", 0.55 * math.sin(j * 0.91), "texture"))

    if synthesizer_type == SYNTH_GENERALUSER_GS:
        emit_step(step_callback, "Saliency-driven solo/accent events")
        add_saliency_solo_events(events, maps, features, melody_notes, duration, beat, solo_i, solo_gain_db, params=params)

    events = [ev for ev in events if ev.start < duration]
    events.sort(key=lambda ev: (ev.start, ev.layer, ev.midi))
    info = CompositionInfo(tempo, bars, duration, key_name, scale_name, main_i, tex_i, bass_i, pad_i, chord_i, solo_i, describe_mood(features), {"Saliency": "drives the GeneralUser GS solo/accent layer"})
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
    else:
        sig = np.sin(2 * np.pi * freq * t)
        env = adsr_envelope(n, sr, .01, .10, .50, min(.20, duration * .4))
    sig = sig * env
    mx = float(np.max(np.abs(sig))) if sig.size else 0
    if mx > 1e-12:
        sig = sig / mx
    return sig * velocity


def normalize_master_audio(audio: np.ndarray, target_peak: float = MASTER_TARGET_PEAK, target_rms: float = MASTER_TARGET_RMS) -> np.ndarray:
    """Master-bus processing after all layers have been mixed.

    This does not change individual layer gains. It only treats the final stereo bus
    before WAV/MP3 export: DC removal, RMS headroom, peak headroom, and a final
    safety clip above the target peak.
    """
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


def render_events(events: List[NoteEvent], duration: float, sr: int = DEFAULT_SAMPLE_RATE, layer: Optional[str] = None, normalize: bool = True) -> np.ndarray:
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
    track.extend(write_var_len(0)); track.extend(b"\xFF\x2F\x00")
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq) + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


def render_with_fluidsynth(
    events: List[NoteEvent],
    duration: float,
    tempo: float,
    sr: int,
    params: Optional[Dict[str, object]] = None,
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
        fluid_gain = get_float_param(params, "fluidsynth_master_gain", FLUIDSYNTH_MASTER_GAIN, 0.05, 2.0)
        cmd = [exe, "-ni", "-g", f"{fluid_gain:.3f}", "-F", wav, "-r", str(sr), sf2, mid]
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=90)
            audio, rendered_sr = wav_file_to_audio(wav)
        except Exception as exc:
            return None, f"GeneralUser GS rendering failed with FluidSynth: {exc}. Falling back to Simple synthesis."
    if rendered_sr != sr:
        return None, f"GeneralUser GS rendered at {rendered_sr} Hz instead of {sr} Hz. Falling back to Simple synthesis."
    target = int(round((duration + .8) * sr))
    audio = audio[:target] if audio.shape[0] >= target else np.vstack([audio, np.zeros((target - audio.shape[0], 2))])
    target_peak = get_float_param(params, "master_target_peak", MASTER_TARGET_PEAK, 0.10, 0.98)
    target_rms = get_float_param(params, "master_target_rms", MASTER_TARGET_RMS, 0.01, 0.50)
    return normalize_master_audio(audio, target_peak=target_peak, target_rms=target_rms), f"Audio rendered with GeneralUser GS through FluidSynth (master gain {fluid_gain:.2f})."


def render_backend(
    events: List[NoteEvent],
    info: CompositionInfo,
    synthesizer_type: str,
    params: Optional[Dict[str, object]] = None,
) -> Tuple[np.ndarray, str]:
    target_peak = get_float_param(params, "master_target_peak", MASTER_TARGET_PEAK, 0.10, 0.98)
    target_rms = get_float_param(params, "master_target_rms", MASTER_TARGET_RMS, 0.01, 0.50)
    if synthesizer_type == SYNTH_GENERALUSER_GS:
        audio, msg = render_with_fluidsynth(events, info.duration, info.tempo, DEFAULT_SAMPLE_RATE, params=params)
        if audio is not None:
            return audio, msg
        return normalize_master_audio(render_events(events, info.duration, DEFAULT_SAMPLE_RATE, normalize=False), target_peak=target_peak, target_rms=target_rms), msg
    return normalize_master_audio(render_events(events, info.duration, DEFAULT_SAMPLE_RATE, normalize=False), target_peak=target_peak, target_rms=target_rms), "Audio rendered with the Simple procedural synthesizer."


def audio_to_mp3_bytes(audio: np.ndarray, sr: int) -> Tuple[Optional[bytes], str]:
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    try:
        import lameenc  # type: ignore
        enc = lameenc.Encoder(); enc.set_bit_rate(192); enc.set_in_sample_rate(sr); enc.set_channels(2); enc.set_quality(2)
        data = enc.encode(pcm.tobytes()) + enc.flush()
        if data:
            return bytes(data), "MP3 export generated with lameenc."
    except Exception as exc:
        lame_error = str(exc)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None, f"MP3 export requires lameenc or ffmpeg. lameenc error: {lame_error}"
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "input.wav"); mp3 = os.path.join(tmp, "output.mp3")
        with open(wav, "wb") as f:
            f.write(audio_to_wav_bytes(audio, sr))
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", wav, "-codec:a", "libmp3lame", "-b:a", "192k", mp3], check=True, timeout=45)
        return open(mp3, "rb").read(), "MP3 export generated with ffmpeg."


def fig_to_bytes(fig: plt.Figure, tight: bool = True) -> bytes:
    buf = io.BytesIO()
    kwargs = {"format": "png", "dpi": 130, "transparent": True, "facecolor": "none", "edgecolor": "none"}
    if tight:
        kwargs["bbox_inches"] = "tight"
    fig.savefig(buf, **kwargs)
    plt.close(fig)
    return buf.getvalue()


def plot_text_color() -> str:
    return "black" if str(st.get_option("theme.base")).lower() == "light" else "white"


def style_ax(fig: plt.Figure, ax: plt.Axes, grid: bool = True) -> str:
    color = plot_text_color()
    fig.patch.set_alpha(0); ax.set_facecolor((0, 0, 0, 0))
    ax.title.set_color(color); ax.xaxis.label.set_color(color); ax.yaxis.label.set_color(color); ax.tick_params(colors=color)
    for sp in ax.spines.values(): sp.set_color(color)
    if grid: ax.grid(True, color=color, alpha=.25)
    return color


def plot_map(data: np.ndarray, title: str, cmap: Optional[str] = "gray") -> bytes:
    arr = np.asarray(data); h, w = arr.shape[:2]; aspect = w / max(1, h)
    fw = 4.8; ih = fw / max(aspect, 1e-6); th = .42
    fig, ax = plt.subplots(figsize=(fw, ih + th)); color = style_ax(fig, ax, False)
    ax.imshow(arr, cmap=cmap, aspect="equal"); ax.set_title(title, fontsize=10, color=color, pad=6); ax.axis("off")
    fig.subplots_adjust(left=0, right=1, bottom=0, top=ih / (ih + th))
    return fig_to_bytes(fig, tight=False)


def mono(audio: np.ndarray) -> np.ndarray:
    return np.mean(audio, axis=1) if audio.ndim == 2 else np.asarray(audio)


def plot_waveform(audio: np.ndarray, sr: int, title="Waveform") -> bytes:
    m = mono(audio); t = np.arange(len(m)) / sr
    fig, ax = plt.subplots(figsize=(4.8, 2.6)); color = style_ax(fig, ax)
    ax.plot(t, m, linewidth=.7); ax.set_xlabel("Time (s)", color=color); ax.set_ylabel("Amplitude", color=color); ax.set_title(title, color=color)
    return fig_to_bytes(fig)


def plot_frequency(audio: np.ndarray, sr: int, title="Fourier magnitude") -> bytes:
    m = mono(audio); fig, ax = plt.subplots(figsize=(4.8, 2.6)); color = style_ax(fig, ax)
    if m.size < 2 or float(np.max(np.abs(m))) <= 1e-12:
        ax.text(.5, .5, "No visible spectral energy", ha="center", va="center", color=color, transform=ax.transAxes)
    else:
        spec = np.fft.rfft(m * np.hanning(m.size)); freqs = np.fft.rfftfreq(m.size, 1 / sr); mag = np.abs(spec); mag = mag / max(float(np.max(mag)), 1e-12)
        ax.plot(freqs, mag, linewidth=.8); ax.set_xlim(0, min(8000, sr // 2))
    ax.set_xlabel("Frequency (Hz)", color=color); ax.set_ylabel("Magnitude", color=color); ax.set_title(title, color=color)
    return fig_to_bytes(fig)


def format_percent(x: float) -> str:
    return f"{100 * x:.1f}%"


def ensure_bytes(x: object) -> bytes:
    if x is None: return b""
    if isinstance(x, bytes): return x
    if isinstance(x, bytearray): return bytes(x)
    if isinstance(x, io.BytesIO): return x.getvalue()
    raise TypeError(type(x).__name__)


def make_signature(**kwargs: object) -> str:
    return hashlib.sha256(json.dumps(kwargs, sort_keys=True, default=str).encode()).hexdigest()


def read_markdown_document(filename: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    for p in [os.path.join(base, filename), os.path.join(os.getcwd(), filename)]:
        if os.path.exists(p):
            return open(p, "r", encoding="utf-8").read()
    return ""


def split_sections(md: str) -> List[Tuple[str, str]]:
    sections, title, lines = [], "Documentation", []
    for line in md.splitlines():
        if line.startswith("## "):
            if lines and "table of contents" not in title.lower() and "table des" not in title.lower():
                sections.append((title, "\n".join(lines).strip()))
            title, lines = line[3:].strip(), [line]
        else:
            lines.append(line)
    if lines and "table of contents" not in title.lower() and "table des" not in title.lower():
        sections.append((title, "\n".join(lines).strip()))
    return sections



# ============================================================
# Documentation helpers  (title-based, matching audio_visualization)
# ============================================================

def _split_markdown_by_h2(text: str) -> "Dict[str, str]":
    import re as _re
    sections: Dict[str, str] = {}
    for part in _re.split(r"(?m)^##\s+", text.strip()):
        part = part.strip()
        if not part:
            continue
        title = part.splitlines()[0].strip()
        if title.lower() in {"table des matières", "table of contents"}:
            continue
        sections[title] = "## " + part
    if not sections and text.strip():
        sections["Documentation"] = text
    return sections


def _load_doc(filename: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    for p in [os.path.join(base, filename), os.path.join(os.getcwd(), filename)]:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as fh:
                return fh.read()
    return ""


DOC_FR_SECTIONS = _split_markdown_by_h2(_load_doc("documentation_fr.md"))
DOC_EN_SECTIONS = _split_markdown_by_h2(_load_doc("documentation_en.md"))
DOC_FR_TITLES   = list(DOC_FR_SECTIONS.keys())
DOC_EN_TITLES   = list(DOC_EN_SECTIONS.keys())


# ============================================================
# Output filename helper
# ============================================================

def _output_stem(image_name: str, max_len: int = 22) -> str:
    import re as _re
    base = os.path.splitext(image_name or "photo")[0]
    base = _re.sub(r"[^\w\-]", "_", base)[:max_len].strip("_") or "photo"
    return f"photosono-{base}"


# ============================================================
# Page configuration & CSS  (identical tokens to audio_visualization)
# ============================================================

def configure_page() -> None:
    st.set_page_config(
        page_title="Photo Sonification",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 100%;
            padding-top: 2.75rem;
            padding-left: 1.5rem;
            padding-right: 1.5rem;
            padding-bottom: 2.5rem;
        }
        .app-header {
            display: flex;
            align-items: baseline;
            gap: 0.75rem;
            margin-bottom: 0.15rem;
        }
        .app-title {
            font-weight: 800;
            font-size: 1.65rem;
            letter-spacing: -0.02em;
            line-height: 1;
            color: inherit;
        }
        .app-subtitle {
            font-size: 0.72rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: #9ca3af;
            margin-bottom: 1.1rem;
            margin-top: 0.1rem;
        }
        h2 {
            text-align: center;
            border: 1px solid rgba(255, 75, 75, 0.18);
            border-radius: 0.35rem;
            padding: 0.55rem 0.75rem;
            margin-top: 0.25rem;
            margin-bottom: 1.00rem;
            background: rgba(255, 75, 75, 0.04);
        }
        div[data-testid="stTabs"] [role="tablist"] {
            margin-top: 0;
            gap: 0.3rem;
            border-bottom: 1px solid rgba(255, 75, 75, 0.15);
            padding-bottom: 0;
        }
        div[data-testid="stTabs"] button[role="tab"] {
            padding: 0.45rem 1.0rem;
            border-radius: 0.35rem 0.35rem 0 0;
        }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            color: #FF4B4B !important;
            border-bottom: 2px solid #FF4B4B !important;
        }
        div[data-testid="stButton"] > button {
            border-radius: 0.35rem;
            min-height: 2.5rem;
            white-space: normal;
            text-align: center;
            transition: all 0.15s ease;
        }
        div[data-testid="stButton"] > button[kind="primary"] {
            font-weight: 700;
            letter-spacing: 0.03em;
        }
        div[data-testid="stButton"] > button[kind="primary"]:not([disabled]):hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(255, 75, 75, 0.35);
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 0.45rem !important;
        }
        div[data-testid="stExpander"] summary {
            font-weight: 700;
            font-size: 0.9rem;
            letter-spacing: 0.04em;
        }
        .small-muted {
            color: #9ca3af;
            font-size: 0.80rem;
            line-height: 1.5;
        }
        .result-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem 1.2rem;
            margin-top: 0.6rem;
        }
        .result-meta-item {
            font-size: 0.78rem;
            color: #9ca3af;
        }
        .result-meta-item span {
            color: #FF4B4B;
            font-weight: 600;
        }
        .section-pill {
            display: inline-block;
            font-size: 0.70rem;
            font-weight: 600;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            background: rgba(255, 75, 75, 0.10);
            border: 1px solid rgba(255, 75, 75, 0.22);
            border-radius: 0.25rem;
            padding: 0.1rem 0.45rem;
            color: #FF4B4B;
            margin-bottom: 0.4rem;
        }
        .param-group-label {
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: #9ca3af;
            margin-bottom: 0.5rem;
            border-bottom: 1px solid rgba(255, 75, 75, 0.12);
            padding-bottom: 0.3rem;
        }
        .portfolio-link-row {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            gap: 0.42rem;
            min-height: 2.35rem;
            margin: 0 0 -2.65rem 0;
            padding-right: 0.15rem;
            position: relative;
            z-index: 20;
        }
        .portfolio-link,
        .portfolio-link:visited {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            height: 2rem !important;
            border: 1px solid rgba(250, 250, 250, 0.18) !important;
            border-radius: 0.35rem !important;
            color: inherit !important;
            text-decoration: none !important;
            font-size: 0.78rem !important;
            font-weight: 600 !important;
            line-height: 1 !important;
            background: rgba(255, 255, 255, 0.025) !important;
            white-space: nowrap !important;
            box-sizing: border-box !important;
            overflow: hidden !important;
            transition: all 0.15s ease !important;
        }
        .portfolio-link:hover {
            border-color: #FF4B4B !important;
            color: #FF4B4B !important;
            background: rgba(255, 75, 75, 0.08) !important;
            text-decoration: none !important;
            transform: translateY(-1px) !important;
        }
        .portfolio-link.icon-only,
        .portfolio-link.icon-only:visited {
            width: 2rem !important; min-width: 2rem !important;
            max-width: 2rem !important; padding: 0 !important; gap: 0 !important;
        }
        .portfolio-link.with-label,
        .portfolio-link.with-label:visited {
            width: auto !important; padding: 0 0.58rem !important; gap: 0.38rem !important;
        }
        .portfolio-icon {
            display: block !important;
            width: 1.10rem !important; height: 1.10rem !important;
            min-width: 1.10rem !important; max-width: 1.10rem !important;
            object-fit: contain !important; flex: 0 0 auto !important;
            margin: 0 !important; padding: 0 !important; border: 0 !important;
        }
        .portfolio-label { display: inline-block !important; }
        .portfolio-link.icon-only .portfolio-label {
            display: none !important; width: 0 !important;
            min-width: 0 !important; max-width: 0 !important;
            margin: 0 !important; padding: 0 !important; overflow: hidden !important;
        }
        @media (max-width: 1180px) {
            .portfolio-link-row {
                justify-content: flex-start;
                flex-wrap: wrap;
                margin-bottom: 0.65rem;
                padding-right: 0;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# Session state
# ============================================================

def init_session_state() -> None:
    defaults: Dict[str, object] = {
        "generation_result":       None,
        "parameter_defaults":      None,
        "photo_analysis_cache":    None,
        "run_in_progress":         False,
        "run_requested":           False,
        "last_run_status":         None,
        "doc_fr_title": DOC_FR_TITLES[0] if DOC_FR_TITLES else "",
        "doc_en_title": DOC_EN_TITLES[0] if DOC_EN_TITLES else "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def request_run() -> None:
    """Lock the Run button and mark a run as pending (on_click callback)."""
    st.session_state.run_requested  = True
    st.session_state.run_in_progress = True
    st.session_state.last_run_status = None


# ============================================================
# Documentation tab renderer
# ============================================================

def _set_doc_section(state_key: str, title: str) -> None:
    st.session_state[state_key] = title


def render_documentation_tab(
    titles: List[str], sections: Dict[str, str], state_key: str
) -> None:
    if not titles:
        st.warning("Documentation file not found.")
        return
    if st.session_state.get(state_key) not in sections:
        st.session_state[state_key] = titles[0]
    left_col, right_col = st.columns([1, 3], gap="large")
    with left_col:
        for title in titles:
            st.button(
                title,
                key=f"{state_key}_{title}",
                type="primary" if st.session_state[state_key] == title else "secondary",
                width="stretch",
                on_click=_set_doc_section,
                args=(state_key, title),
            )
    with right_col:
        st.markdown(sections[st.session_state[state_key]])


# ============================================================
# App tab
# ============================================================

def render_app_tab() -> None:

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="app-header"><span class="app-title">Photo Sonification</span></div>'
        '<div class="app-subtitle">'
        'Image analysis · Fourier feature extraction · Procedural music synthesis'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Pre-declare mutable variables (filled inside the input_col with-block) ─
    uploaded_bytes:   Optional[bytes]        = None
    uploaded_image:   Optional[Image.Image]  = None
    uploaded_hash:    Optional[str]          = None
    upload_error:     Optional[str]          = None
    input_name:       str                    = DEFAULT_IMAGE_NAME
    input_is_default: bool                   = False

    # =========================================================================
    # Row 1:  input column  |  output column
    # =========================================================================
    input_col, output_col = st.columns([1.0, 1.35], gap="large")

    # ── Input column ──────────────────────────────────────────────────────────
    with input_col:
        with st.container(border=True):
            st.markdown("#### Input photo")
            uploaded = st.file_uploader(
                "Input photo",
                type=SUPPORTED_IMAGE_TYPES,
                accept_multiple_files=False,
                label_visibility="collapsed",
            )
            if uploaded is not None:
                try:
                    uploaded_bytes = uploaded.getvalue()
                    uploaded_hash  = hashlib.sha256(uploaded_bytes).hexdigest()
                    uploaded_image = open_image_from_bytes(uploaded_bytes, uploaded.name)
                    input_name     = uploaded.name
                    st.image(uploaded_image, width="stretch")
                except Exception as exc:
                    upload_error = str(exc)
                    st.error(f"Could not read this image: {exc}")
            else:
                try:
                    uploaded_bytes   = load_image_bytes_from_url(DEFAULT_IMAGE_URL)
                    uploaded_hash    = hashlib.sha256(uploaded_bytes).hexdigest()
                    uploaded_image   = open_image_from_bytes(uploaded_bytes, DEFAULT_IMAGE_URL)
                    input_is_default = True
                    st.image(uploaded_image, width="stretch")
                    st.markdown(
                        f'<p class="small-muted">{DEFAULT_IMAGE_CAPTION}</p>',
                        unsafe_allow_html=True,
                    )
                except Exception as exc:
                    upload_error = str(exc)
                    st.info("The default test image could not be loaded. Please upload a photo.")

            st.markdown("")
            st.button(
                "▶  GENERATE AUDIO",
                type="primary",
                width="stretch",
                disabled=(
                    uploaded_image is None
                    or st.session_state.run_in_progress
                ),
                on_click=request_run,
            )

    # ── Derive controls_active AFTER input_col (uploaded_hash is now set) ─────
    parameter_defaults = st.session_state.get("parameter_defaults")
    controls_active = (
        uploaded_hash is not None
        and isinstance(parameter_defaults, dict)
        and parameter_defaults.get("image_id") == uploaded_hash
    )
    if not controls_active:
        for _k in ["mapping_style", "scale_selection", "synthesizer_type"]:
            st.session_state.pop(_k, None)
    if uploaded_hash is None or not (
        isinstance(st.session_state.get("photo_analysis_cache"), dict)
        and st.session_state["photo_analysis_cache"].get("image_id") == uploaded_hash
    ):
        st.session_state["photo_analysis_cache"] = None

    if controls_active:
        bar_min            = int(parameter_defaults["bar_min"])
        bar_max            = int(parameter_defaults["bar_max"])
        bar_default        = int(parameter_defaults["bar_default"])
        variation_default  = float(parameter_defaults["variation_default"])
        complexity_default = float(parameter_defaults["complexity_default"])
    else:
        bar_min, bar_max, bar_default = 4, 24, 8
        variation_default, complexity_default = 0.55, 0.72

    # Validate stored result against current image
    result = st.session_state.get("generation_result")
    if not (
        uploaded_hash is not None
        and isinstance(result, dict)
        and result.get("image_id") == uploaded_hash
    ):
        result = None

    # ── Output column ─────────────────────────────────────────────────────────
    with output_col:
        with st.container(border=True):
            st.markdown("#### Output audio")

            # Progress placeholders — updated live during computation below
            progress_status_placeholder = st.empty()
            progress_bar_placeholder    = st.empty()

            if st.session_state.last_run_status == "Done":
                progress_status_placeholder.success("Done — 100%")

            if result is None:
                st.info(
                    "Generated audio will appear here after you click **▶ Generate Audio**."
                )
                st.download_button(
                    "⬇  Download MP3",
                    data=b"",
                    file_name="photosono.mp3",
                    mime="audio/mpeg",
                    disabled=True,
                    width="stretch",
                )
                st.download_button(
                    "⬇  Download MIDI",
                    data=b"",
                    file_name="photosono.mid",
                    mime="audio/midi",
                    disabled=True,
                    width="stretch",
                )
            else:
                info_r: CompositionInfo = result["info"]
                stem = _output_stem(result.get("image_name", input_name))

                st.audio(result["wav_bytes"], format="audio/wav")

                meta_html = (
                    '<div class="result-meta">'
                    f'<div class="result-meta-item">Tempo <span>{info_r.tempo:.1f} BPM</span></div>'
                    f'<div class="result-meta-item">Length <span>{info_r.bars} bars / {info_r.duration:.1f} s</span></div>'
                    f'<div class="result-meta-item">Key / scale <span>{info_r.key_name} / {info_r.scale_name}</span></div>'
                    f'<div class="result-meta-item">Mood <span>{info_r.mood}</span></div>'
                    '</div>'
                )
                st.markdown(meta_html, unsafe_allow_html=True)
                st.markdown("")

                st.markdown('<div class="section-pill">Instruments</div>', unsafe_allow_html=True)
                inst_line = (
                    f"Main · {instrument_label(info_r.main_instrument)} &nbsp; "
                    f"Texture · {instrument_label(info_r.texture_instrument)} &nbsp; "
                    f"Bass · {instrument_label(info_r.bass_instrument)} &nbsp; "
                    f"Pad · {instrument_label(info_r.pad_instrument)} &nbsp; "
                    f"Chord · {instrument_label(info_r.chord_instrument)}"
                )
                if info_r.solo_instrument != "none":
                    inst_line += f" &nbsp; Solo · {instrument_label(info_r.solo_instrument)}"
                st.markdown(f'<p class="small-muted">{inst_line}</p>', unsafe_allow_html=True)

                synth_msg = result.get("synth_message", "")
                if synth_msg:
                    st.markdown(
                        f'<p class="small-muted"><em>{synth_msg}</em></p>',
                        unsafe_allow_html=True,
                    )
                st.markdown("")

                st.download_button(
                    "⬇  Download MP3",
                    data=ensure_bytes(result["mp3_bytes"]),
                    file_name=f"{stem}.mp3",
                    mime="audio/mpeg",
                    disabled=result["mp3_bytes"] is None,
                    width="stretch",
                )
                st.download_button(
                    "⬇  Download MIDI",
                    data=ensure_bytes(result["midi_bytes"]),
                    file_name=f"{stem}.mid",
                    mime="audio/midi",
                    width="stretch",
                )
                if result["mp3_bytes"] is None:
                    st.markdown(
                        f'<p class="small-muted">{result.get("mp3_message", "MP3 export unavailable.")}</p>',
                        unsafe_allow_html=True,
                    )

    # =========================================================================
    # Row 2:  Parameters  (tabbed mini-pages, matching audio_visualization)
    # =========================================================================
    with st.expander("⚙  Parameters", expanded=False):
        if not controls_active:
            st.info(
                "Click **▶ Generate Audio** once to analyse the photo and unlock photo-adaptive musical defaults. "
                "The analysis, Fourier and saliency thresholds below already use safe default values."
                if uploaded_image is not None
                else "Upload a photo first, then click **▶ Generate Audio** to unlock the parameters."
            )

        advanced_params: Dict[str, object] = {}
        threshold_controls_enabled = uploaded_image is not None

        (
            tab_struct,
            tab_analysis,
            tab_fourier,
            tab_tonal,
            tab_synth,
            tab_inst,
        ) = st.tabs([
            "Structure",
            "Image analysis",
            "Fourier & saliency",
            "Tonality & Tempo",
            "Synth & Mix",
            "Instruments",
        ])

        # ── Tab 1 · Structure ────────────────────────────────────────────────
        with tab_struct:
            s_left, s_right = st.columns(2, gap="large")
            with s_left:
                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Musical shape</div>', unsafe_allow_html=True)
                    number_of_bars = st.slider(
                        "Number of bars",
                        bar_min, bar_max, bar_default, 1,
                        disabled=not controls_active,
                        help="Total length of the composition in 4/4 bars. The min/max/default values are photo-adaptive after the first run.",
                    )
                    variation_strength = st.slider(
                        "Variation strength",
                        0.0, 1.0, variation_default, 0.01,
                        disabled=not controls_active,
                        help="Default derived from image symmetry. Controls how much the second half diverges from the first.",
                    )
                    complexity = st.slider(
                        "Composition complexity",
                        0.10, 1.00, complexity_default, 0.01,
                        disabled=not controls_active,
                        help="Default derived from texture entropy. Controls note density and arpeggio activity.",
                    )
                    random_factor = st.slider(
                        "Random factor",
                        0, 100, 0, 1,
                        disabled=not controls_active,
                        help="Adds controlled perturbation to the image and Fourier-domain analysis before composition.",
                    )
                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Automatic range mapping</div>', unsafe_allow_html=True)
                    auto_complexity_range = st.slider(
                        "Auto complexity range",
                        0.05, 1.00, (0.25, 0.90), 0.01,
                        disabled=not threshold_controls_enabled,
                        help="Texture entropy is mapped into this range. Streamlit keeps the low/high limits ordered.",
                    )
                    auto_variation_range = st.slider(
                        "Auto variation range",
                        0.00, 1.00, (0.25, 0.85), 0.01,
                        disabled=not threshold_controls_enabled,
                        help="1 - symmetry is mapped into this range. Streamlit keeps the low/high limits ordered.",
                    )
                    advanced_params["auto_complexity_range"] = auto_complexity_range
                    advanced_params["auto_variation_range"] = auto_variation_range

            with s_right:
                

                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Auto bar estimator</div>', unsafe_allow_html=True)
                    auto_bar_min_range = st.slider(
                        "Auto min-bars range",
                        1, 32, (4, 8), 1,
                        disabled=not threshold_controls_enabled,
                    )
                    auto_bar_max_range = st.slider(
                        "Auto max-bars range",
                        2, 64, (12, 24), 1,
                        disabled=not threshold_controls_enabled,
                    )
                    auto_bar_default_range = st.slider(
                        "Auto default-bars range",
                        1, 64, (6, 16), 1,
                        disabled=not threshold_controls_enabled,
                    )
                    bar_weight_texture = st.slider("Weight · texture", 0.0, 2.0, 0.40, 0.01, disabled=not threshold_controls_enabled)
                    bar_weight_edge = st.slider("Weight · edges", 0.0, 2.0, 0.25, 0.01, disabled=not threshold_controls_enabled)
                    bar_weight_high_frequency = st.slider("Weight · high frequencies", 0.0, 2.0, 0.20, 0.01, disabled=not threshold_controls_enabled)
                    bar_weight_periodicity = st.slider("Weight · periodicity", 0.0, 2.0, 0.15, 0.01, disabled=not threshold_controls_enabled)
                    advanced_params.update({
                        "auto_bar_min_range": auto_bar_min_range,
                        "auto_bar_max_range": auto_bar_max_range,
                        "auto_bar_default_range": auto_bar_default_range,
                        "bar_weight_texture": bar_weight_texture,
                        "bar_weight_edge": bar_weight_edge,
                        "bar_weight_high_frequency": bar_weight_high_frequency,
                        "bar_weight_periodicity": bar_weight_periodicity,
                    })

        # ── Tab 2 · Image analysis ───────────────────────────────────────────
        with tab_analysis:
            a_left, a_right = st.columns(2, gap="large")
            with a_left:
                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Pre-processing</div>', unsafe_allow_html=True)
                    analysis_max_side = st.slider(
                        "Analysis max side (px)",
                        128, 2048, int(MAX_ANALYSIS_SIDE), 64,
                        disabled=not threshold_controls_enabled,
                        help="The photo is resized only for analysis. Larger values preserve detail but cost more CPU time.",
                    )
                    image_noise_sigma_coeff = st.slider(
                        "Spatial noise coefficient",
                        0.000, 0.250, 0.045, 0.005,
                        disabled=not threshold_controls_enabled,
                        help="Maximum coefficient used by Random factor for spatial perturbation.",
                    )
                    entropy_histogram_bins = st.slider(
                        "Entropy histogram bins",
                        8, 256, 64, 8,
                        disabled=not threshold_controls_enabled,
                    )
                    advanced_params.update({
                        "analysis_max_side": analysis_max_side,
                        "image_noise_sigma_coeff": image_noise_sigma_coeff,
                        "entropy_histogram_bins": entropy_histogram_bins,
                    })

                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Edge detection</div>', unsafe_allow_html=True)
                    edge_threshold_percentile = st.slider(
                        "Edge threshold percentile",
                        0.0, 100.0, 75.0, 0.5,
                        disabled=not threshold_controls_enabled,
                    )
                    edge_threshold_minimum = st.slider(
                        "Minimum edge threshold",
                        0.00, 1.00, 0.08, 0.01,
                        disabled=not threshold_controls_enabled,
                    )
                    advanced_params.update({
                        "edge_threshold_percentile": edge_threshold_percentile,
                        "edge_threshold_minimum": edge_threshold_minimum,
                    })

            with a_right:
                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Luminance thresholds</div>', unsafe_allow_html=True)
                    luminance_percentile_range = st.slider(
                        "Luminance percentile range",
                        0.0, 100.0, (5.0, 95.0), 0.5,
                        disabled=not threshold_controls_enabled,
                        help="Used for dynamic range, shadow threshold and highlight threshold. The range cannot be inverted.",
                    )
                    shadow_dark_floor = st.slider(
                        "Shadow floor",
                        0.00, 1.00, 0.18, 0.01,
                        disabled=not threshold_controls_enabled,
                    )
                    shadow_offset = st.slider(
                        "Shadow percentile offset",
                        0.00, 0.50, 0.03, 0.01,
                        disabled=not threshold_controls_enabled,
                    )
                    highlight_bright_floor = st.slider(
                        "Highlight floor",
                        0.00, 1.00, 0.82, 0.01,
                        disabled=not threshold_controls_enabled,
                    )
                    highlight_offset = st.slider(
                        "Highlight percentile offset",
                        0.00, 0.50, 0.03, 0.01,
                        disabled=not threshold_controls_enabled,
                    )
                    advanced_params.update({
                        "luminance_percentile_range": luminance_percentile_range,
                        "shadow_dark_floor": shadow_dark_floor,
                        "shadow_offset": shadow_offset,
                        "highlight_bright_floor": highlight_bright_floor,
                        "highlight_offset": highlight_offset,
                    })

        # ── Tab 3 · Fourier & saliency ───────────────────────────────────────
        with tab_fourier:
            f_left, f_mid, f_right = st.columns(3, gap="large")
            with f_left:
                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Fourier analysis</div>', unsafe_allow_html=True)
                    fourier_dc_radius = st.slider(
                        "DC exclusion radius",
                        0.000, 0.200, 0.025, 0.005,
                        disabled=not threshold_controls_enabled,
                    )
                    fourier_band_limits = st.slider(
                        "Low/mid/high radial limits",
                        0.03, 0.95, (0.14, 0.34), 0.01,
                        disabled=not threshold_controls_enabled,
                        help="Two ordered limits define low, mid and high Fourier energy bands.",
                    )
                    fourier_orientation_width = st.slider(
                        "Orientation bandwidth",
                        0.05, 0.95, 0.38, 0.01,
                        disabled=not threshold_controls_enabled,
                    )
                    fourier_peak_percentiles = st.slider(
                        "Peak-score percentile range",
                        0.0, 100.0, (90.0, 99.7), 0.1,
                        disabled=not threshold_controls_enabled,
                        help="Used to compare strong periodic peaks to the background. The range cannot be inverted.",
                    )
                    fourier_peak_log_divisor = st.slider(
                        "Peak-score log divisor",
                        0.5, 20.0, 5.0, 0.1,
                        disabled=not threshold_controls_enabled,
                    )
                    fourier_noise_sigma_coeff = st.slider(
                        "Fourier noise coefficient",
                        0.000, 1.000, 0.180, 0.005,
                        disabled=not threshold_controls_enabled,
                    )
                    advanced_params.update({
                        "fourier_dc_radius": fourier_dc_radius,
                        "fourier_band_limits": fourier_band_limits,
                        "fourier_orientation_width": fourier_orientation_width,
                        "fourier_peak_percentiles": fourier_peak_percentiles,
                        "fourier_peak_log_divisor": fourier_peak_log_divisor,
                        "fourier_noise_sigma_coeff": fourier_noise_sigma_coeff,
                    })

            with f_mid:
                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Saliency map</div>', unsafe_allow_html=True)
                    saliency_edge_weight = st.slider("Weight · edge", 0.0, 2.0, 0.42, 0.01, disabled=not threshold_controls_enabled)
                    saliency_color_weight = st.slider("Weight · color rarity", 0.0, 2.0, 0.34, 0.01, disabled=not threshold_controls_enabled)
                    saliency_luminance_weight = st.slider("Weight · luminance rarity", 0.0, 2.0, 0.24, 0.01, disabled=not threshold_controls_enabled)
                    saliency_center_bias_weight = st.slider("Center-bias weight", 0.00, 1.00, 0.12, 0.01, disabled=not threshold_controls_enabled)
                    saliency_threshold_percentile = st.slider("Saliency threshold percentile", 0.0, 100.0, 96.0, 0.5, disabled=not threshold_controls_enabled)
                    saliency_threshold_minimum = st.slider("Minimum saliency threshold", 0.00, 1.00, 0.20, 0.01, disabled=not threshold_controls_enabled)
                    advanced_params.update({
                        "saliency_edge_weight": saliency_edge_weight,
                        "saliency_color_weight": saliency_color_weight,
                        "saliency_luminance_weight": saliency_luminance_weight,
                        "saliency_center_bias_weight": saliency_center_bias_weight,
                        "saliency_threshold_percentile": saliency_threshold_percentile,
                        "saliency_threshold_minimum": saliency_threshold_minimum,
                    })

            with f_right:
                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Saliency solo layer</div>', unsafe_allow_html=True)
                    solo_note_count_range = st.slider("Solo note-count range", 1, 48, (3, 18), 1, disabled=not threshold_controls_enabled)
                    solo_note_cap = st.slider("Solo note cap", 1, 64, 22, 1, disabled=not threshold_controls_enabled)
                    solo_min_distance = st.slider("Minimum saliency-point distance", 0.000, 0.500, 0.055, 0.005, disabled=not threshold_controls_enabled)
                    solo_duration_beats_range = st.slider("Solo duration range (beats)", 0.05, 4.00, (0.18, 1.25), 0.05, disabled=not threshold_controls_enabled)
                    advanced_params.update({
                        "solo_note_count_range": solo_note_count_range,
                        "solo_note_cap": solo_note_cap,
                        "solo_min_distance": solo_min_distance,
                        "solo_duration_beats_range": solo_duration_beats_range,
                    })

        # ── Tab 4 · Tonality & Tempo ─────────────────────────────────────────
        with tab_tonal:
            t_left, t_right = st.columns(2, gap="large")
            with t_left:
                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Tonal center</div>', unsafe_allow_html=True)
                    _cur_scale = st.session_state.get("scale_selection", "Automatic")
                    if _cur_scale not in SCALE_OPTIONS:
                        _cur_scale = "Automatic"
                    requested_scale = st.selectbox(
                        "Scale",
                        SCALE_OPTIONS,
                        index=SCALE_OPTIONS.index(_cur_scale),
                        key="scale_selection",
                        disabled=not controls_active,
                        help="Automatic lets the image brightness, warmth and saturation choose the mode.",
                    )
                
                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Tempo mapping</div>', unsafe_allow_html=True)
                    _mapping_opts = ["Scientific", "Balanced", "Musical", "Manual"]
                    _cur_map = st.session_state.get("mapping_style", "Scientific")
                    if _cur_map not in _mapping_opts:
                        _cur_map = "Scientific"
                    manual_tempo_bpm: Optional[float] = None
                    mapping_style = st.selectbox(
                        "Mapping style (BPM)",
                        _mapping_opts,
                        index=_mapping_opts.index(_cur_map),
                        key="mapping_style",
                        disabled=not controls_active,
                        help=(
                            "Scientific: uses edge density, contrast, Fourier centroid and shadow proportion.\n"
                            "Balanced: softer version of Scientific.\n"
                            "Musical: uses perceptual colour attributes only.\n"
                            "Manual: enter a fixed BPM below."
                        ),
                    )
                    if mapping_style == "Manual":
                        manual_tempo_bpm = st.number_input(
                            "Manual BPM",
                            min_value=1.0,
                            value=90.0,
                            step=1.0,
                            format="%.1f",
                            disabled=not controls_active,
                        )

            with t_right:                
                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Tempo clamp ranges</div>', unsafe_allow_html=True)
                    tempo_scientific_range = st.slider("Scientific BPM range", 1.0, 240.0, (48.0, 152.0), 1.0, disabled=not threshold_controls_enabled)
                    tempo_balanced_range = st.slider("Balanced BPM range", 1.0, 240.0, (56.0, 132.0), 1.0, disabled=not threshold_controls_enabled)
                    tempo_musical_range = st.slider("Musical BPM range", 1.0, 240.0, (72.0, 108.0), 1.0, disabled=not threshold_controls_enabled)
                    advanced_params.update({
                        "tempo_scientific_range": tempo_scientific_range,
                        "tempo_balanced_range": tempo_balanced_range,
                        "tempo_musical_range": tempo_musical_range,
                    })

        # ── Tab 5 · Synth & Mix ──────────────────────────────────────────────
        with tab_synth:
            sy_left, sy_mid, sy_right = st.columns(3, gap="large")
            with sy_left:
                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Engine</div>', unsafe_allow_html=True)
                    _cur_synth = st.session_state.get("synthesizer_type", SYNTH_GENERALUSER_GS)
                    if _cur_synth not in SYNTHESIZER_OPTIONS:
                        _cur_synth = SYNTH_GENERALUSER_GS
                    synthesizer_type = st.radio(
                        "Synthesizer type",
                        SYNTHESIZER_OPTIONS,
                        index=SYNTHESIZER_OPTIONS.index(_cur_synth),
                        key="synthesizer_type",
                        disabled=not controls_active,
                        help=(
                            "Simple: lightweight additive synthesis, fully self-contained.\n"
                            "GeneralUser GS: FluidSynth + General MIDI SoundFont. Requires fluidsynth "
                            "and soundfonts/GeneralUser-GS.sf2."
                        ),
                    )
                    instrument_mode = st.radio(
                        "Instrument layer selection",
                        ["Automatic", "Manual"],
                        index=0,
                        horizontal=True,
                        disabled=not controls_active,
                        help=(
                            "Automatic: each layer instrument is chosen by scoring GM programs against "
                            "visual features (brightness, saturation, Fourier band energies, saliency).\n"
                            "Manual: pick each layer individually in the Instruments tab."
                        ),
                    )
                    
            with sy_mid:
                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Master bus</div>', unsafe_allow_html=True)
                    master_target_peak = st.slider("Target peak", 0.10, 0.98, float(MASTER_TARGET_PEAK), 0.01, disabled=not threshold_controls_enabled)
                    master_target_rms = st.slider("Target RMS", 0.01, 0.50, float(MASTER_TARGET_RMS), 0.01, disabled=not threshold_controls_enabled)
                    max_render_seconds = st.slider("Maximum render duration (s)", 8.0, 240.0, float(MAX_RENDER_SECONDS), 1.0, disabled=not threshold_controls_enabled)
                    fluidsynth_master_gain = st.slider("FluidSynth master gain", 0.05, 2.00, float(FLUIDSYNTH_MASTER_GAIN), 0.05, disabled=not threshold_controls_enabled)
                    advanced_params.update({
                        "master_target_peak": master_target_peak,
                        "master_target_rms": master_target_rms,
                        "max_render_seconds": max_render_seconds,
                        "fluidsynth_master_gain": fluidsynth_master_gain,
                    })

            with sy_right:                
                with st.container(border=True):
                    st.markdown('<div class="param-group-label">Event gates</div>', unsafe_allow_html=True)
                    chord_double_hit_high_freq_threshold = st.slider("Chord double-hit high-frequency threshold", 0.00, 1.00, 0.22, 0.01, disabled=not threshold_controls_enabled)
                    complexity_step_threshold = st.slider("Melody density threshold", 0.00, 1.00, 0.52, 0.01, disabled=not threshold_controls_enabled)
                    melody_energy_gate = st.slider("Melody energy gate", 0.00, 1.00, 0.10, 0.01, disabled=not threshold_controls_enabled)
                    texture_density_threshold = st.slider("Texture activation threshold", 0.00, 1.00, 0.28, 0.01, disabled=not threshold_controls_enabled)
                    percussion_density_threshold = st.slider("Percussion activation threshold", 0.00, 1.00, 0.18, 0.01, disabled=not threshold_controls_enabled)
                    advanced_params.update({
                        "chord_double_hit_high_freq_threshold": chord_double_hit_high_freq_threshold,
                        "complexity_step_threshold": complexity_step_threshold,
                        "melody_energy_gate": melody_energy_gate,
                        "texture_density_threshold": texture_density_threshold,
                        "percussion_density_threshold": percussion_density_threshold,
                    })

        # ── Tab 6 · Instruments ──────────────────────────────────────────────
        with tab_inst:
            choices  = get_instrument_choices_with_none(synthesizer_type)
            fallback = choices[1] if len(choices) > 1 else "None"
            cache    = st.session_state.get("photo_analysis_cache")

            if controls_active and isinstance(cache, dict):
                _fdef: Dict[str, float] = cache["analysis"]["features"]  # type: ignore[assignment]
                _ai = choose_instruments(_fdef, "Automatic", synthesizer_type)
                defaults = [
                    instrument_label(x) if x.startswith("gm_")
                    else SIMPLE_INTERNAL_TO_DISPLAY.get(x, fallback)
                    for x in _ai
                ]
            else:
                defaults = (
                    ["Acoustic Grand Piano", "Orchestral Harp", "Cello",
                     "Pad 2 (warm)", "Acoustic Grand Piano", "Flute"]
                    if synthesizer_type == SYNTH_GENERALUSER_GS
                    else ["Soft piano", "Harp", "Cello-like bass", "Warm pad", "Soft piano", "None"]
                )
            while len(defaults) < 6:
                defaults.append("None")
            main_layer, texture_layer, bass_layer, pad_layer, chord_layer, solo_layer = defaults[:6]
            main_gain_db    = 0.0
            texture_gain_db = -2.0
            bass_gain_db    = 0.0
            pad_gain_db     = -8.0
            chord_gain_db   = -3.0
            solo_gain_db    = -1.0

            def _idx(val: str) -> int:
                return choices.index(val) if val in choices else choices.index(fallback)

            if instrument_mode != "Manual":
                if controls_active and isinstance(cache, dict):
                    st.markdown('<div class="param-group-label">Auto-selected instruments</div>', unsafe_allow_html=True)
                    _layer_names = ["Main", "Texture", "Bass", "Pad", "Chord", "Solo"]
                    _auto_html = '<div class="result-meta">' + "".join(
                        f'<div class="result-meta-item">{_layer_names[i]} <span>{defaults[i]}</span></div>'
                        for i in range(6 if synthesizer_type == SYNTH_GENERALUSER_GS else 5)
                    ) + "</div>"
                    st.markdown(_auto_html, unsafe_allow_html=True)
                    st.markdown("")
                st.info(
                    "Set **Instrument layer selection** to **Manual** in the Synth & Mix tab "
                    "to choose instruments and gain for each layer individually."
                )
            else:
                i_col1, i_col2, i_col3 = st.columns(3, gap="medium")
                with i_col1:
                    with st.container(border=True):
                        st.markdown('<div class="param-group-label">Main</div>', unsafe_allow_html=True)
                        main_layer   = st.selectbox("Main layer",    choices, index=_idx(defaults[0]), disabled=not controls_active, label_visibility="collapsed")
                        main_gain_db = st.slider("Main gain (dB)",   -24.0, 12.0,  0.0, 0.5, disabled=not controls_active)
                with i_col2:
                    with st.container(border=True):
                        st.markdown('<div class="param-group-label">Texture</div>', unsafe_allow_html=True)
                        texture_layer    = st.selectbox("Texture layer", choices, index=_idx(defaults[1]), disabled=not controls_active, label_visibility="collapsed")
                        texture_gain_db  = st.slider("Texture gain (dB)", -24.0, 12.0, -2.0, 0.5, disabled=not controls_active)
                with i_col3:
                    with st.container(border=True):
                        st.markdown('<div class="param-group-label">Bass</div>', unsafe_allow_html=True)
                        bass_layer   = st.selectbox("Bass layer",    choices, index=_idx(defaults[2]), disabled=not controls_active, label_visibility="collapsed")
                        bass_gain_db = st.slider("Bass gain (dB)",   -24.0, 12.0,  0.0, 0.5, disabled=not controls_active)
                i_col4, i_col5, i_col6 = st.columns(3, gap="medium")
                with i_col4:
                    with st.container(border=True):
                        st.markdown('<div class="param-group-label">Pad</div>', unsafe_allow_html=True)
                        pad_layer    = st.selectbox("Pad layer",     choices, index=_idx(defaults[3]), disabled=not controls_active, label_visibility="collapsed")
                        pad_gain_db  = st.slider("Pad gain (dB)",    -24.0, 12.0, -8.0, 0.5, disabled=not controls_active)
                with i_col5:
                    with st.container(border=True):
                        st.markdown('<div class="param-group-label">Chord</div>', unsafe_allow_html=True)
                        chord_layer    = st.selectbox("Chord layer",   choices, index=_idx(defaults[4]), disabled=not controls_active, label_visibility="collapsed")
                        chord_gain_db  = st.slider("Chord gain (dB)",  -24.0, 12.0, -3.0, 0.5, disabled=not controls_active)
                if synthesizer_type == SYNTH_GENERALUSER_GS:
                    with i_col6:
                        with st.container(border=True):
                            st.markdown('<div class="param-group-label">Solo</div>', unsafe_allow_html=True)
                            solo_layer   = st.selectbox("Solo layer",    choices, index=_idx(defaults[5]), disabled=not controls_active, label_visibility="collapsed")
                            solo_gain_db = st.slider("Solo gain (dB)",   -24.0, 12.0, -1.0, 0.5, disabled=not controls_active)

    # =========================================================================
    # Row 3:  Photo analysis  (full width, collapsed by default)
    # =========================================================================
    with st.expander("Photo analysis", expanded=False):
        if result is None:
            st.info("Run the app once to display the photo-derived maps and analysis metrics.")
        else:
            _maps  = result.get("display_maps",    result["maps"])
            _feats = result.get("display_features", result["features"])
            pa_col1, pa_col2 = st.columns([2, 1], gap="large")
            with pa_col1:
                for _key, _title, _cmap in [
                    ("luminance",            "Luminance map",             "gray"),
                    ("edge_map",             "Edge strength map",         "gray"),
                    ("fft_log_magnitude",    "2D Fourier log-magnitude",  "gray"),
                    ("shadow_highlight_map", "Highlights (red) · shadows (blue)", None),
                ]:
                    st.markdown(f'<div class="section-pill">{_title}</div>', unsafe_allow_html=True)
                    st.image(plot_map(_maps[_key], _title, _cmap), width="stretch")
            with pa_col2:
                st.markdown('<div class="param-group-label">Metrics</div>', unsafe_allow_html=True)
                _m = _feats
                st.markdown(
                    '<div class="result-meta">'
                    f'<div class="result-meta-item">Brightness <span>{_m["mean_brightness"]:.3f}</span></div>'
                    f'<div class="result-meta-item">Contrast <span>{_m["contrast"]:.3f}</span></div>'
                    f'<div class="result-meta-item">Saturation <span>{_m["mean_saturation"]:.3f}</span></div>'
                    f'<div class="result-meta-item">Shadows <span>{format_percent(_m["shadow_proportion"])}</span></div>'
                    f'<div class="result-meta-item">Highlights <span>{format_percent(_m["highlight_proportion"])}</span></div>'
                    f'<div class="result-meta-item">Edge density <span>{format_percent(_m["edge_density"])}</span></div>'
                    f'<div class="result-meta-item">Texture entropy <span>{_m["texture_entropy"]:.3f}</span></div>'
                    f'<div class="result-meta-item">Symmetry <span>{_m["symmetry_score"]:.3f}</span></div>'
                    f'<div class="result-meta-item">Saliency peak <span>{_m["saliency_peak"]:.3f}</span></div>'
                    f'<div class="result-meta-item">Fourier low <span>{format_percent(_m["low_frequency_energy"])}</span></div>'
                    f'<div class="result-meta-item">Fourier mid <span>{format_percent(_m["mid_frequency_energy"])}</span></div>'
                    f'<div class="result-meta-item">Fourier high <span>{format_percent(_m["high_frequency_energy"])}</span></div>'
                    f'<div class="result-meta-item">Peak score <span>{_m["periodic_peak_score"]:.3f}</span></div>'
                    '</div>',
                    unsafe_allow_html=True,
                )

    # =========================================================================
    # Row 4:  Audio analysis  (full width, collapsed by default)
    # =========================================================================
    with st.expander("Audio analysis", expanded=False):
        if result is None:
            st.info("Run the app once to display the audio frequency plots.")
        else:
            _audio_arr = result["audio"]
            _evts      = result["events"]
            _sr        = int(result["sample_rate"])
            _dur       = result["info"].duration
            _plots = [
                ("Full Fourier magnitude", plot_frequency(_audio_arr, _sr, "Full Fourier magnitude")),
                ("Waveform",               plot_waveform(_audio_arr,  _sr, "Waveform")),
            ]
            for _lk, _lt in [("main","Main"), ("texture","Texture"), ("bass","Bass"),
                              ("pad","Pad"), ("chord","Chord")]:
                _plots.append((_lt, plot_frequency(render_events(_evts, _dur, _sr, layer=_lk), _sr, _lt)))
            if result["info"].solo_instrument != "none":
                _plots.append(("Solo", plot_frequency(render_events(_evts, _dur, _sr, layer="solo"), _sr, "Solo")))
            _aa_cols = st.columns(3, gap="medium")
            for _pi, (_pt, _pimg) in enumerate(_plots):
                with _aa_cols[_pi % 3]:
                    st.markdown(f'<div class="section-pill">{_pt}</div>', unsafe_allow_html=True)
                    st.image(_pimg, width="stretch")

    # =========================================================================
    # Computation block  —  runs only when run_requested is True
    # Mirrors audio_visualization: progress placeholders filled live,
    # then st.rerun() re-activates the button and shows the result.
    # =========================================================================
    if st.session_state.run_requested and uploaded_image is not None:
        progress_bar = progress_bar_placeholder.progress(0)
        try:
            def _progress(label: str, percent: int) -> None:
                percent = int(clamp(percent, 0, 100))
                progress_status_placeholder.info(f"{label} — {percent}%")
                progress_bar.progress(percent)

            def _stepper(base: int, top: int, total_hint: int):
                state = {"i": 0}
                def _callback(label: str) -> None:
                    state["i"] += 1
                    span = max(1, top - base)
                    pct = min(top, base + int(round(span * state["i"] / max(1, total_hint))))
                    _progress(label, pct)
                return _callback

            analysis_params_signature = make_signature(image_id=uploaded_hash, params=advanced_params)

            # ── Phase 1: first run on this image → use auto parameters ────────
            if not controls_active:
                _progress("Starting photo analysis", 2)
                original_analysis = analyze_image(
                    uploaded_image,
                    0.0,
                    np.random.default_rng(0),
                    params=advanced_params,
                    step_callback=_stepper(4, 30, 7),
                )
                st.session_state["photo_analysis_cache"] = {
                    "image_id": uploaded_hash,
                    "params_signature": analysis_params_signature,
                    "analysis": original_analysis,
                }
                f0: Dict[str, float] = original_analysis["features"]  # type: ignore[assignment]
                _progress("Automatic bar/complexity/variation defaults", 32)
                mn, mx, df = compute_bar_settings(f0, params=advanced_params)
                st.session_state["parameter_defaults"] = {
                    "image_id": uploaded_hash, "bar_min": mn, "bar_max": mx, "bar_default": df,
                    "variation_default": f0.get(
                        "auto_variation_strength",
                        clamp(0.25 + 0.60 * (1.0 - f0["symmetry_score"]), 0.25, 0.85),
                    ),
                    "complexity_default": f0["auto_complexity"],
                }
                effective = dict(
                    bars=df,
                    variation=st.session_state["parameter_defaults"]["variation_default"],
                    complexity=f0["auto_complexity"],
                    random=0,
                    scale="Automatic",
                    synth=SYNTH_GENERALUSER_GS,
                    instrument_mode="Automatic",
                    main="Soft piano", texture="Harp", bass="Cello-like bass",
                    pad="Warm pad", chord="Soft piano", solo="Flute",
                    mapping="Scientific", bpm=None,
                    gains=[0.0, -2.0, 0.0, -8.0, -3.0, -1.0],
                    advanced_params=advanced_params,
                )
                analysis = original_analysis

            # ── Phase 2: subsequent runs → use current slider values ──────────
            else:
                _progress("Preparing original photo analysis", 2)
                _cache = st.session_state.get("photo_analysis_cache")
                if (
                    isinstance(_cache, dict)
                    and _cache.get("image_id") == uploaded_hash
                    and _cache.get("params_signature") == analysis_params_signature
                ):
                    original_analysis = _cache["analysis"]
                    _progress("Reusing cached original photo maps", 10)
                else:
                    original_analysis = analyze_image(
                        uploaded_image,
                        0.0,
                        np.random.default_rng(0),
                        params=advanced_params,
                        step_callback=_stepper(4, 30, 7),
                    )
                st.session_state["photo_analysis_cache"] = {
                    "image_id": uploaded_hash,
                    "params_signature": analysis_params_signature,
                    "analysis": original_analysis,
                }
                _seed = int(
                    hashlib.sha256(f"{uploaded_hash}:{random_factor}:{analysis_params_signature}".encode()).hexdigest()[:16], 16
                )
                if int(random_factor) == 0:
                    analysis = original_analysis
                    _progress("Using original maps for composition", 32)
                else:
                    analysis = analyze_image(
                        uploaded_image,
                        float(random_factor),
                        np.random.default_rng(_seed),
                        params=advanced_params,
                        step_callback=_stepper(30, 42, 7),
                    )
                effective = dict(
                    bars=int(number_of_bars),
                    variation=float(variation_strength),
                    complexity=float(complexity),
                    random=int(random_factor),
                    scale=requested_scale,
                    synth=synthesizer_type,
                    instrument_mode=instrument_mode,
                    main=main_layer, texture=texture_layer,
                    bass=bass_layer, pad=pad_layer,
                    chord=chord_layer, solo=solo_layer,
                    mapping=mapping_style, bpm=manual_tempo_bpm,
                    gains=[
                        main_gain_db, texture_gain_db, bass_gain_db,
                        pad_gain_db, chord_gain_db, solo_gain_db,
                    ],
                    advanced_params=advanced_params,
                )

            # ── Generate composition ──────────────────────────────────────────
            _progress("Generating composition", 43)
            events, info = generate_composition(
                analysis,
                effective["bars"],  effective["complexity"], effective["variation"],
                effective["scale"], effective["synth"],       effective["instrument_mode"],
                effective["main"],  effective["texture"],     effective["bass"],
                effective["pad"],   effective["chord"],       effective["solo"],
                effective["mapping"], effective["bpm"],
                *effective["gains"],
                params=advanced_params,
                step_callback=_stepper(43, 62, 7),
            )

            # ── Render audio ──────────────────────────────────────────────────
            _progress("Rendering waveform / FluidSynth backend", 65)
            audio_arr, synth_message = render_backend(events, info, effective["synth"], params=advanced_params)
            _progress("Master bus normalization", 78)
            audio_arr = normalize_master_audio(
                audio_arr,
                target_peak=get_float_param(advanced_params, "master_target_peak", MASTER_TARGET_PEAK, 0.10, 0.98),
                target_rms=get_float_param(advanced_params, "master_target_rms", MASTER_TARGET_RMS, 0.01, 0.50),
            )

            # ── Encode output files ───────────────────────────────────────────
            _progress("WAV and MIDI encoding", 86)
            wav_bytes_out  = audio_to_wav_bytes(audio_arr, DEFAULT_SAMPLE_RATE)
            midi_bytes_out = midi_bytes_from_events(events, info.tempo)
            _progress("MP3 encoding", 93)
            mp3_bytes_out, mp3_message = audio_to_mp3_bytes(audio_arr, DEFAULT_SAMPLE_RATE)

            # ── Store result ──────────────────────────────────────────────────
            st.session_state["generation_result"] = {
                "image_id":         uploaded_hash,
                "image_name":       input_name,
                "image_is_default": input_is_default,
                "analysis":         analysis,
                "display_analysis": original_analysis,
                "features":         analysis["features"],
                "maps":             analysis["maps"],
                "display_features": original_analysis["features"],
                "display_maps":     original_analysis["maps"],
                "events":           events,
                "info":             info,
                "audio":            audio_arr,
                "wav_bytes":        wav_bytes_out,
                "mp3_bytes":        mp3_bytes_out,
                "mp3_message":      mp3_message,
                "synth_message":    synth_message,
                "midi_bytes":       midi_bytes_out,
                "sample_rate":      DEFAULT_SAMPLE_RATE,
                "parameters":       effective,
            }

            progress_bar.progress(100)
            progress_status_placeholder.success("Done — 100%")

            st.session_state.run_in_progress = False
            st.session_state.run_requested   = False
            st.session_state.last_run_status = "Done"

            # Force a rerun so the button re-activates and the result appears.
            # (The button was rendered earlier in this pass while run_in_progress
            # was still True; rerun makes it interactive again immediately.)
            st.rerun()

        except Exception as _exc:
            progress_bar_placeholder.empty()
            progress_status_placeholder.error(f"Could not generate the composition: {_exc}")
            st.session_state.run_in_progress = False
            st.session_state.run_requested   = False
            st.session_state.last_run_status = None

    elif st.session_state.run_requested and uploaded_image is None:
        # Edge case: button clicked but image not yet available
        progress_status_placeholder.warning(
            "Please upload or wait for the default photo to load before generating."
        )
        st.session_state.run_in_progress = False
        st.session_state.run_requested   = False


# ============================================================
# Entry point
# ============================================================

def main() -> None:
    configure_page()
    init_session_state()
    render_portfolio_links()

    app_tab, doc_fr_tab, doc_en_tab = st.tabs([
        "App",
        "Documentation FR",
        "Documentation EN",
    ])

    with app_tab:
        render_app_tab()

    with doc_fr_tab:
        render_documentation_tab(DOC_FR_TITLES, DOC_FR_SECTIONS, "doc_fr_title")

    with doc_en_tab:
        render_documentation_tab(DOC_EN_TITLES, DOC_EN_SECTIONS, "doc_en_title")


if __name__ == "__main__":
    main()
