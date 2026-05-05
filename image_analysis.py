from __future__ import annotations

import io
import math
import os
import urllib.request
from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image, ImageOps

from config import HEIF_IMAGE_TYPES, HEIF_SUPPORT, MAX_ANALYSIS_SIDE
from utils import (
    clamp,
    emit_step,
    get_float_param,
    get_int_param,
    get_range_param,
    normalize01,
    normalize_positive_weights,
)


# ============================================================
# Image I/O
# ============================================================

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


# ============================================================
# Pixel-level feature extraction
# ============================================================

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
            math.atan2(
                float(np.sum(weights * np.sin(angle))),
                float(np.sum(weights * np.cos(angle))),
            ) / (2.0 * np.pi)
        ) % 1.0
    return {
        "mean_saturation": float(np.mean(sat)),
        "dominant_hue": float(hue_mean),
        "warmth": float(np.mean(rgb[..., 0]) - np.mean(rgb[..., 2])),
    }


def compute_edge_map(
    luminance: np.ndarray, params: Optional[Dict[str, object]] = None
) -> Tuple[np.ndarray, float]:
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
    return (
        float(np.sum(xx * w) / total) / max(1, width - 1),
        float(np.sum(yy * w) / total) / max(1, h - 1),
    )


def compute_symmetry(luminance: np.ndarray) -> float:
    lr = 1.0 - float(np.mean(np.abs(luminance - np.fliplr(luminance))))
    tb = 1.0 - float(np.mean(np.abs(luminance - np.flipud(luminance))))
    return clamp(0.70 * lr + 0.30 * tb, 0.0, 1.0)


# ============================================================
# Saliency map
# ============================================================

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
        spread = float(np.sqrt(
            np.sum(weight * ((xn - cx) ** 2 + (yn - cy) ** 2)) / (np.sum(weight) + 1e-12)
        ))
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


# ============================================================
# 2D Fourier analysis
# ============================================================

def analyze_fourier(
    luminance: np.ndarray,
    random_factor: float = 0.0,
    rng: Optional[np.random.Generator] = None,
    params: Optional[Dict[str, object]] = None,
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
    horizontal_frequency_energy = float(
        np.sum(power_no_dc[np.abs(np.sin(theta)) < orientation_width]) / total
    )
    vertical_frequency_energy = float(
        np.sum(power_no_dc[np.abs(np.cos(theta)) < orientation_width]) / total
    )
    diagonal_frequency_energy = clamp(
        1.0 - horizontal_frequency_energy - vertical_frequency_energy, 0.0, 1.0
    )
    valid = power_no_dc[power_no_dc > 0]
    peak_lo, peak_hi = get_range_param(params, "fourier_peak_percentiles", (90.0, 99.7), 0.0, 100.0, 0.1)
    peak_divisor = get_float_param(params, "fourier_peak_log_divisor", 5.0, 0.5, 20.0)
    peak_score = 0.0 if valid.size == 0 else clamp(
        math.log1p(
            float(np.percentile(valid, peak_hi)) / (float(np.percentile(valid, peak_lo)) + 1e-12)
        ) / peak_divisor,
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


# ============================================================
# Top-level image analysis pipeline
# ============================================================

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
    lum_p_low, lum_p_high = get_range_param(
        params, "luminance_percentile_range", (5.0, 95.0), 0.0, 100.0, 0.1
    )
    p_low = float(np.percentile(lum, lum_p_low))
    p_high = float(np.percentile(lum, lum_p_high))
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
    auto_complexity_lo, auto_complexity_hi = get_range_param(
        params, "auto_complexity_range", (0.25, 0.90), 0.05, 1.0, 0.01
    )
    auto_variation_lo, auto_variation_hi = get_range_param(
        params, "auto_variation_range", (0.25, 0.85), 0.0, 1.0, 0.01
    )
    auto_complexity = clamp(
        auto_complexity_lo + (auto_complexity_hi - auto_complexity_lo) * texture_entropy,
        auto_complexity_lo,
        auto_complexity_hi,
    )
    auto_variation = clamp(
        auto_variation_lo + (auto_variation_hi - auto_variation_lo) * (1.0 - sym),
        auto_variation_lo,
        auto_variation_hi,
    )

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
        "shadow_highlight_map": np.dstack([
            highlight.astype(float),
            np.zeros_like(lum),
            shadow.astype(float),
        ]),
        "saliency_map": saliency,
    }
    return {"features": features, "maps": maps}
