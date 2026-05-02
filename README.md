---
title: Photo Sonification
emoji: 🔥
colorFrom: purple
colorTo: gray
sdk: gradio
sdk_version: 6.14.0
app_file: app.py
pinned: false
license: mit
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference

# Photo Sonification

This repository contains an interactive mini app that transforms a photo into a short musical composition.

The app is designed as an educational and portfolio demo at the intersection of image processing, signal processing and audio synthesis. It does not use a trained model to interpret the semantic content of the image. Instead, it extracts deterministic visual descriptors from the photo and maps them to musical decisions such as tempo, scale, register, chord progression, melody, instrumentation and layer balance.

A Streamlit deployment is available here: https://photo-sonification.streamlit.app/

## Main features

- Load a personal image or use the default sample image.
- Analyze the photo through luminance, contrast, shadows, highlights, edges, texture entropy and symmetry.
- Extract Fourier-domain descriptors from the 2D spatial spectrum of the photo.
- Use a dominant color palette trajectory to generate more varied chord progressions.
- Convert visual information into a multi-layer musical composition.
- Generate five musical layers: main melody, texture, bass, pad and chords.
- Choose instruments automatically from image features or manually from the interface.
- Adjust manual layer gains in dB.
- Export the generated audio as MP3.
- Export the symbolic note events as MIDI.
- Display photo analysis maps and audio analysis plots.
- Read the English and French documentation tabs.

## Method overview

The app follows the pipeline:

```text
Input photo
|
+-- Image analysis
|   +-- luminance, brightness and contrast
|   +-- shadows and highlights
|   +-- edge density and texture entropy
|   +-- symmetry and spatial balance
|   +-- 2D Fourier descriptors
|   +-- dominant color palette trajectory
|
+-- Musical mapping
|   +-- key and scale
|   +-- number of bars
|   +-- tempo
|   +-- chord progression
|   +-- melody and rhythmic activity
|   +-- instrument selection
|
+-- Audio synthesis
    +-- note events
    +-- synthetic instruments
    +-- stereo rendering
    +-- MP3 and MIDI export
```

The goal is not to produce a random melody from an image. The goal is to keep a clear and explainable connection between visual descriptors and musical structure.

When the random factor is set to zero, the mapping is deterministic: the same photo and the same parameters produce the same musical output.

## Image analysis

The input image is converted to RGB and normalized in the range `[0, 1]`. The luminance image is computed using perceptual weights:

```text
Y = 0.2126 R + 0.7152 G + 0.0722 B
```

From this luminance image, the app computes brightness, contrast, dynamic range, shadow proportion, highlight proportion and spatial centroids. These features influence the global mood, register, bass strength, highlights and melodic contour.

Edges are extracted from the spatial gradient magnitude. The edge map is used to compute edge density and texture entropy. These descriptors influence rhythmic density, attack sharpness and the default composition complexity.

The app also estimates image symmetry by comparing the luminance image with its left-right and top-bottom flipped versions. This symmetry score controls the default variation strength: symmetric images tend to produce more stable musical forms, while asymmetric images tend to produce stronger musical evolution.

## Fourier-domain analysis

The app computes a 2D Fourier transform of the luminance image after mean removal and windowing. The displayed Fourier map is the log-magnitude spectrum.

The spectrum is divided into low, mid and high spatial-frequency regions:

- low frequencies describe large smooth structures and illumination variations;
- mid frequencies describe medium-scale shapes and transitions;
- high frequencies describe edges, fine details, micro-textures and noise.

Fourier descriptors are used to control sustained layers, bass weight, texture brightness, arpeggio density, rhythmic activity and scientific tempo mapping. A periodic peak score is also computed to detect repeated visual structures such as grids, stripes or strong periodic textures.

## Color palette trajectory

A single average hue is often too limited to describe a photo. For this reason, the app extracts a dominant color palette using a deterministic, non-learning k-means procedure in RGB-luminance space.

For each dominant color cluster, the app computes:

- color weight;
- hue;
- saturation;
- brightness;
- spatial centroid.

The significant color regions are ordered from left to right to create a color palette trajectory. This trajectory is used to generate more diverse chord progressions. Large hue changes, brightness jumps, saturated colors and complex palettes create stronger harmonic motion, while simple palettes tend to produce more stable harmonic loops.

## Musical mapping

### Key and scale

The tonal center is derived from the dominant hue. The hue angle is mapped onto the 12 chromatic pitch classes:

```text
C, C#, D, D#, E, F, F#, G, G#, A, A#, B
```

If the scale is set to automatic, the app selects a scale from brightness, warmth, saturation and contrast. The available scales are:

- Major pentatonic;
- Minor pentatonic;
- Major;
- Natural minor;
- Dorian;
- Lydian.

The user can also force a scale manually.

### Number of bars

The app uses a number of musical bars rather than a direct target duration in seconds. The automatic minimum, maximum and default values are estimated from texture entropy, edge density, high-frequency Fourier energy and periodicity.

