from __future__ import annotations

import hashlib
import html
import io
import inspect
import os
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st
from PIL import Image

from config import (
    DEFAULT_IMAGE_CAPTION,
    DEFAULT_IMAGE_NAME,
    DEFAULT_IMAGE_URL,
    DEFAULT_SAMPLE_RATE,
    PORTFOLIO_LINKS,
    SCALE_OPTIONS,
    SUPPORTED_IMAGE_TYPES,
    SYNTHESIZER_OPTIONS,
    SYNTH_SIMPLE,
)
from image_analysis import load_image_bytes_from_url, open_image_from_bytes
from photo_batch import generate_batch_composition
from ui import (
    configure_page,
    ensure_bytes,
    plot_frequency,
    plot_waveform,
    render_documentation_tab,
    st_image_full_width,
    DOC_EN_SECTIONS,
    DOC_EN_TITLES,
    DOC_FR_SECTIONS,
    DOC_FR_TITLES,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_open_image(data: bytes, name: str) -> Image.Image:
    return open_image_from_bytes(data, name).convert("RGB")


def _image_item_from_bytes(data: bytes, name: str) -> Dict[str, object]:
    return {
        "name": name,
        "bytes": data,
        "image_id": _sha256(data),
        "image": _safe_open_image(data, name),
    }


def _load_default_items() -> List[Dict[str, object]]:
    data = load_image_bytes_from_url(DEFAULT_IMAGE_URL)
    return [_image_item_from_bytes(data, DEFAULT_IMAGE_NAME)]


def init_session_state() -> None:
    defaults: Dict[str, object] = {
        "local_generation_result": None,
        "local_run_in_progress": False,
        "local_camera_sequence": [],
        "local_doc_fr_title": DOC_FR_TITLES[0] if DOC_FR_TITLES else "",
        "local_doc_en_title": DOC_EN_TITLES[0] if DOC_EN_TITLES else "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value



def _full_width_button_kwargs() -> Dict[str, object]:
    """Return the full-width argument supported by the installed Streamlit version."""
    params = inspect.signature(st.button).parameters
    if "width" in params:
        return {"width": "stretch"}
    if "use_container_width" in params:
        return {"use_container_width": True}
    return {}


def render_local_portfolio_links() -> None:
    """Render the local desktop header without HuggingFace and CV links."""
    hidden_platforms = {"Hugging Face", "CV FR", "CV EN"}
    links_html_parts: List[str] = []

    for item in PORTFOLIO_LINKS:
        if item.get("platform") in hidden_platforms:
            continue

        platform = html.escape(str(item.get("platform", "")))
        label = html.escape(str(item.get("label", "")))
        href = html.escape(str(item.get("url", "")))
        icon = html.escape(str(item.get("icon_url", item.get("icon", ""))))
        title = html.escape(f"Open {platform}: {label}")

        links_html_parts.append(
            f'<a class="portfolio-link icon-only" href="{href}" target="_blank" '
            f'rel="noopener noreferrer" title="{title}">'
            f'<img src="{icon}" alt="{platform}" />'
            f'</a>'
        )

    st.markdown(
        f'<div class="portfolio-links">{"".join(links_html_parts)}</div>',
        unsafe_allow_html=True,
    )

def _render_image_sequence_preview(items: List[Dict[str, object]]) -> None:
    if not items:
        st.info("No image selected yet.")
        return

    st.caption(f"{len(items)} image(s) selected. The melody will follow this order.")
    cols = st.columns(min(4, max(1, len(items))))
    for i, item in enumerate(items[:12]):
        with cols[i % len(cols)]:
            st.image(item["image"], caption=f"{i + 1}. {item['name']}")
    if len(items) > 12:
        st.caption(f"Preview limited to 12 images out of {len(items)}.")


def _load_input_items(max_images: Optional[int] = None) -> List[Dict[str, object]]:
    source_mode = st.radio(
        "Image source",
        ["Default sequence", "Upload photos", "Camera sequence"],
        horizontal=True,
        key="local_input_source_mode",
    )

    items: List[Dict[str, object]] = []

    if source_mode == "Default sequence":
        try:
            items = _load_default_items()
            st.markdown(DEFAULT_IMAGE_CAPTION)
        except Exception as exc:
            st.error(f"Could not load the default image: {exc}")

    elif source_mode == "Upload photos":
        uploads = st.file_uploader(
            "Upload one or several photos",
            type=SUPPORTED_IMAGE_TYPES,
            accept_multiple_files=True,
            key="local_multi_photo_upload",
        )
        if uploads:
            selected_uploads = uploads if max_images is None else uploads[:max_images]
            for uploaded in selected_uploads:
                try:
                    data = uploaded.getvalue()
                    items.append(_image_item_from_bytes(data, uploaded.name))
                except Exception as exc:
                    st.warning(f"Could not read {uploaded.name}: {exc}")
            if max_images is not None and len(uploads) > max_images:
                st.warning(f"Only the first {max_images} images are used.")
        else:
            st.info("Upload several photos to create a longer melody.")

    else:
        captured = st.camera_input("Take a picture", key="local_camera_input")
        c1, c2 = st.columns(2)
        with c1:
            add_clicked = st.button("Add captured photo", disabled=captured is None)
        with c2:
            clear_clicked = st.button("Clear camera sequence")

        if clear_clicked:
            st.session_state.local_camera_sequence = []
            st.rerun()

        if add_clicked and captured is not None:
            data = captured.getvalue()
            seq = list(st.session_state.get("local_camera_sequence", []))
            seq.append({"name": captured.name or f"camera_{len(seq) + 1}.jpg", "bytes": data})
            st.session_state.local_camera_sequence = seq if max_images is None else seq[:max_images]
            st.rerun()

        camera_entries = list(st.session_state.get("local_camera_sequence", []))
        if max_images is not None:
            camera_entries = camera_entries[:max_images]
        for i, entry in enumerate(camera_entries):
            try:
                data = bytes(entry["bytes"])
                name = str(entry.get("name", f"camera_{i + 1}.jpg"))
                items.append(_image_item_from_bytes(data, name))
            except Exception as exc:
                st.warning(f"Could not read camera image {i + 1}: {exc}")

    return items


def _render_options() -> Dict[str, object]:
    with st.expander("Local batch parameters", expanded=False):
        st.markdown("These parameters are applied to each image segment before concatenation.")
        c1, c2, c3 = st.columns(3)
        with c1:
            auto_bars = st.checkbox("Automatic bars per image", value=True)
            bars = st.slider("Manual bars per image", 2, 32, 8, 1, disabled=auto_bars)
            random_factor = st.slider("Random factor", 0, 100, 0, 1)
        with c2:
            complexity = st.slider("Composition complexity", 0.10, 1.00, 0.72, 0.01)
            variation = st.slider("Variation strength", 0.00, 1.00, 0.55, 0.01)
            crossfade_seconds = st.slider("Crossfade between photos (s)", 0.00, 3.00, 0.60, 0.01)
        with c3:
            scale = st.selectbox("Scale", SCALE_OPTIONS, index=0)
            synth = st.selectbox("Synthesizer", SYNTHESIZER_OPTIONS, index=SYNTHESIZER_OPTIONS.index(SYNTH_SIMPLE) if SYNTH_SIMPLE in SYNTHESIZER_OPTIONS else 0)
            mapping = st.selectbox("Tempo mapping", ["Scientific", "Balanced", "Musical", "Manual"], index=0)
            bpm = None
            if mapping == "Manual":
                bpm = st.slider("Manual tempo (BPM)", 50, 180, 100, 1)

        st.markdown("Layer gains")
        g1, g2, g3 = st.columns(3)
        with g1:
            main_gain = st.slider("Main gain (dB)", -24.0, 12.0, 0.0, 0.5)
            texture_gain = st.slider("Texture gain (dB)", -24.0, 12.0, -2.0, 0.5)
        with g2:
            bass_gain = st.slider("Bass gain (dB)", -24.0, 12.0, 0.0, 0.5)
            pad_gain = st.slider("Pad gain (dB)", -24.0, 12.0, -8.0, 0.5)
        with g3:
            chord_gain = st.slider("Chord gain (dB)", -24.0, 12.0, -3.0, 0.5)
            solo_gain = st.slider("Solo gain (dB)", -24.0, 12.0, -1.0, 0.5)

    return {
        "auto_bars": auto_bars,
        "bars": bars,
        "complexity": complexity,
        "variation": variation,
        "random_factor": random_factor,
        "scale": scale,
        "synth": synth,
        "mapping": mapping,
        "bpm": bpm,
        "instrument_mode": "Automatic",
        "main": "Soft piano",
        "texture": "Harp",
        "bass": "Cello-like bass",
        "pad": "Warm pad",
        "chord": "Soft piano",
        "solo": "Flute",
        "gains": [main_gain, texture_gain, bass_gain, pad_gain, chord_gain, solo_gain],
        "crossfade_seconds": crossfade_seconds,
        "advanced_params": {},
    }


def render_app_tab() -> None:
    # LOCAL_FULL_WIDTH_BUTTON_CSS
    # Do not use st.button(width=...) or st.button(use_container_width=...).
    # The installed Streamlit version on this machine rejects these keyword arguments.
    st.markdown(
        """
        <style>
        div[data-testid="stButton"] > button {
            width: 100%;
        }
        div[data-testid="stDownloadButton"] > button {
            width: 100%;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="app-title">Photo Sonification - Local Desktop Batch</div>
        <div class="app-subtitle">Multiple photos · Long melody · Local rendering · MP3/WAV/MIDI export</div>
        """,
        unsafe_allow_html=True,
    )

    input_col, output_col = st.columns([1.0, 1.35], gap="large")

    with input_col:
        with st.container(border=True):
            st.markdown("#### Input photos")
            items = _load_input_items(max_images=None)
            _render_image_sequence_preview(items)

            run_disabled = not items or bool(st.session_state.local_run_in_progress)
            run_clicked = st.button(
                "▶ GENERATE AUDIO",
                type="primary",
                disabled=run_disabled,
                key="local_generate_audio_button",
                **_full_width_button_kwargs(),
            )

        options = _render_options()

    with output_col:
        with st.container(border=True):
            st.markdown("#### Output audio")
            status = st.empty()
            progress = st.progress(0)

            if run_clicked and items:
                st.session_state.local_run_in_progress = True

                def _progress(label: str, percent: int) -> None:
                    status.info(f"{label} — {percent}%")
                    progress.progress(max(0, min(100, int(percent))))

                try:
                    result = generate_batch_composition(items, options=options, progress_callback=_progress)
                    st.session_state.local_generation_result = result
                    st.session_state.local_run_in_progress = False
                    status.success("Done — 100%")
                    progress.progress(100)
                    st.rerun()
                except Exception as exc:
                    st.session_state.local_run_in_progress = False
                    status.error(f"Could not generate the audio: {exc}")

            result = st.session_state.get("local_generation_result")
            if not isinstance(result, dict):
                st.info("Generated audio will appear here after you click **▶ Generate Audio**.")
                return

            info = result["info"]
            st.audio(result["wav_bytes"], format="audio/wav")
            st.markdown(
                f"Duration: **{float(info.duration):.1f} s** · Images: **{len(result['segments'])}** · Bars: **{int(info.bars)}** · Avg tempo: **{float(info.tempo):.1f} BPM**"
            )

            d1, d2, d3 = st.columns(3)
            with d1:
                st.download_button(
                    "⬇ Download MP3",
                    data=ensure_bytes(result.get("mp3_bytes") or b""),
                    file_name="photosono-local-batch.mp3",
                    mime="audio/mpeg",
                    disabled=result.get("mp3_bytes") is None,
                )
            with d2:
                st.download_button(
                    "⬇ Download WAV",
                    data=ensure_bytes(result.get("wav_bytes") or b""),
                    file_name="photosono-local-batch.wav",
                    mime="audio/wav",
                )
            with d3:
                st.download_button(
                    "⬇ Download MIDI",
                    data=ensure_bytes(result.get("midi_bytes") or b""),
                    file_name="photosono-local-batch.mid",
                    mime="audio/midi",
                )

            if result.get("mp3_bytes") is None:
                st.warning(str(result.get("mp3_message", "MP3 export unavailable.")))

            st.markdown("#### Sequence summary")
            rows = []
            for i, seg in enumerate(result["segments"]):
                seg_info = seg["info"]
                rows.append(
                    {
                        "#": i + 1,
                        "Image": seg["image_name"],
                        "Offset (s)": round(float(result["offsets"][i]), 2),
                        "Duration (s)": round(float(seg_info.duration), 2),
                        "Bars": int(seg_info.bars),
                        "Tempo": round(float(seg_info.tempo), 1),
                        "Mood": str(seg_info.mood),
                    }
                )
            st.dataframe(pd.DataFrame(rows), hide_index=True)

            st.markdown("#### Audio analysis")
            a1, a2 = st.columns(2)
            with a1:
                st.image(plot_waveform(result["audio"], DEFAULT_SAMPLE_RATE, "Long waveform"))
            with a2:
                st.image(plot_frequency(result["audio"], DEFAULT_SAMPLE_RATE, "Long Fourier magnitude"))

def main() -> None:
    configure_page()
    init_session_state()
    render_local_portfolio_links()
    app_tab, doc_fr_tab, doc_en_tab = st.tabs(["Local App", "Documentation FR", "Documentation EN"])
    with app_tab:
        render_app_tab()
    with doc_fr_tab:
        render_documentation_tab(DOC_FR_TITLES, DOC_FR_SECTIONS, "local_doc_fr_title")
    with doc_en_tab:
        render_documentation_tab(DOC_EN_TITLES, DOC_EN_SECTIONS, "local_doc_en_title")


if __name__ == "__main__":
    main()
