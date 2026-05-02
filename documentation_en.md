## Table of Contents

1. [Overview: From Photo to Musical Composition](#1-overview-from-photo-to-musical-composition)
2. [Visual-to-Musical Mapping at a Glance](#2-visual-to-musical-mapping-at-a-glance)
3. [Image Representation and Luminance Analysis](#3-image-representation-and-luminance-analysis)
4. [Spatial Descriptors: Edges, Texture Entropy and Symmetry](#4-spatial-descriptors-edges-texture-entropy-and-symmetry)
5. [Chromatic and Color Features](#5-chromatic-and-color-features)
6. [Visual Saliency Estimation](#6-visual-saliency-estimation)
7. [Two-Dimensional Fourier Analysis](#7-two-dimensional-fourier-analysis)
8. [Automatic Musical Parameters](#8-automatic-musical-parameters)
9. [Chord Progression and Harmonic Structure](#9-chord-progression-and-harmonic-structure)
10. [Melody and Layered Composition](#10-melody-and-layered-composition)
11. [Automatic and Manual Instrument Selection](#11-automatic-and-manual-instrument-selection)
12. [Additive Synthesis and ADSR Envelopes](#12-additive-synthesis-and-adsr-envelopes)
13. [Saliency-Driven Solo Layer](#13-saliency-driven-solo-layer)
14. [Stereo Rendering and Equal-Power Panning](#14-stereo-rendering-and-equal-power-panning)
15. [Master Bus Processing](#15-master-bus-processing)
16. [MIDI Export](#16-midi-export)
17. [Random Factor and Controlled Perturbations](#17-random-factor-and-controlled-perturbations)
18. [Audio Analysis Plots](#18-audio-analysis-plots)
19. [Limitations and Interpretation](#19-limitations-and-interpretation)

---

## 1. Overview: From Photo to Musical Composition

This application converts a still image into a short multi-layer musical composition. No trained model is used at any stage. The entire pipeline consists of classical signal-processing and image-processing operations whose outputs are mapped deterministically to musical decisions.

The core idea is **sonification**: the assignment of measurable physical or perceptual attributes of a non-audio signal to audible parameters. Here the source signal is a photograph, and the target is a structured musical piece with melody, harmony, rhythm and timbre.

The processing pipeline is:

$$
\text{photo}
\;\xrightarrow{\text{analysis}}\;
\mathbf{f}
\;\xrightarrow{\text{mapping}}\;
\{\text{events}\}
\;\xrightarrow{\text{synthesis}}\;
\text{audio} + \text{MIDI}
$$

where $\mathbf{f}$ is a vector of scalar visual descriptors and $\{\text{events}\}$ is an ordered list of note events, each carrying a start time, duration, MIDI pitch, velocity, instrument identifier, stereo pan value and layer label.

The mapping is fully deterministic when the random factor is set to zero: identical input and identical parameters always produce identical output. This reproducibility makes the system interpretable and verifiable — a deliberate contrast with generative AI audio systems whose internal state is not accessible.

The composition is organized into six layers:

| Layer | Role |
|---|---|
| Main | principal melodic contour derived from luminance slices |
| Texture | arpeggios, highlight accents and rhythmic micro-events |
| Bass | low-frequency harmonic foundation |
| Pad | long atmospheric sustained tones |
| Chord | harmonic support and chord hits |
| Solo | accent melody driven by visual saliency (GeneralUser GS mode only) |

---

## 2. Visual-to-Musical Mapping at a Glance

Before entering the mathematical detail of each module, this section provides a consolidated reading of the full pipeline. Every musical decision in the composition traces back to a specific, named visual quantity. The table below is the complete map.

| Visual descriptor | How it is measured | What it controls in the music |
|---|---|---|
| **Mean luminance** (brightness) | spatial mean of the perceptual luminance field $Y$ | melodic register (dark → low octave, bright → high octave); bass weight; mood label |
| **Luminance contrast** | standard deviation of $Y$ | tempo (Scientific/Balanced modes); chord hit velocity; melodic velocity spread |
| **Shadow proportion** | fraction of pixels below an adaptive low-percentile threshold | bass velocity; scale tendency toward minor/Dorian; pad weight; tempo reduction |
| **Highlight proportion** | fraction of pixels above an adaptive high-percentile threshold | arpeggio frequency; bright-timbre affinity (bells, celesta); chord activity |
| **Edge density** | fraction of gradient-magnitude pixels above an adaptive 75th-percentile threshold | tempo (dominant term in Scientific mode); attack sharpness; rhythmic activity |
| **Texture entropy** | normalized Shannon entropy of the edge-magnitude histogram | composition complexity (note density); bar-count default; instrument brightness affinity |
| **Symmetry score** | mean absolute difference between $Y$ and its left-right / top-bottom mirrors | variation strength default (symmetric → stable loop; asymmetric → strong evolution) |
| **Dominant hue** | circular weighted mean of the hue angle, weighted by saturation and luminance | tonal key (mapped to 12 chromatic pitch classes) |
| **Warmth** | mean red-minus-blue channel difference | scale preference toward Lydian/Major vs. Dorian/Natural minor; instrument warm-tone affinity |
| **Mean saturation** | mean of the HSV saturation channel | scale selection (Dorian preference at moderate saturation); instrument colorfulness affinity |
| **Bright centroid** (horizontal) | center of mass of bright pixels along the horizontal axis | stereo pan bias of the main melody and chord layers |
| **Shadow centroid** (horizontal) | center of mass of shadow pixels along the horizontal axis | stereo pan bias of the bass layer |
| **Low Fourier energy** | fraction of non-DC power in radial frequencies $r < 0.14$ | pad velocity and sustain weight; bass strength; smooth-timbre affinity (strings, organ) |
| **High Fourier energy** | fraction of non-DC power in radial frequencies $r \geq 0.34$ | arpeggio density; texture layer brightness; tempo boost (Scientific mode); bright-timbre affinity |
| **Spectral centroid** | power-weighted mean radial frequency | tempo contribution (Scientific mode); texture density |
| **Spectral bandwidth** | power-weighted standard deviation around the centroid | arpeggio density; texture richness |
| **Periodic peak score** | ratio of extreme Fourier peak to background power | scale tendency toward pentatonic; melodic repetition; percussive-timbre affinity (kalimba, marimba) |
| **Saliency peak / area / spread** | derived from a 3-component saliency map (color rarity + luminance rarity + edge strength) | number of solo-layer accent notes; their durations; whether the solo layer is sparse or dense |
| **Saliency pixel positions** | horizontal and vertical coordinates of the most salient pixels | timing and pitch of each individual solo note |
| **Luminance slice sequence** | left-to-right scan of vertical slice energies and vertical centroids | full melodic contour of the main layer: each image column becomes one note |
| **Color palette trajectory** | ordered sequence of dominant color clusters, left to right | chord progression selection: hue diversity and brightness jumps drive harmonic variety |

A few design principles are apparent from reading this table together:

- **Tempo and rhythm** are driven primarily by spatial complexity: edge density, contrast and high Fourier energy. Smooth, low-contrast images tend to produce slow, sparse rhythms; sharp, detailed images tend to produce faster, denser ones.
- **Tonality and mode** are driven primarily by perceptual color: hue → key, brightness + warmth → mode, saturation → modal nuance.
- **Instrumentation** integrates all feature groups: dark and smooth → strings and pads; bright and detailed → bells and plucked instruments; periodic → mallet percussion.
- **Melody** has the most direct spatial encoding: the image is literally read left-to-right, top-to-bottom, with brighter high-placed regions producing higher pitches.
- **Harmony** bridges color and structure: the dominant color palette is ordered spatially and its diversity drives chord progression variety.
- **Stereo image** mirrors the spatial layout of the photo: bright regions pan the melody to the side where brightness is concentrated; shadow regions anchor the bass.

---

## 3. Image Representation and Luminance Analysis

### 2.1 Input Normalization

The input image is converted to the RGB color space and normalized so that each channel lies in $[0, 1]$. If the image has a fourth channel (RGBA), the alpha channel is discarded. Let $R, G, B : \Omega \to [0,1]$ denote the three normalized channel images over the pixel grid $\Omega$ of size $H \times W$.

### 2.2 Perceptual Luminance

A luminance image is computed using the ITU-R BT.709 perceptual weights:

$$
Y(x,y) = 0.2126\, R(x,y) + 0.7152\, G(x,y) + 0.0722\, B(x,y)
$$

These coefficients reflect the different sensitivity of the human visual system to the three primary colors: green contributes more than seventy percent of perceived brightness, red slightly more than twenty percent, and blue less than eight percent. The resulting $Y$ is the principal scalar field used for most structural descriptors.

### 2.3 Global Brightness and Contrast

The global brightness is the spatial mean of luminance:

$$
\mu_Y = \frac{1}{HW} \sum_{(x,y) \in \Omega} Y(x,y)
$$

The contrast is the standard deviation:

$$
\sigma_Y = \sqrt{\frac{1}{HW} \sum_{(x,y) \in \Omega} \bigl(Y(x,y) - \mu_Y\bigr)^2}
$$

The dynamic range is estimated from robust percentiles to avoid sensitivity to outlier pixels:

$$
D_Y = P_{95}(Y) - P_{05}(Y)
$$

where $P_q$ denotes the $q$-th percentile taken over all pixel values.

### 2.4 Shadow and Highlight Regions

Shadow and highlight masks are derived from adaptive percentile-based thresholds:

$$
\mathcal{S} = \bigl\{(x,y) : Y(x,y) < \max\bigl(0.18,\; P_{05}(Y) + 0.03\bigr)\bigr\}
$$

$$
\mathcal{H} = \bigl\{(x,y) : Y(x,y) > \min\bigl(0.82,\; P_{95}(Y) - 0.03\bigr)\bigr\}
$$

The shadow proportion and highlight proportion are:

$$
s = \frac{|\mathcal{S}|}{HW}, \qquad h = \frac{|\mathcal{H}|}{HW}
$$

These two scalars influence the musical mood, bass weight, melodic register and automatic scale selection.

### 2.5 Spatial Centroids

For musical panning, the app computes the horizontal center of mass of the bright region, the shadow region and the highlight region separately. Given a weight map $w(x,y)$, the horizontal centroid is:

$$
c_x = \frac{\sum_{(x,y)} x \cdot w(x,y)}{\sum_{(x,y)} w(x,y)}
$$

normalized so that $c_x \in [0, 1]$.

The bright centroid uses $w = \max(Y - \mu_Y, 0)$, the shadow centroid uses $w = (1-Y) \cdot \mathbf{1}_{\mathcal{S}}$, and the highlight centroid uses $w = Y \cdot \mathbf{1}_{\mathcal{H}}$. These positions control the initial pan offset of the main melody, the bass layer and the chord hits, giving the stereo image a spatial correspondence to the photograph.

---

## 4. Spatial Descriptors: Edges, Texture Entropy and Symmetry

### 3.1 Gradient-Based Edge Map

Spatial edges are extracted by computing the gradient of the luminance field. The discrete gradient components $\partial_x Y$ and $\partial_y Y$ are obtained via `numpy.gradient`, which uses second-order central differences in the interior and first-order one-sided differences at the boundaries. The edge magnitude is:

$$
G(x,y) = \sqrt{\bigl(\partial_x Y(x,y)\bigr)^2 + \bigl(\partial_y Y(x,y)\bigr)^2}
$$

The map $G$ is then normalized to $[0,1]$:

$$
\hat{G}(x,y) = \frac{G(x,y) - \min G}{\max G - \min G}
$$

The edge density is the fraction of pixels whose normalized magnitude exceeds an adaptive threshold:

$$
D_e = \frac{1}{HW}\, \bigl|\bigl\{(x,y) : \hat{G}(x,y) > \max(0.08,\; P_{75}(\hat{G}))\bigr\}\bigr|
$$

This threshold adapts to the overall edge distribution of the image, so it remains meaningful for both soft and sharp photographs. Musically, edge density controls rhythmic activity, attack sharpness and the Scientific tempo mode.

### 3.2 Texture Entropy

The normalized edge map $\hat{G}$ is treated as a spatial texture descriptor. Its histogram over $K = 64$ equally spaced bins on $[0, 1]$ defines a probability mass function $\{p_k\}$. The normalized Shannon entropy of this distribution is:

$$
H_{\mathrm{tex}} = -\frac{1}{\log_2 K} \sum_{k=1}^{K} p_k \log_2 p_k
$$

The normalization by $\log_2 K$ maps the entropy to $[0, 1]$ regardless of $K$, with $H_{\mathrm{tex}} = 0$ for a perfectly uniform edge map (all pixels identical) and $H_{\mathrm{tex}} \to 1$ for a maximally spread edge distribution.

A smooth photographic background yields low $H_{\mathrm{tex}}$. A busy scene with irregular structures and varied edge strengths yields high $H_{\mathrm{tex}}$. This descriptor drives two musical defaults:

$$
C_{\mathrm{auto}} = \operatorname{clip}\!\bigl(0.25 + 0.65\, H_{\mathrm{tex}},\; 0.25,\; 0.90\bigr)
$$

$$
B_s = 0.40\, H_{\mathrm{tex}} + 0.25\, D_e + 0.20\, E_{\mathrm{high}} + 0.15\, P
$$

where $C_{\mathrm{auto}}$ is the automatic composition complexity, $B_s$ is the bar-count score, $E_{\mathrm{high}}$ is the high Fourier band energy and $P$ is the periodic peak score (both defined in Section 6).

### 3.3 Left-Right and Top-Bottom Symmetry

Symmetry is estimated by comparing the luminance image with its reflections. Let $\tilde{Y}_{LR}(x,y) = Y(W-1-x, y)$ denote the left-right mirror and $\tilde{Y}_{TB}(x,y) = Y(x, H-1-y)$ the top-bottom mirror. The corresponding similarity scores are:

$$
S_{LR} = 1 - \frac{1}{HW}\sum_{(x,y)} \bigl|Y(x,y) - \tilde{Y}_{LR}(x,y)\bigr|
$$

$$
S_{TB} = 1 - \frac{1}{HW}\sum_{(x,y)} \bigl|Y(x,y) - \tilde{Y}_{TB}(x,y)\bigr|
$$

The combined symmetry score weights left-right symmetry more strongly:

$$
S = 0.70\, S_{LR} + 0.30\, S_{TB}
$$

The automatic variation strength is then:

$$
V_{\mathrm{auto}} = \operatorname{clip}\!\bigl(0.25 + 0.60\,(1 - S),\; 0.25,\; 0.85\bigr)
$$

A symmetric image therefore tends to produce stable, repetitive musical forms. An asymmetric image tends to produce stronger second-half evolution, greater melodic deviation and richer harmonic motion.

---

## 5. Chromatic and Color Features

### 4.1 HSV Decomposition

The hue, saturation and value (HSV) representation provides perceptually meaningful chromatic features. Starting from normalized RGB values, the value (brightness) is:

$$
V_c = \max(R, G, B)
$$

The chroma (color extent) is:

$$
\delta = V_c - \min(R, G, B)
$$

The saturation is:

$$
\text{Sat} = \begin{cases} \delta / V_c & \text{if } V_c > 0 \\ 0 & \text{otherwise} \end{cases}
$$

The hue angle in $[0,1)$ is computed from the dominant channel, following the standard formula with the result taken modulo 1.

### 4.2 Dominant Hue via Circular Weighted Mean

A single arithmetic mean of hue values is meaningless because hue is a circular quantity defined on the unit circle. The app uses a circular weighted mean. The weight of each pixel is:

$$
w(x,y) = \mathrm{Sat}(x,y) \cdot \bigl(0.25 + Y(x,y)\bigr)
$$

so that highly saturated and well-lit pixels contribute more. The mean hue angle is then:

$$
\bar{h} = \frac{1}{2\pi} \arctan_2\!\left(\sum_{(x,y)} w \sin(2\pi h),\; \sum_{(x,y)} w \cos(2\pi h)\right) \bmod 1
$$

where $\arctan_2$ returns a value in $(-\pi, \pi]$. The resulting $\bar{h} \in [0,1)$ encodes the dominant chromatic identity of the image in a manner that is invariant to the arbitrary placement of red at $h=0$ and robust to bimodal hue distributions.

### 4.3 Warmth

A scalar warmth index is defined as the average red-blue channel difference:

$$
w_{\mathrm{arm}} = \frac{1}{HW}\sum_{(x,y)} \bigl(R(x,y) - B(x,y)\bigr)
$$

A positive value indicates a warm-toned image (more red, orange or yellow), while a negative value indicates a cool-toned image (more blue or cyan). Warmth contributes to scale selection and instrument affinity scoring.

---

## 6. Visual Saliency Estimation

### 5.1 Motivation

Visual saliency is the property of a region to draw the eye. Salient regions are not simply bright or contrasted: they are visually distinctive relative to their surroundings. In this app, a saliency map guides the placement, pitch and spacing of the solo-layer accent notes, so that the most visually prominent features of the image produce the most prominent melodic events.

### 5.2 Three-Component Saliency Model

The saliency map is built from three complementary components.

**Color rarity** measures how different each pixel's color is from the image average:

$$
C_r(x,y) = \left\| \begin{pmatrix} R(x,y) \\ G(x,y) \\ B(x,y) \end{pmatrix} - \begin{pmatrix} \bar{R} \\ \bar{G} \\ \bar{B} \end{pmatrix} \right\|_2
$$

where $(\bar{R}, \bar{G}, \bar{B})$ is the mean RGB vector over all pixels. Pixels far from the global average color appear locally unusual and therefore tend to be salient.

**Luminance rarity** measures how different each pixel's brightness is from the mean:

$$
L_r(x,y) = |Y(x,y) - \mu_Y|
$$

**Edge strength** $\hat{G}(x,y)$ (defined in Section 3) contributes because high-contrast boundaries attract attention.

Both $C_r$ and $L_r$ are normalized to $[0,1]$ independently before combination. The base saliency is:

$$
\mathcal{B}(x,y) = 0.42\, \hat{G}(x,y) + 0.34\, \hat{C}_r(x,y) + 0.24\, \hat{L}_r(x,y)
$$

### 5.3 Center Bias

Natural photography tends to center subjects, and the human visual system has a documented center-viewing bias during free gaze. A Gaussian-like radial weight is therefore added:

$$
\text{CB}(x,y) = 1 - \left\|\begin{pmatrix} x/(W-1) - 0.5 \\ y/(H-1) - 0.5 \end{pmatrix}\right\|_2
$$

normalized to $[0,1]$.

The final saliency map is:

$$
\mathcal{S}(x,y) = \mathrm{normalize}_{[0,1]}\!\bigl(0.88\,\mathcal{B}(x,y) + 0.12\,\text{CB}(x,y)\bigr)
$$

### 5.4 Saliency Descriptors

The top 4% of saliency values defines the foreground mask $\mathcal{M}$. From this mask, the app extracts:

| Descriptor | Formula |
|---|---|
| Saliency peak | $\max_{(x,y)} \mathcal{S}(x,y)$ |
| Saliency mean | $\frac{1}{HW}\sum \mathcal{S}(x,y)$ |
| Saliency area | $\frac{1}{HW}|\mathcal{M}|$ |
| Saliency centroid | $(c_x, c_y)$ from weighted center of mass of $\mathcal{M}$ |
| Saliency spread | weighted standard deviation of distance to centroid, normalized |

The spread is:

$$
\sigma_{\mathcal{S}} = \operatorname{clip}\!\left(\frac{1}{0.45}\sqrt{\frac{\sum_{(x,y)} w(x,y) \bigl[(x_n - c_x)^2 + (y_n - c_y)^2\bigr]}{\sum_{(x,y)} w(x,y)}},\; 0,\; 1\right)
$$

where $x_n = x/(W-1)$, $y_n = y/(H-1)$ and $w(x,y) = \mathcal{S}(x,y) \cdot \mathbf{1}_{\mathcal{M}}$.

---

## 7. Two-Dimensional Fourier Analysis

### 6.1 Preprocessing

Before computing the 2D DFT, the luminance image is preprocessed to reduce spectral leakage. The mean luminance is subtracted (DC removal), and a separable Hanning window is applied:

$$
\tilde{Y}(x,y) = \bigl(Y(x,y) - \mu_Y\bigr) \cdot w_H(x) \cdot w_H(y)
$$

where $w_H(n) = 0.5 - 0.5\cos(2\pi n / (N-1))$ is the $N$-point Hanning window. The windowing reduces the Gibbs phenomenon that arises from treating a finite image as a periodic signal, and prevents strong boundary discontinuities from polluting the spectral estimates.

### 6.2 Centered Spectrum

The 2D DFT is computed via the FFT algorithm and immediately frequency-shifted so that the DC component is at the center of the spectrum:

$$
F(u, v) = \mathrm{FFTshift}\!\left[\,\sum_{x=0}^{W-1}\sum_{y=0}^{H-1} \tilde{Y}(x,y)\, e^{-j2\pi(ux/W + vy/H)}\right]
$$

The displayed map is the log-magnitude:

$$
M_{\log}(u,v) = \log\!\bigl(1 + |F(u,v)|\bigr)
$$

normalized to $[0,1]$ for visualization. The logarithm is necessary because the DFT magnitude has a very large dynamic range: the strongest coefficients can be orders of magnitude larger than the weakest ones.

### 6.3 Radial Frequency Bands

Let $r(u,v)$ be the normalized radial frequency, defined as the Euclidean distance from the DC center to each frequency bin, divided by the maximum available radial frequency. Three frequency bands partition the non-DC spectrum:

| Band | Radial range $r$ | Visual meaning |
|---|---|---|
| Low | $[0.025,\; 0.14)$ | large smooth structures, slow luminance gradients |
| Mid | $[0.14,\; 0.34)$ | medium-scale shapes and transitions |
| High | $[0.34,\; 1]$ | edges, fine textures, micro-details, noise |

The normalized energy in a band $\mathcal{B}$ is:

$$
E_{\mathcal{B}} = \frac{\displaystyle\sum_{(u,v)\in\mathcal{B}} |F(u,v)|^2}{\displaystyle\sum_{(u,v)\notin\mathcal{D}} |F(u,v)|^2}
$$

where $\mathcal{D}$ is the DC region $r < 0.025$, excluded from all band computations. Low-frequency energy governs the weight of sustained layers (pad, bass). High-frequency energy governs arpeggio density, texture layer brightness and the aggressiveness of the Scientific tempo formula.

### 6.4 Spectral Centroid and Bandwidth

The power-weighted centroid of the non-DC spectrum is:

$$
\rho_c = \frac{\displaystyle\sum_{(u,v)\notin\mathcal{D}} r(u,v)\,|F(u,v)|^2}{\displaystyle\sum_{(u,v)\notin\mathcal{D}} |F(u,v)|^2}
$$

and the spectral bandwidth is the power-weighted standard deviation around this centroid:

$$
B = \sqrt{\frac{\displaystyle\sum_{(u,v)\notin\mathcal{D}} \bigl(r(u,v) - \rho_c\bigr)^2 |F(u,v)|^2}{\displaystyle\sum_{(u,v)\notin\mathcal{D}} |F(u,v)|^2}}
$$

A high centroid means the spectral energy is concentrated at fine scales. A large bandwidth means the spectrum is spread across many scales. Both quantities contribute to the Scientific tempo formula and to the arpeggio density parameter.

### 6.5 Directional Frequency Energy

The angle of each frequency bin is $\theta(u,v) = \arctan_2(v, u)$. The spectrum is split into:

- **horizontal** energy: bins where $|\sin\theta| < 0.38$ (frequencies oriented along horizontal structures)
- **vertical** energy: bins where $|\cos\theta| < 0.38$
- **diagonal** energy: the complement $1 - E_h - E_v$

These directional components are not directly used for note generation in the current version, but they are computed and exported to the analysis panel.

### 6.6 Periodic Peak Score

The periodic peak score estimates how much the spectrum is dominated by a few prominent frequencies, as opposed to a broad background:

$$
P = \operatorname{clip}\!\left(\frac{\log\!\bigl(1 + P_{99.7}(|F|^2) / (P_{90}(|F|^2) + \varepsilon)\bigr)}{5},\; 0,\; 1\right)
$$

where $P_q$ denotes the $q$-th percentile over all non-DC power values and $\varepsilon = 10^{-12}$. A high $P$ indicates the presence of regular periodic structures such as grids, stripes or strong repetitive textures. Musically, it encourages repetitive motifs, pentatonic scales, loop-like harmonic behavior and percussive timbres.

---

## 8. Automatic Musical Parameters

### 7.1 Tonal Center

The dominant hue $\bar{h} \in [0,1)$ is mapped to the 12 chromatic pitch classes by:

$$
k = \operatorname{round}(12\,\bar{h}) \bmod 12
$$

The result is an index into the sequence $\{C, C\sharp, D, D\sharp, E, F, F\sharp, G, G\sharp, A, A\sharp, B\}$.

The MIDI note of the root (the lowest note of the main melodic range) is shifted by brightness:

$$
\text{root} = \operatorname{clip}\!\Bigl(\,48 + k + \operatorname{round}\!\bigl(\operatorname{interp}(\mu_Y,\,[0,1],\,[-5,7])\bigr),\; 38,\; 58\Bigr)
$$

Darker images therefore use a lower register and brighter images a higher one, consistent with common psychoacoustic associations between luminance and pitch height.

### 7.2 Scale Selection

Six modal scales are available:

| Scale | Intervals (semitones from tonic) |
|---|---|
| Major pentatonic | $0, 2, 4, 7, 9$ |
| Minor pentatonic | $0, 3, 5, 7, 10$ |
| Major (Ionian) | $0, 2, 4, 5, 7, 9, 11$ |
| Natural minor (Aeolian) | $0, 2, 3, 5, 7, 8, 10$ |
| Dorian | $0, 2, 3, 5, 7, 9, 10$ |
| Lydian | $0, 2, 4, 6, 7, 9, 11$ |

In automatic mode, the selection follows a threshold tree:

- $\mu_Y > 0.60$: Lydian if $w_{\mathrm{arm}} > 0.06$, else Major pentatonic
- $0.42 < \mu_Y \leq 0.60$: Dorian if ($w_{\mathrm{arm}} > 0.06$ and $\mathrm{Sat} > 0.38$) or $\sigma_Y > 0.22$, else Major pentatonic
- $\mu_Y \leq 0.42$: Dorian if $w_{\mathrm{arm}} > 0.05$ and $\mathrm{Sat} > 0.30$, else Natural minor

The logic reflects the standard association between brightness and major tonalities, and between darkness and minor or modal tonalities, while letting warmth and saturation introduce intermediary cases.

### 7.3 Number of Bars

The bar-count score $B_s$ defined in Section 3.2 drives three interpolated values:

$$
B_{\min} = \operatorname{round}\!\bigl(\operatorname{interp}(B_s,\,[0,1],\,[4,8])\bigr)
$$

$$
B_{\max} = \operatorname{round}\!\bigl(\operatorname{interp}(B_s,\,[0,1],\,[12,24])\bigr)
$$

$$
B_0 = \operatorname{round}\!\bigl(\operatorname{interp}(B_s,\,[0,1],\,[6,16])\bigr)
$$

$B_0$ is the default value offered to the user. Simple images suggest short compositions; complex images suggest longer ones. The user can override the number of bars within the automatically suggested range, or can enter values outside it by selecting Manual mode.

### 7.4 Tempo

Four tempo strategies are available. Let $\Delta t = 60 / T$ denote the beat period in seconds:

**Scientific** mapping uses the full set of Fourier and spatial descriptors:

$$
T = \operatorname{clip}\!\bigl(50 + 70\,D_e + 58\,\sigma_Y + 42\,P + 34\,E_{\mathrm{high}} + 22\,\rho_c - 20\,s,\; 48,\; 152\bigr)
$$

**Balanced** mapping is a softer variant:

$$
T = \operatorname{clip}\!\bigl(62 + 38\,D_e + 28\,\sigma_Y + 20\,P + 10\,E_{\mathrm{high}} - 8\,s,\; 56,\; 132\bigr)
$$

**Musical** mapping is smoother and more conservative, relying on perceptual color attributes:

$$
T = \operatorname{clip}\!\bigl(82 + 10\,\bar{\text{Sat}} + 8\,\mu_Y - 6\,s + 4\,w_{\mathrm{arm}},\; 72,\; 108\bigr)
$$

**Manual** mode lets the user specify $T$ directly in BPM.

---

## 9. Chord Progression and Harmonic Structure

### 8.1 Triads from Scale Degrees

For a scale with interval sequence $I = [i_0, i_1, \ldots, i_{n-1}]$ of length $n$, the triad rooted at degree $d$ is built by taking every other scale step:

$$
\text{chord}(d) = \bigl\{i_{d \bmod n},\; i_{(d+2) \bmod n} + 12\cdot\mathbf{1}_{d+2 \geq n},\; i_{(d+4) \bmod n} + 12\cdot\mathbf{1}_{d+4 \geq n}\bigr\}
$$

This is the standard tertian stacking used throughout Western harmonic theory. For a seven-note diatonic scale this yields major, minor and diminished triads at the appropriate degrees. For a pentatonic scale the chord members are more widely spaced, producing an open, modal sound.

### 8.2 Progression Pool

Two progression pools are available depending on scale length. For seven-note scales, the degree sequences available are $[0,4,5,3]$, $[0,5,3,4]$, $[0,2,5,4]$ and $[0,3,1,4]$. For shorter scales, simpler pools are used.

The selection is deterministic from a seed derived from visual features:

$$
\text{seed} = \operatorname{round}\!\bigl(997\,\bar{h} + 113\,P + 71\,H_{\mathrm{tex}} + 53\,c_x^{\mathcal{S}}\bigr)
$$

where $c_x^{\mathcal{S}}$ is the horizontal saliency centroid. This seed is stable under small image perturbations but changes substantially when the visual content changes.

### 8.3 Variation-Driven Progression Shift

When the variation strength exceeds 0.45, the second half of the composition uses a shifted progression index. This means the harmonic loop evolves at the midpoint, creating an A–B form typical of many musical structures without requiring a separately programmed bridge section.

---

## 10. Melody and Layered Composition

### 9.1 Available Note Set

The melodic note pool is built by enumerating all MIDI pitches of the form $\text{root} + 12k + i_j$ that lie within the range $[\text{root}+10, \text{root}+31]$, where $i_j$ ranges over the scale intervals. This confines the melody to a two-octave window centered slightly above the tonal root. The bass pool uses a lower window $[\text{root}-18, \text{root}+7]$.

### 9.2 Luminance Slice Scanning

The image is divided into $8B$ vertical slices (where $B$ is the number of bars). For each slice $i$, the average luminance, local contrast (standard deviation), and vertical brightness centroid are computed. The centroid uses a percentile-trimmed weight map:

$$
w_i(y) = \max\!\bigl(Y_i(y) - P_{35}(Y_i),\; 0\bigr)
$$

to focus on the upper luminance values within the slice.

The melodic position within the available note set is mapped from a combination of inverted vertical centroid and local energy deviation:

$$
\text{pos} = \operatorname{clip}\!\bigl(1 - c_{y,i} + 0.18\,(\bar{Y}_i - \mu_Y),\; 0,\; 1\bigr)
$$

A bright region placed high in the image (small $c_{y,i}$, large $\bar{Y}_i$) produces a high-pitched note. A dark region placed low produces a low-pitched note. This spatial-to-pitch mapping is the central expressive link between image content and musical contour.

### 9.3 Melodic Offset from Variation

The note pool is divided into four equal sections. A section-dependent offset $\delta_s \in \{0, 2, -2, 5\}$ is added to the nominal note index and scaled by the variation strength:

$$
\text{note}_{\mathrm{final}} = \text{note}_{\mathrm{nominal}} + \operatorname{round}(\delta_s \cdot V)
$$

For low $V$, the melody is nearly identical in both halves. For high $V$, the melodic contour shifts significantly in the second half.

### 9.4 Texture Layer

A texture arpeggio density parameter is derived from:

$$
\rho_{\mathrm{tex}} = \operatorname{clip}(0.20 + 0.80\,C + 0.75\,E_{\mathrm{high}} + 0.45\,B,\; 0,\; 1)
$$

where $C$ is composition complexity and $B$ is Fourier bandwidth. When $\rho_{\mathrm{tex}} > 0.28$, arpeggio events are generated at a rate of one per beat (or two per beat when $\rho_{\mathrm{tex}} > 0.55$), cycling through an extended chord pattern. Additionally, rhythmic tick events (unpitched percussion on MIDI channel 9) are added at subdivisions of the beat when $\rho_{\mathrm{tex}} > 0.18$.

### 9.5 Pad and Chord Layers

Pad events span the full duration of each bar (four beats) with a slight legato extension of 0.05 beats. Their velocity is proportional to low-frequency Fourier energy, making the pad louder when the image has smooth, large-scale structures:

$$
v_{\mathrm{pad}} = \operatorname{clip}(0.07 + 0.18\,E_{\mathrm{low}} + 0.04\,(1 - E_{\mathrm{high}}),\; 0.04,\; 0.28)
$$

Chord events are triggered once per bar (or twice when $E_{\mathrm{high}} > 0.22$), playing all three notes of the current progression chord simultaneously.

Bass events follow a root–fifth pattern: the root note at beat 1 and the perfect fifth (7 semitones above the root) at beat 3, with velocities proportional to shadow proportion and low-frequency energy.

---

## 11. Automatic and Manual Instrument Selection

### 10.1 Simple Synthesizer Mode

In Simple mode, instruments are chosen from a fixed palette of 15 internally synthesized timbres using explicit feature threshold rules. For example:

- Main layer: bright bell if $h > 0.14$ and $E_{\mathrm{high}} > 0.28$; celesta if $\mu_Y > 0.64$; kalimba if $P > 0.58$; marimba if $P > 0.48$; harp if warm and saturated; soft piano otherwise.
- Pad layer: warm pad if low-frequency energy is strong and the image is warm, or if shadows are prevalent; glass pad otherwise.

### 10.2 GeneralUser GS Mode: GM Family Scoring

In GeneralUser GS mode, each layer selects from the full 128 General MIDI programs. Selection uses a continuous affinity scoring system. Each GM program belongs to one of 16 families (piano, chromatic percussion, organ, guitar, bass, solo strings, ensemble, brass, reed, pipe, synth lead, synth pad, synth FX, ethnic, percussive, sound FX). A family weight $W_{\ell}(f)$ is defined for each layer $\ell$ and family $f$ as a linear combination of visual feature scalars:

For example, for the main layer, the piano family weight is:

$$
W_{\mathrm{main}}(\mathrm{piano}) = 0.35 + 0.35\,\lambda_{\mathrm{smooth}}
$$

where $\lambda_{\mathrm{smooth}} = \operatorname{clip}(E_{\mathrm{low}} + 0.35(1-E_{\mathrm{high}}) + 0.25\,S, 0, 1)$ is a smoothness score derived from Fourier energy and symmetry. The pipe family weight for the main layer is:

$$
W_{\mathrm{main}}(\mathrm{pipe}) = 0.18 + 0.45\,\lambda_{\mathrm{bright}} + 0.20\,\lambda_{\mathrm{smooth}}
$$

with $\lambda_{\mathrm{bright}} = \operatorname{clip}(0.55\,\mu_Y + 0.45\,h, 0, 1)$.

For individual programs within a family, additional fine-grained bonuses are added: for example, programs in the celesta/music-box group (8–14) gain a bonus proportional to highlight proportion, high Fourier energy and saliency peak.

The final score of program $p$ for layer $\ell$ is:

$$
\text{score}(p, \ell) = W_\ell(f_p) + \text{program bonus}(p) + 0.42\,u(p, \ell)
$$

where $u(p, \ell)$ is a deterministic pseudo-random jitter in $[0,1]$ derived from a SHA-256 hash of the feature vector. The jitter prevents the same few programs from being selected in every composition while keeping the selection reproducible for fixed inputs.

### 10.3 Layer Gain

The per-layer gain in decibels is applied to the velocity of every note event in that layer before audio rendering:

$$
g = 10^{G_{\mathrm{dB}} / 20}
$$

Note velocities after gain application are clipped to $[0, 1]$.

---

## 12. Additive Synthesis and ADSR Envelopes

### 11.1 ADSR Model

Each note is shaped by an Attack–Decay–Sustain–Release envelope. Given a note of $n$ samples at sample rate $f_s$, the envelope is:

$$
e[t] = \begin{cases}
t / t_A & 0 \leq t < t_A \\
1 - (1 - S_L)(t - t_A) / t_D & t_A \leq t < t_A + t_D \\
S_L & t_A + t_D \leq t < n - t_R \\
S_L \cdot (1 - (t - (n-t_R)) / t_R) & n - t_R \leq t < n
\end{cases}
$$

where $t_A, t_D, t_R$ are the attack, decay and release sample counts, and $S_L \in (0,1]$ is the sustain level. The envelope is then multiplied element-wise by the instantaneous harmonic waveform.

### 11.2 Instrument Recipes

Each instrument uses a specific combination of harmonic content and envelope parameters.

**Soft piano.** The waveform is a sum of harmonics with decreasing amplitudes:

$$
x[t] = \sum_{m \in \{1,2,3,4,5\}} a_m \sin(2\pi m f_0 t / f_s)
$$

with $(a_1, a_2, a_3, a_4, a_5) = (1, 0.42, 0.20, 0.10, 0.04)$. An exponential decay is applied on top of the ADSR: $e_{\mathrm{exp}}[t] = \exp(-2.7\, t / (n / f_s))$, modeling the natural decay of a struck string.

**Bright bell / celesta / music box / kalimba.** These instruments use inharmonic partials whose frequency ratios deviate from integers to simulate the behavior of metallic bars or plates. For the bright bell:

$$
(\text{ratios, amplitudes}) = \{(1, 1),\, (2.41, 0.55),\, (3.77, 0.30),\, (5.93, 0.16),\, (8.12, 0.06)\}
$$

These non-integer ratios are characteristic of inharmonic spectra and produce the characteristic metallic or glassy timbre. The fast exponential decay ($\tau = 4.2$) reinforces the short sustain of physical bells.

**Harp / marimba / synth pluck.** The harmonic series uses power-law amplitude decay:

$$
x[t] = \sum_{k=1}^{7} k^{-1.25} \sin(2\pi k f_0 t / f_s)
$$

The exponent $-1.25$ (between $-1$ for sawtooth and $-2$ for triangle) produces a moderately bright plucked timbre.

**Warm pad / glass pad.** These instruments use vibrato, implemented as a continuous-phase oscillator with sinusoidal frequency modulation:

$$
\phi[t] = \frac{2\pi f_0}{f_s}\sum_{\tau=0}^{t}\!\bigl(1 + 0.0025\sin(2\pi \cdot 4.5\, \tau / f_s)\bigr)
$$

$$
x[t] = 0.75\sin(\phi[t]) + 0.24\sin(2.01\,\phi[t]) + 0.12\sin(3.98\,\phi[t])
$$

The ADSR has a slow attack (up to 65% of note duration) and high sustain level (0.78), producing the characteristic slow swell.

**Cello-like bass / bowed string.** Similar vibrato model with a higher modulation depth ($0.004$) and slightly faster rate ($5.1$ Hz):

$$
x[t] = 0.75\sin(\phi[t]) + 0.33\sin(2\phi[t]) + 0.17\sin(3\phi[t])
$$

The ADSR models the bow attack ($t_A = 0.07\,\text{s}$) and long sustain.

**Clarinet-like reed.** The clarinet spectrum is dominated by odd harmonics. The waveform $x[t] = \sin(2\pi f_0 t) - 0.33\sin(6\pi f_0 t) + 0.17\sin(10\pi f_0 t)$ approximates this characteristic.

After envelope application, each note is peak-normalized and multiplied by its velocity $v \in [0,1]$, so velocity controls amplitude without distorting the timbre.

---

## 13. Saliency-Driven Solo Layer

### 12.1 Motivation

The solo layer, available only in GeneralUser GS mode, places a sparse set of accent notes at time positions and pitches derived directly from the saliency map. The idea is to make the most visually prominent features of the photograph audible as distinct melodic events, floating above the harmonic texture of the other layers.

### 12.2 Spatial Sampling of Salient Pixels

A composite saliency strength scalar is first derived:

$$
\eta = \operatorname{clip}\!\bigl(0.55\,\text{sal\_peak} + 0.25\,\text{sal\_mean} + 0.20\,(1 - \text{sal\_area}),\; 0,\; 1\bigr)
$$

This combines peak intensity, spatial density and the inverse of salient area: a focused, intense region gives a high $\eta$, while a diffuse weakly salient image gives a low $\eta$.

The number of solo notes is:

$$
N_{\mathrm{solo}} = \operatorname{clip}\!\bigl(\operatorname{round}(\operatorname{interp}(\eta,\,[0,1],\,[3,18])),\; 2,\; 22\bigr)
$$

The top-$N_{\mathrm{cand}}$ salient pixels (with $N_{\mathrm{cand}} = \max(64, 18 N_{\mathrm{solo}})$) are identified, then filtered with a spatial inhibition-of-return rule: two selected positions must be at least 5.5% of the image diagonal apart. This prevents the solo notes from clustering on a single small region.

### 12.3 Time and Pitch Assignment

The horizontal position of each selected salient pixel is mapped to time:

$$
t_k = x_k^{\mathrm{norm}} \cdot T_{\mathrm{dur}} + 0.10\,\Delta t\,\sin(1.7\,k)
$$

where $x_k^{\mathrm{norm}} \in [0,1]$ is the normalized horizontal coordinate, $T_{\mathrm{dur}}$ is the total composition duration and $\Delta t$ is the beat period. The small sinusoidal jitter prevents all notes from aligning to the horizontal pixel grid.

The vertical position maps to pitch height: high salient points (small $y^{\mathrm{norm}}$) produce higher pitches, consistently with the main melody convention:

$$
\text{note}_k = \text{melody\_notes}\!\left[\operatorname{round}\bigl((1 - y_k^{\mathrm{norm}})\,(N_{\mathrm{mel}} - 1)\bigr)\right] + 12
$$

The solo is transposed one octave above the main melody range ($+12$ semitones). Every fifth note gets an additional perfect fifth ($+7$ semitones), adding interval variety to the solo line.

Note duration is proportional to saliency strength and saliency spread:

$$
d_k = \operatorname{clip}\!\bigl((0.32 + 0.70\,\mathcal{S}(y_k, x_k) + 0.20\,\sigma_{\mathcal{S}})\,\Delta t,\; 0.18\,\Delta t,\; 1.25\,\Delta t\bigr)
$$

---

## 14. Stereo Rendering and Equal-Power Panning

### 13.1 Event-to-Sample Placement

Each note event with start time $t_{\mathrm{start}}$ is placed at sample index $n_s = \operatorname{round}(t_{\mathrm{start}} \cdot f_s)$. The synthesized waveform of length $n_{\mathrm{note}} = \operatorname{round}(d \cdot f_s)$ samples is added to a pre-allocated stereo buffer of length $\lceil (T_{\mathrm{dur}} + 0.8) \cdot f_s \rceil$ samples. The 0.8-second tail allows for the release phase of long notes near the end of the composition.

### 13.2 Equal-Power Panning

Each note carries a pan value $p \in [-1, 1]$. The stereo gain is assigned using the standard equal-power panning law:

$$
g_L = \cos\!\left(\frac{\pi}{4}(p + 1)\right), \qquad g_R = \sin\!\left(\frac{\pi}{4}(p + 1)\right)
$$

For $p = -1$ (hard left): $g_L = 1, g_R = 0$. For $p = 0$ (center): $g_L = g_R = 1/\sqrt{2}$. For $p = +1$ (hard right): $g_L = 0, g_R = 1$. The equal-power law ensures that the perceived loudness remains constant as the pan position is swept from left to right, unlike a linear law which would produce a dip at the center.

The pan values are derived from visual positions:
- Main layer: panned toward the horizontal position of the bright centroid $c_x^{\mathrm{bright}}$, with a slow sinusoidal oscillation $\sin(0.37\,i)$ indexed by slice number $i$.
- Bass layer: panned toward the shadow centroid $c_x^{\mathrm{shadow}}$.
- Chord layer: panned toward the bright centroid with reduced swing.
- Texture arpeggios: panned progressively from left to right as the arpeggio index increases.

---

## 15. Master Bus Processing

After all layers have been mixed into the stereo buffer, a master bus normalization stage is applied. It does not alter individual layer gains; it operates solely on the final stereo mix.

**DC removal.** The mean value of each channel is subtracted:

$$
x_{\mathrm{dc}}[t] = x[t] - \frac{1}{N}\sum_{\tau=0}^{N-1} x[\tau]
$$

**RMS normalization.** The root-mean-square level across all samples and both channels is computed:

$$
\text{RMS} = \sqrt{\frac{1}{2N}\sum_{t=0}^{N-1}\!\bigl(x_L[t]^2 + x_R[t]^2\bigr)}
$$

If $\text{RMS} > \text{RMS}_{\mathrm{target}} = 0.16$, the signal is scaled down by $\text{RMS}_{\mathrm{target}} / \text{RMS}$.

**Peak normalization.** If the resulting peak amplitude exceeds $\text{Peak}_{\mathrm{target}} = 0.86$, the signal is scaled by $\text{Peak}_{\mathrm{target}} / \max|x|$.

**Safety limiter.** A final hard clip to $\pm 0.98$ prevents floating-point overflow from propagating into the audio format converter.

This two-stage process (RMS then peak) ensures a consistent loudness level across compositions while preserving headroom for transients. A WAV file is written at 44100 Hz, 16-bit signed PCM, 2 channels. MP3 encoding uses an external codec if available.

---

## 16. MIDI Export

### 15.1 MIDI File Structure

The MIDI export generates a single-track, format-0 MIDI file. The timing resolution is $\text{PPQ} = 480$ pulses per quarter note. This gives a tick rate of:

$$
\text{ticks/second} = \text{PPQ} \cdot T / 60
$$

where $T$ is the tempo in BPM. The tempo is stored in the file header as microseconds per quarter note:

$$
\mu_{\text{QPB}} = \operatorname{round}(60{,}000{,}000 / T)
$$

### 15.2 Channel Assignments

Each layer is assigned a fixed MIDI channel:

| Layer | MIDI channel |
|---|---|
| Main | 0 |
| Texture | 1 |
| Bass | 2 |
| Pad | 3 |
| Chord | 4 |
| Solo | 5 |
| Percussion (texture tick) | 9 |

Program change events are emitted before the first note of each channel, using the GM program number corresponding to the selected instrument. Channel 9 is the General MIDI percussion channel and does not receive program changes.

### 15.3 Variable-Length Encoding

MIDI delta times are encoded in the variable-length quantity (VLQ) format: the binary representation of the value is split into 7-bit groups, each stored in one byte with the most significant bit set to 1 for all bytes except the last. This allows encoding tick values up to $2^{28} - 1$ with at most 4 bytes, a compact scheme suited to sparse musical events.

---

## 17. Random Factor and Controlled Perturbations

The random factor $r \in [0, 100]$ adds controlled perturbations to the image and Fourier analysis used for composition generation. It does not replace the photo-based mapping by pure randomness.

Define $\alpha = r / 100 \in [0,1]$. Two perturbation stages are applied before feature extraction:

**RGB noise.** Additive Gaussian noise is injected into the normalized RGB image:

$$
\tilde{R}(x,y) = \operatorname{clip}\!\bigl(R(x,y) + \eta_R(x,y),\; 0,\; 1\bigr), \qquad \eta_R \sim \mathcal{N}(0,\, \sigma_{\mathrm{img}}^2)
$$

with $\sigma_{\mathrm{img}} = 0.045\,\alpha^2$. The quadratic law means the perturbation is negligible for small $r$ and significant only for large $r$.

**Fourier magnitude noise.** After computing the 2D DFT, the magnitude is perturbed by a log-normal multiplicative factor:

$$
|F'(u,v)| = |F(u,v)| \cdot \exp(\eta_{uv}), \qquad \eta_{uv} \sim \mathcal{N}(0,\, \sigma_{\mathrm{Fou}}^2)
$$

with $\sigma_{\mathrm{Fou}} = 0.18\,\alpha^2$. The log-normal distribution ensures the magnitude remains strictly positive and that the perturbation is multiplicative rather than additive, which is the more natural model for spectral amplitude uncertainty.

The photo analysis panel always displays the unperturbed analysis (computed with $r=0$) so that the visualization and metrics are not contaminated by the added noise.

**Deterministic seeding.** For a given random factor value and uploaded image, the seed is derived from the SHA-256 hash of the image bytes and the random factor value. The same image and the same random factor always produce the same perturbation, so the system remains reproducible even in its stochastic mode.

---

## 18. Audio Analysis Plots

The audio analysis panel displays the frequency content and time-domain waveform of the generated composition, broken down per layer. All frequency plots use the magnitude of the one-sided DFT:

$$
|X[k]| = \left|\sum_{n=0}^{N-1} x[n]\, e^{-j2\pi kn/N}\right|, \qquad k = 0, 1, \ldots, \lfloor N/2 \rfloor
$$

The horizontal axis is converted to frequency in Hz using $f_k = k \cdot f_s / N$.

Available plots:

| Plot | Meaning |
|---|---|
| Full Fourier magnitude | global spectrum of the mixed stereo composition |
| Waveform | time-domain amplitude envelope of the mix |
| Main layer Fourier | spectral contribution of the melody |
| Texture layer Fourier | spectral contribution of arpeggios and rhythmic events |
| Bass layer Fourier | spectral contribution of the bass line |
| Pad layer Fourier | spectral contribution of the atmospheric sustained layer |
| Chord layer Fourier | spectral contribution of the harmonic hits |
| Solo layer Fourier | spectral contribution of the saliency accent layer (GS mode) |

Each per-layer plot is rendered by re-synthesizing only the note events belonging to that layer, mixed to mono, then computing the DFT. This allows an independent inspection of each layer's spectral content and verifies that bass events occupy low frequencies, texture events occupy mid-to-high frequencies, and pads occupy the low-mid band.

---

## 19. Limitations and Interpretation

**Semantic blindness.** The app extracts only measurable visual quantities: luminance, gradient magnitude, color statistics, spatial frequency content and saliency derived from color rarity and edge contrast. It has no representation of objects, scenes or semantics. An image of a calm forest and an abstract painting with similar brightness, edge density and color distribution will produce similar musical outputs. This is a fundamental consequence of using interpretable signal-processing features.

**Resolution sensitivity.** Because the analysis uses the full uploaded resolution (up to the configurable `MAX_ANALYSIS_SIDE` limit), the mapping can be sensitive to camera noise, JPEG compression artifacts and small high-frequency textures. These may inflate the edge density and high-frequency Fourier energy, pushing the automatic tempo and complexity toward higher values. For photographs, downsampling to 512 pixels on the longest side (the default) is generally appropriate.

**Synthetic instruments.** The Simple synthesizer uses lightweight additive recipes. They are not physically accurate models of real instruments. Their purpose is to keep the system lightweight, fully self-contained and explainable. The GeneralUser GS path uses a SoundFont rendered by FluidSynth and produces substantially more realistic timbres, but requires the SoundFont file and the FluidSynth system package to be installed.

**Musical conventions.** The chord progression generator, scale selection rules and tempo formulas all encode aesthetic decisions specific to Western tonal music. The mapping is not universal and does not represent a unique or optimal correspondence between visual features and musical parameters. It is one explicit, reproducible and inspectable design choice among many possible alternatives.

---
