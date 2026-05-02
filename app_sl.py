from __future__ import annotations

import hashlib
import io
import json
import math
import os
import shutil
import struct
import subprocess
import tempfile
import wave
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.mlab as mlab
import numpy as np
import streamlit as st
from PIL import Image

APP_TITLE = "Photo Sonification Lab"
DEFAULT_SAMPLE_RATE = 44100
# Use None to keep the original image resolution for all image-derived analyses.
# This affects luminance, edges, Fourier descriptors, palette extraction, and displayed maps.
#MAX_ANALYSIS_SIDE = None
MAX_ANALYSIS_SIDE = int(os.getenv("MAX_ANALYSIS_SIDE", "1024"))
MAX_RENDER_SECONDS = 120.0

DEFAULT_IMAGE_URL = "https://media.mutualart.com/Images/2016_04/28/19/194441798/8a90ad07-2349-43df-825f-c3ecacc072e2_570.Jpeg"

DEFAULT_IMAGE_SOURCE_PAGE = "https://www.mutualart.com/Artwork/Night-lights/171ACA7174BEDBD6"

DEFAULT_IMAGE_CAPTION = (
    "Default sample image: Félix De Boeck, Night lights, 1954. "
    "Source image: MutualArt. This image is preloaded only to let users test the app; "
    "it is not presented as open-source/licensed material. You can upload your own photo "
    "to replace this default image."
)

DEFAULT_IMAGE_NAME = "Félix De Boeck, Night lights, 1954"


def load_image_bytes_from_url(url: str, timeout: float = 20.0) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Photo-Sonification-Lab/1.0)",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


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
    if max_side is not None:
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

    return {
        "mean_saturation": float(np.mean(sat)),
        "dominant_hue": float(hue_mean),
        "warmth": float(np.mean(rgb[..., 0]) - np.mean(rgb[..., 2])),
    }


def compute_edge_map(luminance: np.ndarray) -> Tuple[np.ndarray, float]:
    gy, gx = np.gradient(luminance)
    mag = np.sqrt(gx * gx + gy * gy)
    norm_mag = normalize01(mag)
    threshold = np.percentile(norm_mag, 75.0)
    edge_density = float(np.mean(norm_mag > max(0.08, threshold)))
    return norm_mag, edge_density


def compute_gradient_orientation_features(luminance: np.ndarray) -> Dict[str, float]:
    gy, gx = np.gradient(luminance)
    mag = np.sqrt(gx ** 2 + gy ** 2)
    total_mag = float(np.sum(mag)) + 1e-12
    angle = np.arctan2(gy, gx)
    cos_a = np.abs(np.cos(angle))
    sin_a = np.abs(np.sin(angle))
    horiz_orient = float(np.sum(mag[cos_a > 0.70]) / total_mag)
    vert_orient = float(np.sum(mag[sin_a > 0.70]) / total_mag)
    diag_orient = max(0.0, 1.0 - horiz_orient - vert_orient)
    return {
        "horiz_orientation": horiz_orient,
        "vert_orientation": vert_orient,
        "diag_orientation": diag_orient,
        "staccato_score": clamp(vert_orient * 2.0, 0.0, 1.0),
        "legato_score": clamp(horiz_orient * 2.0 + 0.5 * diag_orient, 0.0, 1.0),
        "offbeat_tendency": clamp(diag_orient * 2.5, 0.0, 1.0),
    }


