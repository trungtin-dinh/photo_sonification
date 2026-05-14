from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from config import (
    DEFAULT_SAMPLE_RATE,
    MASTER_TARGET_PEAK,
    MASTER_TARGET_RMS,
    SCALE_OPTIONS,
    SYNTH_GENERALUSER_GS,
    SYNTH_SIMPLE,
)
from utils import CompositionInfo, NoteEvent, clamp, get_float_param
from image_analysis import analyze_image
from composition import compute_bar_settings, generate_composition
from audio import (
    audio_to_mp3_bytes,
    audio_to_wav_bytes,
    midi_bytes_from_events,
    normalize_master_audio,
    render_backend,
)

ProgressCallback = Optional[Callable[[str, int], None]]
StepCallback = Optional[Callable[[str], None]]


def _seed_from_text(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def _as_stereo(audio: np.ndarray) -> np.ndarray:
    arr = np.asarray(audio, dtype=np.float64)
    if arr.ndim == 1:
        arr = np.column_stack([arr, arr])
    if arr.ndim == 2 and arr.shape[1] == 1:
        arr = np.repeat(arr, 2, axis=1)
    if arr.ndim != 2 or arr.shape[1] < 2:
        return np.zeros((0, 2), dtype=np.float64)
    return arr[:, :2]


def _apply_edge_fade(
    audio: np.ndarray,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    fade_seconds: float = 0.020,
) -> np.ndarray:
    """Apply a tiny fade-in/fade-out to remove clicks at segment borders."""
    arr = _as_stereo(audio).copy()
    if len(arr) <= 2:
        return arr

    n = int(max(0.0, float(fade_seconds)) * sample_rate)
    n = min(n, max(1, len(arr) // 2))
    if n <= 1:
        return arr

    fade_in = np.linspace(0.0, 1.0, n, endpoint=True)[:, None]
    fade_out = np.linspace(1.0, 0.0, n, endpoint=True)[:, None]
    arr[:n] *= fade_in
    arr[-n:] *= fade_out
    return arr


def concatenate_audio_segments(
    segments: Sequence[np.ndarray],
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    crossfade_seconds: float = 0.60,
) -> np.ndarray:
    """
    Concatenate stereo audio segments with an equal-power crossfade.

    A plain np.concatenate creates audible cuts because the waveform may jump
    abruptly from the end of one photo segment to the beginning of the next.
    The short edge fade removes clicks, and the equal-power overlap makes the
    transition more musical than a linear fade.
    """
    cleaned = [
        _apply_edge_fade(seg, sample_rate=sample_rate, fade_seconds=0.020)
        for seg in segments
        if np.asarray(seg).size > 0
    ]
    if not cleaned:
        return np.zeros((0, 2), dtype=np.float64)

    out = cleaned[0]
    fade_samples_requested = int(max(0.0, float(crossfade_seconds)) * sample_rate)

    for seg in cleaned[1:]:
        fade_samples = min(fade_samples_requested, len(out), len(seg))
        if fade_samples <= 1:
            out = np.vstack([out, seg])
            continue

        theta = np.linspace(0.0, np.pi / 2.0, fade_samples, endpoint=True)[:, None]
        fade_out = np.cos(theta)
        fade_in = np.sin(theta)
        overlap = out[-fade_samples:] * fade_out + seg[:fade_samples] * fade_in
        out = np.vstack([out[:-fade_samples], overlap, seg[fade_samples:]])

    return out

def shift_events(events: Iterable[NoteEvent], offset_seconds: float) -> List[NoteEvent]:
    """Shift note events in absolute time for a global long MIDI export."""
    offset = float(max(0.0, offset_seconds))
    return [replace(ev, start=float(ev.start) + offset) for ev in events]


def default_batch_options() -> Dict[str, object]:
    return {
        "auto_bars": True,
        "bars": 8,
        "complexity": None,
        "variation": None,
        "random_factor": 0,
        "scale": "Automatic" if "Automatic" in SCALE_OPTIONS else SCALE_OPTIONS[0],
        "synth": SYNTH_SIMPLE,
        "instrument_mode": "Automatic",
        "main": "Soft piano",
        "texture": "Harp",
        "bass": "Cello-like bass",
        "pad": "Warm pad",
        "chord": "Soft piano",
        "solo": "Flute",
        "mapping": "Scientific",
        "bpm": None,
        "gains": [0.0, -2.0, 0.0, -8.0, -3.0, -1.0],
        "crossfade_seconds": 0.60,
        "advanced_params": {},
    }


def _progress(progress_callback: ProgressCallback, label: str, percent: int) -> None:
    if progress_callback is not None:
        progress_callback(label, int(clamp(percent, 0, 100)))


def _segment_stepper(progress_callback: ProgressCallback, prefix: str, base: int, top: int) -> StepCallback:
    state = {"i": 0}

    def _callback(label: str) -> None:
        state["i"] += 1
        span = max(1, top - base)
        pct = min(top, base + int(round(span * state["i"] / 10)))
        _progress(progress_callback, f"{prefix}: {label}", pct)

    return _callback


def generate_photo_segment(
    image: Image.Image,
    image_name: str,
    image_id: str,
    index: int,
    total: int,
    options: Optional[Dict[str, object]] = None,
    progress_callback: ProgressCallback = None,
) -> Dict[str, object]:
    """Generate one complete sonification segment from one PIL image."""
    opts = default_batch_options()
    if options:
        opts.update(options)

    advanced_params = opts.get("advanced_params") if isinstance(opts.get("advanced_params"), dict) else {}
    random_factor = int(opts.get("random_factor", 0) or 0)

    segment_base = int(round(100 * index / max(1, total)))
    segment_top = int(round(100 * (index + 1) / max(1, total)))
    prefix = f"Image {index + 1}/{total}"

    _progress(progress_callback, f"{prefix}: analysing photo", segment_base)
    original_analysis = analyze_image(
        image,
        0.0,
        np.random.default_rng(0),
        params=advanced_params,
        step_callback=_segment_stepper(progress_callback, prefix, segment_base, segment_base + 15),
    )

    if random_factor > 0:
        seed = _seed_from_text(f"{image_id}:{image_name}:{index}:{random_factor}")
        analysis = analyze_image(
            image,
            float(random_factor),
            np.random.default_rng(seed),
            params=advanced_params,
            step_callback=_segment_stepper(progress_callback, prefix, segment_base + 15, segment_base + 25),
        )
    else:
        analysis = original_analysis

    features = original_analysis["features"]
    if bool(opts.get("auto_bars", True)):
        _, _, bars = compute_bar_settings(features, params=advanced_params)
    else:
        bars = int(opts.get("bars", 8) or 8)

    complexity = opts.get("complexity")
    if complexity is None:
        complexity = float(features.get("auto_complexity", 0.72))
    variation = opts.get("variation")
    if variation is None:
        variation = float(
            features.get(
                "auto_variation_strength",
                clamp(0.25 + 0.60 * (1.0 - float(features.get("symmetry_score", 0.5))), 0.25, 0.85),
            )
        )

    gains = list(opts.get("gains", [0.0, -2.0, 0.0, -8.0, -3.0, -1.0]))
    while len(gains) < 6:
        gains.append(0.0)

    _progress(progress_callback, f"{prefix}: generating musical events", segment_base + 30)
    events, info = generate_composition(
        analysis,
        int(bars),
        float(complexity),
        float(variation),
        str(opts.get("scale", "Automatic")),
        str(opts.get("synth", SYNTH_SIMPLE)),
        str(opts.get("instrument_mode", "Automatic")),
        str(opts.get("main", "Soft piano")),
        str(opts.get("texture", "Harp")),
        str(opts.get("bass", "Cello-like bass")),
        str(opts.get("pad", "Warm pad")),
        str(opts.get("chord", "Soft piano")),
        str(opts.get("solo", "Flute")),
        str(opts.get("mapping", "Scientific")),
        opts.get("bpm", None),
        float(gains[0]),
        float(gains[1]),
        float(gains[2]),
        float(gains[3]),
        float(gains[4]),
        float(gains[5]),
        params=advanced_params,
        step_callback=_segment_stepper(progress_callback, prefix, segment_base + 30, segment_base + 55),
    )

    _progress(progress_callback, f"{prefix}: rendering audio", segment_base + 60)
    audio_arr, synth_message = render_backend(events, info, str(opts.get("synth", SYNTH_SIMPLE)), params=advanced_params)
    audio_arr = normalize_master_audio(
        audio_arr,
        target_peak=get_float_param(advanced_params, "master_target_peak", MASTER_TARGET_PEAK, 0.10, 0.98),
        target_rms=get_float_param(advanced_params, "master_target_rms", MASTER_TARGET_RMS, 0.01, 0.50),
    )

    return {
        "image_id": image_id,
        "image_name": image_name,
        "analysis": analysis,
        "display_analysis": original_analysis,
        "features": analysis["features"],
        "maps": analysis["maps"],
        "events": events,
        "info": info,
        "audio": audio_arr,
        "synth_message": synth_message,
        "parameters": {
            "bars": int(bars),
            "complexity": float(complexity),
            "variation": float(variation),
            "random_factor": random_factor,
        },
    }


def generate_batch_composition(
    image_items: Sequence[Dict[str, object]],
    options: Optional[Dict[str, object]] = None,
    progress_callback: ProgressCallback = None,
) -> Dict[str, object]:
    """
    Generate one long sonification from multiple images.

    image_items must contain dictionaries with:
      - image: PIL.Image.Image
      - name: str
      - image_id: str
    """
    items = list(image_items)
    if not items:
        raise ValueError("No image was provided.")

    opts = default_batch_options()
    if options:
        opts.update(options)

    segments: List[Dict[str, object]] = []
    audio_segments: List[np.ndarray] = []
    shifted_events: List[NoteEvent] = []
    offsets: List[float] = []

    running_samples = 0
    sr = DEFAULT_SAMPLE_RATE
    crossfade_seconds = float(opts.get("crossfade_seconds", 0.60) or 0.0)
    crossfade_samples = int(max(0.0, crossfade_seconds) * sr)

    for idx, item in enumerate(items):
        image = item.get("image")
        if not isinstance(image, Image.Image):
            raise TypeError(f"Invalid image at index {idx}.")
        name = str(item.get("name", f"image_{idx + 1}.png"))
        image_id = str(item.get("image_id", _seed_from_text(name)))

        segment = generate_photo_segment(
            image=image,
            image_name=name,
            image_id=image_id,
            index=idx,
            total=len(items),
            options=opts,
            progress_callback=progress_callback,
        )
        audio_arr = _as_stereo(segment["audio"])  # type: ignore[arg-type]

        offset_seconds = max(0.0, running_samples / sr)
        offsets.append(offset_seconds)
        shifted_events.extend(shift_events(segment["events"], offset_seconds))  # type: ignore[arg-type]
        segments.append(segment)
        audio_segments.append(audio_arr)

        if idx == 0:
            running_samples = len(audio_arr)
        else:
            running_samples += max(0, len(audio_arr) - min(crossfade_samples, running_samples, len(audio_arr)))

    _progress(progress_callback, "Concatenating audio segments", 96)
    long_audio = concatenate_audio_segments(audio_segments, sample_rate=sr, crossfade_seconds=crossfade_seconds)
    long_audio = normalize_master_audio(
        long_audio,
        target_peak=get_float_param(opts.get("advanced_params"), "master_target_peak", MASTER_TARGET_PEAK, 0.10, 0.98),
        target_rms=get_float_param(opts.get("advanced_params"), "master_target_rms", MASTER_TARGET_RMS, 0.01, 0.50),
    )

    duration = float(len(long_audio) / sr) if len(long_audio) else 0.0
    first_info: CompositionInfo = segments[0]["info"]  # type: ignore[assignment]
    avg_tempo = float(np.mean([float(seg["info"].tempo) for seg in segments]))  # type: ignore[index]
    total_bars = int(sum(int(seg["info"].bars) for seg in segments))  # type: ignore[index]

    info = CompositionInfo(
        tempo=avg_tempo,
        bars=total_bars,
        duration=duration,
        key_name="Multiple",
        scale_name="Multiple",
        main_instrument=first_info.main_instrument,
        texture_instrument=first_info.texture_instrument,
        bass_instrument=first_info.bass_instrument,
        pad_instrument=first_info.pad_instrument,
        chord_instrument=first_info.chord_instrument,
        solo_instrument=first_info.solo_instrument,
        mood=f"Batch sequence: {len(segments)} images",
        mapping_summary={
            "images": str(len(segments)),
            "crossfade_seconds": f"{crossfade_seconds:.3f}",
            "duration_seconds": f"{duration:.3f}",
        },
    )

    _progress(progress_callback, "Encoding WAV, MP3 and MIDI", 98)
    wav_bytes = audio_to_wav_bytes(long_audio, sr)
    midi_bytes = midi_bytes_from_events(shifted_events, avg_tempo if avg_tempo > 0 else 120.0)
    mp3_bytes, mp3_message = audio_to_mp3_bytes(long_audio, sr)

    _progress(progress_callback, "Done", 100)
    return {
        "segments": segments,
        "offsets": offsets,
        "events": shifted_events,
        "info": info,
        "audio": long_audio,
        "wav_bytes": wav_bytes,
        "mp3_bytes": mp3_bytes,
        "mp3_message": mp3_message,
        "midi_bytes": midi_bytes,
        "sample_rate": sr,
        "parameters": opts,
    }
