from __future__ import annotations

import io
import math
import os
import shutil
import struct
import subprocess
import tempfile
import wave
from typing import List, Optional, Tuple

import numpy as np

from config import (
    DEFAULT_SAMPLE_RATE,
    FLUIDSYNTH_MASTER_GAIN,
    GM_PROGRAMS,
    LAYER_CHANNELS,
    MASTER_TARGET_PEAK,
    MASTER_TARGET_RMS,
    PERCUSSION_NOTES,
    SOUNDFONT_CANDIDATES,
    SYNTH_GENERALUSER_GS,
)
from utils import NoteEvent, CompositionInfo, clamp, get_float_param, midi_to_freq


# ============================================================
# SoundFont discovery
# ============================================================

def find_generaluser_soundfont() -> Optional[str]:
    for p in SOUNDFONT_CANDIDATES:
        if p and os.path.exists(p):
            return p
    return None


# ============================================================
# Simple additive synthesizer
# ============================================================

def adsr_envelope(
    n: int, sr: int, attack: float, decay: float, sustain: float, release: float
) -> np.ndarray:
    env = np.ones(max(1, n), dtype=np.float64) * sustain
    a = int(max(1, attack * sr))
    d = int(max(1, decay * sr))
    r = int(max(1, release * sr))
    env[:min(n, a)] = np.linspace(0, 1, min(n, a), endpoint=False)
    if min(n, a + d) > min(n, a):
        env[min(n, a):min(n, a + d)] = np.linspace(1, sustain, min(n, a + d) - min(n, a), endpoint=False)
    rs = max(0, n - r)
    env[rs:] *= np.linspace(1, 0, n - rs)
    return env


def gm_to_simple(instrument: str) -> str:
    """Map a General MIDI program identifier to the nearest Simple synthesizer voice."""
    if not instrument.startswith("gm_"):
        return instrument
    try:
        p = int(instrument.split("_", 1)[1])
    except Exception:
        return "soft_piano"
    if p in {8, 9, 10, 11, 14, 98, 112}:  return "bright_bell"
    if p in {12, 13, 108}:                 return "marimba"
    if p in {46, 104, 105, 106, 107}:      return "harp"
    if 32 <= p <= 39:                      return "soft_bass"
    if 40 <= p <= 51:                      return "bowed_string"
    if 64 <= p <= 79:                      return "flute_like_lead"
    if 80 <= p <= 87:                      return "synth_pluck"
    if 88 <= p <= 103:                     return "warm_pad"
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


# ============================================================
# Master-bus normalisation
# ============================================================

def normalize_master_audio(
    audio: np.ndarray,
    target_peak: float = MASTER_TARGET_PEAK,
    target_rms: float = MASTER_TARGET_RMS,
) -> np.ndarray:
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


# ============================================================
# Event renderer (Simple synthesizer backend)
# ============================================================

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
        end  = min(total, start + len(tone))
        tone = tone[:end - start]
        pan  = clamp(ev.pan, -1, 1)
        audio[start:end, 0] += tone * math.cos((pan + 1) * math.pi / 4)
        audio[start:end, 1] += tone * math.sin((pan + 1) * math.pi / 4)
    return normalize_master_audio(audio) if normalize else audio


# ============================================================
# WAV encoding / decoding
# ============================================================

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


# ============================================================
# MIDI export
# ============================================================

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
    seen: set = set()
    for ev in events:
        if ev.instrument == "none":
            continue
        ch   = midi_channel(ev)
        tick = int(round(ev.start * tps))
        if ch != 9:
            program = int(GM_PROGRAMS.get(ev.instrument, 0))
            if (ch, program) not in seen:
                raw.append((max(0, tick - 1), 1, bytes([0xC0 | ch, program])))
                seen.add((ch, program))
    for ev in events:
        if ev.instrument == "none":
            continue
        ch   = midi_channel(ev)
        note = PERCUSSION_NOTES.get(ev.instrument, 75) if ch == 9 else int(clamp(ev.midi, 0, 127))
        vel  = int(clamp(ev.velocity, .05, 1) * 110)
        s    = int(round(ev.start * tps))
        e    = int(round((ev.start + max(.05, ev.duration)) * tps))
        raw.append((s, 2, bytes([0x90 | ch, note, vel])))
        raw.append((e, 1, bytes([0x80 | ch, note, 0])))
    raw.sort(key=lambda x: (x[0], x[1]))
    track = bytearray()
    last  = 0
    for tick, _, payload in raw:
        track.extend(write_var_len(max(0, tick - last)))
        track.extend(payload)
        last = tick
    track.extend(write_var_len(0))
    track.extend(b"\xFF\x2F\x00")
    return (
        b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq)
        + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)
    )


