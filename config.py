from __future__ import annotations

import os

# ============================================================
# App-level constants
# ============================================================

APP_TITLE = "Photo Sonification"
DEFAULT_SAMPLE_RATE = 44100
MAX_ANALYSIS_SIDE = int(os.getenv("MAX_ANALYSIS_SIDE", "512"))
MAX_RENDER_SECONDS = 120.0
MASTER_TARGET_PEAK = float(os.getenv("MASTER_TARGET_PEAK", "0.86"))
MASTER_TARGET_RMS = float(os.getenv("MASTER_TARGET_RMS", "0.16"))
FLUIDSYNTH_MASTER_GAIN = float(os.getenv("FLUIDSYNTH_MASTER_GAIN", "0.45"))

# ============================================================
# Default image
# ============================================================

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

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_SUPPORT = True
except Exception:
    HEIF_SUPPORT = False

# ============================================================
# Portfolio links
# ============================================================

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

# ============================================================
# Synthesizer identifiers
# ============================================================

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

# ============================================================
# Music theory tables
# ============================================================

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

# ============================================================
# Simple synthesizer instrument mappings
# ============================================================

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

# ============================================================
# General MIDI instrument names (programs 0–127)
# ============================================================

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
    name: f"gm_{program:03d}"
    for name, program in GENERALUSER_GS_DISPLAY_TO_PROGRAM.items()
}
GENERALUSER_GS_INTERNAL_TO_DISPLAY = {v: k for k, v in GENERALUSER_GS_DISPLAY_TO_INTERNAL.items()}

# ============================================================
# GM family ranges and per-layer instrument pools
# ============================================================

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
GM_PROGRAM_TO_FAMILY = {
    program: family
    for family, program_range in GM_FAMILY_RANGES.items()
    for program in program_range
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
        [45, 46, 47] + list(GM_FAMILY_RANGES["synth_fx"]) + list(GM_FAMILY_RANGES["ethnic"]) +
        list(GM_FAMILY_RANGES["percussive"]) + list(GM_FAMILY_RANGES["sound_fx"])
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

# Any GM program not yet in any pool falls back to the texture pool.
_missing_gm_programs = sorted(
    set(range(128)) - set().union(*[set(v) for v in GENERALUSER_GS_LAYER_POOLS.values()])
)
if _missing_gm_programs:
    GENERALUSER_GS_LAYER_POOLS["texture"] = sorted(
        set(GENERALUSER_GS_LAYER_POOLS["texture"] + _missing_gm_programs)
    )

# ============================================================
# GM program numbers used by the simple synthesizer fallback
# ============================================================

GM_PROGRAMS: dict = {
    "bowed_string": 48, "bright_bell": 14, "celesta": 8, "cello": 42,
    "clarinet_like_reed": 71, "flute_like_lead": 73, "glass_pad": 89,
    "harp": 46, "kalimba": 108, "marimba": 12, "music_box": 10,
    "soft_bass": 32, "soft_piano": 0, "synth_pluck": 84, "warm_pad": 88,
}
GM_PROGRAMS.update({f"gm_{i:03d}": i for i in range(128)})

# ============================================================
# MIDI channel assignments and percussion note map
# ============================================================

LAYER_CHANNELS = {"main": 0, "texture": 1, "bass": 2, "pad": 3, "chord": 4, "solo": 5, "other": 6}
PERCUSSION_NOTES = {"texture_tick": 75}
