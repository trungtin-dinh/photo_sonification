from __future__ import annotations

import hashlib
import html
import io
import os
import re
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
from PIL import Image

from config import (
    DEFAULT_IMAGE_CAPTION,
    DEFAULT_IMAGE_NAME,
    DEFAULT_IMAGE_URL,
    DEFAULT_SAMPLE_RATE,
    FLUIDSYNTH_MASTER_GAIN,
    MASTER_TARGET_PEAK,
    MASTER_TARGET_RMS,
    MAX_ANALYSIS_SIDE,
    MAX_RENDER_SECONDS,
    PORTFOLIO_LINKS,
    SCALE_OPTIONS,
    SIMPLE_INTERNAL_TO_DISPLAY,
    SUPPORTED_IMAGE_TYPES,
    SYNTH_GENERALUSER_GS,
    SYNTHESIZER_OPTIONS,
)
from utils import clamp, get_float_param, make_signature
from image_analysis import analyze_image, load_image_bytes_from_url, open_image_from_bytes
from composition import (
    choose_instruments,
    compute_bar_settings,
    get_instrument_choices_with_none,
    instrument_label,
)
from audio import (
    audio_to_mp3_bytes,
    audio_to_wav_bytes,
    midi_bytes_from_events,
    normalize_master_audio,
    render_backend,
    render_events,
)


# ============================================================
# Portfolio links
# ============================================================
def render_portfolio_links() -> None:
    links_html_parts: List[str] = []

    for item in PORTFOLIO_LINKS:
        show_label = item["platform"] in {"CV FR", "CV EN"}
        link_class = "portfolio-link with-label" if show_label else "portfolio-link icon-only"
        title = f"Open {item['platform']}"
        if not show_label:
            title = f"Open {item['platform']}: {item['label']}"

        label_html = html.escape(item["label"]) if show_label else ""
        href = html.escape(item["url"])
        icon = html.escape(item.get("icon_url", item.get("icon", "")))
        links_html_parts.append(
            f'<a class="{link_class}" href="{href}" target="_blank" title="{html.escape(title)}">'
            f'<img src="{icon}" alt="{html.escape(item["platform"])}" />'
            f'{label_html}'
            f'</a>'
        )

    st.markdown(
        f'<div class="portfolio-links">{"".join(links_html_parts)}</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# Plot helpers
# ============================================================
def fig_to_bytes(fig: plt.Figure, tight: bool = True) -> bytes:
    buf = io.BytesIO()
    kwargs = {
        "format": "png",
        "dpi": 130,
        "transparent": True,
        "facecolor": "none",
        "edgecolor": "none",
    }
    if tight:
        kwargs["bbox_inches"] = "tight"
    fig.savefig(buf, **kwargs)
    plt.close(fig)
    return buf.getvalue()


def plot_text_color() -> str:
    return "black" if str(st.get_option("theme.base")).lower() == "light" else "white"


def style_ax(fig: plt.Figure, ax: plt.Axes, grid: bool = True) -> str:
    color = plot_text_color()
    fig.patch.set_alpha(0)
    ax.set_facecolor((0, 0, 0, 0))
    ax.title.set_color(color)
    ax.xaxis.label.set_color(color)
    ax.yaxis.label.set_color(color)
    ax.tick_params(colors=color)
    for sp in ax.spines.values():
        sp.set_color(color)
    if grid:
        ax.grid(True, color=color, alpha=0.25)
    return color


def plot_map(data: np.ndarray, title: str, cmap: Optional[str] = "gray") -> bytes:
    arr = np.asarray(data)
    h, w = arr.shape[:2]
    aspect = w / max(1, h)
    fw = 4.8
    ih = fw / max(aspect, 1e-6)
    th = 0.42
    fig, ax = plt.subplots(figsize=(fw, ih + th))
    color = style_ax(fig, ax, False)
    ax.imshow(arr, cmap=cmap, aspect="equal")
    ax.set_title(title, fontsize=10, color=color, pad=6)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, bottom=0, top=ih / (ih + th))
    return fig_to_bytes(fig, tight=False)


def mono(audio: np.ndarray) -> np.ndarray:
    return np.mean(audio, axis=1) if audio.ndim == 2 else np.asarray(audio)


def plot_waveform(audio: np.ndarray, sr: int, title: str = "Waveform") -> bytes:
    m = mono(audio)
    t = np.arange(len(m)) / sr
    fig, ax = plt.subplots(figsize=(4.8, 2.6))
    color = style_ax(fig, ax)
    ax.plot(t, m, linewidth=0.7)
    ax.set_xlabel("Time (s)", color=color)
    ax.set_ylabel("Amplitude", color=color)
    ax.set_title(title, color=color)
    return fig_to_bytes(fig)