# ============================================================
# FluidSynth renderer
# ============================================================

def render_with_fluidsynth(
    events: List[NoteEvent],
    duration: float,
    tempo: float,
    sr: int,
    params: Optional[dict] = None,
) -> Tuple[Optional[np.ndarray], str]:
    sf2 = find_generaluser_soundfont()
    if sf2 is None:
        return None, (
            "GeneralUser GS selected, but no SoundFont was found. "
            "Put GeneralUser-GS.sf2 in ./soundfonts/. Falling back to Simple synthesis."
        )
    exe = shutil.which("fluidsynth")
    if exe is None:
        return None, (
            "GeneralUser GS selected, but the fluidsynth system package is unavailable. "
            "Falling back to Simple synthesis."
        )
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
            return None, (
                f"GeneralUser GS rendering failed with FluidSynth: {exc}. "
                "Falling back to Simple synthesis."
            )
    if rendered_sr != sr:
        return None, (
            f"GeneralUser GS rendered at {rendered_sr} Hz instead of {sr} Hz. "
            "Falling back to Simple synthesis."
        )
    target = int(round((duration + .8) * sr))
    audio = audio[:target] if audio.shape[0] >= target else np.vstack([audio, np.zeros((target - audio.shape[0], 2))])
    target_peak = get_float_param(params, "master_target_peak", MASTER_TARGET_PEAK, 0.10, 0.98)
    target_rms  = get_float_param(params, "master_target_rms",  MASTER_TARGET_RMS,  0.01, 0.50)
    return (
        normalize_master_audio(audio, target_peak=target_peak, target_rms=target_rms),
        f"Audio rendered with GeneralUser GS through FluidSynth (master gain {fluid_gain:.2f}).",
    )


def render_backend(
    events: List[NoteEvent],
    info: CompositionInfo,
    synthesizer_type: str,
    params: Optional[dict] = None,
) -> Tuple[np.ndarray, str]:
    target_peak = get_float_param(params, "master_target_peak", MASTER_TARGET_PEAK, 0.10, 0.98)
    target_rms  = get_float_param(params, "master_target_rms",  MASTER_TARGET_RMS,  0.01, 0.50)
    if synthesizer_type == SYNTH_GENERALUSER_GS:
        audio, msg = render_with_fluidsynth(events, info.duration, info.tempo, DEFAULT_SAMPLE_RATE, params)
        if audio is not None:
            return audio, msg
        return (
            normalize_master_audio(
                render_events(events, info.duration, DEFAULT_SAMPLE_RATE, normalize=False),
                target_peak=target_peak, target_rms=target_rms,
            ),
            msg,
        )
    return (
        normalize_master_audio(
            render_events(events, info.duration, DEFAULT_SAMPLE_RATE, normalize=False),
            target_peak=target_peak, target_rms=target_rms,
        ),
        "Audio rendered with the Simple procedural synthesizer.",
    )


# ============================================================
# MP3 export
# ============================================================

def audio_to_mp3_bytes(audio: np.ndarray, sr: int) -> Tuple[Optional[bytes], str]:
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    lame_error = "lameenc not installed"
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
        wav_path = os.path.join(tmp, "input.wav")
        mp3_path = os.path.join(tmp, "output.mp3")
        with open(wav_path, "wb") as f:
            f.write(audio_to_wav_bytes(audio, sr))
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", wav_path, "-codec:a", "libmp3lame", "-b:a", "192k", mp3_path],
            check=True, timeout=45,
        )
        return open(mp3_path, "rb").read(), "MP3 export generated with ffmpeg."