def compute_quadrant_brightness(luminance: np.ndarray) -> Dict[str, float]:
    h, w = luminance.shape
    h2, w2 = max(1, h // 2), max(1, w // 2)
    q_tl = float(np.mean(luminance[:h2, :w2]))
    q_tr = float(np.mean(luminance[:h2, w2:]))
    q_bl = float(np.mean(luminance[h2:, :w2]))
    q_br = float(np.mean(luminance[h2:, w2:]))
    q_sum = q_tl + q_tr + q_bl + q_br + 1e-12
    return {
        "quad_tl": q_tl,
        "quad_tr": q_tr,
        "quad_bl": q_bl,
        "quad_br": q_br,
        "quad_brightness_range": max(q_tl, q_tr, q_bl, q_br) - min(q_tl, q_tr, q_bl, q_br),
        "quad_accent_1": q_tl / q_sum,
        "quad_accent_2": q_tr / q_sum,
        "quad_accent_3": q_bl / q_sum,
        "quad_accent_4": q_br / q_sum,
    }


def compute_local_contrast_variance(luminance: np.ndarray, n_blocks: int = 8) -> Dict[str, float]:
    h, w = luminance.shape
    local_stds: List[float] = []
    for bi in range(n_blocks):
        for bj in range(n_blocks):
            y0, y1 = bi * h // n_blocks, (bi + 1) * h // n_blocks
            x0, x1 = bj * w // n_blocks, (bj + 1) * w // n_blocks
            block = luminance[y0:y1, x0:x1]
            if block.size > 0:
                local_stds.append(float(np.std(block)))
    lcv = float(np.var(local_stds)) if local_stds else 0.0
    lcm = float(np.mean(local_stds)) if local_stds else 0.0
    return {
        "local_contrast_variance": lcv,
        "local_contrast_variance_norm": clamp(lcv / 0.012, 0.0, 1.0),
        "local_contrast_mean": lcm,
    }


def compute_color_temperature_gradient(rgb: np.ndarray) -> Dict[str, float]:
    h, w = rgb.shape[:2]
    h2, w2 = max(1, h // 2), max(1, w // 2)
    warmth_map = rgb[..., 0] - rgb[..., 2]
    temp_grad_x = float(np.mean(warmth_map[:, w2:]) - np.mean(warmth_map[:, :w2]))
    temp_grad_y = float(np.mean(warmth_map[h2:, :]) - np.mean(warmth_map[:h2, :]))
    return {
        "color_temp_gradient_x": temp_grad_x,
        "color_temp_gradient_y": temp_grad_y,
        "color_temp_gradient_magnitude": float(np.sqrt(temp_grad_x ** 2 + temp_grad_y ** 2)),
    }


def compute_luminance_cdf_features(luminance: np.ndarray) -> Dict[str, float]:
    lum_flat = luminance.ravel()
    p25 = float(np.percentile(lum_flat, 25.0))
    p50 = float(np.percentile(lum_flat, 50.0))
    p75 = float(np.percentile(lum_flat, 75.0))
    p05 = float(np.percentile(lum_flat, 5.0))
    p95 = float(np.percentile(lum_flat, 95.0))
    return {
        "lum_p25": p25,
        "lum_p50": p50,
        "lum_p75": p75,
        "lum_cdf_iqr": p75 - p25,
        "lum_cdf_spread": p95 - p05,
        "brightness_skew": clamp((p50 - 0.5) * 2.0, -1.0, 1.0),
    }


def center_of_mass(mask_or_weight: np.ndarray) -> Tuple[float, float]:
    w = np.asarray(mask_or_weight, dtype=np.float64)
    total = float(np.sum(w))
    h, width = w.shape
    if total <= 1e-12:
        return 0.5, 0.5
    y_idx, x_idx = np.indices(w.shape)
    cx = float(np.sum(x_idx * w) / total) / max(1, width - 1)
    cy = float(np.sum(y_idx * w) / total) / max(1, h - 1)
    return cx, cy


def compute_symmetry_features(luminance: np.ndarray) -> Dict[str, float]:
    lum = np.asarray(luminance, dtype=np.float64)
    lr_diff = float(np.mean(np.abs(lum - np.fliplr(lum))))
    tb_diff = float(np.mean(np.abs(lum - np.flipud(lum))))
    left_right_symmetry = clamp(1.0 - lr_diff, 0.0, 1.0)
    top_bottom_symmetry = clamp(1.0 - tb_diff, 0.0, 1.0)
    symmetry_score = clamp(0.70 * left_right_symmetry + 0.30 * top_bottom_symmetry, 0.0, 1.0)
    return {
        "left_right_symmetry": left_right_symmetry,
        "top_bottom_symmetry": top_bottom_symmetry,
        "symmetry_score": symmetry_score,
    }


def normalized_histogram_entropy(values: np.ndarray, bins: int = 64) -> float:
    x = np.asarray(values, dtype=np.float64).ravel()
    if x.size == 0:
        return 0.0
    hist, _ = np.histogram(x, bins=bins, range=(0.0, 1.0), density=False)
    total = float(np.sum(hist))
    if total <= 1e-12:
        return 0.0
    p = hist.astype(np.float64) / total
    p = p[p > 0]
    if p.size <= 1:
        return 0.0
    return clamp(-float(np.sum(p * np.log2(p))) / math.log2(bins), 0.0, 1.0)


def auto_variation_from_symmetry(symmetry_score: float) -> float:
    return clamp(0.25 + 0.60 * (1.0 - float(symmetry_score)), 0.25, 0.85)


def auto_complexity_from_texture_entropy(texture_entropy: float) -> float:
    return clamp(0.25 + 0.65 * float(texture_entropy), 0.25, 0.90)


def compute_bar_settings(features: Dict[str, float]) -> Tuple[int, int, int]:
    bar_score = clamp(
        0.40 * float(features.get("texture_entropy", 0.0))
        + 0.25 * float(features.get("edge_density", 0.0))
        + 0.20 * float(features.get("high_frequency_energy", 0.0))
        + 0.15 * float(features.get("periodic_peak_score", 0.0)),
        0.0,
        1.0,
    )
    min_bars = int(round(np.interp(bar_score, [0.0, 1.0], [4.0, 8.0])))
    max_bars = int(round(np.interp(bar_score, [0.0, 1.0], [12.0, 24.0])))
    default_bars = int(round(np.interp(bar_score, [0.0, 1.0], [6.0, 16.0])))
    min_bars = int(clamp(min_bars, 4, 8))
    max_bars = int(clamp(max_bars, max(min_bars + 1, 8), 24))
    default_bars = int(clamp(default_bars, min_bars, max_bars))
    return min_bars, max_bars, default_bars



def _rgb_to_hsv_arrays(rgb: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
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
    return hue, sat, mx


def circular_hue_distance(h1: float, h2: float) -> float:
    d = abs(float(h1) - float(h2)) % 1.0
    return float(min(d, 1.0 - d) * 2.0)


def compute_color_palette_trajectory(rgb: np.ndarray, luminance: np.ndarray, n_colors: int = 5) -> Dict[str, float]:
    """Dominant color palette trajectory used for deterministic harmonic diversity.

    The extraction is deliberately non-learning: a small deterministic k-means is run in
    RGB-luminance space, then the resulting color clusters are ordered from left to
    right according to their spatial centroids. The ordered palette gives a visual
    trajectory that can drive chord progression choice without adding UI parameters.
    """
    rgb = np.asarray(rgb, dtype=np.float64)
    luminance = np.asarray(luminance, dtype=np.float64)
    h, w = luminance.shape
    pixels = rgb.reshape(-1, 3)
    lum_flat = luminance.ravel()
    n_pixels = pixels.shape[0]
    n_colors = int(clamp(n_colors, 2, 8))

    hue_map, sat_map, val_map = _rgb_to_hsv_arrays(rgb)
    hue_flat = hue_map.ravel()
    sat_flat = sat_map.ravel()
    val_flat = val_map.ravel()
    y_grid, x_grid = np.indices((h, w))
    x_flat = x_grid.ravel() / max(1, w - 1)
    y_flat = y_grid.ravel() / max(1, h - 1)

    if n_pixels == 0:
        out = {
            "palette_count": 0.0,
            "palette_entropy": 0.0,
            "palette_hue_spread": 0.0,
            "palette_saturation_mean": 0.0,
            "palette_brightness_range": 0.0,
            "palette_transition_tension": 0.0,
            "palette_spatial_flow": 0.0,
        }
        for i in range(n_colors):
            out.update({
                f"palette_hue_{i}": 0.0,
                f"palette_saturation_{i}": 0.0,
                f"palette_brightness_{i}": 0.0,
                f"palette_weight_{i}": 0.0,
                f"palette_x_{i}": 0.5,
                f"palette_y_{i}": 0.5,
            })
        return out

    # Deterministic subsampling keeps the app responsive while preserving the photo.
    sample_count = min(8192, n_pixels)
    sample_idx = np.linspace(0, n_pixels - 1, sample_count, dtype=int)
    sample_rgb = pixels[sample_idx]
    sample_lum = lum_flat[sample_idx]
    sample_sat = sat_flat[sample_idx]
    sample_feat = np.column_stack([sample_rgb, 0.35 * sample_lum])

    # Deterministic farthest-point initialization. Saturated and contrasted pixels
    # are more likely to initialize clusters, which improves palette diversity.
    importance = 0.35 + 0.45 * sample_sat + 0.20 * np.abs(sample_lum - float(np.mean(sample_lum)))
    centers = np.empty((n_colors, sample_feat.shape[1]), dtype=np.float64)
    first_idx = int(np.argmax(importance))
    centers[0] = sample_feat[first_idx]
    min_d2 = np.sum((sample_feat - centers[0]) ** 2, axis=1)
    for k in range(1, n_colors):
        next_idx = int(np.argmax(min_d2 * importance))
        centers[k] = sample_feat[next_idx]
        min_d2 = np.minimum(min_d2, np.sum((sample_feat - centers[k]) ** 2, axis=1))

    for _ in range(12):
        d2 = np.sum((sample_feat[:, None, :] - centers[None, :, :]) ** 2, axis=2)
        labels = np.argmin(d2, axis=1)
        new_centers = centers.copy()
        for k in range(n_colors):
            mask = labels == k
            if np.any(mask):
                new_centers[k] = np.mean(sample_feat[mask], axis=0)
        if np.max(np.abs(new_centers - centers)) < 1e-5:
            centers = new_centers
            break
        centers = new_centers

    all_feat = np.column_stack([pixels, 0.35 * lum_flat])
    all_d2 = np.sum((all_feat[:, None, :] - centers[None, :, :]) ** 2, axis=2)
    all_labels = np.argmin(all_d2, axis=1)

    clusters = []
    for k in range(n_colors):
        mask = all_labels == k
        count = int(np.sum(mask))
        if count <= 0:
            continue
        weight = count / max(1, n_pixels)
        sat_weight = sat_flat[mask] + 1e-3
        hue_angle = 2.0 * np.pi * hue_flat[mask]
        hue_mean = (math.atan2(float(np.sum(sat_weight * np.sin(hue_angle))), float(np.sum(sat_weight * np.cos(hue_angle)))) / (2.0 * np.pi)) % 1.0
        clusters.append({
            "weight": float(weight),
            "hue": float(hue_mean),
            "saturation": float(np.mean(sat_flat[mask])),
            "brightness": float(np.mean(lum_flat[mask])),
            "value": float(np.mean(val_flat[mask])),
            "x": float(np.mean(x_flat[mask])),
            "y": float(np.mean(y_flat[mask])),
        })

    if not clusters:
        clusters = [{"weight": 1.0, "hue": 0.0, "saturation": 0.0, "brightness": float(np.mean(lum_flat)), "value": float(np.mean(val_flat)), "x": 0.5, "y": 0.5}]

    # Ignore very tiny regions in the trajectory, unless that would remove everything.
    significant = [c for c in clusters if c["weight"] >= 0.025]
    if not significant:
        significant = sorted(clusters, key=lambda c: c["weight"], reverse=True)[:1]

    # Palette trajectory: color regions are ordered from left to right, with vertical
    # position as a weak tie-breaker. This produces a deterministic harmonic motion.
    trajectory = sorted(significant, key=lambda c: (c["x"], c["y"]))
    total_weight = sum(c["weight"] for c in trajectory) + 1e-12
    for c in trajectory:
        c["weight"] = float(c["weight"] / total_weight)

    weights = np.array([c["weight"] for c in trajectory], dtype=np.float64)
    entropy = 0.0
    if weights.size > 1:
        entropy = -float(np.sum(weights * np.log2(np.maximum(weights, 1e-12)))) / math.log2(len(weights))
        entropy = clamp(entropy, 0.0, 1.0)

    if len(trajectory) > 1:
        transitions = []
        for c0, c1 in zip(trajectory[:-1], trajectory[1:]):
            hue_dist = circular_hue_distance(c0["hue"], c1["hue"])
            sat_pair = 0.5 * (c0["saturation"] + c1["saturation"])
            bright_jump = abs(c1["brightness"] - c0["brightness"])
            transitions.append(clamp(0.65 * hue_dist * sat_pair + 0.35 * bright_jump, 0.0, 1.0))
        transition_tension = float(np.mean(transitions))
        spatial_flow = float(trajectory[-1]["brightness"] - trajectory[0]["brightness"])
    else:
        transition_tension = 0.0
        spatial_flow = 0.0

    hue_values = [c["hue"] for c in trajectory]
    hue_spread = 0.0
    if len(hue_values) > 1:
        pairwise = [circular_hue_distance(a, b) for i, a in enumerate(hue_values) for b in hue_values[i + 1:]]
        hue_spread = float(np.mean(pairwise)) if pairwise else 0.0

    brightness_values = [c["brightness"] for c in trajectory]
    saturation_values = [c["saturation"] for c in trajectory]
    out = {
        "palette_count": float(len(trajectory)),
        "palette_entropy": float(entropy),
        "palette_hue_spread": float(hue_spread),
        "palette_saturation_mean": float(np.mean(saturation_values)) if saturation_values else 0.0,
        "palette_brightness_range": float(max(brightness_values) - min(brightness_values)) if brightness_values else 0.0,
        "palette_transition_tension": float(transition_tension),
        "palette_spatial_flow": float(spatial_flow),
    }

    for i in range(n_colors):
        if i < len(trajectory):
            c = trajectory[i]
            out.update({
                f"palette_hue_{i}": float(c["hue"]),
                f"palette_saturation_{i}": float(c["saturation"]),
                f"palette_brightness_{i}": float(c["brightness"]),
                f"palette_weight_{i}": float(c["weight"]),
                f"palette_x_{i}": float(c["x"]),
                f"palette_y_{i}": float(c["y"]),
            })
        else:
            out.update({
                f"palette_hue_{i}": 0.0,
                f"palette_saturation_{i}": 0.0,
                f"palette_brightness_{i}": 0.0,
                f"palette_weight_{i}": 0.0,
                f"palette_x_{i}": 0.5,
                f"palette_y_{i}": 0.5,
            })
    return out

def analyze_fourier(luminance: np.ndarray, random_factor: float = 0.0, rng: Optional[np.random.Generator] = None) -> Dict[str, np.ndarray | float]:
    h, w = luminance.shape
    window_y = np.hanning(h) if h > 1 else np.ones(h)
    window_x = np.hanning(w) if w > 1 else np.ones(w)
    window = np.outer(window_y, window_x)
    random_level = clamp(float(random_factor) / 100.0, 0.0, 1.0)
    rng = np.random.default_rng() if rng is None else rng

    centered = luminance - float(np.mean(luminance))
    spectrum = np.fft.fftshift(np.fft.fft2(centered * window))
    magnitude = np.abs(spectrum)
    fourier_noise_sigma = 0.18 * (random_level ** 2)
    if fourier_noise_sigma > 0.0:
        magnitude = magnitude * np.exp(rng.normal(0.0, fourier_noise_sigma, size=magnitude.shape))

    power = magnitude ** 2
    fy = np.fft.fftshift(np.fft.fftfreq(h))
    fx = np.fft.fftshift(np.fft.fftfreq(w))
    uu, vv = np.meshgrid(fx, fy)
    radius = np.sqrt(uu * uu + vv * vv)
    max_radius = float(np.max(radius)) if np.max(radius) > 1e-12 else 1.0
    r = radius / max_radius

    power_no_dc = power.copy()
    power_no_dc[r < 0.025] = 0.0
    total = float(np.sum(power_no_dc))
    if total <= 1e-12:
        total = 1e-12

    low_mask = (r >= 0.025) & (r < 0.14)
    mid_mask = (r >= 0.14) & (r < 0.34)
    high_mask = r >= 0.34
    low_energy = float(np.sum(power_no_dc[low_mask]) / total)
    mid_energy = float(np.sum(power_no_dc[mid_mask]) / total)
    high_energy = float(np.sum(power_no_dc[high_mask]) / total)
    centroid = float(np.sum(r * power_no_dc) / total)
    bandwidth = float(np.sqrt(np.sum(((r - centroid) ** 2) * power_no_dc) / total))

    theta = np.arctan2(vv, uu)
    abs_sin = np.abs(np.sin(theta))
    abs_cos = np.abs(np.cos(theta))
    horizontal_freq_mask = abs_sin < 0.38
    vertical_freq_mask = abs_cos < 0.38
    diagonal_freq_mask = ~(horizontal_freq_mask | vertical_freq_mask)

    valid_power = power_no_dc[power_no_dc > 0]
    if valid_power.size == 0:
        peak_score = 0.0
    else:
        p997 = float(np.percentile(valid_power, 99.7))
        p90 = float(np.percentile(valid_power, 90.0)) + 1e-12
        peak_score = clamp(math.log1p(p997 / p90) / 5.0, 0.0, 1.0)

    return {
        "fft_log_magnitude": normalize01(np.log1p(magnitude)),
        "low_frequency_energy": low_energy,
        "mid_frequency_energy": mid_energy,
        "high_frequency_energy": high_energy,
        "fourier_centroid": centroid,
        "fourier_bandwidth": bandwidth,
        "horizontal_frequency_energy": float(np.sum(power_no_dc[horizontal_freq_mask]) / total),
        "vertical_frequency_energy": float(np.sum(power_no_dc[vertical_freq_mask]) / total),
        "diagonal_frequency_energy": float(np.sum(power_no_dc[diagonal_freq_mask]) / total),
        "periodic_peak_score": float(peak_score),
        "fourier_noise_sigma": float(fourier_noise_sigma),
    }


def analyze_image(image: Image.Image, random_factor: float = 0.0, rng: Optional[np.random.Generator] = None) -> Dict[str, object]:
    rgb = image_to_rgb_array(image)
    random_level = clamp(float(random_factor) / 100.0, 0.0, 1.0)
    rng = np.random.default_rng() if rng is None else rng
    image_noise_sigma = 0.045 * (random_level ** 2)
    if image_noise_sigma > 0.0:
        rgb = np.clip(rgb + rng.normal(0.0, image_noise_sigma, size=rgb.shape), 0.0, 1.0)

    luminance = rgb_to_luminance(rgb)
    h, w = luminance.shape
    p05 = float(np.percentile(luminance, 5.0))
    p95 = float(np.percentile(luminance, 95.0))
    shadow_mask = luminance < max(0.18, p05 + 0.03)
    highlight_mask = luminance > min(0.82, p95 - 0.03)
    shadow_weight = np.where(shadow_mask, 1.0 - luminance, 0.0)
    highlight_weight = np.where(highlight_mask, luminance, 0.0)
    bright_weight = np.maximum(luminance - np.mean(luminance), 0.0)

    edge_map, edge_density = compute_edge_map(luminance)
    texture_entropy = normalized_histogram_entropy(edge_map, bins=64)
    symmetry = compute_symmetry_features(luminance)
    hsv = rgb_to_hsv_features(rgb, luminance)
    fourier = analyze_fourier(luminance, random_factor=random_factor, rng=rng)
    palette = compute_color_palette_trajectory(rgb, luminance, n_colors=5)

    features = {
        "analysis_width": int(w),
        "analysis_height": int(h),
        "aspect_ratio": float(w / max(1, h)),
        "mean_brightness": float(np.mean(luminance)),
        "contrast": float(np.std(luminance)),
        "dynamic_range": float(p95 - p05),
        "shadow_proportion": float(np.mean(shadow_mask)),
        "highlight_proportion": float(np.mean(highlight_mask)),
        "edge_density": float(edge_density),
        "texture_entropy": float(texture_entropy),
        "auto_complexity": float(auto_complexity_from_texture_entropy(texture_entropy)),
        "auto_variation_strength": float(auto_variation_from_symmetry(symmetry["symmetry_score"])),
        "image_noise_sigma": float(image_noise_sigma),
        "bright_centroid_x": center_of_mass(bright_weight)[0],
        "bright_centroid_y": center_of_mass(bright_weight)[1],
        "shadow_centroid_x": center_of_mass(shadow_weight)[0],
        "shadow_centroid_y": center_of_mass(shadow_weight)[1],
        "highlight_centroid_x": center_of_mass(highlight_weight)[0],
        "highlight_centroid_y": center_of_mass(highlight_weight)[1],
        **symmetry,
        **hsv,
        **palette,
        **compute_gradient_orientation_features(luminance),
        **compute_quadrant_brightness(luminance),
        **compute_local_contrast_variance(luminance),
        **compute_color_temperature_gradient(rgb),
        **compute_luminance_cdf_features(luminance),
    }

    for key, value in fourier.items():
        if not isinstance(value, np.ndarray):
            features[key] = value

    maps = {
        "rgb": rgb,
        "luminance": luminance,
        "edge_map": edge_map,
        "shadow_highlight_map": np.dstack([
            highlight_mask.astype(float),
            np.zeros_like(luminance),
            shadow_mask.astype(float),
        ]),
        "fft_log_magnitude": fourier["fft_log_magnitude"],
    }
    return {"features": features, "maps": maps}


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

MAJOR_PROGRESSIONS = [
    [[0, 4, 7], [7, 11, 14], [9, 12, 16], [5, 9, 12]],
    [[0, 4, 7], [5, 9, 12], [9, 12, 16], [7, 11, 14]],
    [[0, 4, 7], [9, 12, 16], [5, 9, 12], [7, 11, 14]],
]
MINOR_PROGRESSIONS = [
    [[0, 3, 7], [8, 12, 15], [3, 7, 10], [10, 14, 17]],
    [[0, 3, 7], [5, 8, 12], [8, 12, 15], [10, 14, 17]],
    [[0, 3, 7], [10, 14, 17], [8, 12, 15], [7, 10, 14]],
]
PENTATONIC_PROGRESSIONS = [
    [[0, 7, 12], [9, 12, 16], [5, 9, 12], [7, 12, 14]],
    [[0, 7, 12], [5, 9, 12], [7, 12, 14], [9, 12, 16]],
]


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
    mood: str
    mapping_summary: Dict[str, str]


INSTRUMENT_DISPLAY_TO_INTERNAL = {
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
INSTRUMENT_CHOICES = sorted(INSTRUMENT_DISPLAY_TO_INTERNAL.keys())
INSTRUMENT_CHOICES_WITH_NONE = ["None"] + INSTRUMENT_CHOICES
INSTRUMENT_INTERNAL_TO_DISPLAY = {v: k for k, v in INSTRUMENT_DISPLAY_TO_INTERNAL.items()}


def instrument_key(display_name: str, default: str = "soft_piano") -> str:
    if display_name == "None":
        return "none"
    return INSTRUMENT_DISPLAY_TO_INTERNAL.get(display_name, default)


def choose_scale(features: Dict[str, float], requested_scale: str) -> str:
    if requested_scale != "Automatic" and requested_scale in SCALES:
        return requested_scale
    brightness = features["mean_brightness"]
    saturation = features["mean_saturation"]
    warmth = features["warmth"]
    contrast = features["contrast"]
    if brightness > 0.60:
        if warmth > 0.06:
            return "Lydian"
        if warmth > -0.02:
            return "Major pentatonic"
        return "Major"
    if brightness > 0.42:
        if warmth > 0.06 and saturation > 0.38:
            return "Dorian"
        if warmth > 0.03:
            return "Major pentatonic"
        if contrast > 0.22:
            return "Dorian"
        return "Major pentatonic"
    if warmth > 0.05 and saturation > 0.30:
        return "Dorian"
    return "Natural minor"


def choose_instruments(
    features: Dict[str, float],
    instrument_mode: str,
    manual_main_layer: str = "Soft piano",
    manual_texture_layer: str = "Harp",
    manual_bass_layer: str = "Cello-like bass",
    manual_pad_layer: str = "Warm pad",
    manual_chord_layer: str = "Soft piano",
) -> Tuple[str, str, str, str, str]:
    if instrument_mode == "Manual":
        return (
            instrument_key(manual_main_layer, "soft_piano"),
            instrument_key(manual_texture_layer, "harp"),
            instrument_key(manual_bass_layer, "cello"),
            instrument_key(manual_pad_layer, "warm_pad"),
            instrument_key(manual_chord_layer, "soft_piano"),
        )

    brightness = float(features["mean_brightness"])
    contrast = float(features["contrast"])
    saturation = float(features["mean_saturation"])
    warmth = float(features["warmth"])
    highlights = float(features["highlight_proportion"])
    shadows = float(features["shadow_proportion"])
    high_freq = float(features["high_frequency_energy"])
    low_freq = float(features["low_frequency_energy"])
    bandwidth = float(features["fourier_bandwidth"])
    peak_score = float(features["periodic_peak_score"])

    if highlights > 0.14 and high_freq > 0.28:
        main = "bright_bell"
    elif brightness > 0.64 and highlights > 0.08:
        main = "celesta"
    elif peak_score > 0.58 and high_freq > 0.24:
        main = "kalimba"
    elif peak_score > 0.48:
        main = "marimba"
    elif low_freq > 0.50 and high_freq < 0.20:
        main = "glass_pad" if brightness > 0.52 else "warm_pad"
    elif warmth > 0.07 and saturation > 0.42:
        main = "harp"
    elif contrast > 0.25 and high_freq > 0.28:
        main = "synth_pluck"
    else:
        main = "soft_piano"

    if high_freq > 0.44 or highlights > 0.16:
        texture = "bright_bell"
    elif high_freq > 0.32:
        texture = "celesta"
    elif peak_score > 0.55:
        texture = "kalimba"
    elif bandwidth > 0.22 and contrast > 0.18:
        texture = "synth_pluck"
    elif saturation > 0.45 and warmth > 0.02:
        texture = "harp"
    else:
        texture = "music_box"

    if shadows > 0.26 or brightness < 0.36:
        bass = "cello"
    elif low_freq > 0.48 and high_freq < 0.24:
        bass = "soft_bass"
    elif warmth > 0.04 and contrast < 0.18:
        bass = "bowed_string"
    else:
        bass = "soft_bass"

    if low_freq > 0.52 and warmth > 0.04:
        pad = "warm_pad"
    elif low_freq > 0.44 and brightness > 0.52:
        pad = "glass_pad"
    elif shadows > 0.20:
        pad = "warm_pad"
    else:
        pad = "glass_pad"

    if main not in ("warm_pad", "glass_pad"):
        chord = "soft_piano" if main != "soft_piano" else "harp"
    elif warmth > 0.04:
        chord = "harp"
    else:
        chord = "bowed_string"

    return main, texture, bass, pad, chord


def describe_mood(features: Dict[str, float]) -> str:
    brightness = features["mean_brightness"]
    contrast = features["contrast"]
    high_freq = features["high_frequency_energy"]
    warmth = features["warmth"]
    light_word = "bright" if brightness > 0.58 else "dark" if brightness < 0.40 else "balanced"
    texture_word = "textured" if high_freq > 0.32 else "smooth" if high_freq < 0.18 else "moderately textured"
    contrast_word = "dynamic" if contrast > 0.24 else "soft" if contrast < 0.13 else "moderately dynamic"
    color_word = "warm" if warmth > 0.04 else "cool" if warmth < -0.04 else "neutral"
    return f"{light_word}, {color_word}, {contrast_word}, {texture_word}"


def build_scale_notes(root: int, scale_intervals: List[int], low: int, high: int) -> List[int]:
    notes: List[int] = []
    for octave in range(-3, 6):
        for interval in scale_intervals:
            n = root + 12 * octave + interval
            if low <= n <= high:
                notes.append(n)
    return sorted(set(notes))


def chord_from_scale_degree(scale_intervals: List[int], degree: int) -> List[int]:
    n = max(1, len(scale_intervals))

    def interval_at(step: int) -> int:
        return int(scale_intervals[step % n] + 12 * (step // n))

    return [interval_at(degree), interval_at(degree + 2), interval_at(degree + 4)]


def choose_progression(scale_name: str, features: Dict[str, float]) -> List[List[int]]:
    scale_intervals = SCALES.get(scale_name, SCALES["Major pentatonic"])
    n_degrees = len(scale_intervals)
    palette_count = int(round(float(features.get("palette_count", 0.0))))

    # Fallback to the old compact progression bank if palette extraction is unavailable.
    if palette_count <= 0:
        idx_seed = int((features["dominant_hue"] * 997.0 + features["periodic_peak_score"] * 113.0))
        if "minor" in scale_name.lower() or scale_name == "Dorian":
            return MINOR_PROGRESSIONS[idx_seed % len(MINOR_PROGRESSIONS)]
        if "pentatonic" in scale_name.lower():
            return PENTATONIC_PROGRESSIONS[idx_seed % len(PENTATONIC_PROGRESSIONS)]
        return MAJOR_PROGRESSIONS[idx_seed % len(MAJOR_PROGRESSIONS)]

    dominant_hue = float(features.get("dominant_hue", 0.0))
    palette_entropy = float(features.get("palette_entropy", 0.0))
    palette_tension = float(features.get("palette_transition_tension", 0.0))
    palette_hue_spread = float(features.get("palette_hue_spread", 0.0))
    texture_entropy = float(features.get("texture_entropy", 0.0))
    symmetry = float(features.get("symmetry_score", 0.5))
    shadows = float(features.get("shadow_proportion", 0.0))
    highlights = float(features.get("highlight_proportion", 0.0))
    peak_score = float(features.get("periodic_peak_score", 0.0))

    # More varied palettes generate longer harmonic phrases, while symmetric or
    # highly periodic images keep a shorter loop feeling.
    diversity_score = clamp(
        0.38 * palette_entropy
        + 0.26 * palette_tension
        + 0.20 * palette_hue_spread
        + 0.16 * texture_entropy
        - 0.12 * symmetry
        + 0.08 * (1.0 - peak_score),
        0.0,
        1.0,
    )
    progression_length = int(round(np.interp(diversity_score, [0.0, 1.0], [4.0, 8.0])))
    progression_length = int(clamp(progression_length, 4, 8))

    is_minor_like = "minor" in scale_name.lower() or scale_name == "Dorian"
    if n_degrees >= 7:
        if is_minor_like:
            stable_pool = [0, 3, 5, 6]
            bright_pool = [2, 5, 6]
            dark_pool = [0, 3, 6, 4]
            tension_pool = [1, 2, 4]
            cadence_degree = 0 if symmetry > 0.58 else 6
        else:
            stable_pool = [0, 3, 4, 5]
            bright_pool = [3, 4, 5]
            dark_pool = [5, 1, 2]
            tension_pool = [1, 2, 6]
            cadence_degree = 0 if symmetry > 0.58 else 4
    else:
        stable_pool = [0, 2, 3]
        bright_pool = [1, 2, 4]
        dark_pool = [0, 3, 4]
        tension_pool = [1, 4, 2]
        cadence_degree = 0 if symmetry > 0.58 else 2

    # Start from the tonal center for a clear reference, then let the ordered
    # color palette define the harmonic trajectory.
    degrees: List[int] = [0]
    previous_hue = float(features.get("palette_hue_0", dominant_hue))
    previous_brightness = float(features.get("palette_brightness_0", features.get("mean_brightness", 0.5)))

    for step in range(1, progression_length):
        pidx = (step - 1) % max(1, palette_count)
        hue = float(features.get(f"palette_hue_{pidx}", dominant_hue))
        sat = float(features.get(f"palette_saturation_{pidx}", features.get("mean_saturation", 0.0)))
        lum = float(features.get(f"palette_brightness_{pidx}", features.get("mean_brightness", 0.5)))
        weight = float(features.get(f"palette_weight_{pidx}", 1.0 / max(1, palette_count)))

        rel_hue = (hue - dominant_hue) % 1.0
        hue_bin = int(round(rel_hue * max(1, n_degrees - 1)))
        hue_jump = circular_hue_distance(previous_hue, hue)
        lum_jump = abs(lum - previous_brightness)
        local_tension = clamp(0.55 * hue_jump * (0.25 + sat) + 0.45 * lum_jump + 0.20 * palette_tension, 0.0, 1.0)

        if shadows > 0.24 and lum < 0.46:
            pool = dark_pool + tension_pool + stable_pool
        elif highlights > 0.10 and lum > 0.56:
            pool = bright_pool + stable_pool + tension_pool
        elif local_tension > 0.42 or sat > 0.55:
            pool = tension_pool + bright_pool + stable_pool
        else:
            pool = stable_pool + dark_pool + tension_pool

        pool = [d % n_degrees for d in pool]
        index = (hue_bin + int(round(4.0 * sat)) + int(round(5.0 * weight)) + step) % len(pool)
        degree = pool[index]

        # Avoid static repetitions unless the image is intentionally very stable.
        if len(degrees) >= 1 and degree == degrees[-1] and diversity_score > 0.22:
            degree = pool[(index + 1 + int(round(2.0 * local_tension))) % len(pool)]

        degrees.append(int(degree % n_degrees))
        previous_hue = hue
        previous_brightness = lum

    # The last chord determines whether the loop feels resolved or suspended.
    if progression_length >= 4:
        if palette_tension < 0.28 and symmetry > 0.52:
            degrees[-1] = 0
        elif highlights > shadows and palette_hue_spread > 0.28:
            degrees[-1] = bright_pool[(int(round(10.0 * palette_hue_spread)) + progression_length) % len(bright_pool)] % n_degrees
        else:
            degrees[-1] = cadence_degree % n_degrees

    return [chord_from_scale_degree(scale_intervals, degree) for degree in degrees]


def time_slice_statistics(luminance: np.ndarray, n_slices: int) -> List[Dict[str, float]]:
    h, w = luminance.shape
    stats: List[Dict[str, float]] = []
    for i in range(n_slices):
        x0 = int(round(i * w / n_slices))
        x1 = max(x0 + 1, int(round((i + 1) * w / n_slices)))
        sl = luminance[:, x0:x1]
        energy = float(np.mean(sl))
        contrast = float(np.std(sl))
        weights = np.maximum(sl - np.percentile(sl, 35.0), 0.0)
        total = float(np.sum(weights))
        if total <= 1e-12:
            y_centroid = 0.5
        else:
            y_idx = np.arange(h).reshape(-1, 1)
            y_centroid = float(np.sum(y_idx * weights) / total) / max(1, h - 1)
        stats.append({"energy": energy, "contrast": contrast, "y_centroid": y_centroid})
    return stats


def generate_composition(
    analysis: Dict[str, object],
    number_of_bars: int,
    complexity: float,
    variation_strength: float,
    requested_scale: str,
    instrument_mode: str,
    manual_main_layer: str,
    manual_texture_layer: str,
    manual_bass_layer: str,
    manual_pad_layer: str,
    manual_chord_layer: str,
    musicality: str,
    manual_tempo_bpm: Optional[float] = None,
    main_gain_db: float = 0.0,
    texture_gain_db: float = 0.0,
    bass_gain_db: float = 0.0,
    pad_gain_db: float = 0.0,
    chord_gain_db: float = 0.0,
) -> Tuple[List[NoteEvent], CompositionInfo]:
    features = analysis["features"]  # type: ignore[assignment]
    maps = analysis["maps"]  # type: ignore[assignment]
    luminance = maps["luminance"]  # type: ignore[index]
    assert isinstance(features, dict)
    assert isinstance(luminance, np.ndarray)

    brightness = float(features["mean_brightness"])
    contrast = float(features["contrast"])
    shadow = float(features["shadow_proportion"])
    highlight = float(features["highlight_proportion"])
    edge_density = float(features["edge_density"])
    saturation = float(features["mean_saturation"])
    warmth = float(features["warmth"])
    low_freq = float(features["low_frequency_energy"])
    high_freq = float(features["high_frequency_energy"])
    centroid = float(features["fourier_centroid"])
    bandwidth = float(features["fourier_bandwidth"])
    peak_score = float(features["periodic_peak_score"])
    dominant_hue = float(features["dominant_hue"])

    key_index = int(round(dominant_hue * 12.0)) % 12
    key_name = KEY_NAMES[key_index]
    scale_name = choose_scale(features, requested_scale)  # type: ignore[arg-type]
    scale_intervals = SCALES[scale_name]

    register_shift = int(round(np.interp(brightness, [0.0, 1.0], [-5.0, 7.0])))
    root = int(clamp(48 + key_index + register_shift, 38, 58))
    variation_strength = clamp(float(variation_strength), 0.0, 1.0)
    complexity = clamp(float(complexity), 0.10, 1.00)

    if musicality == "Manual":
        tempo = max(1e-6, float(manual_tempo_bpm if manual_tempo_bpm is not None else 90.0))
        mode_density_factor, mode_texture_factor, mode_rest_threshold = 1.00, 1.00, 0.10
    elif musicality == "Scientific":
        tempo = 50.0 + 70.0 * edge_density + 58.0 * contrast + 42.0 * peak_score + 34.0 * high_freq + 22.0 * centroid - 20.0 * shadow
        tempo = clamp(tempo, 48.0, 152.0)
        mode_density_factor, mode_texture_factor, mode_rest_threshold = 1.18, 1.22, 0.08
    elif musicality == "Musical":
        tempo = 82.0 + 10.0 * saturation + 8.0 * brightness - 6.0 * shadow + 4.0 * warmth
        tempo = clamp(tempo, 72.0, 108.0)
        mode_density_factor, mode_texture_factor, mode_rest_threshold = 0.82, 0.72, 0.18
    else:
        tempo = 62.0 + 38.0 * edge_density + 28.0 * contrast + 20.0 * peak_score + 10.0 * high_freq - 8.0 * shadow
        tempo = clamp(tempo, 56.0, 132.0)
        mode_density_factor, mode_texture_factor, mode_rest_threshold = 1.00, 1.00, 0.10

    beat = 60.0 / tempo
    bars = int(clamp(int(number_of_bars), 1, 64))
    actual_duration = min(MAX_RENDER_SECONDS, bars * 4.0 * beat)

    staccato_score = float(features.get("staccato_score", 0.3))
    legato_score = float(features.get("legato_score", 0.5))
    offbeat_tendency = float(features.get("offbeat_tendency", 0.3))
    local_contrast_variance_norm = float(features.get("local_contrast_variance_norm", 0.3))
    color_temp_grad_x = float(features.get("color_temp_gradient_x", 0.0))
    lum_cdf_spread = float(features.get("lum_cdf_spread", 0.5))
    brightness_skew = float(features.get("brightness_skew", 0.0))

    articulation_factor = clamp(1.0 - staccato_score * 0.5 + legato_score * 0.3, 0.55, 1.40)
    section_dynamic_range = clamp(0.3 + local_contrast_variance_norm * 0.7, 0.3, 1.0)
    beat_accent_weights_norm = np.array([
        float(features.get("quad_accent_1", 0.25)),
        float(features.get("quad_accent_2", 0.25)),
        float(features.get("quad_accent_3", 0.25)),
        float(features.get("quad_accent_4", 0.25)),
    ])
    beat_accent_weights_norm = beat_accent_weights_norm / (beat_accent_weights_norm.sum() + 1e-12)

    main_inst, texture_inst, bass_inst, pad_inst, chord_inst = choose_instruments(
        features,
        instrument_mode,
        manual_main_layer,
        manual_texture_layer,
        manual_bass_layer,
        manual_pad_layer,
        manual_chord_layer,
    )
    highlight_inst = texture_inst if instrument_mode == "Manual" and texture_inst != "none" else "music_box"

    progression = choose_progression(scale_name, features)  # type: ignore[arg-type]
    melody_notes = build_scale_notes(root, scale_intervals, root + 10, root + 31)
    bass_notes = build_scale_notes(root, scale_intervals, root - 18, root + 7)
    events: List[NoteEvent] = []

    pan_bias = np.interp(float(features["bright_centroid_x"]), [0.0, 1.0], [-0.45, 0.45])
    shadow_pan = np.interp(float(features["shadow_centroid_x"]), [0.0, 1.0], [-0.35, 0.35])
    highlight_pan = np.interp(float(features["highlight_centroid_x"]), [0.0, 1.0], [-0.65, 0.65])
    chord_velocity = clamp(0.28 + 0.42 * brightness + 0.18 * low_freq, 0.22, 0.78)
    pad_velocity = clamp(0.07 + 0.18 * low_freq + 0.04 * (1.0 - high_freq), 0.04, 0.28)
    bass_velocity = clamp(0.30 + 0.55 * shadow + 0.25 * low_freq, 0.22, 0.86)
    melody_velocity_base = clamp(0.30 + 0.30 * lum_cdf_spread + 0.20 * contrast + 0.15 * saturation + 0.08 * brightness_skew, 0.28, 0.90)

    for bar in range(bars):
        start = bar * 4.0 * beat
        progression_index = bar % len(progression)
        if variation_strength > 0.35 and bar >= bars // 2:
            progression_index = (progression_index + 1 + int((bar * variation_strength) % len(progression))) % len(progression)
        chord = progression[progression_index]
        chord_root_shift = 0
        if musicality == "Scientific":
            chord_root_shift = int(round((centroid - 0.28) * 8.0))
        if abs(color_temp_grad_x) > 0.03:
            chord_root_shift += int(round(color_temp_grad_x * 6.0 * (bar / max(1, bars - 1))))
        if variation_strength > 0.55 and bar >= bars // 2:
            chord_root_shift += int(round((variation_strength - 0.50) * 4.0))
        chord_notes = [int(root + interval + chord_root_shift) for interval in chord]
        section = min(3, int((bar / max(1, bars)) * 4.0))
        section_dyn = [0.75, 1.00, 1.15 * section_dynamic_range, 0.90][section]

        if pad_inst != "none":
            for n in chord_notes:
                events.append(NoteEvent(start, 4.05 * beat, int(clamp(n + 12, 36, 88)), clamp(pad_velocity * section_dyn, 0.035, 0.32), pad_inst, 0.15 * math.sin(bar * 0.7), "pad"))

        if chord_inst != "none":
            chord_hits = 1 if musicality == "Scientific" and high_freq < 0.22 else 2
            for hit in range(chord_hits):
                beat_idx = hit * 2
                beat_accent = float(beat_accent_weights_norm[min(beat_idx, 3)])
                offbeat_offset = 0.12 * beat if offbeat_tendency > 0.5 and hit == 1 else 0.0
                hit_start = start + hit * 2.0 * beat + offbeat_offset
                for n in chord_notes:
                    events.append(NoteEvent(hit_start, 1.75 * beat, int(clamp(n + 12, 38, 92)), clamp(chord_velocity * section_dyn * (0.8 + 0.4 * beat_accent) * (0.92 if hit else 1.0), 0.18, 0.88), chord_inst, pan_bias * 0.45, "chord"))

        if bass_inst != "none":
            root_bass = min(bass_notes, key=lambda x: abs(x - (root - 12))) if bass_notes else root - 12
            fifth_bass = int(root_bass + 7)
            octave_bass = int(root_bass + 12)
            events.append(NoteEvent(start, 1.55 * beat * articulation_factor, root_bass, clamp(bass_velocity * section_dyn, 0.18, 0.90), bass_inst, shadow_pan, "bass"))
            events.append(NoteEvent(start + 2.0 * beat, 1.35 * beat * articulation_factor, fifth_bass, clamp(bass_velocity * section_dyn * 0.82, 0.14, 0.80), bass_inst, shadow_pan * 0.7, "bass"))
            if low_freq > 0.45 and complexity > 0.50:
                hit3_beat = 1.0 if offbeat_tendency > 0.45 else 1.5
                events.append(NoteEvent(start + hit3_beat * beat, 0.85 * beat * articulation_factor, int(clamp(octave_bass if peak_score > 0.45 else root_bass, 28, 72)), clamp(bass_velocity * section_dyn * 0.65, 0.12, 0.68), bass_inst, shadow_pan * 0.4, "bass"))
            if offbeat_tendency > 0.60 and bar % 2 == 1:
                events.append(NoteEvent(start + 3.0 * beat, 0.55 * beat * articulation_factor, fifth_bass, clamp(bass_velocity * section_dyn * 0.55, 0.10, 0.60), bass_inst, shadow_pan * 0.5, "bass"))

    slice_count = bars * 8
    slices = time_slice_statistics(luminance, slice_count)
    edge_map_arr = maps.get("edge_map", None)
    if isinstance(edge_map_arr, np.ndarray) and edge_map_arr.ndim == 2:
        eh, ew = edge_map_arr.shape
        edge_col_profile = np.array([
            float(np.mean(edge_map_arr[:, max(0, int(round(i * ew / slice_count))): max(1, int(round((i + 1) * ew / slice_count)))]))
            for i in range(slice_count)
        ])
    else:
        edge_col_profile = np.full(slice_count, 0.3)

    melody_step = 1 if complexity * mode_density_factor > 0.52 else 2
    if main_inst != "none":
        for i in range(0, slice_count, melody_step):
            sl = slices[i]
            local_energy = sl["energy"]
            local_contrast = sl["contrast"]
            y_centroid = sl["y_centroid"]
            t = i * 0.5 * beat
            if local_energy < mode_rest_threshold and (i % 4 != 0):
                continue
            pitch_position = clamp(1.0 - y_centroid + 0.18 * (local_energy - brightness), 0.0, 1.0)
            note = melody_notes[int(round(pitch_position * (len(melody_notes) - 1)))]
            phrase = (i // 16) % 4
            section = min(3, int((t / max(actual_duration, 1e-6)) * 4.0))
            if phrase == 1 and len(scale_intervals) >= 5:
                note += 2
            elif phrase == 2:
                note -= 1 if musicality == "Scientific" else 0
            elif phrase == 3:
                note += 5 if local_energy > brightness else -2
            if variation_strength > 0.05:
                section_offsets = [0, 2, -2, 5]
                note += int(round(section_offsets[section] * variation_strength))
                if section >= 2 and variation_strength > 0.45 and i % 5 == 0:
                    note += -3 if local_energy < brightness else 4
                if section == 3 and variation_strength > 0.70 and i % 7 == 0:
                    note += 7
            local_edge_strength = float(edge_col_profile[i])
            edge_duration_factor = clamp(articulation_factor * (1.0 - 0.55 * local_edge_strength + 0.30 * legato_score), 0.30, 1.60)
            duration = (0.42 + 0.52 * (1.0 - high_freq) + 0.25 * local_energy) * beat * edge_duration_factor
            if complexity * mode_density_factor > 0.72 and i % 6 == 0:
                duration *= 1.4
            if variation_strength > 0.05:
                duration *= clamp(1.0 + 0.22 * variation_strength * math.sin(0.73 * i + 1.7 * section), 0.70, 1.35)
                if section >= 2 and variation_strength > 0.55 and i % 9 == 0:
                    duration *= 0.62
            lum_velocity_mod = clamp((local_energy - 0.5) * lum_cdf_spread * 2.0, -0.25, 0.35)
            velocity = clamp(melody_velocity_base + lum_velocity_mod + 0.25 * local_contrast, 0.20, 0.96)
            pan = clamp(pan_bias + 0.20 * math.sin(i * 0.37), -0.75, 0.75)
            events.append(NoteEvent(t, duration, int(clamp(note, 36, 100)), velocity, main_inst, pan, "main"))

    arpeggio_density = clamp((0.20 + 0.80 * complexity + 0.75 * high_freq + 0.45 * bandwidth) * mode_texture_factor, 0.0, 1.0)
    arp_interval = 0.5 * beat if arpeggio_density > 0.55 else beat
    if arpeggio_density > 0.28 and texture_inst != "none":
        n_steps = int(actual_duration / arp_interval)
        for j in range(n_steps):
            if musicality == "Scientific" and (j % 3 == 2) and high_freq < 0.30 and variation_strength < 0.55:
                continue
            t = j * arp_interval
            bar = int(t // (4.0 * beat))
            chord = progression[(bar + (1 if variation_strength > 0.60 and bar >= bars // 2 else 0)) % len(progression)]
            pattern = chord + [chord[1] + 12, chord[2] + 12]
            note = int(clamp(root + pattern[j % len(pattern)] + 12, 45, 96))
            vel = clamp(0.16 + 0.40 * high_freq + 0.22 * edge_density, 0.12, 0.68)
            pan = clamp(-0.45 + 0.90 * ((j % 8) / 7.0), -0.65, 0.65)
            events.append(NoteEvent(t, 0.34 * beat, note, vel, texture_inst, pan, "texture"))

    highlight_count = int(round(np.interp(highlight + high_freq, [0.02, 0.70], [4, 26]) * complexity * mode_density_factor))
    highlight_count = int(clamp(highlight_count, 2, 32))
    lum = luminance
    h, w = lum.shape
    bright_score = np.maximum(lum - np.percentile(lum, 88), 0.0)
    if np.sum(bright_score) > 1e-12 and highlight_inst != "none":
        flat_idx = np.argsort(bright_score.ravel())[-highlight_count:]
        coords = [np.unravel_index(int(k), bright_score.shape) for k in flat_idx]
        coords = sorted(coords, key=lambda rc: rc[1])
        for k, (yy, xx) in enumerate(coords):
            x_norm = xx / max(1, w - 1)
            y_norm = yy / max(1, h - 1)
            t = clamp(x_norm * actual_duration, 0.0, actual_duration - 0.3)
            note = melody_notes[int(round(clamp(1.0 - y_norm, 0.0, 1.0) * (len(melody_notes) - 1)))] + 12
            vel = clamp(0.22 + 0.58 * float(lum[yy, xx]), 0.20, 0.88)
            pan = clamp(highlight_pan + 0.25 * math.sin(k), -0.85, 0.85)
            events.append(NoteEvent(t, 0.72 * beat, int(clamp(note, 55, 108)), vel, highlight_inst, pan, "texture"))

    texture_strength = clamp((0.20 * edge_density + 0.35 * high_freq + 0.35 * peak_score + 0.15 * complexity) * mode_texture_factor, 0.0, 1.0)
    if texture_strength > 0.18:
        subdivision = 0.5 * beat if texture_strength < 0.55 else 0.25 * beat
        n_hits = int(actual_duration / subdivision)
        for j in range(n_hits):
            if j % 2 == 1 and texture_strength < 0.62:
                continue
            t = j * subdivision
            accent = 1.0 if j % 8 == 0 else 0.62
            midi = 76 if (j % 4 in [0, 3]) else 72
            vel = clamp((0.10 + 0.42 * texture_strength) * accent, 0.05, 0.55)
            pan = 0.55 * math.sin(j * 0.91 + float(features["diagonal_frequency_energy"]) * 2.0)
            events.append(NoteEvent(t, 0.08 * beat, midi, vel, "texture_tick", pan, "texture"))

    layer_gain_db = {
        "main": float(main_gain_db),
        "texture": float(texture_gain_db),
        "bass": float(bass_gain_db),
        "pad": float(pad_gain_db),
        "chord": float(chord_gain_db),
    }
    for ev in events:
        gain_linear = 10.0 ** (layer_gain_db.get(ev.layer, 0.0) / 20.0)
        ev.velocity = clamp(ev.velocity * gain_linear, 0.0, 1.0)

    mapping_summary = {
        "Brightness": "controls the global pitch register and melody velocity",
        "Shadows": "reinforce cello/bass notes and low-frequency warmth",
        "Highlights": "create bell-like notes placed according to their positions",
        "Contrast": "controls loudness variation and note articulation",
        "Edge density": "controls rhythmic activity and attack sharpness",
        "Fourier low frequencies": "control pad and bass weight",
        "Fourier high frequencies": "control arpeggio density and timbre brightness",
        "Fourier peak score": "controls repetition and periodic rhythmic motifs",
        "Image symmetry": "sets the default variation strength",
        "Texture entropy": "sets the default composition complexity",
        "Color palette trajectory": "drives chord progression diversity from dominant colors and their left-to-right order",
        "Random factor": "adds controlled white perturbation in the image and Fourier domains",
    }
    info = CompositionInfo(tempo, bars, actual_duration, key_name, scale_name, main_inst, texture_inst, bass_inst, pad_inst, chord_inst, describe_mood(features), mapping_summary)
    events = [ev for ev in events if ev.start < actual_duration]
    events.sort(key=lambda ev: (ev.start, ev.midi, ev.instrument, ev.layer))
    return events, info


def adsr_envelope(n: int, sr: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    if n <= 0:
        return np.zeros(0, dtype=np.float64)
    env = np.ones(n, dtype=np.float64) * sustain
    a = int(max(1, attack * sr))
    d = int(max(1, decay * sr))
    r = int(max(1, release * sr))
    a_end = min(n, a)
    env[:a_end] = np.linspace(0.0, 1.0, a_end, endpoint=False)
    d_end = min(n, a + d)
    if d_end > a_end:
        env[a_end:d_end] = np.linspace(1.0, sustain, d_end - a_end, endpoint=False)
    r_start = max(0, n - r)
    if r_start < n:
        env[r_start:] *= np.linspace(1.0, 0.0, n - r_start)
    return env


def synthesize_note(freq: float, duration: float, sr: int, instrument: str, velocity: float) -> np.ndarray:
    n = max(1, int(round(duration * sr)))
    t = np.arange(n, dtype=np.float64) / sr
    velocity = clamp(velocity, 0.0, 1.0)

    if instrument == "none":
        return np.zeros(n, dtype=np.float64)
    if instrument == "soft_piano":
        harmonics = [(1.0, 1.0), (2.0, 0.42), (3.0, 0.20), (4.0, 0.10), (5.0, 0.04)]
        sig = sum(amp * np.sin(2.0 * np.pi * freq * mult * t) for mult, amp in harmonics)
        env = np.exp(-2.7 * t / max(duration, 1e-6)) * adsr_envelope(n, sr, 0.008, 0.12, 0.20, min(0.20, duration * 0.35))
    elif instrument == "music_box":
        partials = [(1.0, 1.00), (2.01, 0.52), (3.02, 0.28), (4.17, 0.14), (6.2, 0.05)]
        sig = sum(amp * np.sin(2.0 * np.pi * freq * mult * t) for mult, amp in partials)
        env = np.exp(-5.5 * t / max(duration, 1e-6)) * adsr_envelope(n, sr, 0.002, 0.05, 0.08, min(0.12, duration * 0.4))
    elif instrument == "bright_bell":
        partials = [(1.0, 1.00), (2.41, 0.62), (3.77, 0.38), (5.93, 0.20), (8.12, 0.08)]
        sig = sum(amp * np.sin(2.0 * np.pi * freq * mult * t) for mult, amp in partials)
        env = np.exp(-3.8 * t / max(duration, 1e-6)) * adsr_envelope(n, sr, 0.001, 0.08, 0.05, min(0.18, duration * 0.45))
    elif instrument == "celesta":
        partials = [(1.0, 1.00), (2.0, 0.34), (3.0, 0.18), (4.02, 0.12), (6.01, 0.06)]
        sig = sum(amp * np.sin(2.0 * np.pi * freq * mult * t) for mult, amp in partials)
        env = np.exp(-3.2 * t / max(duration, 1e-6)) * adsr_envelope(n, sr, 0.004, 0.09, 0.13, min(0.16, duration * 0.40))
    elif instrument == "kalimba":
        partials = [(1.0, 1.00), (2.17, 0.42), (3.41, 0.18), (5.02, 0.08)]
        sig = sum(amp * np.sin(2.0 * np.pi * freq * mult * t) for mult, amp in partials)
        env = np.exp(-4.9 * t / max(duration, 1e-6)) * adsr_envelope(n, sr, 0.003, 0.05, 0.08, min(0.12, duration * 0.35))
    elif instrument == "synth_pluck":
        sig = sum((1.0 / k) * np.sin(2.0 * np.pi * freq * k * t) for k in range(1, 10))
        env = np.exp(-6.2 * t / max(duration, 1e-6)) * adsr_envelope(n, sr, 0.002, 0.04, 0.07, min(0.10, duration * 0.30))
    elif instrument == "harp":
        sig = sum((1.0 / (k ** 1.25)) * np.sin(2.0 * np.pi * freq * k * t) for k in range(1, 8))
        env = np.exp(-4.0 * t / max(duration, 1e-6)) * adsr_envelope(n, sr, 0.004, 0.08, 0.10, min(0.18, duration * 0.35))
    elif instrument in ("warm_pad", "glass_pad"):
        vib_rate = 4.8 if instrument == "warm_pad" else 3.1
        vib_depth = 0.0025 if instrument == "warm_pad" else 0.0018
        phase = 2.0 * np.pi * freq * np.cumsum(1.0 + vib_depth * np.sin(2.0 * np.pi * vib_rate * t)) / sr
        sig = 0.75 * np.sin(phase) + 0.24 * np.sin(2.01 * phase) + 0.12 * np.sin(3.98 * phase)
        env = adsr_envelope(n, sr, min(0.65, duration * 0.45), 0.45, 0.78, min(0.75, duration * 0.50))
    elif instrument in ("cello", "bowed_string"):
        vib_depth = 0.0045 if instrument == "cello" else 0.0038
        phase = 2.0 * np.pi * freq * np.cumsum(1.0 + vib_depth * np.sin(2.0 * np.pi * 5.1 * t)) / sr
        sig = 0.75 * np.sin(phase) + 0.33 * np.sin(2.0 * phase) + 0.17 * np.sin(3.0 * phase) + 0.06 * np.sin(4.0 * phase)
        env = adsr_envelope(n, sr, 0.07, 0.18, 0.72, min(0.35, duration * 0.40))
    elif instrument == "soft_bass":
        sig = 0.92 * np.sin(2.0 * np.pi * freq * t) + 0.30 * np.sin(2.0 * np.pi * 2.0 * freq * t)
        env = adsr_envelope(n, sr, 0.015, 0.12, 0.58, min(0.25, duration * 0.35))
    elif instrument == "marimba":
        partials = [(1.0, 1.0), (3.98, 0.36), (9.1, 0.12)]
        sig = sum(amp * np.sin(2.0 * np.pi * freq * mult * t) for mult, amp in partials)
        env = np.exp(-5.0 * t / max(duration, 1e-6)) * adsr_envelope(n, sr, 0.003, 0.06, 0.10, min(0.10, duration * 0.35))
    elif instrument == "flute_like_lead":
        phase = 2.0 * np.pi * freq * np.cumsum(1.0 + 0.0035 * np.sin(2.0 * np.pi * 5.6 * t)) / sr
        sig = 0.90 * np.sin(phase) + 0.12 * np.sin(2.0 * phase) + 0.012 * np.sin(2.0 * np.pi * 11.0 * t)
        env = adsr_envelope(n, sr, 0.035, 0.10, 0.78, min(0.22, duration * 0.35))
    elif instrument == "clarinet_like_reed":
        sig = sum(amp * np.sin(2.0 * np.pi * freq * k * t) for k, amp in [(1, 1.0), (3, 0.38), (5, 0.18), (7, 0.08), (9, 0.04)])
        env = adsr_envelope(n, sr, 0.025, 0.12, 0.70, min(0.24, duration * 0.35))
    elif instrument == "texture_tick":
        rng = np.random.default_rng(int(freq * 1000) % 2**32)
        noise = rng.normal(0.0, 1.0, n)
        tone = np.sin(2.0 * np.pi * freq * t)
        sig = 0.55 * noise + 0.45 * tone
        env = np.exp(-25.0 * t) * adsr_envelope(n, sr, 0.001, 0.02, 0.02, min(0.05, duration * 0.5))
    else:
        sig = np.sin(2.0 * np.pi * freq * t)
        env = adsr_envelope(n, sr, 0.01, 0.1, 0.5, min(0.2, duration * 0.4))

    sig = sig * env
    max_abs = float(np.max(np.abs(sig))) if sig.size else 1.0
    if max_abs > 1e-12:
        sig = sig / max_abs
    return sig * velocity


def render_events(events: List[NoteEvent], duration: float, sr: int = DEFAULT_SAMPLE_RATE, layer: Optional[str] = None) -> np.ndarray:
    total_samples = int(round((duration + 0.8) * sr))
    audio = np.zeros((total_samples, 2), dtype=np.float64)
    for ev in events:
        if layer is not None and ev.layer != layer:
            continue
        if ev.duration <= 0.0 or ev.instrument == "none":
            continue
        start = int(round(ev.start * sr))
        if start >= total_samples:
            continue
        tone = synthesize_note(midi_to_freq(ev.midi), ev.duration, sr, ev.instrument, ev.velocity)
        end = min(total_samples, start + len(tone))
        tone = tone[: end - start]
        pan = clamp(ev.pan, -1.0, 1.0)
        left = math.cos((pan + 1.0) * math.pi / 4.0)
        right = math.sin((pan + 1.0) * math.pi / 4.0)
        audio[start:end, 0] += tone * left
        audio[start:end, 1] += tone * right
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 1e-12:
        audio = np.tanh(audio / max(0.5, peak * 0.85))
        audio = audio / max(float(np.max(np.abs(audio))), 1e-12) * 0.92
    return audio


def audio_to_wav_bytes(audio: np.ndarray, sr: int) -> bytes:
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(2 if pcm.ndim == 2 else 1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return buffer.getvalue()


GM_PROGRAMS = {
    "bowed_string": 48,
    "bright_bell": 14,
    "celesta": 8,
    "cello": 42,
    "clarinet_like_reed": 71,
    "flute_like_lead": 73,
    "glass_pad": 89,
    "harp": 46,
    "kalimba": 108,
    "marimba": 12,
    "music_box": 10,
    "soft_bass": 32,
    "soft_piano": 0,
    "synth_pluck": 84,
    "warm_pad": 88,
}
MIDI_CHANNELS = {
    "soft_piano": 0,
    "music_box": 1,
    "harp": 2,
    "warm_pad": 3,
    "cello": 4,
    "soft_bass": 5,
    "marimba": 6,
    "bright_bell": 7,
    "celesta": 8,
    "kalimba": 10,
    "synth_pluck": 11,
    "flute_like_lead": 12,
    "clarinet_like_reed": 13,
    "bowed_string": 14,
    "glass_pad": 15,
    "texture_tick": 9,
}
PERCUSSION_NOTES = {"texture_tick": 75}


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


def midi_bytes_from_events(events: List[NoteEvent], tempo: float) -> bytes:
    ppq = 480
    ticks_per_second = ppq * tempo / 60.0
    microseconds_per_quarter = int(round(60_000_000 / tempo))
    raw_events: List[Tuple[int, int, bytes]] = []
    raw_events.append((0, 0, b"\xFF\x51\x03" + microseconds_per_quarter.to_bytes(3, byteorder="big", signed=False)))
    used_instruments = sorted({ev.instrument for ev in events if ev.instrument != "none"})
    for inst in used_instruments:
        if inst == "texture_tick":
            continue
        channel = MIDI_CHANNELS.get(inst, 0)
        program = GM_PROGRAMS.get(inst, 0)
        raw_events.append((0, 1, bytes([0xC0 | channel, program])))
    for ev in events:
        if ev.instrument == "none":
            continue
        channel = MIDI_CHANNELS.get(ev.instrument, 0)
        midi_note = PERCUSSION_NOTES.get(ev.instrument, 75) if channel == 9 else int(clamp(ev.midi, 0, 127))
        velocity = int(clamp(ev.velocity, 0.05, 1.0) * 110)
        start_tick = int(round(ev.start * ticks_per_second))
        end_tick = int(round((ev.start + max(0.05, ev.duration)) * ticks_per_second))
        raw_events.append((start_tick, 2, bytes([0x90 | channel, midi_note, velocity])))
        raw_events.append((end_tick, 1, bytes([0x80 | channel, midi_note, 0])))
    raw_events.sort(key=lambda x: (x[0], x[1]))
    track_data = bytearray()
    last_tick = 0
    for tick, _, payload in raw_events:
        track_data.extend(write_var_len(max(0, tick - last_tick)))
        track_data.extend(payload)
        last_tick = tick
    track_data.extend(write_var_len(0))
    track_data.extend(b"\xFF\x2F\x00")
    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq)
    track = b"MTrk" + struct.pack(">I", len(track_data)) + bytes(track_data)
    return header + track


PLOT_GRID_ALPHA = 0.25


def current_plot_text_color() -> str:
    base = st.get_option("theme.base")
    return "black" if str(base).lower() == "light" else "white"


def style_transparent_figure(fig: plt.Figure, ax: plt.Axes, keep_axes: bool = True) -> str:
    text_color = current_plot_text_color()
    fig.patch.set_alpha(0.0)
    ax.set_facecolor((0.0, 0.0, 0.0, 0.0))
    ax.title.set_color(text_color)
    ax.xaxis.label.set_color(text_color)
    ax.yaxis.label.set_color(text_color)
    ax.tick_params(axis="both", colors=text_color)
    for spine in ax.spines.values():
        spine.set_color(text_color)
    if keep_axes:
        ax.grid(True, color=text_color, alpha=PLOT_GRID_ALPHA)
    return text_color


def fig_to_bytes(fig: plt.Figure, tight: bool = True) -> bytes:
    buffer = io.BytesIO()
    save_kwargs = {
        "format": "png",
        "dpi": 130,
        "transparent": True,
        "facecolor": "none",
        "edgecolor": "none",
    }
    if tight:
        save_kwargs["bbox_inches"] = "tight"
    fig.savefig(buffer, **save_kwargs)
    plt.close(fig)
    return buffer.getvalue()


def plot_map(data: np.ndarray, title: str, cmap: Optional[str] = "gray") -> bytes:
    arr = np.asarray(data)
    h, w = arr.shape[:2]
    aspect = w / max(1, h)
    fig_w = 4.8
    image_h = fig_w / max(aspect, 1e-6)
    title_h = 0.42
    fig, ax = plt.subplots(figsize=(fig_w, image_h + title_h))
    text_color = style_transparent_figure(fig, ax, keep_axes=False)
    ax.imshow(arr, cmap=cmap, aspect="equal")
    ax.set_title(title, color=text_color, fontsize=10, pad=6)
    ax.axis("off")
    fig.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=image_h / (image_h + title_h))
    return fig_to_bytes(fig, tight=False)


def _mono(audio: np.ndarray) -> np.ndarray:
    return np.mean(audio, axis=1) if audio.ndim == 2 else np.asarray(audio, dtype=np.float64)


def plot_waveform(audio: np.ndarray, sr: int, title: str = "Generated waveform") -> bytes:
    mono = _mono(audio)
    time = np.arange(len(mono)) / sr
    fig, ax = plt.subplots(figsize=(4.8, 2.6))
    text_color = style_transparent_figure(fig, ax, keep_axes=True)
    ax.plot(time, mono, linewidth=0.7)
    ax.set_xlabel("Time (s)", color=text_color)
    ax.set_ylabel("Amplitude", color=text_color)
    ax.set_title(title, color=text_color)
    return fig_to_bytes(fig)


def plot_spectrogram(audio: np.ndarray, sr: int, title: str = "Spectrogram") -> bytes:
    mono = _mono(audio)
    fig, ax = plt.subplots(figsize=(4.8, 2.9))
    text_color = style_transparent_figure(fig, ax, keep_axes=False)
    if mono.size < 2 or float(np.max(np.abs(mono))) <= 1e-12:
        ax.text(0.5, 0.5, "No visible spectral energy", ha="center", va="center", color=text_color, transform=ax.transAxes)
    else:
        nfft = min(1024, max(64, 2 ** int(np.floor(np.log2(max(64, min(mono.size, 1024)))))))
        noverlap = min(int(0.75 * nfft), nfft - 1)
        spec, freqs, bins = mlab.specgram(mono, NFFT=nfft, Fs=sr, noverlap=noverlap)
        spec_db = 10.0 * np.log10(np.maximum(spec, np.finfo(np.float64).tiny))
        ax.pcolormesh(bins, freqs, spec_db, shading="auto")
    ax.set_ylim(0, min(8000, sr // 2))
    ax.set_xlabel("Time (s)", color=text_color)
    ax.set_ylabel("Frequency (Hz)", color=text_color)
    ax.set_title(title, color=text_color)
    return fig_to_bytes(fig)


def plot_frequency_domain(audio: np.ndarray, sr: int, title: str = "Fourier magnitude") -> bytes:
    mono = _mono(audio)
    fig, ax = plt.subplots(figsize=(4.8, 2.6))
    text_color = style_transparent_figure(fig, ax, keep_axes=True)
    if mono.size < 2 or float(np.max(np.abs(mono))) <= 1e-12:
        ax.text(0.5, 0.5, "No visible spectral energy", ha="center", va="center", color=text_color, transform=ax.transAxes)
    else:
        window = np.hanning(mono.size)
        spectrum = np.fft.rfft(mono * window)
        freqs = np.fft.rfftfreq(mono.size, d=1.0 / sr)
        mag = np.abs(spectrum)
        if np.max(mag) > 1e-12:
            mag = mag / np.max(mag)
        ax.plot(freqs, mag, linewidth=0.8)
        ax.set_xlim(0, min(8000, sr // 2))
    ax.set_xlabel("Frequency (Hz)", color=text_color)
    ax.set_ylabel("Magnitude", color=text_color)
    ax.set_title(title, color=text_color)
    return fig_to_bytes(fig)


def format_percent(x: float) -> str:
    return f"{100.0 * x:.1f}%"


def instrument_label(name: str) -> str:
    labels = {
        "bowed_string": "bowed string",
        "bright_bell": "bright bell",
        "celesta": "celesta",
        "cello": "cello-like bass",
        "clarinet_like_reed": "clarinet-like reed",
        "flute_like_lead": "flute-like lead",
        "glass_pad": "glass pad",
        "harp": "harp",
        "kalimba": "kalimba",
        "marimba": "marimba",
        "music_box": "music box",
        "soft_bass": "soft bass",
        "soft_piano": "soft piano",
        "synth_pluck": "synth pluck",
        "texture_tick": "texture ticks",
        "warm_pad": "warm pad",
        "none": "—",
    }
    return labels.get(name, name)


def ensure_download_bytes(data: object) -> bytes:
    if data is None:
        return b""
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, memoryview):
        return data.tobytes()
    if isinstance(data, io.BytesIO):
        return data.getvalue()
    if isinstance(data, np.ndarray):
        return data.tobytes()
    raise TypeError(f"Unsupported download data type: {type(data).__name__}")


def audio_to_mp3_bytes(audio: np.ndarray, sr: int) -> Tuple[Optional[bytes], str]:
    clipped = np.clip(audio, -1.0, 1.0)
    if clipped.ndim == 1:
        clipped = np.column_stack([clipped, clipped])
    pcm = (clipped * 32767.0).astype(np.int16)
    try:
        import lameenc  # type: ignore
        encoder = lameenc.Encoder()
        encoder.set_bit_rate(192)
        encoder.set_in_sample_rate(int(sr))
        encoder.set_channels(2)
        encoder.set_quality(2)
        mp3_data = encoder.encode(pcm.tobytes()) + encoder.flush()
        if mp3_data:
            return bytes(mp3_data), "MP3 export generated with lameenc."
    except Exception as exc:
        lameenc_error = str(exc)
    else:
        lameenc_error = "Unknown lameenc error."
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None, f"MP3 export requires lameenc or ffmpeg. lameenc error: {lameenc_error}"
    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = os.path.join(tmpdir, "input.wav")
        mp3_path = os.path.join(tmpdir, "output.mp3")
        with open(wav_path, "wb") as f:
            f.write(audio_to_wav_bytes(audio, int(sr)))
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", wav_path, "-codec:a", "libmp3lame", "-b:a", "192k", mp3_path]
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=45)
        except Exception as exc:
            return None, f"MP3 export failed with ffmpeg: {exc}"
        if not os.path.exists(mp3_path):
            return None, "MP3 export failed because ffmpeg did not create the output file."
        with open(mp3_path, "rb") as f:
            return f.read(), "MP3 export generated with ffmpeg."


def make_parameter_signature(
    number_of_bars: int,
    complexity: float,
    variation_strength: float,
    random_factor: int,
    musicality: str,
    requested_scale: str,
    instrument_mode: str,
    manual_main_layer: str,
    manual_texture_layer: str,
    manual_bass_layer: str,
    manual_pad_layer: str,
    manual_chord_layer: str,
    manual_tempo_bpm: Optional[float],
    main_gain_db: float = 0.0,
    texture_gain_db: float = 0.0,
    bass_gain_db: float = 0.0,
    pad_gain_db: float = 0.0,
    chord_gain_db: float = 0.0,
) -> str:
    payload = {
        "number_of_bars": int(number_of_bars),
        "complexity": round(float(complexity), 4),
        "variation_strength": round(float(variation_strength), 4),
        "random_factor": int(random_factor),
        "musicality": musicality,
        "manual_tempo_bpm": round(float(manual_tempo_bpm), 4) if musicality == "Manual" and manual_tempo_bpm is not None else None,
        "requested_scale": requested_scale,
        "instrument_mode": instrument_mode,
        "manual_main_layer": manual_main_layer if instrument_mode == "Manual" else None,
        "manual_texture_layer": manual_texture_layer if instrument_mode == "Manual" else None,
        "manual_bass_layer": manual_bass_layer if instrument_mode == "Manual" else None,
        "manual_pad_layer": manual_pad_layer if instrument_mode == "Manual" else None,
        "manual_chord_layer": manual_chord_layer if instrument_mode == "Manual" else None,
        "main_gain_db": round(float(main_gain_db), 2) if instrument_mode == "Manual" else None,
        "texture_gain_db": round(float(texture_gain_db), 2) if instrument_mode == "Manual" else None,
        "bass_gain_db": round(float(bass_gain_db), 2) if instrument_mode == "Manual" else None,
        "pad_gain_db": round(float(pad_gain_db), 2) if instrument_mode == "Manual" else None,
        "chord_gain_db": round(float(chord_gain_db), 2) if instrument_mode == "Manual" else None,
        "sample_rate": DEFAULT_SAMPLE_RATE,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()



def read_markdown_document(filename: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    candidates = [
        os.path.join(base_dir, filename),
        os.path.join(os.getcwd(), filename),
        os.path.join(os.path.dirname(os.getcwd()), filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    return ""


def split_markdown_sections(markdown_text: str) -> List[Tuple[str, str]]:
    lines = markdown_text.splitlines()
    sections: List[Tuple[str, str]] = []
    current_title = "Documentation"
    current_lines: List[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_lines:
                body = "\n".join(current_lines).strip()
                if body:
                    sections.append((current_title, body))
            current_title = line[3:].strip() or "Documentation"
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append((current_title, body))

    cleaned_sections: List[Tuple[str, str]] = []
    for title, body in sections:
        normalized_title = title.lower().strip()
        if normalized_title in {"table of contents", "table des matières", "table des matieres"}:
            continue
        cleaned_sections.append((title, body))
    return cleaned_sections


def set_doc_section(state_key: str, section_index: int) -> None:
    st.session_state[state_key] = int(section_index)


def format_documentation_section(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    if lines and lines[0].startswith("## "):
        lines[0] = "# " + lines[0][3:]
    while lines and lines[0].strip() == "---":
        lines.pop(0)
    return "\n".join(lines).strip()


def render_documentation_tab(filename: str, state_key: str, missing_label: str) -> None:
    markdown_text = read_markdown_document(filename)
    if not markdown_text.strip():
        st.warning(missing_label)
        return

    sections = split_markdown_sections(markdown_text)
    if not sections:
        st.markdown(markdown_text)
        return

    if state_key not in st.session_state:
        st.session_state[state_key] = 0

    selected_index = int(st.session_state.get(state_key, 0))
    selected_index = max(0, min(selected_index, len(sections) - 1))
    st.session_state[state_key] = selected_index

    nav_col, content_col = st.columns([1.05, 2.05], gap="medium")
    with nav_col:
        for idx, (title, _) in enumerate(sections):
            st.button(
                title,
                key=f"{state_key}_{idx}",
                type="primary" if idx == selected_index else "secondary",
                width="stretch",
                on_click=set_doc_section,
                args=(state_key, idx),
            )

    selected_index = int(st.session_state.get(state_key, selected_index))
    selected_index = max(0, min(selected_index, len(sections) - 1))
    with content_col:
        st.markdown(format_documentation_section(sections[selected_index][1]))


st.set_page_config(page_title=None, page_icon=None, layout="wide")
st.markdown(
    """
    <style>
    .block-container { padding-top: 4.2rem; padding-bottom: 2.5rem; max-width: 1500px; }
    div[data-testid="stMetricValue"] { font-size: 1.12rem; }
    .small-note { color: #666; font-size: 0.92rem; }
    .column-title { font-size: 1.12rem; font-weight: 650; margin-bottom: 0.3rem; }
    div[data-testid="stExpander"] details { border-radius: 0.45rem; }
    div[data-testid="stButton"] > button { border-radius: 0.45rem; min-height: 2.35rem; white-space: normal; }
    div[data-testid="stButton"] > button[kind="primary"] { font-weight: 650; }
    </style>
    """,
    unsafe_allow_html=True,
)

app_tab, doc_fr_tab, doc_en_tab = st.tabs(["App", "Documentation FR", "Documentation EN"])
if "generation_result" not in st.session_state:
    st.session_state["generation_result"] = None
if "generation_message" not in st.session_state:
    st.session_state["generation_message"] = None
if "generation_message_type" not in st.session_state:
    st.session_state["generation_message_type"] = None
if "parameter_defaults" not in st.session_state:
    st.session_state["parameter_defaults"] = None
if "photo_analysis_cache" not in st.session_state:
    st.session_state["photo_analysis_cache"] = None

with app_tab:
    input_col, analysis_col, output_col = st.columns([1.0, 1.45, 1.05], gap="large")
    uploaded_bytes: Optional[bytes] = None
    uploaded_image: Optional[Image.Image] = None
    uploaded_hash: Optional[str] = None
    upload_error: Optional[str] = None
    input_image_name = DEFAULT_IMAGE_NAME
    input_is_default_image = False

    with input_col:
        st.markdown("<div class='column-title'>Input photo</div>", unsafe_allow_html=True)
        uploaded = st.file_uploader("Input photo", type=["png", "jpg", "jpeg", "webp", "bmp"], accept_multiple_files=False, label_visibility="collapsed")
        if uploaded is not None:
            try:
                uploaded_bytes = uploaded.getvalue()
                uploaded_hash = hashlib.sha256(uploaded_bytes).hexdigest()
                uploaded_image = Image.open(io.BytesIO(uploaded_bytes)).convert("RGB")
                input_image_name = uploaded.name
                st.image(uploaded_image, width="stretch")
            except Exception as exc:
                uploaded_image = None
                uploaded_bytes = None
                uploaded_hash = None
                upload_error = str(exc)
                st.error(f"Could not read this image: {exc}")
        else:
            try:
                uploaded_bytes = load_image_bytes_from_url(DEFAULT_IMAGE_URL)
                uploaded_hash = hashlib.sha256(uploaded_bytes).hexdigest()
                uploaded_image = Image.open(io.BytesIO(uploaded_bytes)).convert("RGB")
                input_is_default_image = True
                st.image(uploaded_image, width="stretch")
                st.caption(DEFAULT_IMAGE_CAPTION)
            except Exception as exc:
                uploaded_image = None
                uploaded_bytes = None
                uploaded_hash = None
                upload_error = str(exc)
                st.info("The default test image could not be loaded from its source URL. Please load a photo here.")

    parameter_defaults = st.session_state.get("parameter_defaults")
    controls_active = uploaded_image is not None and uploaded_hash is not None and isinstance(parameter_defaults, dict) and parameter_defaults.get("image_id") == uploaded_hash

    cached_photo_analysis = st.session_state.get("photo_analysis_cache")
    if uploaded_hash is None:
        st.session_state["photo_analysis_cache"] = None
    elif not (isinstance(cached_photo_analysis, dict) and cached_photo_analysis.get("image_id") == uploaded_hash):
        st.session_state["photo_analysis_cache"] = None

    if not controls_active:
        for widget_key in ["mapping_style", "scale_selection"]:
            if widget_key in st.session_state:
                del st.session_state[widget_key]

    if controls_active:
        bar_min = int(parameter_defaults.get("bar_min", 4))
        bar_max = int(parameter_defaults.get("bar_max", 24))
        bar_default = int(parameter_defaults.get("bar_default", 8))
        variation_default = float(parameter_defaults.get("variation_default", 0.55))
        complexity_default = float(parameter_defaults.get("complexity_default", 0.72))
    else:
        bar_min, bar_max, bar_default = 4, 24, 8
        variation_default, complexity_default = 0.55, 0.72

    with analysis_col:
        with st.expander("Audio output parameters", expanded=False):
            if not controls_active:
                st.info("Load a photo, then click Run to analyze it and activate the parameters." if uploaded_image is None else "Click Run to analyze the photo and activate the parameters.")
            slider_col_1, slider_col_2 = st.columns([1.0, 1.0], gap="large")
            with slider_col_1:
                number_of_bars = st.slider("Number of bars", int(bar_min), int(bar_max), int(bar_default), 1, disabled=not controls_active)
                variation_strength = st.slider("Variation strength", 0.0, 1.0, float(variation_default), 0.01, help="Default value is computed from image symmetry.", disabled=not controls_active)
            with slider_col_2:
                complexity = st.slider("Composition complexity", 0.10, 1.00, float(complexity_default), 0.01, help="Default value is computed from texture entropy.", disabled=not controls_active)
                random_factor = st.slider("Random factor", 0, 100, 0, 1, help="Adds controlled white perturbation to the image and Fourier-domain analysis. 0 is deterministic.", disabled=not controls_active)

            scale_col, mapping_style_col = st.columns([1.0, 1.0], gap="large")
            with scale_col:
                current_scale = st.session_state.get("scale_selection", "Automatic")
                if current_scale not in SCALE_OPTIONS:
                    current_scale = "Automatic"
                requested_scale = st.selectbox("Scale", SCALE_OPTIONS, index=SCALE_OPTIONS.index(current_scale), key="scale_selection", disabled=not controls_active)
            with mapping_style_col:
                mapping_options = ["Scientific", "Balanced", "Musical", "Manual"]
                current_mapping_style = st.session_state.get("mapping_style", "Scientific")
                if current_mapping_style not in mapping_options:
                    current_mapping_style = "Scientific"
                manual_tempo_bpm = None
                if current_mapping_style == "Manual":
                    mapping_col, bpm_col = st.columns([1.0, 1.0], gap="medium")
                    with mapping_col:
                        musicality = st.selectbox("Mapping style (BPM)", mapping_options, index=mapping_options.index(current_mapping_style), key="mapping_style", disabled=not controls_active)
                    with bpm_col:
                        manual_tempo_bpm = st.number_input("Manual BPM", min_value=1.0, value=90.0, step=1.0, format="%.1f", disabled=not controls_active)
                else:
                    musicality = st.selectbox("Mapping style (BPM)", mapping_options, index=mapping_options.index(current_mapping_style), key="mapping_style", disabled=not controls_active)

            instrument_mode = st.radio("Instrument layer selection", ["Automatic", "Manual"], index=0, horizontal=True, disabled=not controls_active)
            if controls_active and isinstance(parameter_defaults, dict):
                _def_main = parameter_defaults.get("auto_main_display", "Soft piano")
                _def_texture = parameter_defaults.get("auto_texture_display", "Harp")
                _def_bass = parameter_defaults.get("auto_bass_display", "Cello-like bass")
                _def_pad = parameter_defaults.get("auto_pad_display", "Warm pad")
                _def_chord = parameter_defaults.get("auto_chord_display", "Soft piano")
            else:
                _def_main, _def_texture, _def_bass, _def_pad, _def_chord = "Soft piano", "Harp", "Cello-like bass", "Warm pad", "Soft piano"

            def _safe_idx(choices: List[str], val: str, fallback: str) -> int:
                return choices.index(val) if val in choices else choices.index(fallback) if fallback in choices else 0

            manual_main_layer = _def_main
            manual_texture_layer = _def_texture
            manual_bass_layer = _def_bass
            manual_pad_layer = _def_pad
            manual_chord_layer = _def_chord
            main_gain_db = 0.0
            texture_gain_db = -2.0
            bass_gain_db = 0.0
            pad_gain_db = -8.0
            chord_gain_db = -3.0
            if instrument_mode == "Manual":
                row1_c1, row1_c2, row1_c3 = st.columns(3, gap="medium")
                with row1_c1:
                    manual_main_layer = st.selectbox("Main layer", INSTRUMENT_CHOICES_WITH_NONE, index=_safe_idx(INSTRUMENT_CHOICES_WITH_NONE, _def_main, "Soft piano"), disabled=not controls_active)
                    main_gain_db = st.slider("Main gain (dB)", -24.0, 12.0, 0.0, 0.5, disabled=not controls_active)
                with row1_c2:
                    manual_texture_layer = st.selectbox("Texture layer", INSTRUMENT_CHOICES_WITH_NONE, index=_safe_idx(INSTRUMENT_CHOICES_WITH_NONE, _def_texture, "Harp"), disabled=not controls_active)
                    texture_gain_db = st.slider("Texture gain (dB)", -24.0, 12.0, -2.0, 0.5, disabled=not controls_active)
                with row1_c3:
                    manual_bass_layer = st.selectbox("Bass layer", INSTRUMENT_CHOICES_WITH_NONE, index=_safe_idx(INSTRUMENT_CHOICES_WITH_NONE, _def_bass, "Cello-like bass"), disabled=not controls_active)
                    bass_gain_db = st.slider("Bass gain (dB)", -24.0, 12.0, 0.0, 0.5, disabled=not controls_active)
                row2_c1, row2_c2, _ = st.columns([1, 1, 1], gap="medium")
                with row2_c1:
                    manual_pad_layer = st.selectbox("Pad layer", INSTRUMENT_CHOICES_WITH_NONE, index=_safe_idx(INSTRUMENT_CHOICES_WITH_NONE, _def_pad, "Warm pad"), disabled=not controls_active)
                    pad_gain_db = st.slider("Pad gain (dB)", -24.0, 12.0, -8.0, 0.5, disabled=not controls_active)
                with row2_c2:
                    manual_chord_layer = st.selectbox("Chord layer", INSTRUMENT_CHOICES_WITH_NONE, index=_safe_idx(INSTRUMENT_CHOICES_WITH_NONE, _def_chord, "Soft piano"), disabled=not controls_active)
                    chord_gain_db = st.slider("Chord gain (dB)", -24.0, 12.0, -3.0, 0.5, disabled=not controls_active)

        run_clicked = st.button("Run", type="primary", width="stretch")

    current_parameter_signature = make_parameter_signature(number_of_bars, complexity, variation_strength, random_factor, musicality, requested_scale, instrument_mode, manual_main_layer, manual_texture_layer, manual_bass_layer, manual_pad_layer, manual_chord_layer, manual_tempo_bpm, main_gain_db, texture_gain_db, bass_gain_db, pad_gain_db, chord_gain_db)
    should_rerun_to_activate_controls = False

    if run_clicked:
        st.session_state["generation_message"] = None
        st.session_state["generation_message_type"] = None
        if uploaded_image is None or uploaded_bytes is None or uploaded_hash is None:
            st.session_state["generation_result"] = None
            st.session_state["generation_message"] = f"Could not generate the composition because the input image could not be loaded: {upload_error}" if upload_error else "Please choose an input photo before running the sonification."
            st.session_state["generation_message_type"] = "error" if upload_error else "warning"
        else:
            try:
                with st.spinner("Generating the composition from the photo..."):
                    if not controls_active:
                        should_rerun_to_activate_controls = True
                        default_analysis = analyze_image(uploaded_image, random_factor=0.0, rng=np.random.default_rng(0))
                        st.session_state["photo_analysis_cache"] = {
                            "image_id": uploaded_hash,
                            "analysis": default_analysis,
                        }
                        default_features: Dict[str, float] = default_analysis["features"]  # type: ignore[assignment]
                        auto_bar_min, auto_bar_max, auto_bar_default = compute_bar_settings(default_features)
                        auto_variation = float(default_features.get("auto_variation_strength", 0.55))
                        auto_complexity = float(default_features.get("auto_complexity", 0.72))
                        ai_main, ai_tex, ai_bass, ai_pad, ai_chord = choose_instruments(default_features, "Automatic")
                        st.session_state["parameter_defaults"] = {
                            "image_id": uploaded_hash,
                            "bar_min": int(auto_bar_min),
                            "bar_max": int(auto_bar_max),
                            "bar_default": int(auto_bar_default),
                            "variation_default": float(auto_variation),
                            "complexity_default": float(auto_complexity),
                            "auto_main_display": INSTRUMENT_INTERNAL_TO_DISPLAY.get(ai_main, "Soft piano"),
                            "auto_texture_display": INSTRUMENT_INTERNAL_TO_DISPLAY.get(ai_tex, "Harp"),
                            "auto_bass_display": INSTRUMENT_INTERNAL_TO_DISPLAY.get(ai_bass, "Cello-like bass"),
                            "auto_pad_display": INSTRUMENT_INTERNAL_TO_DISPLAY.get(ai_pad, "Warm pad"),
                            "auto_chord_display": INSTRUMENT_INTERNAL_TO_DISPLAY.get(ai_chord, "Soft piano"),
                        }
                        effective_number_of_bars = int(auto_bar_default)
                        effective_variation_strength = float(auto_variation)
                        effective_complexity = float(auto_complexity)
                        effective_random_factor = 0
                        effective_requested_scale = "Automatic"
                        effective_instrument_mode = "Automatic"
                        effective_manual_main_layer = "Soft piano"
                        effective_manual_texture_layer = "Harp"
                        effective_manual_bass_layer = "Cello-like bass"
                        effective_manual_pad_layer = "Warm pad"
                        effective_manual_chord_layer = "Soft piano"
                        effective_musicality = "Scientific"
                        effective_manual_tempo_bpm = None
                        effective_main_gain_db = 0.0
                        effective_texture_gain_db = 0.0
                        effective_bass_gain_db = 0.0
                        effective_pad_gain_db = 0.0
                        effective_chord_gain_db = 0.0
                        original_analysis = default_analysis
                        analysis = default_analysis
                    else:
                        effective_number_of_bars = int(number_of_bars)
                        effective_variation_strength = float(variation_strength)
                        effective_complexity = float(complexity)
                        effective_random_factor = int(random_factor)
                        effective_requested_scale = requested_scale
                        effective_instrument_mode = instrument_mode
                        effective_manual_main_layer = manual_main_layer
                        effective_manual_texture_layer = manual_texture_layer
                        effective_manual_bass_layer = manual_bass_layer
                        effective_manual_pad_layer = manual_pad_layer
                        effective_manual_chord_layer = manual_chord_layer
                        effective_musicality = musicality
                        effective_manual_tempo_bpm = manual_tempo_bpm
                        if effective_instrument_mode == "Manual":
                            effective_main_gain_db = float(main_gain_db)
                            effective_texture_gain_db = float(texture_gain_db)
                            effective_bass_gain_db = float(bass_gain_db)
                            effective_pad_gain_db = float(pad_gain_db)
                            effective_chord_gain_db = float(chord_gain_db)
                        else:
                            effective_main_gain_db = 0.0
                            effective_texture_gain_db = 0.0
                            effective_bass_gain_db = 0.0
                            effective_pad_gain_db = 0.0
                            effective_chord_gain_db = 0.0
                        cached_photo_analysis = st.session_state.get("photo_analysis_cache")
                        if isinstance(cached_photo_analysis, dict) and cached_photo_analysis.get("image_id") == uploaded_hash:
                            original_analysis = cached_photo_analysis["analysis"]
                        else:
                            original_analysis = analyze_image(uploaded_image, random_factor=0.0, rng=np.random.default_rng(0))
                            st.session_state["photo_analysis_cache"] = {
                                "image_id": uploaded_hash,
                                "analysis": original_analysis,
                            }
                        analysis = analyze_image(uploaded_image, random_factor=float(effective_random_factor), rng=np.random.default_rng())

                    current_parameter_signature = make_parameter_signature(effective_number_of_bars, effective_complexity, effective_variation_strength, effective_random_factor, effective_musicality, effective_requested_scale, effective_instrument_mode, effective_manual_main_layer, effective_manual_texture_layer, effective_manual_bass_layer, effective_manual_pad_layer, effective_manual_chord_layer, effective_manual_tempo_bpm, effective_main_gain_db, effective_texture_gain_db, effective_bass_gain_db, effective_pad_gain_db, effective_chord_gain_db)
                    original_features: Dict[str, float] = original_analysis["features"]  # type: ignore[assignment]
                    original_maps: Dict[str, np.ndarray] = original_analysis["maps"]  # type: ignore[assignment]
                    features: Dict[str, float] = analysis["features"]  # type: ignore[assignment]
                    maps: Dict[str, np.ndarray] = analysis["maps"]  # type: ignore[assignment]
                    events, info = generate_composition(analysis, effective_number_of_bars, effective_complexity, effective_variation_strength, effective_requested_scale, effective_instrument_mode, effective_manual_main_layer, effective_manual_texture_layer, effective_manual_bass_layer, effective_manual_pad_layer, effective_manual_chord_layer, effective_musicality, effective_manual_tempo_bpm, effective_main_gain_db, effective_texture_gain_db, effective_bass_gain_db, effective_pad_gain_db, effective_chord_gain_db)
                    audio = render_events(events, info.duration, DEFAULT_SAMPLE_RATE)
                    wav_bytes = audio_to_wav_bytes(audio, DEFAULT_SAMPLE_RATE)
                    midi_bytes = midi_bytes_from_events(events, info.tempo)
                    mp3_bytes, mp3_message = audio_to_mp3_bytes(audio, DEFAULT_SAMPLE_RATE)
                st.session_state["generation_result"] = {
                    "image_id": uploaded_hash,
                    "image_name": input_image_name,
                    "image_is_default": bool(input_is_default_image),
                    "image_source_page": DEFAULT_IMAGE_SOURCE_PAGE if input_is_default_image else None,
                    "image_bytes": uploaded_bytes,
                    "parameter_signature": current_parameter_signature,
                    "analysis": analysis,
                    "features": features,
                    "maps": maps,
                    "display_analysis": original_analysis,
                    "display_features": original_features,
                    "display_maps": original_maps,
                    "events": events,
                    "info": info,
                    "audio": audio,
                    "wav_bytes": wav_bytes,
                    "mp3_bytes": mp3_bytes,
                    "mp3_message": mp3_message,
                    "midi_bytes": midi_bytes,
                    "sample_rate": DEFAULT_SAMPLE_RATE,
                    "parameters": {
                        "number_of_bars": int(effective_number_of_bars),
                        "complexity": float(effective_complexity),
                        "variation_strength": float(effective_variation_strength),
                        "random_factor": int(effective_random_factor),
                        "mapping_style": effective_musicality,
                        "manual_tempo_bpm": float(effective_manual_tempo_bpm) if effective_musicality == "Manual" and effective_manual_tempo_bpm is not None else None,
                        "scale": effective_requested_scale,
                        "instrument_mode": effective_instrument_mode,
                        "main_gain_db": float(effective_main_gain_db),
                        "texture_gain_db": float(effective_texture_gain_db),
                        "bass_gain_db": float(effective_bass_gain_db),
                        "pad_gain_db": float(effective_pad_gain_db),
                        "chord_gain_db": float(effective_chord_gain_db),
                        "sample_rate": DEFAULT_SAMPLE_RATE,
                    },
                }
                st.session_state["generation_message"] = "Composition generated."
                st.session_state["generation_message_type"] = "success"
            except Exception as exc:
                st.session_state["generation_result"] = None
                st.session_state["generation_message"] = f"Could not generate the composition: {exc}"
                st.session_state["generation_message_type"] = "error"

    if should_rerun_to_activate_controls and st.session_state.get("generation_message_type") == "success":
        st.rerun()

    message = st.session_state.get("generation_message")
    message_type = st.session_state.get("generation_message_type")
    if message:
        if message_type == "success":
            st.success(message)
        elif message_type == "warning":
            st.warning(message)
        elif message_type == "error":
            st.error(message)
        else:
            st.info(message)

    result = st.session_state.get("generation_result")
    if not (uploaded_hash is not None and isinstance(result, dict) and result.get("image_id") == uploaded_hash):
        result = None

    with analysis_col:
        with st.expander("Photo analysis", expanded=False):
            if result is None:
                st.info("Run the app once to display the photo-derived maps and analysis metrics.")
            else:
                maps = result.get("display_maps", result["maps"])
                features = result.get("display_features", result["features"])
                st.image(plot_map(maps["luminance"], "Luminance map"), width="stretch")
                st.image(plot_map(maps["edge_map"], "Edge strength map"), width="stretch")
                st.image(plot_map(maps["fft_log_magnitude"], "2D Fourier log-magnitude"), width="stretch")
                st.image(plot_map(maps["shadow_highlight_map"], "Highlights in red, shadows in blue", cmap=None), width="stretch")
                st.markdown("##### Photo analysis")
                a1, a2, a3 = st.columns(3)
                a1.metric("Brightness", f"{features['mean_brightness']:.3f}")
                a2.metric("Contrast", f"{features['contrast']:.3f}")
                a3.metric("Saturation", f"{features['mean_saturation']:.3f}")
                a4, a5, a6 = st.columns(3)
                a4.metric("Shadows", format_percent(features["shadow_proportion"]))
                a5.metric("Highlights", format_percent(features["highlight_proportion"]))
                a6.metric("Edge density", format_percent(features["edge_density"]))
                e1, e2, e3 = st.columns(3)
                e1.metric("Texture entropy", f"{features['texture_entropy']:.3f}")
                e2.metric("Symmetry", f"{features['symmetry_score']:.3f}")
                e3.metric("Auto variation", f"{features['auto_variation_strength']:.3f}")
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("Fourier low", format_percent(features["low_frequency_energy"]))
                f2.metric("Fourier mid", format_percent(features["mid_frequency_energy"]))
                f3.metric("Fourier high", format_percent(features["high_frequency_energy"]))
                f4.metric("Peak score", f"{features['periodic_peak_score']:.3f}")

    with output_col:
        st.markdown("<div class='column-title'>Output audio</div>", unsafe_allow_html=True)
        if result is None:
            st.info("No generated audio yet.")
            st.download_button("Download MP3 file", data=b"", file_name="photo_sonification.mp3", mime="audio/mpeg", disabled=True, width="stretch")
            st.download_button("Download MIDI file", data=b"", file_name="photo_sonification_score.mid", mime="audio/midi", disabled=True, width="stretch")
            with st.expander("Audio analysis", expanded=False):
                st.info("Run the app once to display the audio plots.")
        else:
            info: CompositionInfo = result["info"]
            wav_bytes: bytes = result["wav_bytes"]
            mp3_bytes: Optional[bytes] = result["mp3_bytes"]
            midi_bytes: bytes = result["midi_bytes"]
            st.audio(wav_bytes, format="audio/wav")
            c1, c2 = st.columns(2)
            c1.metric("Tempo", f"{info.tempo:.1f} BPM")
            c2.metric("Bars / length", f"{info.bars} bars / {info.duration:.1f} s")
            st.metric("Key / scale", f"{info.key_name} / {info.scale_name}")
            st.write(
                f"Mood: {info.mood} | "
                f"Main: {instrument_label(info.main_instrument)} | "
                f"Texture: {instrument_label(info.texture_instrument)} | "
                f"Bass: {instrument_label(info.bass_instrument)} | "
                f"Pad: {instrument_label(info.pad_instrument)} | "
                f"Chord: {instrument_label(info.chord_instrument)}"
            )
            if result.get("parameter_signature") != current_parameter_signature:
                st.warning("Some parameters changed after the last generation. Click Run to update the output.")
            st.download_button("Download MP3 file", data=ensure_download_bytes(mp3_bytes), file_name="photo_sonification.mp3", mime="audio/mpeg", disabled=mp3_bytes is None, width="stretch")
            st.download_button("Download MIDI file", data=ensure_download_bytes(midi_bytes), file_name="photo_sonification_score.mid", mime="audio/midi", width="stretch")
            with st.expander("Audio analysis", expanded=False):
                audio: np.ndarray = result["audio"]
                events: List[NoteEvent] = result["events"]
                result_sr = int(result["sample_rate"])
                layer_audio = {
                    "Main layer Fourier": render_events(events, info.duration, result_sr, layer="main"),
                    "Texture layer Fourier": render_events(events, info.duration, result_sr, layer="texture"),
                    "Bass layer Fourier": render_events(events, info.duration, result_sr, layer="bass"),
                    "Pad layer Fourier": render_events(events, info.duration, result_sr, layer="pad"),
                    "Chord layer Fourier": render_events(events, info.duration, result_sr, layer="chord"),
                }
                audio_plots = [
                    ("Full Fourier magnitude", plot_frequency_domain(audio, result_sr, "Full Fourier magnitude")),
                    ("Waveform", plot_waveform(audio, result_sr, "Waveform")),
                    ("Main layer Fourier", plot_frequency_domain(layer_audio["Main layer Fourier"], result_sr, "Main layer Fourier")),
                    ("Texture layer Fourier", plot_frequency_domain(layer_audio["Texture layer Fourier"], result_sr, "Texture layer Fourier")),
                    ("Bass layer Fourier", plot_frequency_domain(layer_audio["Bass layer Fourier"], result_sr, "Bass layer Fourier")),
                    ("Pad layer Fourier", plot_frequency_domain(layer_audio["Pad layer Fourier"], result_sr, "Pad layer Fourier")),
                    ("Chord layer Fourier", plot_frequency_domain(layer_audio["Chord layer Fourier"], result_sr, "Chord layer Fourier")),
                ]
                for _, plot_bytes in audio_plots:
                    st.image(plot_bytes, width="stretch")
            if mp3_bytes is None:
                st.caption(result.get("mp3_message", "MP3 export is unavailable on this environment."))

with doc_fr_tab:
    render_documentation_tab(
        "documentation_fr.md",
        "documentation_fr_section",
        "Le fichier `documentation_fr.md` est introuvable à côté de `app_sl.py`.",
    )

with doc_en_tab:
    render_documentation_tab(
        "documentation_en.md",
        "documentation_en_section",
        "The file `documentation_en.md` could not be found next to `app_sl.py`.",
    )