def plot_frequency(audio: np.ndarray, sr: int, title: str = "Fourier magnitude") -> bytes:
    m = mono(audio)
    fig, ax = plt.subplots(figsize=(4.8, 2.6))
    color = style_ax(fig, ax)
    if m.size < 2 or float(np.max(np.abs(m))) <= 1e-12:
        ax.text(
            0.5,
            0.5,
            "No visible spectral energy",
            ha="center",
            va="center",
            color=color,
            transform=ax.transAxes,
        )
    else:
        spec = np.fft.rfft(m * np.hanning(m.size))
        freqs = np.fft.rfftfreq(m.size, 1 / sr)
        mag = np.abs(spec)
        mag = mag / max(float(np.max(mag)), 1e-12)
        ax.plot(freqs, mag, linewidth=0.8)
        ax.set_xlim(0, min(8000, sr // 2))
        ax.set_xlabel("Frequency (Hz)", color=color)
        ax.set_ylabel("Magnitude", color=color)
        ax.set_title(title, color=color)
    return fig_to_bytes(fig)


# ============================================================
# Small UI helpers
# ============================================================
def format_percent(x: float) -> str:
    return f"{100 * x:.1f}%"


def ensure_bytes(x: object) -> bytes:
    if x is None:
        return b""
    if isinstance(x, bytes):
        return x
    if isinstance(x, bytearray):
        return bytes(x)
    if isinstance(x, io.BytesIO):
        return x.getvalue()
    raise TypeError(type(x).__name__)


def _output_stem(image_name: str, max_len: int = 22) -> str:
    base = os.path.splitext(image_name or "photo")[0]
    base = re.sub(r"[^\w\-]", "_", base)[:max_len].strip("_") or "photo"
    return f"photosono-{base}"


def st_image_full_width(image: object, **kwargs: object) -> None:
    """Display an image using the full available column width.

    Streamlit versions differ on image sizing:
    - recent versions prefer width="stretch";
    - older versions raise a TypeError for string widths and require
      use_container_width=True.

    This wrapper keeps the UI compatible with both behaviours.
    """
    try:
        st.image(image, width="stretch", **kwargs)
    except TypeError:
        st.image(image, use_container_width=True, **kwargs)


def load_input_image_from_streamlit() -> tuple[
    Optional[bytes],
    Optional[Image.Image],
    Optional[str],
    Optional[str],
    str,
    bool,
]:
    """
    Load the image selected in the Input photo box.

    The function keeps the same downstream variables as the previous UI:
    uploaded_bytes, uploaded_image, uploaded_hash, upload_error, input_name,
    and input_is_default.
    """
    uploaded_bytes: Optional[bytes] = None
    uploaded_image: Optional[Image.Image] = None
    uploaded_hash: Optional[str] = None
    upload_error: Optional[str] = None
    input_name: str = DEFAULT_IMAGE_NAME
    input_is_default = False

    source_mode = st.radio(
        "Image source",
        ["Default image", "Upload image", "Record image"],
        horizontal=True,
        key="input_source_mode",
    )

    if source_mode == "Default image":
        try:
            uploaded_bytes = load_image_bytes_from_url(DEFAULT_IMAGE_URL)
            uploaded_hash = hashlib.sha256(uploaded_bytes).hexdigest()
            uploaded_image = open_image_from_bytes(uploaded_bytes, DEFAULT_IMAGE_URL)
            input_name = DEFAULT_IMAGE_NAME
            input_is_default = True
        except Exception as exc:
            upload_error = str(exc)

    elif source_mode == "Upload image":
        uploaded = st.file_uploader(
            "Upload an image",
            type=SUPPORTED_IMAGE_TYPES,
            accept_multiple_files=False,
            key="input_photo_upload",
        )
        if uploaded is not None:
            try:
                uploaded_bytes = uploaded.getvalue()
                uploaded_hash = hashlib.sha256(uploaded_bytes).hexdigest()
                uploaded_image = open_image_from_bytes(uploaded_bytes, uploaded.name)
                input_name = uploaded.name
            except Exception as exc:
                upload_error = str(exc)

    else:
        captured = st.camera_input(
            "Take a picture",
            key="input_photo_camera",
        )
        if captured is not None:
            try:
                uploaded_bytes = captured.getvalue()
                uploaded_hash = hashlib.sha256(uploaded_bytes).hexdigest()
                input_name = captured.name or "camera_capture.jpg"
                uploaded_image = open_image_from_bytes(uploaded_bytes, input_name)
            except Exception as exc:
                upload_error = str(exc)

    return (
        uploaded_bytes,
        uploaded_image,
        uploaded_hash,
        upload_error,
        input_name,
        input_is_default,
    )


# ============================================================
# Documentation loading helpers
# ============================================================
def _load_doc(filename: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    for p in [os.path.join(base, filename), os.path.join(os.getcwd(), filename)]:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as fh:
                return fh.read()
    return ""


def _split_markdown_by_h2(text: str) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    for part in re.split(r"(?m)^##\s+", text.strip()):
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


DOC_FR_SECTIONS = _split_markdown_by_h2(_load_doc("documentation_fr.md"))
DOC_EN_SECTIONS = _split_markdown_by_h2(_load_doc("documentation_en.md"))
DOC_FR_TITLES = list(DOC_FR_SECTIONS.keys())
DOC_EN_TITLES = list(DOC_EN_SECTIONS.keys())


# ============================================================
# Page configuration & CSS
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
    padding-top: 2.6rem;
    padding-bottom: 2rem;
}
.portfolio-links {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 0.45rem;
    margin-bottom: 0.4rem;
}
.portfolio-link {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.25rem 0.45rem;
    border-radius: 999px;
    text-decoration: none !important;
    border: 1px solid rgba(128,128,128,0.25);
    color: inherit !important;
    font-size: 0.82rem;
}
.portfolio-link img {
    height: 1.05rem;
    width: 1.05rem;
    object-fit: contain;
}
.hero-title {
    font-size: 2.25rem;
    font-weight: 750;
    line-height: 1.05;
    margin-bottom: 0.25rem;
}
.hero-subtitle {
    opacity: 0.82;
    margin-bottom: 1.15rem;
}
.small-caption {
    font-size: 0.90rem;
    opacity: 0.82;
    margin-top: 0.35rem;
}
.metric-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.45rem;
}
.metric-card, .instrument-card {
    border: 1px solid rgba(128,128,128,0.22);
    border-radius: 0.65rem;
    padding: 0.50rem 0.60rem;
    background: rgba(128,128,128,0.05);
}
.metric-card b, .instrument-card b {
    display: block;
    font-size: 0.78rem;
    opacity: 0.75;
    margin-bottom: 0.12rem;
}
.section-label {
    font-weight: 700;
    margin-bottom: 0.45rem;
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
        "generation_result": None,
        "parameter_defaults": None,
        "photo_analysis_cache": None,
        "run_in_progress": False,
        "run_requested": False,
        "last_run_status": None,
        "doc_fr_title": DOC_FR_TITLES[0] if DOC_FR_TITLES else "",
        "doc_en_title": DOC_EN_TITLES[0] if DOC_EN_TITLES else "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def request_run() -> None:
    """Lock the Run button and mark a run as pending."""
    st.session_state.run_requested = True
    st.session_state.run_in_progress = True
    st.session_state.last_run_status = None


# ============================================================
# Documentation tab renderer
# ============================================================
def _set_doc_section(state_key: str, title: str) -> None:
    st.session_state[state_key] = title


def render_documentation_tab(
    titles: List[str],
    sections: Dict[str, str],
    state_key: str,
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
    st.markdown(
        """
<div class="hero-title">Photo Sonification</div>
<div class="hero-subtitle">Image analysis · Fourier feature extraction · Procedural music synthesis</div>
""",
        unsafe_allow_html=True,
    )

    uploaded_bytes: Optional[bytes] = None
    uploaded_image: Optional[Image.Image] = None
    uploaded_hash: Optional[str] = None
    upload_error: Optional[str] = None
    input_name: str = DEFAULT_IMAGE_NAME
    input_is_default = False

    input_col, output_col = st.columns([1.0, 1.35], gap="large")

    # ── Input column ─────────────────────────────────────────────────────
    with input_col:
        with st.container(border=True):
            st.markdown("#### Input photo")

            (
                uploaded_bytes,
                uploaded_image,
                uploaded_hash,
                upload_error,
                input_name,
                input_is_default,
            ) = load_input_image_from_streamlit()

            if uploaded_image is not None:
                st_image_full_width(uploaded_image)
                if input_is_default:
                    st.markdown(
                        f'<div class="small-caption">{DEFAULT_IMAGE_CAPTION}</div>',
                        unsafe_allow_html=True,
                    )
            else:
                mode = st.session_state.get("input_source_mode", "Default image")
                if mode == "Default image":
                    st.info("The default test image could not be loaded. Choose another input mode.")
                elif mode == "Upload image":
                    st.info("Upload a photo to continue.")
                else:
                    st.info("Capture a photo to continue.")
                if upload_error:
                    st.error(f"Could not read this image: {upload_error}")

            st.markdown("")
            st.button(
                "▶ GENERATE AUDIO",
                type="primary",
                width="stretch",
                disabled=(uploaded_image is None or st.session_state.run_in_progress),
                on_click=request_run,
            )

    # ── Derive controls_active AFTER input_col ───────────────────────────
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
        bar_min = int(parameter_defaults["bar_min"])
        bar_max = int(parameter_defaults["bar_max"])
        bar_default = int(parameter_defaults["bar_default"])
        variation_default = float(parameter_defaults["variation_default"])
        complexity_default = float(parameter_defaults["complexity_default"])
    else:
        bar_min, bar_max, bar_default = 4, 24, 8
        variation_default, complexity_default = 0.55, 0.72

    result = st.session_state.get("generation_result")
    if not (
        uploaded_hash is not None
        and isinstance(result, dict)
        and result.get("image_id") == uploaded_hash
    ):
        result = None

    # ── Output column ────────────────────────────────────────────────────
    with output_col:
        with st.container(border=True):
            st.markdown("#### Output audio")
            progress_status_placeholder = st.empty()
            progress_bar_placeholder = st.empty()

            if st.session_state.last_run_status == "Done":
                progress_status_placeholder.success("Done — 100%")

            if result is None:
                st.info("Generated audio will appear here after you click **▶ Generate Audio**.")
                st.download_button(
                    "⬇ Download MP3",
                    data=b"",
                    file_name="photosono.mp3",
                    mime="audio/mpeg",
                    disabled=True,
                    width="stretch",
                )
                st.download_button(
                    "⬇ Download MIDI",
                    data=b"",
                    file_name="photosono.mid",
                    mime="audio/midi",
                    disabled=True,
                    width="stretch",
                )
            else:
                from utils import CompositionInfo

                info_r: CompositionInfo = result["info"]
                stem = _output_stem(result.get("image_name", input_name))

                st.audio(result["wav_bytes"], format="audio/wav")
                meta_html = (
                    '<div class="metric-grid">'
                    f'<div class="metric-card"><b>Tempo</b>{info_r.tempo:.1f} BPM</div>'
                    f'<div class="metric-card"><b>Length</b>{info_r.bars} bars / {info_r.duration:.1f} s</div>'
                    f'<div class="metric-card"><b>Key / scale</b>{info_r.key_name} / {info_r.scale_name}</div>'
                    f'<div class="metric-card"><b>Mood</b>{html.escape(str(info_r.mood))}</div>'
                    "</div>"
                )
                st.markdown(meta_html, unsafe_allow_html=True)

                st.markdown("")
                st.markdown('<div class="section-label">Instruments</div>', unsafe_allow_html=True)
                inst_line = (
                    f"Main · {instrument_label(info_r.main_instrument)} &nbsp; "
                    f"Texture · {instrument_label(info_r.texture_instrument)} &nbsp; "
                    f"Bass · {instrument_label(info_r.bass_instrument)} &nbsp; "
                    f"Pad · {instrument_label(info_r.pad_instrument)} &nbsp; "
                    f"Chord · {instrument_label(info_r.chord_instrument)}"
                )
                if info_r.solo_instrument != "none":
                    inst_line += f" &nbsp; Solo · {instrument_label(info_r.solo_instrument)}"
                st.markdown(f'<div class="instrument-card">{inst_line}</div>', unsafe_allow_html=True)

                synth_msg = result.get("synth_message", "")
                if synth_msg:
                    st.markdown(
                        f'<div class="small-caption">{html.escape(str(synth_msg))}</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown("")
                st.download_button(
                    "⬇ Download MP3",
                    data=ensure_bytes(result["mp3_bytes"]),
                    file_name=f"{stem}.mp3",
                    mime="audio/mpeg",
                    disabled=result["mp3_bytes"] is None,
                    width="stretch",
                )
                st.download_button(
                    "⬇ Download MIDI",
                    data=ensure_bytes(result["midi_bytes"]),
                    file_name=f"{stem}.mid",
                    mime="audio/midi",
                    width="stretch",
                )
                if result["mp3_bytes"] is None:
                    st.markdown(
                        f'<div class="small-caption">{html.escape(str(result.get("mp3_message", "MP3 export unavailable.")))}</div>',
                        unsafe_allow_html=True,
                    )

    # =========================================================================
    # Row 2: Parameters
    # =========================================================================
    with st.expander("⚙ Parameters", expanded=False):
        if not controls_active:
            st.info(
                "Click **▶ Generate Audio** once to analyse the photo and unlock photo-adaptive musical defaults. "
                "The analysis, Fourier and saliency thresholds below already use safe default values."
                if uploaded_image is not None
                else "Choose a photo first, then click **▶ Generate Audio** to unlock the parameters."
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
        ) = st.tabs(
            [
                "Structure",
                "Image analysis",
                "Fourier & saliency",
                "Tonality & Tempo",
                "Synth & Mix",
                "Instruments",
            ]
        )

        # ── Tab 1 · Structure ───────────────────────────────────────────
        with tab_struct:
            s_left, s_right = st.columns(2, gap="large")
            with s_left:
                with st.container(border=True):
                    st.markdown('<div class="section-label">Musical shape</div>', unsafe_allow_html=True)
                    number_of_bars = st.slider(
                        "Number of bars",
                        bar_min,
                        bar_max,
                        bar_default,
                        1,
                        disabled=not controls_active,
                        help="Total length of the composition in 4/4 bars. The min/max/default values are photo-adaptive after the first run.",
                    )
                    variation_strength = st.slider(
                        "Variation strength",
                        0.0,
                        1.0,
                        variation_default,
                        0.01,
                        disabled=not controls_active,
                        help="Default derived from image symmetry. Controls how much the second half diverges from the first.",
                    )
                    complexity = st.slider(
                        "Composition complexity",
                        0.10,
                        1.00,
                        complexity_default,
                        0.01,
                        disabled=not controls_active,
                        help="Default derived from texture entropy. Controls note density and arpeggio activity.",
                    )
                    random_factor = st.slider(
                        "Random factor",
                        0,
                        100,
                        0,
                        1,
                        disabled=not controls_active,
                        help="Adds controlled perturbation to the image and Fourier-domain analysis before composition.",
                    )

                with st.container(border=True):
                    st.markdown('<div class="section-label">Automatic range mapping</div>', unsafe_allow_html=True)
                    auto_complexity_range = st.slider(
                        "Auto complexity range",
                        0.05,
                        1.00,
                        (0.25, 0.90),
                        0.01,
                        disabled=not threshold_controls_enabled,
                    )
                    auto_variation_range = st.slider(
                        "Auto variation range",
                        0.00,
                        1.00,
                        (0.25, 0.85),
                        0.01,
                        disabled=not threshold_controls_enabled,
                    )
                    advanced_params["auto_complexity_range"] = auto_complexity_range
                    advanced_params["auto_variation_range"] = auto_variation_range

            with s_right:
                with st.container(border=True):
                    st.markdown('<div class="section-label">Auto bar estimator</div>', unsafe_allow_html=True)
                    auto_bar_min_range = st.slider("Auto min-bars range", 1, 32, (4, 8), 1, disabled=not threshold_controls_enabled)
                    auto_bar_max_range = st.slider("Auto max-bars range", 2, 64, (12, 24), 1, disabled=not threshold_controls_enabled)
                    auto_bar_default_range = st.slider("Auto default-bars range", 1, 64, (6, 16), 1, disabled=not threshold_controls_enabled)
                    bar_weight_texture = st.slider("Weight · texture", 0.0, 2.0, 0.40, 0.01, disabled=not threshold_controls_enabled)
                    bar_weight_edge = st.slider("Weight · edges", 0.0, 2.0, 0.25, 0.01, disabled=not threshold_controls_enabled)
                    bar_weight_high_frequency = st.slider("Weight · high frequencies", 0.0, 2.0, 0.20, 0.01, disabled=not threshold_controls_enabled)
                    bar_weight_periodicity = st.slider("Weight · periodicity", 0.0, 2.0, 0.15, 0.01, disabled=not threshold_controls_enabled)
                    advanced_params.update(
                        {
                            "auto_bar_min_range": auto_bar_min_range,
                            "auto_bar_max_range": auto_bar_max_range,
                            "auto_bar_default_range": auto_bar_default_range,
                            "bar_weight_texture": bar_weight_texture,
                            "bar_weight_edge": bar_weight_edge,
                            "bar_weight_high_frequency": bar_weight_high_frequency,
                            "bar_weight_periodicity": bar_weight_periodicity,
                        }
                    )

        # ── Tab 2 · Image analysis ───────────────────────────────────────
        with tab_analysis:
            a_left, a_right = st.columns(2, gap="large")
            with a_left:
                with st.container(border=True):
                    st.markdown('<div class="section-label">Pre-processing</div>', unsafe_allow_html=True)
                    analysis_max_side = st.slider(
                        "Analysis max side (px)",
                        128,
                        2048,
                        int(MAX_ANALYSIS_SIDE),
                        64,
                        disabled=not threshold_controls_enabled,
                        help="The photo is resized only for analysis. Larger values preserve detail but cost more CPU time.",
                    )
                    image_noise_sigma_coeff = st.slider(
                        "Spatial noise coefficient",
                        0.000,
                        0.250,
                        0.045,
                        0.005,
                        disabled=not threshold_controls_enabled,
                    )
                    entropy_histogram_bins = st.slider(
                        "Entropy histogram bins",
                        8,
                        256,
                        64,
                        8,
                        disabled=not threshold_controls_enabled,
                    )
                    advanced_params.update(
                        {
                            "analysis_max_side": analysis_max_side,
                            "image_noise_sigma_coeff": image_noise_sigma_coeff,
                            "entropy_histogram_bins": entropy_histogram_bins,
                        }
                    )

                with st.container(border=True):
                    st.markdown('<div class="section-label">Edge detection</div>', unsafe_allow_html=True)
                    edge_threshold_percentile = st.slider("Edge threshold percentile", 0.0, 100.0, 75.0, 0.5, disabled=not threshold_controls_enabled)
                    edge_threshold_minimum = st.slider("Minimum edge threshold", 0.00, 1.00, 0.08, 0.01, disabled=not threshold_controls_enabled)
                    advanced_params.update(
                        {
                            "edge_threshold_percentile": edge_threshold_percentile,
                            "edge_threshold_minimum": edge_threshold_minimum,
                        }
                    )

            with a_right:
                with st.container(border=True):
                    st.markdown('<div class="section-label">Luminance thresholds</div>', unsafe_allow_html=True)
                    luminance_percentile_range = st.slider(
                        "Luminance percentile range",
                        0.0,
                        100.0,
                        (5.0, 95.0),
                        0.5,
                        disabled=not threshold_controls_enabled,
                    )
                    shadow_dark_floor = st.slider("Shadow floor", 0.00, 1.00, 0.18, 0.01, disabled=not threshold_controls_enabled)
                    shadow_offset = st.slider("Shadow percentile offset", 0.00, 0.50, 0.03, 0.01, disabled=not threshold_controls_enabled)
                    highlight_bright_floor = st.slider("Highlight floor", 0.00, 1.00, 0.82, 0.01, disabled=not threshold_controls_enabled)
                    highlight_offset = st.slider("Highlight percentile offset", 0.00, 0.50, 0.03, 0.01, disabled=not threshold_controls_enabled)
                    advanced_params.update(
                        {
                            "luminance_percentile_range": luminance_percentile_range,
                            "shadow_dark_floor": shadow_dark_floor,
                            "shadow_offset": shadow_offset,
                            "highlight_bright_floor": highlight_bright_floor,
                            "highlight_offset": highlight_offset,
                        }
                    )

        # ── Tab 3 · Fourier & saliency ───────────────────────────────────
        with tab_fourier:
            f_left, f_mid, f_right = st.columns(3, gap="large")
            with f_left:
                with st.container(border=True):
                    st.markdown('<div class="section-label">Fourier analysis</div>', unsafe_allow_html=True)
                    fourier_dc_radius = st.slider("DC exclusion radius", 0.000, 0.200, 0.025, 0.005, disabled=not threshold_controls_enabled)
                    fourier_band_limits = st.slider(
                        "Low/mid/high radial limits",
                        0.03,
                        0.95,
                        (0.14, 0.34),
                        0.01,
                        disabled=not threshold_controls_enabled,
                    )
                    fourier_orientation_width = st.slider("Orientation bandwidth", 0.05, 0.95, 0.38, 0.01, disabled=not threshold_controls_enabled)
                    fourier_peak_percentiles = st.slider(
                        "Peak-score percentile range",
                        0.0,
                        100.0,
                        (90.0, 99.7),
                        0.1,
                        disabled=not threshold_controls_enabled,
                    )
                    fourier_peak_log_divisor = st.slider("Peak-score log divisor", 0.5, 20.0, 5.0, 0.1, disabled=not threshold_controls_enabled)
                    fourier_noise_sigma_coeff = st.slider("Fourier noise coefficient", 0.000, 1.000, 0.180, 0.005, disabled=not threshold_controls_enabled)
                    advanced_params.update(
                        {
                            "fourier_dc_radius": fourier_dc_radius,
                            "fourier_band_limits": fourier_band_limits,
                            "fourier_orientation_width": fourier_orientation_width,
                            "fourier_peak_percentiles": fourier_peak_percentiles,
                            "fourier_peak_log_divisor": fourier_peak_log_divisor,
                            "fourier_noise_sigma_coeff": fourier_noise_sigma_coeff,
                        }
                    )

            with f_mid:
                with st.container(border=True):
                    st.markdown('<div class="section-label">Saliency map</div>', unsafe_allow_html=True)
                    saliency_edge_weight = st.slider("Weight · edge", 0.0, 2.0, 0.42, 0.01, disabled=not threshold_controls_enabled)
                    saliency_color_weight = st.slider("Weight · color rarity", 0.0, 2.0, 0.34, 0.01, disabled=not threshold_controls_enabled)
                    saliency_luminance_weight = st.slider("Weight · luminance rarity", 0.0, 2.0, 0.24, 0.01, disabled=not threshold_controls_enabled)
                    saliency_center_bias_weight = st.slider("Center-bias weight", 0.00, 1.00, 0.12, 0.01, disabled=not threshold_controls_enabled)
                    saliency_threshold_percentile = st.slider("Saliency threshold percentile", 0.0, 100.0, 96.0, 0.5, disabled=not threshold_controls_enabled)
                    saliency_threshold_minimum = st.slider("Minimum saliency threshold", 0.00, 1.00, 0.20, 0.01, disabled=not threshold_controls_enabled)
                    advanced_params.update(
                        {
                            "saliency_edge_weight": saliency_edge_weight,
                            "saliency_color_weight": saliency_color_weight,
                            "saliency_luminance_weight": saliency_luminance_weight,
                            "saliency_center_bias_weight": saliency_center_bias_weight,
                            "saliency_threshold_percentile": saliency_threshold_percentile,
                            "saliency_threshold_minimum": saliency_threshold_minimum,
                        }
                    )

            with f_right:
                with st.container(border=True):
                    st.markdown('<div class="section-label">Saliency solo layer</div>', unsafe_allow_html=True)
                    solo_note_count_range = st.slider("Solo note-count range", 1, 48, (3, 18), 1, disabled=not threshold_controls_enabled)
                    solo_note_cap = st.slider("Solo note cap", 1, 64, 22, 1, disabled=not threshold_controls_enabled)
                    solo_min_distance = st.slider("Minimum saliency-point distance", 0.000, 0.500, 0.055, 0.005, disabled=not threshold_controls_enabled)
                    solo_duration_beats_range = st.slider("Solo duration range (beats)", 0.05, 4.00, (0.18, 1.25), 0.05, disabled=not threshold_controls_enabled)
                    advanced_params.update(
                        {
                            "solo_note_count_range": solo_note_count_range,
                            "solo_note_cap": solo_note_cap,
                            "solo_min_distance": solo_min_distance,
                            "solo_duration_beats_range": solo_duration_beats_range,
                        }
                    )

        # ── Tab 4 · Tonality & Tempo ─────────────────────────────────────
        with tab_tonal:
            t_left, t_right = st.columns(2, gap="large")
            with t_left:
                with st.container(border=True):
                    st.markdown('<div class="section-label">Tonal center</div>', unsafe_allow_html=True)
                    _cur_scale = st.session_state.get("scale_selection", "Automatic")
                    if _cur_scale not in SCALE_OPTIONS:
                        _cur_scale = "Automatic"
                    requested_scale = st.selectbox(
                        "Scale",
                        SCALE_OPTIONS,
                        index=SCALE_OPTIONS.index(_cur_scale),
                        key="scale_selection",
                        disabled=not controls_active,
                    )

                with st.container(border=True):
                    st.markdown('<div class="section-label">Tempo mapping</div>', unsafe_allow_html=True)
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
                    st.markdown('<div class="section-label">Tempo clamp ranges</div>', unsafe_allow_html=True)
                    tempo_scientific_range = st.slider("Scientific BPM range", 1.0, 240.0, (48.0, 152.0), 1.0, disabled=not threshold_controls_enabled)
                    tempo_balanced_range = st.slider("Balanced BPM range", 1.0, 240.0, (56.0, 132.0), 1.0, disabled=not threshold_controls_enabled)
                    tempo_musical_range = st.slider("Musical BPM range", 1.0, 240.0, (72.0, 108.0), 1.0, disabled=not threshold_controls_enabled)
                    advanced_params.update(
                        {
                            "tempo_scientific_range": tempo_scientific_range,
                            "tempo_balanced_range": tempo_balanced_range,
                            "tempo_musical_range": tempo_musical_range,
                        }
                    )

        # ── Tab 5 · Synth & Mix ─────────────────────────────────────────
        with tab_synth:
            sy_left, sy_mid, sy_right = st.columns(3, gap="large")
            with sy_left:
                with st.container(border=True):
                    st.markdown('<div class="section-label">Engine</div>', unsafe_allow_html=True)
                    _cur_synth = st.session_state.get("synthesizer_type", SYNTH_GENERALUSER_GS)
                    if _cur_synth not in SYNTHESIZER_OPTIONS:
                        _cur_synth = SYNTH_GENERALUSER_GS
                    synthesizer_type = st.radio(
                        "Synthesizer type",
                        SYNTHESIZER_OPTIONS,
                        index=SYNTHESIZER_OPTIONS.index(_cur_synth),
                        key="synthesizer_type",
                        disabled=not controls_active,
                    )
                    instrument_mode = st.radio(
                        "Instrument layer selection",
                        ["Automatic", "Manual"],
                        index=0,
                        horizontal=True,
                        disabled=not controls_active,
                    )

            with sy_mid:
                with st.container(border=True):
                    st.markdown('<div class="section-label">Master bus</div>', unsafe_allow_html=True)
                    master_target_peak = st.slider("Target peak", 0.10, 0.98, float(MASTER_TARGET_PEAK), 0.01, disabled=not threshold_controls_enabled)
                    master_target_rms = st.slider("Target RMS", 0.01, 0.50, float(MASTER_TARGET_RMS), 0.01, disabled=not threshold_controls_enabled)
                    max_render_seconds = st.slider("Maximum render duration (s)", 8.0, 240.0, float(MAX_RENDER_SECONDS), 1.0, disabled=not threshold_controls_enabled)
                    fluidsynth_master_gain = st.slider("FluidSynth master gain", 0.05, 2.00, float(FLUIDSYNTH_MASTER_GAIN), 0.05, disabled=not threshold_controls_enabled)
                    advanced_params.update(
                        {
                            "master_target_peak": master_target_peak,
                            "master_target_rms": master_target_rms,
                            "max_render_seconds": max_render_seconds,
                            "fluidsynth_master_gain": fluidsynth_master_gain,
                        }
                    )

            with sy_right:
                with st.container(border=True):
                    st.markdown('<div class="section-label">Event gates</div>', unsafe_allow_html=True)
                    chord_double_hit_high_freq_threshold = st.slider("Chord double-hit high-frequency threshold", 0.00, 1.00, 0.22, 0.01, disabled=not threshold_controls_enabled)
                    complexity_step_threshold = st.slider("Melody density threshold", 0.00, 1.00, 0.52, 0.01, disabled=not threshold_controls_enabled)
                    melody_energy_gate = st.slider("Melody energy gate", 0.00, 1.00, 0.10, 0.01, disabled=not threshold_controls_enabled)
                    texture_density_threshold = st.slider("Texture activation threshold", 0.00, 1.00, 0.28, 0.01, disabled=not threshold_controls_enabled)
                    percussion_density_threshold = st.slider("Percussion activation threshold", 0.00, 1.00, 0.18, 0.01, disabled=not threshold_controls_enabled)
                    advanced_params.update(
                        {
                            "chord_double_hit_high_freq_threshold": chord_double_hit_high_freq_threshold,
                            "complexity_step_threshold": complexity_step_threshold,
                            "melody_energy_gate": melody_energy_gate,
                            "texture_density_threshold": texture_density_threshold,
                            "percussion_density_threshold": percussion_density_threshold,
                        }
                    )

        # ── Tab 6 · Instruments ─────────────────────────────────────────
        with tab_inst:
            choices = get_instrument_choices_with_none(synthesizer_type)
            fallback = choices[1] if len(choices) > 1 else "None"
            cache = st.session_state.get("photo_analysis_cache")

            if controls_active and isinstance(cache, dict):
                _fdef: Dict[str, float] = cache["analysis"]["features"]  # type: ignore[assignment]
                _ai = choose_instruments(_fdef, "Automatic", synthesizer_type)
                defaults = [
                    instrument_label(x) if x.startswith("gm_") else SIMPLE_INTERNAL_TO_DISPLAY.get(x, fallback)
                    for x in _ai
                ]
            else:
                defaults = (
                    ["Acoustic Grand Piano", "Orchestral Harp", "Cello", "Pad 2 (warm)", "Acoustic Grand Piano", "Flute"]
                    if synthesizer_type == SYNTH_GENERALUSER_GS
                    else ["Soft piano", "Harp", "Cello-like bass", "Warm pad", "Soft piano", "None"]
                )

            while len(defaults) < 6:
                defaults.append("None")

            main_layer, texture_layer, bass_layer, pad_layer, chord_layer, solo_layer = defaults[:6]
            main_gain_db = 0.0
            texture_gain_db = -2.0
            bass_gain_db = 0.0
            pad_gain_db = -8.0
            chord_gain_db = -3.0
            solo_gain_db = -1.0

            def _idx(val: str) -> int:
                if val in choices:
                    return choices.index(val)
                return choices.index(fallback) if fallback in choices else 0

            if instrument_mode != "Manual":
                if controls_active and isinstance(cache, dict):
                    st.markdown('<div class="section-label">Auto-selected instruments</div>', unsafe_allow_html=True)
                    _layer_names = ["Main", "Texture", "Bass", "Pad", "Chord", "Solo"]
                    _count = 6 if synthesizer_type == SYNTH_GENERALUSER_GS else 5
                    _auto_html = '<div class="metric-grid">' + "".join(
                        f'<div class="metric-card"><b>{_layer_names[i]}</b>{defaults[i]}</div>'
                        for i in range(_count)
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
                        st.markdown('<div class="section-label">Main</div>', unsafe_allow_html=True)
                        main_layer = st.selectbox("Main layer", choices, index=_idx(defaults[0]), disabled=not controls_active, label_visibility="collapsed")
                        main_gain_db = st.slider("Main gain (dB)", -24.0, 12.0, 0.0, 0.5, disabled=not controls_active)
                with i_col2:
                    with st.container(border=True):
                        st.markdown('<div class="section-label">Texture</div>', unsafe_allow_html=True)
                        texture_layer = st.selectbox("Texture layer", choices, index=_idx(defaults[1]), disabled=not controls_active, label_visibility="collapsed")
                        texture_gain_db = st.slider("Texture gain (dB)", -24.0, 12.0, -2.0, 0.5, disabled=not controls_active)
                with i_col3:
                    with st.container(border=True):
                        st.markdown('<div class="section-label">Bass</div>', unsafe_allow_html=True)
                        bass_layer = st.selectbox("Bass layer", choices, index=_idx(defaults[2]), disabled=not controls_active, label_visibility="collapsed")
                        bass_gain_db = st.slider("Bass gain (dB)", -24.0, 12.0, 0.0, 0.5, disabled=not controls_active)

                i_col4, i_col5, i_col6 = st.columns(3, gap="medium")
                with i_col4:
                    with st.container(border=True):
                        st.markdown('<div class="section-label">Pad</div>', unsafe_allow_html=True)
                        pad_layer = st.selectbox("Pad layer", choices, index=_idx(defaults[3]), disabled=not controls_active, label_visibility="collapsed")
                        pad_gain_db = st.slider("Pad gain (dB)", -24.0, 12.0, -8.0, 0.5, disabled=not controls_active)
                with i_col5:
                    with st.container(border=True):
                        st.markdown('<div class="section-label">Chord</div>', unsafe_allow_html=True)
                        chord_layer = st.selectbox("Chord layer", choices, index=_idx(defaults[4]), disabled=not controls_active, label_visibility="collapsed")
                        chord_gain_db = st.slider("Chord gain (dB)", -24.0, 12.0, -3.0, 0.5, disabled=not controls_active)
                if synthesizer_type == SYNTH_GENERALUSER_GS:
                    with i_col6:
                        with st.container(border=True):
                            st.markdown('<div class="section-label">Solo</div>', unsafe_allow_html=True)
                            solo_layer = st.selectbox("Solo layer", choices, index=_idx(defaults[5]), disabled=not controls_active, label_visibility="collapsed")
                            solo_gain_db = st.slider("Solo gain (dB)", -24.0, 12.0, -1.0, 0.5, disabled=not controls_active)

    # =========================================================================
    # Row 3: Photo analysis
    # =========================================================================
    with st.expander("Photo analysis", expanded=False):
        if result is None:
            st.info("Run the app once to display the photo-derived maps and analysis metrics.")
        else:
            _maps = result.get("display_maps", result["maps"])
            _feats = result.get("display_features", result["features"])
            pa_col1, pa_col2 = st.columns([2, 1], gap="large")
            with pa_col1:
                for _key, _title, _cmap in [
                    ("luminance", "Luminance map", "gray"),
                    ("edge_map", "Edge strength map", "gray"),
                    ("fft_log_magnitude", "2D Fourier log-magnitude", "gray"),
                    ("shadow_highlight_map", "Highlights (red) · shadows (blue)", None),
                ]:
                    st.markdown(f'<div class="section-label">{_title}</div>', unsafe_allow_html=True)
                    st_image_full_width(plot_map(_maps[_key], _title, _cmap))
            with pa_col2:
                st.markdown('<div class="section-label">Metrics</div>', unsafe_allow_html=True)
                _m = _feats
                st.markdown(
                    '<div class="metric-grid">'
                    f'<div class="metric-card"><b>Brightness</b>{_m["mean_brightness"]:.3f}</div>'
                    f'<div class="metric-card"><b>Contrast</b>{_m["contrast"]:.3f}</div>'
                    f'<div class="metric-card"><b>Saturation</b>{_m["mean_saturation"]:.3f}</div>'
                    f'<div class="metric-card"><b>Shadows</b>{format_percent(_m["shadow_proportion"])}</div>'
                    f'<div class="metric-card"><b>Highlights</b>{format_percent(_m["highlight_proportion"])}</div>'
                    f'<div class="metric-card"><b>Edge density</b>{format_percent(_m["edge_density"])}</div>'
                    f'<div class="metric-card"><b>Texture entropy</b>{_m["texture_entropy"]:.3f}</div>'
                    f'<div class="metric-card"><b>Symmetry</b>{_m["symmetry_score"]:.3f}</div>'
                    f'<div class="metric-card"><b>Saliency peak</b>{_m["saliency_peak"]:.3f}</div>'
                    f'<div class="metric-card"><b>Fourier low</b>{format_percent(_m["low_frequency_energy"])}</div>'
                    f'<div class="metric-card"><b>Fourier mid</b>{format_percent(_m["mid_frequency_energy"])}</div>'
                    f'<div class="metric-card"><b>Fourier high</b>{format_percent(_m["high_frequency_energy"])}</div>'
                    f'<div class="metric-card"><b>Peak score</b>{_m["periodic_peak_score"]:.3f}</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )

    # =========================================================================
    # Row 4: Audio analysis
    # =========================================================================
    with st.expander("Audio analysis", expanded=False):
        if result is None:
            st.info("Run the app once to display the audio frequency plots.")
        else:
            _audio_arr = result["audio"]
            _evts = result["events"]
            _sr = int(result["sample_rate"])
            _dur = result["info"].duration
            _plots = [
                ("Full Fourier magnitude", plot_frequency(_audio_arr, _sr, "Full Fourier magnitude")),
                ("Waveform", plot_waveform(_audio_arr, _sr, "Waveform")),
            ]
            for _lk, _lt in [("main", "Main"), ("texture", "Texture"), ("bass", "Bass"), ("pad", "Pad"), ("chord", "Chord")]:
                _plots.append((_lt, plot_frequency(render_events(_evts, _dur, _sr, layer=_lk), _sr, _lt)))
            if result["info"].solo_instrument != "none":
                _plots.append(("Solo", plot_frequency(render_events(_evts, _dur, _sr, layer="solo"), _sr, "Solo")))

            _aa_cols = st.columns(3, gap="medium")
            for _pi, (_pt, _pimg) in enumerate(_plots):
                with _aa_cols[_pi % 3]:
                    st.markdown(f'<div class="section-label">{_pt}</div>', unsafe_allow_html=True)
                    st_image_full_width(_pimg)

    # =========================================================================
    # Computation block — runs only when run_requested is True
    # =========================================================================
    if st.session_state.run_requested and uploaded_image is not None:
        from composition import generate_composition

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
                    "image_id": uploaded_hash,
                    "bar_min": mn,
                    "bar_max": mx,
                    "bar_default": df,
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
                    main="Soft piano",
                    texture="Harp",
                    bass="Cello-like bass",
                    pad="Warm pad",
                    chord="Soft piano",
                    solo="Flute",
                    mapping="Scientific",
                    bpm=None,
                    gains=[0.0, -2.0, 0.0, -8.0, -3.0, -1.0],
                    advanced_params=advanced_params,
                )
                analysis = original_analysis

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
                    hashlib.sha256(f"{uploaded_hash}:{random_factor}:{analysis_params_signature}".encode()).hexdigest()[:16],
                    16,
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
                    main=main_layer,
                    texture=texture_layer,
                    bass=bass_layer,
                    pad=pad_layer,
                    chord=chord_layer,
                    solo=solo_layer,
                    mapping=mapping_style,
                    bpm=manual_tempo_bpm,
                    gains=[
                        main_gain_db,
                        texture_gain_db,
                        bass_gain_db,
                        pad_gain_db,
                        chord_gain_db,
                        solo_gain_db,
                    ],
                    advanced_params=advanced_params,
                )

            _progress("Generating composition", 43)
            events, info = generate_composition(
                analysis,
                effective["bars"],
                effective["complexity"],
                effective["variation"],
                effective["scale"],
                effective["synth"],
                effective["instrument_mode"],
                effective["main"],
                effective["texture"],
                effective["bass"],
                effective["pad"],
                effective["chord"],
                effective["solo"],
                effective["mapping"],
                effective["bpm"],
                *effective["gains"],
                params=advanced_params,
                step_callback=_stepper(43, 62, 7),
            )

            _progress("Rendering waveform / FluidSynth backend", 65)
            audio_arr, synth_message = render_backend(events, info, effective["synth"], params=advanced_params)

            _progress("Master bus normalization", 78)
            audio_arr = normalize_master_audio(
                audio_arr,
                target_peak=get_float_param(advanced_params, "master_target_peak", MASTER_TARGET_PEAK, 0.10, 0.98),
                target_rms=get_float_param(advanced_params, "master_target_rms", MASTER_TARGET_RMS, 0.01, 0.50),
            )

            _progress("WAV and MIDI encoding", 86)
            wav_bytes_out = audio_to_wav_bytes(audio_arr, DEFAULT_SAMPLE_RATE)
            midi_bytes_out = midi_bytes_from_events(events, info.tempo)

            _progress("MP3 encoding", 93)
            mp3_bytes_out, mp3_message = audio_to_mp3_bytes(audio_arr, DEFAULT_SAMPLE_RATE)

            st.session_state["generation_result"] = {
                "image_id": uploaded_hash,
                "image_name": input_name,
                "image_is_default": input_is_default,
                "analysis": analysis,
                "display_analysis": original_analysis,
                "features": analysis["features"],
                "maps": analysis["maps"],
                "display_features": original_analysis["features"],
                "display_maps": original_analysis["maps"],
                "events": events,
                "info": info,
                "audio": audio_arr,
                "wav_bytes": wav_bytes_out,
                "mp3_bytes": mp3_bytes_out,
                "mp3_message": mp3_message,
                "synth_message": synth_message,
                "midi_bytes": midi_bytes_out,
                "sample_rate": DEFAULT_SAMPLE_RATE,
                "parameters": effective,
            }

            progress_bar.progress(100)
            progress_status_placeholder.success("Done — 100%")
            st.session_state.run_in_progress = False
            st.session_state.run_requested = False
            st.session_state.last_run_status = "Done"
            st.rerun()

        except Exception as _exc:
            progress_bar_placeholder.empty()
            progress_status_placeholder.error(f"Could not generate the composition: {_exc}")
            st.session_state.run_in_progress = False
            st.session_state.run_requested = False
            st.session_state.last_run_status = None

    elif st.session_state.run_requested and uploaded_image is None:
        progress_status_placeholder.warning("Please choose a photo before generating.")
        st.session_state.run_in_progress = False
        st.session_state.run_requested = False


# ============================================================
# Entry point
# ============================================================
def main() -> None:
    configure_page()
    init_session_state()
    render_portfolio_links()

    app_tab, doc_fr_tab, doc_en_tab = st.tabs(
        ["App", "Documentation FR", "Documentation EN"]
    )
    with app_tab:
        render_app_tab()
    with doc_fr_tab:
        render_documentation_tab(DOC_FR_TITLES, DOC_FR_SECTIONS, "doc_fr_title")
    with doc_en_tab:
        render_documentation_tab(DOC_EN_TITLES, DOC_EN_SECTIONS, "doc_en_title")
