## Table of Contents

1. [Overview: From Photo to Musical Composition](#1-overview-from-photo-to-musical-composition)
2. [Image Representation and Luminance Analysis](#2-image-representation-and-luminance-analysis)
3. [Spatial Descriptors: Contrast, Edges, Texture and Symmetry](#3-spatial-descriptors-contrast-edges-texture-and-symmetry)
4. [Fourier-Domain Descriptors of the Photo](#4-fourier-domain-descriptors-of-the-photo)
5. [Color Palette Trajectory and Harmonic Diversity](#5-color-palette-trajectory-and-harmonic-diversity)
6. [Automatic Musical Parameters](#6-automatic-musical-parameters)
7. [Melody, Chords and Layered Composition](#7-melody-chords-and-layered-composition)
8. [Instrument Synthesis Without Learning Models](#8-instrument-synthesis-without-learning-models)
9. [Random Factor and Controlled Perturbations](#9-random-factor-and-controlled-perturbations)
10. [Audio Rendering, MIDI Export and Analysis Plots](#10-audio-rendering-midi-export-and-analysis-plots)
11. [Parameter Guide](#11-parameter-guide)
12. [Limitations and Interpretation](#12-limitations-and-interpretation)

---

## 1. Overview: From Photo to Musical Composition

This application transforms a still image into a short musical composition by extracting deterministic visual descriptors from the photo and mapping them to musical decisions.

The goal is not to classify the semantic content of the image, nor to use a trained model to guess what the image represents.
Instead, the app uses classical signal and image processing tools: luminance analysis, gradients, local contrast, texture entropy, symmetry, dominant color palette extraction, and two-dimensional Fourier analysis.

The general pipeline is:

$$
\text{photo} \rightarrow \text{visual descriptors} \rightarrow \text{musical parameters} \rightarrow \text{note events} \rightarrow \text{audio and MIDI}
$$

The mapping is deterministic when the random factor is set to zero: the same input photo and the same parameters produce the same musical output.
This makes the app closer to an interpretable sonification system than to a random music generator.

The composition is organized into five musical layers:

| Layer | Role |
|---|---|
| Main | principal melodic contour |
| Texture | arpeggios, highlights and small rhythmic elements |
| Bass | low-frequency harmonic foundation |
| Pad | long atmospheric sustained tones |
| Chord | harmonic support and chord accents |

The user can let the app choose the instruments automatically from the image features, or select the instruments manually and adjust the gain of each layer in decibels.
A default image may be loaded only to make the app immediately testable; the user can replace it with any uploaded photo.

---

## 2. Image Representation and Luminance Analysis

The input image is first converted to RGB and normalized in $[0,1]$.
In the current version, the analysis keeps the original image resolution, so the global descriptors are computed from the uploaded image size.
This choice preserves fine image details, but it can make the first analysis slower for very large photos.

The luminance image is computed from the RGB channels using perceptual weighting:

$$
Y(x,y) = 0.2126 R(x,y) + 0.7152 G(x,y) + 0.0722 B(x,y)
$$

The luminance image is the central representation used for most structural descriptors.
It is also displayed in the Photo analysis panel as the luminance map.

The global brightness is the mean luminance:

$$
\mu_Y = \frac{1}{HW}\sum_{x,y} Y(x,y)
$$

The contrast is the standard deviation of luminance:

$$
\sigma_Y = \sqrt{\frac{1}{HW}\sum_{x,y}(Y(x,y)-\mu_Y)^2}
$$

The dynamic range is estimated from robust percentiles:

$$
D_Y = P_{95}(Y) - P_{5}(Y)
$$

This avoids making the dynamic range too sensitive to a few isolated pixels.
The app also detects shadow and highlight regions from luminance thresholds derived from low and high percentiles.
The shadow proportion and highlight proportion influence the musical mood, the bass weight, the texture events and the automatic scale choice.

---

## 3. Spatial Descriptors: Contrast, Edges, Texture and Symmetry

### 3.1 Gradient and Edge Strength

Edges are extracted from the luminance image using spatial gradients.
Let $\partial_x Y$ and $\partial_y Y$ denote the horizontal and vertical derivatives.
The edge magnitude is:

$$
G(x,y) = \sqrt{(\partial_x Y(x,y))^2 + (\partial_y Y(x,y))^2}
$$

The magnitude map is normalized in $[0,1]$ and displayed as the edge strength map.
The edge density is the proportion of pixels whose normalized gradient magnitude is above an adaptive threshold.
It is used musically to control rhythmic activity, attack sharpness and tempo.

### 3.2 Texture Entropy

The app computes a texture entropy from the histogram of the normalized edge map.
If $p_k$ denotes the probability of bin $k$ in the edge histogram, the normalized entropy is:

$$
H_{\text{tex}} = -\frac{1}{\log_2 K}\sum_{k=1}^{K} p_k \log_2(p_k)
$$

where $K$ is the number of histogram bins.
A smooth image has a low texture entropy, while a highly irregular image has a higher entropy.

The default composition complexity is computed from this descriptor:

$$
C = \operatorname{clip}\left(0.25 + 0.65 H_{\text{tex}},\;0.25,\;0.90\right)
$$

Therefore, more textured images naturally produce denser musical material.

### 3.3 Symmetry

The app computes left-right and top-bottom symmetry from the luminance image:

$$
S_{LR} = 1 - \frac{1}{HW}\sum_{x,y}\left|Y(x,y)-Y(W-1-x,y)\right|
$$

$$
S_{TB} = 1 - \frac{1}{HW}\sum_{x,y}\left|Y(x,y)-Y(x,H-1-y)\right|
$$

The final symmetry score is:

$$
S = 0.70S_{LR} + 0.30S_{TB}
$$

The default variation strength is then:

$$
V = \operatorname{clip}\left(0.25 + 0.60(1-S),\;0.25,\;0.85\right)
$$

A symmetric image therefore tends to generate a stable and repetitive composition, while an asymmetric image tends to generate stronger musical evolution.

### 3.4 Gradient Orientation and Spatial Accents

The app also estimates whether the image contains predominantly horizontal, vertical or diagonal gradient structures.
Horizontal structures tend to favor longer legato-like durations.
Vertical and diagonal structures tend to favor sharper attacks, offbeat events and more articulated textures.

The image is also split into four quadrants.
The average brightness of each quadrant is used as a weak accent profile for chord hits and dynamic emphasis inside each bar.

---

## 4. Fourier-Domain Descriptors of the Photo

### 4.1 Two-Dimensional Fourier Transform

The luminance image is analyzed in the Fourier domain.
After subtracting the mean luminance and applying a separable Hanning window, the centered 2D Fourier transform is computed:

$$
F(u,v) = \mathcal{F}\left\{(Y(x,y)-\mu_Y)w(x,y)\right\}
$$

The displayed Fourier map is:

$$
\log(1+|F(u,v)|)
$$

normalized for visualization.
The logarithm is necessary because the magnitude spectrum usually has a very large dynamic range.

### 4.2 Frequency Bands

Let $r(u,v)$ be the normalized radial frequency, where $r=0$ corresponds to the center of the Fourier plane and $r=1$ corresponds to the maximum available radial frequency.
The app separates Fourier energy into three bands:

| Band | Radial range | Visual meaning |
|---|---:|---|
| Low frequencies | $0.025 \leq r < 0.14$ | large smooth structures and illumination variations |
| Mid frequencies | $0.14 \leq r < 0.34$ | medium-scale shapes and transitions |
| High frequencies | $r \geq 0.34$ | edges, fine details, micro-textures and noise |

The normalized energy in a band $\mathcal{B}$ is:

$$
E_{\mathcal{B}} = \frac{\sum_{(u,v)\in\mathcal{B}} |F(u,v)|^2}{\sum_{(u,v)} |F(u,v)|^2}
$$

Low-frequency energy influences sustained layers such as pad and bass.
High-frequency energy influences arpeggio density, texture brightness and rhythmic activity.

### 4.3 Fourier Centroid and Bandwidth

The Fourier centroid is computed as:

$$
\rho_c = \frac{\sum_{u,v} r(u,v)|F(u,v)|^2}{\sum_{u,v}|F(u,v)|^2}
$$

and the Fourier bandwidth is:

$$
B = \sqrt{\frac{\sum_{u,v}(r(u,v)-\rho_c)^2|F(u,v)|^2}{\sum_{u,v}|F(u,v)|^2}}
$$

The centroid indicates whether the spectral energy is concentrated near low or high spatial frequencies.
The bandwidth measures how spread the spectrum is.
Both quantities contribute to the musical mapping, especially in Scientific mode.

### 4.4 Periodic Peak Score

The app estimates a periodic peak score from high percentiles of the non-DC Fourier power.
A high value means that a few frequencies dominate the spectrum, which often corresponds to repeated patterns, grids, stripes, textures or periodic structures.
Musically, this encourages more repetitive motifs and more loop-like harmonic behavior.

---

## 5. Color Palette Trajectory and Harmonic Diversity

A single average hue is often too poor to describe a photo.
For example, a sunset may contain orange, dark purple, pale blue and white highlights.
Reducing this to one hue would remove much of the visual identity of the image.

For this reason, the app extracts a dominant color palette using a deterministic k-means procedure in RGB-luminance space.
The method is non-learning: no neural network or pretrained model is used.

The palette extraction follows these steps:

1. represent each pixel by RGB values and luminance;
2. initialize color centers deterministically using a farthest-point rule;
3. run a small number of k-means iterations;
4. assign all pixels to the nearest color cluster;
5. compute the hue, saturation, brightness, weight and spatial centroid of each cluster;
6. order the significant color clusters from left to right.

The ordered palette defines a color trajectory:

$$
\mathcal{C}_1 \rightarrow \mathcal{C}_2 \rightarrow \cdots \rightarrow \mathcal{C}_K
$$

This trajectory drives chord progression diversity.
Color regions with different hues, brightness values or saturation levels produce different chord degrees, different tension levels and different cadence behavior.

The palette entropy is computed from the normalized cluster weights:

$$
H_{\text{pal}} = -\frac{1}{\log_2 K}\sum_{k=1}^{K} w_k\log_2(w_k)
$$

A simple palette tends to generate stable harmonic loops.
A diverse palette tends to generate longer and more varied progressions.

The app also measures hue spread and transition tension between consecutive palette regions.
Large hue distances and brightness jumps tend to create stronger harmonic motion, while small transitions tend to keep the progression more stable.

---

## 6. Automatic Musical Parameters

### 6.1 Tonal Center

The tonal center is derived from the dominant hue.
The hue angle is mapped onto the 12 chromatic pitch classes:

$$
\text{key index} = \operatorname{round}(12h) \bmod 12
$$

where $h \in [0,1)$ is the dominant hue.
The result is mapped to the usual chromatic names:

$$
C, C\#, D, D\#, E, F, F\#, G, G\#, A, A\#, B
$$

The pitch register is then shifted according to brightness.
Darker images tend to use a lower register, while brighter images tend to use a higher register.

### 6.2 Scale Selection

If the Scale menu is set to Automatic, the app chooses the scale from brightness, warmth, saturation and contrast.
The available scales are:

| Scale | Intervals from tonic |
|---|---|
| Major pentatonic | $0,2,4,7,9$ |
| Minor pentatonic | $0,3,5,7,10$ |
| Major | $0,2,4,5,7,9,11$ |
| Natural minor | $0,2,3,5,7,8,10$ |
| Dorian | $0,2,3,5,7,9,10$ |
| Lydian | $0,2,4,6,7,9,11$ |

Bright and warm images tend to select brighter modes.
Darker images tend to select darker modes such as Natural minor.
The user can override the automatic choice by selecting a scale manually.

### 6.3 Number of Bars

The app does not use an exact target duration in seconds.
Instead, it generates a composition with a number of musical bars.
The automatic limits and default value are derived from an image complexity score:

$$
B_s = 0.40H_{\text{tex}} + 0.25D_e + 0.20E_{\text{high}} + 0.15P
$$

where $H_{\text{tex}}$ is texture entropy, $D_e$ is edge density, $E_{\text{high}}$ is high-frequency Fourier energy and $P$ is the periodic peak score.

The bar settings are obtained by interpolation:

$$
B_{\min} = \operatorname{round}\left(\operatorname{interp}(B_s,[0,1],[4,8])\right)
$$

$$
B_{\max} = \operatorname{round}\left(\operatorname{interp}(B_s,[0,1],[12,24])\right)
$$

$$
B_0 = \operatorname{round}\left(\operatorname{interp}(B_s,[0,1],[6,16])\right)
$$

Simple images therefore suggest shorter compositions, while detailed images suggest longer structures.

### 6.4 Tempo

The Mapping style controls how the tempo is inferred.
In Scientific mode, tempo is strongly driven by edge density, contrast, Fourier peaks and high-frequency energy:

$$
T = 50 + 70D_e + 58\sigma_Y + 42P + 34E_{\text{high}} + 22\rho_c - 20S_h
$$

where $S_h$ is the shadow proportion.
This value is clipped to a musically usable range.

Balanced mode uses a milder version of the same principle.
Musical mode is smoother and more conservative, relying more on saturation, brightness, shadows and warmth.
Manual mode lets the user choose the BPM directly.

---

## 7. Melody, Chords and Layered Composition

### 7.1 Chord Progression

The chord progression is generated from the selected key, scale and color palette trajectory.
For a given scale, the app builds triads by taking every other scale degree:

$$
\text{chord}(d) = \{s_d, s_{d+2}, s_{d+4}\}
$$

where $s_d$ denotes the scale interval at degree $d$.

The first chord starts from the tonal center, so the listener has a clear harmonic reference.
The following chords follow the visual color movement of the photo.
Hue differences, saturation, brightness jumps, palette weights, shadows and highlights all contribute to the selected chord degrees.

### 7.2 Melody from Luminance Slices

The image is divided into vertical slices.
Each slice is summarized by its average luminance, local contrast and vertical brightness centroid.
This creates a left-to-right visual scan of the image.

A bright region located high in the image tends to produce higher melodic notes, while darker or lower regions tend to produce lower notes.
The melodic pitch is chosen from the available notes of the selected scale.

The melody is therefore not a random sequence: it is driven by the spatial distribution of brightness in the photo.

### 7.3 Musical Variation

Variation strength modifies the second part of the composition by changing melodic offsets, chord progression indexing and local note durations.
It is not white noise.
It is a structured musical evolution parameter.

A low variation strength keeps the composition stable and loop-like.
A high variation strength introduces stronger second-half changes, melodic deviations and harmonic motion.

### 7.4 Layer Organization

The final note events are assigned to layers:

| Layer | Generated content |
|---|---|
| Main | principal melody from luminance slices |
| Texture | arpeggios, highlights, small ticks and high-frequency details |
| Bass | root, fifth and octave bass patterns |
| Pad | sustained chord tones from low-frequency and smooth visual content |
| Chord | harmonic hits and chord support |

The output is therefore a mid-complex composition rather than isolated notes played one after another.

---

## 8. Instrument Synthesis Without Learning Models

The app does not use soundfonts, sample libraries or neural audio models.
Each instrument is synthesized from simple acoustic recipes: additive harmonics, inharmonic partials, vibrato, ADSR envelopes and decay laws.

The available instruments include:

| Instrument | Synthesis idea |
|---|---|
| Soft piano | harmonic partials with exponential decay |
| Music box | bright inharmonic partials with short decay |
| Bright bell | inharmonic metallic spectrum |
| Celesta | bright but softer bell-like spectrum |
| Kalimba | plucked inharmonic spectrum |
| Marimba | percussive wooden partials |
| Harp | harmonic pluck with smooth decay |
| Synth pluck | rich harmonic waveform with fast decay |
| Warm pad | slow attack, sustained harmonic layer and vibrato |
| Glass pad | smoother sustained pad with lighter vibrato |
| Cello-like bass | bowed low register with vibrato |
| Soft bass | sinusoidal low-frequency foundation |
| Bowed string | sustained string-like harmonic tone |
| Flute-like lead | nearly sinusoidal lead with vibrato |
| Clarinet-like reed | odd-harmonic reed-like spectrum |

In Automatic mode, the app chooses instruments from image descriptors.
Bright and detailed images tend to favor bell-like instruments.
Periodic images may favor kalimba or marimba.
Dark or shadowed images tend to strengthen cello-like or bass-like layers.
Smooth low-frequency images tend to reinforce pad-like layers.

In Manual mode, the user can choose the instrument of each layer and adjust its gain.
The gain in decibels is converted to a linear factor by:

$$
g = 10^{G_{\text{dB}}/20}
$$

and applied to the velocity of all note events in that layer before audio rendering.

---

## 9. Random Factor and Controlled Perturbations

The Random factor does not replace the photo-based mapping by pure randomness.
It adds controlled perturbations before the feature extraction used for generation.

Let $r$ be the Random factor in $[0,100]$ and let:

$$
\alpha = \frac{r}{100}
$$

The spatial image perturbation has standard deviation:

$$
\sigma_{\text{image}} = 0.045\alpha^2
$$

and is added to RGB values before clipping to $[0,1]$.
The Fourier-domain perturbation has standard deviation:

$$
\sigma_{\text{Fourier}} = 0.18\alpha^2
$$

and multiplies the Fourier magnitude by a log-normal perturbation:

$$
|F'(u,v)| = |F(u,v)|\exp(\eta(u,v)), \qquad \eta(u,v) \sim \mathcal{N}(0,\sigma_{\text{Fourier}}^2)
$$

The quadratic law makes small values very gentle, while high values become experimental.
The Photo analysis panel remains based on the original photo, so the displayed maps and metrics are not visually polluted by the added perturbation.

---

## 10. Audio Rendering, MIDI Export and Analysis Plots

The generated note events are rendered into a stereo waveform at:

$$
f_s = 44100\text{ Hz}
$$

Each note has a MIDI pitch, duration, velocity, instrument, pan value and layer label.
Panning is applied with an equal-power law:

$$
L = \cos\left(\frac{\pi}{4}(p+1)\right), \qquad R = \sin\left(\frac{\pi}{4}(p+1)\right)
$$

where $p \in [-1,1]$ is the pan position.

The app exports:

| Output | Description |
|---|---|
| MP3 | rendered stereo audio file |
| MIDI | symbolic representation of the generated note events |

The Audio analysis panel displays:

| Plot | Meaning |
|---|---|
| Full Fourier magnitude | global spectrum of the generated audio |
| Waveform | time-domain audio amplitude |
| Main layer Fourier | spectrum of the main melody layer |
| Texture layer Fourier | spectrum of the texture layer |
| Bass layer Fourier | spectrum of the bass layer |
| Pad layer Fourier | spectrum of the pad layer |
| Chord layer Fourier | spectrum of the chord layer |

These plots help separate what is heard globally from what each musical layer contributes spectrally.

---

## 11. Parameter Guide

| Parameter | Meaning | Automatic relation to the image |
|---|---|---|
| Number of bars | musical length of the composition | default and limits from texture entropy, edges, high-frequency Fourier energy and periodicity |
| Variation strength | structured evolution across the composition | default from image symmetry |
| Composition complexity | density of notes and texture events | default from texture entropy |
| Random factor | controlled perturbation of image and Fourier descriptors | user-controlled only |
| Scale | set of allowed notes | automatic mode from brightness, warmth, saturation and contrast |
| Mapping style (BPM) | tempo mapping behavior | Scientific, Balanced and Musical use different image-to-BPM formulas |
| Instrument layer selection | automatic or manual layer timbres | automatic mode from brightness, shadows, highlights, Fourier descriptors and color information |
| Layer gain | manual volume of each layer in dB | only visible in Manual instrument mode |

The Run button is intentionally required.
Changing a parameter does not immediately regenerate the audio.
This avoids expensive recomputation and makes the interaction more controlled.

---

## 12. Limitations and Interpretation

The app is designed as an educational and artistic sonification system.
It does not understand the semantic content of a photo.
For example, it does not know whether the image contains a face, a landscape or an object.
It only uses measurable visual features.

This is a deliberate choice.
The result remains interpretable from a signal processing point of view: brightness, contrast, edges, color trajectory and Fourier energy all have explicit roles in the generated music.

The use of original image resolution can reveal richer details, but it can also make the analysis slower on large photos.
It can also make the mapping more sensitive to camera noise, compression artifacts and tiny textures.

The generated instruments are synthetic approximations based on harmonic recipes.
They are not meant to replace professional soundfonts or sampled instruments.
Their purpose is to keep the app lightweight, deterministic and fully explainable.