Simple images tend to suggest shorter structures, while more detailed images tend to suggest longer ones.

### Tempo

The mapping style controls how the BPM is computed:

- `Scientific` gives a stronger connection to measurable descriptors such as edge density, contrast, Fourier centroid, high-frequency energy and periodicity.
- `Balanced` keeps the same idea with a softer mapping.
- `Musical` produces smoother and more conservative tempi.
- `Manual` lets the user choose the BPM directly.

### Melody and chords

The main melody is generated by scanning the image from left to right. Each vertical slice contributes brightness, contrast and vertical centroid information. Bright regions placed higher in the image tend to produce higher notes, while darker or lower regions tend to produce lower notes.

The chord progression is generated from the selected key, selected scale and color palette trajectory. The first chord gives a tonal reference, while the following chords follow the visual movement of the dominant color regions.

## Layered composition

The generated music is organized into five layers:

| Layer | Role |
|---|---|
| Main | principal melodic contour derived from luminance slices |
| Texture | arpeggios, highlight notes and small rhythmic impulses |
| Bass | low-frequency harmonic foundation |
| Pad | long atmospheric sustained tones |
| Chord | harmonic support and chord accents |

This structure makes the output more like a compact composition than a sequence of isolated notes.

## Instrument synthesis

The app does not rely on soundfonts, external sample libraries or neural audio models. Each instrument is synthesized with lightweight signal-processing recipes such as additive harmonics, inharmonic partials, vibrato, ADSR envelopes and decay laws.

Available instruments include:

- Soft piano;
- Music box;
- Bright bell;
- Celesta;
- Kalimba;
- Marimba;
- Harp;
- Synth pluck;
- Warm pad;
- Glass pad;
- Cello-like bass;
- Soft bass;
- Bowed string;
- Flute-like lead;
- Clarinet-like reed.

In automatic mode, the app chooses instruments from image descriptors. Bright and detailed images tend to favor bell-like or plucked timbres. Dark and shadowed images tend to reinforce bass-like or bowed-string layers. Smooth low-frequency images tend to favor sustained pads.

In manual mode, the user can choose the instrument of each layer and adjust its relative gain in dB.

## Random factor

The random factor adds controlled perturbations to the image and Fourier-domain analysis used for generation. It does not replace the photo-based mapping by pure randomness.

The spatial image perturbation and the Fourier perturbation both follow a quadratic law with respect to the slider value. Small values remain subtle, while high values produce more experimental variations.

The photo analysis panel remains based on the original photo so that the displayed maps and metrics are not polluted by the added perturbation.

## Repository structure

```text
.
├── app.py                # Gradio / Hugging Face Space entry point
├── app_sl.py             # Streamlit version of the app
├── documentation_en.md   # English documentation
├── documentation_fr.md   # French documentation
├── requirements.txt      # Python dependencies
├── LICENSE.txt           # License file
└── README.md             # Repository and Hugging Face Space description
```

## Installation

Clone the repository:

```bash
git clone https://github.com/trungtin-dinh/photo_sonification.git
cd photo_sonification
```

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

The repository requirements include the core packages used for numerical processing, image manipulation, plotting, audio export and the web interface.

If you want to run the Streamlit version locally and Streamlit is not already installed, install it as well:

```bash
pip install streamlit
```

## Run the Gradio app

```bash
python app.py
```

The local interface will usually be available at:

```text
http://127.0.0.1:7860
```

## Run the Streamlit app

```bash
streamlit run app_sl.py
```

The local interface will usually be available at:

```text
http://localhost:8501
```

## Hugging Face Space notes

The YAML block at the top of this README is used by Hugging Face Spaces.

The current metadata launches the Gradio version:

```yaml
sdk: gradio
app_file: app.py
```

If you want Hugging Face to launch the Streamlit version instead, update the metadata to:

```yaml
sdk: streamlit
app_file: app_sl.py
```

In that case, make sure `streamlit` is included in `requirements.txt`.

## Documentation

The repository includes two Markdown documentation files:

- `documentation_en.md` for the English documentation;
- `documentation_fr.md` for the French documentation.

These files explain the image descriptors, Fourier analysis, color palette trajectory, chord progression generation, musical mapping, synthetic instruments, random factor and audio/MIDI export.

## Notes and limitations

This app is an artistic and educational sonification system. It does not understand the semantic content of a photo. It does not know whether the image contains a person, a landscape or an object. It only uses measurable visual descriptors.

The use of original image resolution can reveal richer details, but it can also make analysis slower on large photos. It can also make the mapping more sensitive to camera noise, compression artifacts and very small textures.

The synthetic instruments are lightweight approximations. They are not meant to replace professional sampled instruments or dedicated sound libraries. Their purpose is to keep the app explainable, deterministic and easy to run online.

## License

This project is released under the MIT License.

## Author

Developed by Trung-Tin Dinh as part of a portfolio of interactive signal, audio, image and computer vision mini apps.
