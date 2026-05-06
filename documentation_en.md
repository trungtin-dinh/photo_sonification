# Photo Sonification

Course-style documentation for the English version of the application

This document is designed as an applied course note. It first presents the general idea of the application, then describes the image descriptors, the musical mapping rules and the audio rendering stage. The intended level is that of a Master's student with basic knowledge of signal processing or image processing. The necessary musical and software concepts are recalled when they appear in the model.

## Table of Contents

1. [Purpose of the App](#1-purpose-of-the-app)
2. [Conceptual Principle](#2-conceptual-principle)
3. [Pipeline](#3-pipeline)
4. [Notation and Operators](#4-notation-and-operators)
5. [Image Preprocessing](#5-image-preprocessing)
6. [Luminance, Contrast, Shadows and Highlights](#6-luminance-contrast-shadows-and-highlights)
7. [Edges, Texture and Symmetry](#7-edges-texture-and-symmetry)
8. [Color Descriptors](#8-color-descriptors)
9. [Fourier Analysis of the Image](#9-fourier-analysis-of-the-image)
10. [Visual Saliency](#10-visual-saliency)
11. [Feature Vector](#11-feature-vector)
12. [From Image Descriptors to Musical Decisions](#12-from-image-descriptors-to-musical-decisions)
13. [Automatic Structure: Complexity, Variation and Number of Bars](#13-automatic-structure-complexity-variation-and-number-of-bars)
14. [Tonality, Scale and Tempo](#14-tonality-scale-and-tempo)
15. [Harmony and Chord Progression](#15-harmony-and-chord-progression)
16. [Musical Layers](#16-musical-layers)
17. [Instrument Selection](#17-instrument-selection)
18. [Audio Rendering](#18-audio-rendering)
19. [MIDI, MP3 and Analysis Outputs](#19-midi-mp3-and-analysis-outputs)
20. [Random Factor](#20-random-factor)
21. [Parameter Reference](#21-parameter-reference)
22. [How to Interpret the Result](#22-how-to-interpret-the-result)
23. [Limitations](#23-limitations)

---

## 1. Purpose of the App

Photo Sonification converts a still image into a short musical composition.

The application does not perform semantic recognition. It does not detect faces, objects, places, emotions or scenes. It treats the image as a two-dimensional signal and extracts measurable visual descriptors: luminance, contrast, edge density, texture entropy, symmetry, color statistics, Fourier energy distribution and saliency.

These descriptors are then associated with musical variables: tonality, scale, tempo, register, note density, layer balance, instrument choice, stereo placement and melodic contour. This association is called musical mapping in this document.

The objective is not to obtain the only correct music for a photograph. No such unique answer exists. The objective is to build a deterministic and interpretable correspondence between visual structure and musical structure.

When the Random Factor parameter is set to zero, the same image and the same parameters produce the same result.

The central idea can be written as

$$
\text{image}
\xrightarrow{\text{feature extraction}}
\mathbf{f}
\xrightarrow{\text{musical mapping}}
\mathcal{E}
\xrightarrow{\text{audio synthesis}}
\text{audio} + \text{MIDI},
$$

where $\mathbf{f}$ is the feature vector and $\mathcal{E}$ is the set of generated note events.

A personal way to summarize the application is this: the photo is not translated as a sentence; it is read as a signal. The music is the trace left by that reading.

---

## 2. Conceptual Principle

A digital image can be studied as a discrete function. For an RGB image, each pixel contains three values. After normalization, the image can be written as

$$
I(x,y)=\bigl(R(x,y),G(x,y),B(x,y)\bigr),
$$

with

$$
R(x,y),G(x,y),B(x,y) \in [0,1].
$$

The application does not directly convert RGB values into sound. It first computes descriptors that have a clear signal-processing meaning.

For example:

| Image property | Signal-processing interpretation | Possible musical role |
|---|---|---|
| Mean luminance | average signal level | register, general color, scale tendency |
| Contrast | dispersion around the mean | energy, tempo, velocity |
| Edge density | local spatial variation | rhythmic density, attacks |
| High-frequency Fourier energy | fine details and rapid spatial changes | texture, brightness, tempo |
| Low-frequency Fourier energy | large smooth structures | pads, bass, sustained layers |
| Symmetry | similarity under reflection | stability or variation |
| Saliency | visually dominant regions | solo accents |

The mapping is intentionally explicit. This makes the application different from a black-box generative model. The user can inspect the descriptors and understand why a given image produced a slow, dark, smooth result or, conversely, a fast, bright, dense result.

---

## 3. Pipeline

The complete pipeline is divided into four stages.

| Stage | Input | Output | Role |
|---|---|---|---|
| Image analysis | RGB image | descriptors and visual maps | describe the image as a signal |
| Musical mapping | feature vector | tonality, tempo, layers, instruments | convert visual quantities into musical decisions |
| Event generation | musical settings | note events | build a symbolic composition |
| Rendering | note events | waveform, MIDI, MP3, plots | synthesize and export the result |

A note event is represented by

$$
e_i=(t_i,d_i,m_i,v_i,I_i,p_i,\ell_i),
$$

where:

| Symbol | Meaning |
|---|---|
| $t_i$ | start time in seconds |
| $d_i$ | duration in seconds |
| $m_i$ | MIDI pitch |
| $v_i$ | velocity or normalized amplitude |
| $I_i$ | instrument or synthesis model |
| $p_i$ | stereo pan in $[-1,1]$ |
| $\ell_i$ | layer label |

The application generates several layers. The Main layer carries the principal melody. Texture adds short events and arpeggios. Bass provides low-register support. Pad provides a sustained harmonic background. Chord adds harmonic hits. Solo adds saliency-driven accents when the GeneralUser GS mode is used.

---

## 4. Notation and Operators

| Symbol | Definition |
|---|---|
| $H,W$ | image height and width after resizing for analysis |
| $\Omega$ | pixel grid, $\Omega=\{0,\ldots,W-1\}\times\{0,\ldots,H-1\}$ |
| $R,G,B$ | normalized color channels |
| $Y$ | luminance image |
| $P_q(X)$ | $q$-th percentile of array $X$ |
| $\mu_Y$ | mean luminance |
| $\sigma_Y$ | luminance standard deviation |
| $D_Y$ | robust luminance dynamic range |
| $\hat{G}$ | normalized gradient magnitude |
| $D_e$ | edge density |
| $H_{\mathrm{tex}}$ | texture entropy |
| $S$ | symmetry score |
| $\bar{h}$ | dominant hue |
| $\overline{\mathrm{Sat}}$ | mean saturation |
| $w_{\mathrm{warm}}$ | chromatic warmth score |
| $F(u,v)$ | centered 2D Fourier transform of luminance |
| $r(u,v)$ | normalized radial spatial frequency |
| $E_{\mathrm{low}},E_{\mathrm{mid}},E_{\mathrm{high}}$ | Fourier energy proportions |
| $\rho_c$ | Fourier radial centroid |
| $B_F$ | Fourier radial bandwidth |
| $P_F$ | periodic peak score |
| $\mathcal{S}$ | saliency map |
| $T$ | tempo in beats per minute |
| $\Delta t$ | beat duration, $\Delta t=60/T$ |
| $B_{\mathrm{bars}}$ | number of musical bars |

The operator

$$
\operatorname{clip}(x,a,b)
$$

limits $x$ to the interval $[a,b]$.

The operator

$$
\operatorname{interp}(x,[a,b],[c,d])
$$

performs linear interpolation from interval $[a,b]$ to interval $[c,d]$.

The notation

$$
\operatorname{normalize}_{[0,1]}(X)
$$

means min-max normalization:

$$
\operatorname{normalize}_{[0,1]}(X)=\frac{X-\min(X)}{\max(X)-\min(X)+\varepsilon},
$$

where $\varepsilon>0$ prevents division by zero.

### 4.1 Short Technical Vocabulary

Some terms are kept in English because they correspond to interface labels, software standards or common usage in digital audio.

| Term | Meaning in this document |
|---|---|
| Mapping | correspondence between visual descriptors and musical decisions |
| MIDI | symbolic representation of music using notes, durations, velocities, instruments and channels |
| Velocity | intensity of a note in the MIDI representation; during audio rendering, it is used as a normalized amplitude before mixing |
| Register | pitch region used by the notes, for example low, middle or high |
| Stereo pan | distribution of a sound between the left and right channels |
| Waveform | time-domain audio signal, represented by a sequence of samples |
| Buffer | memory area where audio samples are accumulated before being written or played |
| Spectrogram | time-frequency representation of audio energy |
| SoundFont | sound bank used by a MIDI synthesizer to transform symbolic notes into audio |
| FluidSynth | software engine able to render MIDI events using a SoundFont |
| Synthesis engine | part of the program that transforms note events into an audio signal |
| Deterministic seed | value computed from image descriptors to obtain a pseudo-random but reproducible choice |
| Deterministic jitter | small reproducible pseudo-random perturbation used to avoid overly repetitive choices |

---

## 5. Image Preprocessing

The input file is loaded as an RGB image. EXIF orientation is corrected when available. If the image is too large, it is resized for analysis. This resizing only affects feature extraction and computation time. It does not redefine the conceptual model of the image.

The normalized RGB channels are

$$
R(x,y),G(x,y),B(x,y) \in [0,1].
$$

Large images contain more details, but they also increase the cost of Fourier analysis and saliency computation. For an online application, the analysis resolution is therefore a compromise between precision and responsiveness.

---

## 6. Luminance, Contrast, Shadows and Highlights

### 6.1 Perceptual Luminance

Many image structures are described more clearly in luminance than in raw RGB channels. The application uses the BT.709 luminance formula:

$$
Y(x,y)=0.2126R(x,y)+0.7152G(x,y)+0.0722B(x,y).
$$

The green channel has the largest coefficient because human brightness perception is more sensitive to green than to blue.

### 6.2 Mean Luminance

The mean luminance is

$$
\mu_Y=\frac{1}{HW}\sum_{(x,y)\in\Omega}Y(x,y).
$$

A low value of $\mu_Y$ indicates a globally dark image. A high value indicates a globally bright image. In the musical mapping, this quantity influences register and scale tendency.

### 6.3 Contrast

The luminance contrast is measured by the standard deviation:

$$
\sigma_Y=\sqrt{\frac{1}{HW}\sum_{(x,y)\in\Omega}\left(Y(x,y)-\mu_Y\right)^2}.
$$

A high value means that the image contains strong intensity variations. It generally leads to a more energetic musical result.

### 6.4 Robust Dynamic Range

The robust dynamic range is computed from percentiles:

$$
D_Y=P_{p_H}(Y)-P_{p_L}(Y),
$$

where $p_L$ and $p_H$ are user-controlled lower and upper percentiles. The default values are usually close to $5\%$ and $95\%$.

Percentiles are used instead of the absolute minimum and maximum because one isolated black or white pixel should not dominate the descriptor.

### 6.5 Shadow and Highlight Masks

The shadow mask is defined by

$$
\mathcal{M}_{\mathrm{shadow}}=
\left\{(x,y):Y(x,y)<\max\left(\tau_s,P_{p_L}(Y)+\delta_s\right)\right\}.
$$

The highlight mask is defined by

$$
\mathcal{M}_{\mathrm{highlight}}=
\left\{(x,y):Y(x,y)>\min\left(\tau_h,P_{p_H}(Y)-\delta_h\right)\right\}.
$$

The corresponding proportions are

$$
s=\frac{|\mathcal{M}_{\mathrm{shadow}}|}{HW},
\qquad
h=\frac{|\mathcal{M}_{\mathrm{highlight}}|}{HW}.
$$

The shadow proportion strengthens the bass and darker timbres. The highlight proportion strengthens bright attacks, bells, arpeggios and accents.

---

## 7. Edges, Texture and Symmetry

### 7.1 Gradient Magnitude

Edges are local changes in luminance. The gradient magnitude is

$$
G(x,y)=\sqrt{\left(\partial_xY(x,y)\right)^2+\left(\partial_yY(x,y)\right)^2}.
$$

It is normalized as

$$
\hat{G}(x,y)=\frac{G(x,y)-\min(G)}{\max(G)-\min(G)+\varepsilon}.
$$

### 7.2 Edge Density

The edge density is the proportion of pixels whose normalized gradient exceeds an adaptive threshold:

$$
D_e=\frac{1}{HW}\left|\left\{(x,y):\hat{G}(x,y)>\max\left(\tau_e,P_{q_e}(\hat{G})\right)\right\}\right|.
$$

The percentile term adapts the threshold to the image. The fixed threshold prevents very weak fluctuations from being counted as edges.

Musically, $D_e$ increases rhythmic activity and can raise the tempo in Scientific and Balanced modes.

### 7.3 Texture Entropy

The normalized gradient map is summarized by a histogram with $K$ bins. Let $p_k$ be the probability of bin $k$. The texture entropy is

$$
H_{\mathrm{tex}}=-\frac{1}{\log_2K}\sum_{k=1}^{K}p_k\log_2(p_k+\varepsilon).
$$

The division by $\log_2K$ approximately normalizes the value to $[0,1]$.

A smooth image produces a low entropy. A visually complex image produces a high entropy. The application uses this descriptor to estimate composition complexity and number of bars.

### 7.4 Symmetry

The image is compared with its left-right and top-bottom reflections:

$$
S_{LR}=1-\frac{1}{HW}\sum_{(x,y)\in\Omega}|Y(x,y)-Y(W-1-x,y)|,
$$

$$
S_{TB}=1-\frac{1}{HW}\sum_{(x,y)\in\Omega}|Y(x,y)-Y(x,H-1-y)|.
$$

The final score gives more weight to left-right symmetry:

$$
S=0.70S_{LR}+0.30S_{TB}.
$$

A high symmetry score corresponds to visual stability. In the application, this reduces automatic variation. A low symmetry score corresponds to stronger imbalance or directional structure. This increases variation, especially in the second half of the music.

---

## 8. Color Descriptors

### 8.1 Saturation

For each pixel, saturation is computed from RGB chroma:

$$
\mathrm{Sat}(x,y)=
\begin{cases}
\dfrac{\max(R,G,B)-\min(R,G,B)}{\max(R,G,B)}, & \max(R,G,B)>0,\\
0, & \max(R,G,B)=0.
\end{cases}
$$

The mean saturation is

$$
\overline{\mathrm{Sat}}=\frac{1}{HW}\sum_{(x,y)\in\Omega}\mathrm{Sat}(x,y).
$$

High saturation favors brighter or more colorful musical choices. Low saturation favors softer or more neutral choices.

### 8.2 Circular Mean Hue

Hue is circular. A direct arithmetic mean is incorrect because hue values near 0 and 1 represent neighboring colors, not opposite colors.

The application computes a weighted circular mean. Let $h(x,y)\in[0,1)$ be the hue. Each pixel receives the weight

$$
w(x,y)=\mathrm{Sat}(x,y)\left(0.25+Y(x,y)\right).
$$

The dominant hue is

$$
\bar{h}=\frac{1}{2\pi}\operatorname{atan2}\left(
\sum w(x,y)\sin(2\pi h(x,y)),
\sum w(x,y)\cos(2\pi h(x,y))
\right) \bmod 1.
$$

Saturated and bright pixels contribute more strongly to the tonal center.

### 8.3 Chromatic Warmth

The warmth score is

$$
w_{\mathrm{warm}}=\frac{1}{HW}\sum_{(x,y)\in\Omega}\left(R(x,y)-B(x,y)\right).
$$

Positive values indicate a warmer image. Negative values indicate a cooler image. This quantity influences scale tendency and instrument affinity.

---

## 9. Fourier Analysis of the Image

Fourier analysis describes how the energy of the luminance image is distributed across spatial frequencies.

Low spatial frequencies correspond to large smooth structures. High spatial frequencies correspond to fine details, edges, textures and noise.

### 9.1 Windowed Luminance

Before computing the FFT, the mean luminance is removed and a separable Hann window is applied:

$$
\tilde{Y}(x,y)=\left(Y(x,y)-\mu_Y\right)w_H(x)w_H(y),
$$

with

$$
w_H(n)=0.5-0.5\cos\left(\frac{2\pi n}{N-1}\right).
$$

The window reduces boundary discontinuities. Without this step, the FFT would implicitly treat the image as a periodic tile and introduce artificial frequency content at the borders.

### 9.2 Two-Dimensional Fourier Transform

The discrete two-dimensional Fourier transform is

$$
F(u,v)=\sum_{x=0}^{W-1}\sum_{y=0}^{H-1}\tilde{Y}(x,y)
\exp\left[-j2\pi\left(\frac{ux}{W}+\frac{vy}{H}\right)\right].
$$

The displayed spectrum uses the log-magnitude

$$
M_{\log}(u,v)=\log\left(1+|F(u,v)|\right),
$$

then normalizes it to $[0,1]$ for visualization. The logarithm is necessary because Fourier magnitudes often have a large dynamic range.

### 9.3 Radial Frequency

For each frequency bin, the normalized radial frequency is

$$
r(u,v)=\frac{\sqrt{u^2+v^2}}{\max\sqrt{u^2+v^2}}.
$$

The central DC region is excluded from band energy computations because it mostly contains the average component, not the spatial structure.

### 9.4 Low, Mid and High Frequency Energies

The spectrum is split into radial bands:

| Band | Typical range | Interpretation |
|---|---|---|
| Low | $[r_{DC},0.14)$ | large smooth structures |
| Mid | $[0.14,0.34)$ | intermediate-scale shapes |
| High | $[0.34,1]$ | edges, fine textures, micro-details |

For a band $\mathcal{B}$, the normalized energy is

$$
E_{\mathcal{B}}=
\frac{\sum_{(u,v)\in\mathcal{B}}|F(u,v)|^2}
{\sum_{r(u,v)\ge r_{DC}}|F(u,v)|^2+\varepsilon}.
$$

The three proportions approximately satisfy

$$
E_{\mathrm{low}}+E_{\mathrm{mid}}+E_{\mathrm{high}}\approx 1.
$$

Low-frequency energy favors sustained layers such as pad and bass. High-frequency energy increases texture, attacks, bright timbres and sometimes tempo.

### 9.5 Fourier Centroid and Bandwidth

The radial centroid is

$$
\rho_c=\frac{\sum r(u,v)|F(u,v)|^2}{\sum |F(u,v)|^2+\varepsilon}.
$$

The radial bandwidth is

$$
B_F=\sqrt{\frac{\sum \left(r(u,v)-\rho_c\right)^2|F(u,v)|^2}{\sum |F(u,v)|^2+\varepsilon}}.
$$

A high centroid means that the image contains many fine-scale structures. A high bandwidth means that energy is distributed across several spatial scales.

### 9.6 Directional Energies

The angle of a frequency bin is

$$
\theta(u,v)=\operatorname{atan2}(v,u).
$$

With an orientation tolerance $\omega_o$, the horizontal and vertical directional energies are estimated by

$$
E_{\mathrm{horizontal}}=
\frac{\sum_{|\sin\theta|<\omega_o}|F|^2}{\sum |F|^2+\varepsilon},
$$

$$
E_{\mathrm{vertical}}=
\frac{\sum_{|\cos\theta|<\omega_o}|F|^2}{\sum |F|^2+\varepsilon}.
$$

The diagonal residual is

$$
E_{\mathrm{diagonal}}=1-E_{\mathrm{horizontal}}-E_{\mathrm{vertical}}.
$$

These descriptors help interpret the photo analysis panel. They are less central than the radial band energies for musical mapping.

### 9.7 Periodic Peak Score

Repeated visual patterns produce isolated strong peaks in the Fourier spectrum. The application summarizes this property with a percentile ratio:

$$
P_F=\operatorname{clip}\left(
\frac{\log\left(1+\dfrac{P_{p_H}(|F|^2)}{P_{p_L}(|F|^2)+\varepsilon}\right)}{d_F},0,1
\right).
$$

A high value indicates a regular pattern, such as stripes, tiles, windows or repeated texture. Musically, it favors loop-like behavior, repeated motifs and mallet-like timbres.

---

## 10. Visual Saliency

Saliency estimates which regions of the image are visually dominant. In this application, saliency is not semantic: it does not try to determine whether a region contains a face, an object or text. It only measures local and global contrasts. It is computed from edge strength, color rarity, luminance rarity and a slight center bias.

### 10.1 Color Rarity

Let the mean RGB vector be

$$
\bar{\mathbf{c}}=(\bar{R},\bar{G},\bar{B}).
$$

The color rarity is

$$
C_r(x,y)=\left\|\begin{bmatrix}R(x,y)\\G(x,y)\\B(x,y)\end{bmatrix}
-\bar{\mathbf{c}}\right\|_2.
$$

A pixel is color-salient if its color differs strongly from the global average.

### 10.2 Luminance Rarity

The luminance rarity is

$$
L_r(x,y)=|Y(x,y)-\mu_Y|.
$$

Very bright and very dark pixels can both be salient when they are unusual relative to the whole image.

### 10.3 Saliency Combination

The application normalizes the edge, color rarity and luminance rarity maps. The base saliency is

$$
B_s(x,y)=w_e\hat{G}(x,y)+w_c\hat{C}_r(x,y)+w_l\hat{L}_r(x,y),
$$

where the weights are normalized internally so that

$$
w_e+w_c+w_l=1.
$$

A center bias is added:

$$
C_B(x,y)=1-\left\|\begin{bmatrix}
\dfrac{x}{W-1}-0.5\\[3pt]
\dfrac{y}{H-1}-0.5
\end{bmatrix}\right\|_2.
$$

The final saliency map is

$$
\mathcal{S}(x,y)=\operatorname{normalize}_{[0,1]}\left((1-\lambda_c)B_s(x,y)+\lambda_cC_B(x,y)\right).
$$

The center bias is deliberately weak. It reflects the common photographic tendency to place subjects near the center, without erasing the actual structure of the image.

### 10.4 Saliency Mask

A salient mask is defined by

$$
\mathcal{M}_{\mathcal{S}}=
\left\{(x,y):\mathcal{S}(x,y)\ge\max\left(\tau_{\mathcal{S}},P_{q_{\mathcal{S}}}(\mathcal{S})\right)\right\}.
$$

From this mask, the application computes peak saliency, mean saliency, saliency area, saliency centroid and saliency spread. These descriptors drive the Solo layer.

---

## 11. Feature Vector

After analysis, the application can be understood as having built the feature vector

$$
\mathbf{f}=\left[
\mu_Y,\sigma_Y,D_Y,s,h,D_e,H_{\mathrm{tex}},S,
\bar{h},\overline{\mathrm{Sat}},w_{\mathrm{warm}},
E_{\mathrm{low}},E_{\mathrm{mid}},E_{\mathrm{high}},\rho_c,B_F,P_F,
\eta_{\mathcal{S}},c_x^{\mathcal{S}},c_y^{\mathcal{S}}
\right].
$$

Here $\eta_{\mathcal{S}}$ denotes a compact saliency strength score, and $(c_x^{\mathcal{S}},c_y^{\mathcal{S}})$ denotes the saliency centroid.

The rest of the application is a deterministic function of this vector and the user parameters:

$$
\mathcal{E}=\Phi(\mathbf{f},\mathbf{p}),
$$

where $\mathbf{p}$ represents user-controlled parameters such as tempo mode, scale mode, number of bars, complexity, variation strength, instrumentation mode and layer gains.

---

## 12. From Image Descriptors to Musical Decisions

The following table gives the practical correspondence used to interpret the output. It should not be read as a general aesthetic law, but as the internal rule of the application: a variation of one descriptor leads to a predictable variation of one or several musical parameters.

| Descriptor | Musical consequence |
|---|---|
| $\mu_Y$ | register, root shift, bright/dark tendency |
| $\sigma_Y$ | energy, velocity, tempo contribution |
| $s$ | bass strength, darker timbres, tempo reduction |
| $h$ | bright timbres, accents, chord activity |
| $D_e$ | rhythmic density, attacks, tempo contribution |
| $H_{\mathrm{tex}}$ | automatic complexity and number-of-bars estimate |
| $S$ | inverse control of variation strength |
| $\bar{h}$ | tonal center |
| $\overline{\mathrm{Sat}}$ | color of scales and instruments |
| $w_{\mathrm{warm}}$ | warm/cool tendency |
| $E_{\mathrm{low}}$ | pad weight, bass weight, smooth timbres |
| $E_{\mathrm{high}}$ | texture activity, bright instruments, fast events |
| $\rho_c$ | fine-detail contribution to Scientific tempo |
| $B_F$ | richness of texture |
| $P_F$ | repetitive motifs and mallet-like timbre affinity |
| saliency peak and area | number and strength of solo accents |
| saliency position | timing and pitch of solo accents |
| bright centroid | stereo pan of the main and chord layers |
| shadow centroid | stereo pan of the bass layer |

This table should be read as a causal map inside the application. For instance, if the output is fast and dense, the likely causes are high edge density, strong high-frequency energy and high texture entropy. If the output is slow and heavy, the likely causes are a high shadow proportion, weak high-frequency energy and significant low-frequency content.

---

## 13. Automatic Structure: Complexity, Variation and Number of Bars

### 13.1 Automatic Complexity

The automatic complexity is derived from texture entropy:

$$
C_{\mathrm{auto}}=C_{\min}+(C_{\max}-C_{\min})H_{\mathrm{tex}}.
$$

The user controls the allowed range. The resulting complexity affects note density, melodic activity and texture activation.

### 13.2 Automatic Variation Strength

Variation is derived from lack of symmetry:

$$
V_{\mathrm{auto}}=V_{\min}+(V_{\max}-V_{\min})(1-S).
$$

A symmetric image gives a lower variation strength. An asymmetric image gives a higher variation strength. This rule is musically useful because symmetry often corresponds to stability, while asymmetry often suggests movement or tension.

### 13.3 Number of Bars

The number of bars is estimated from a weighted activity score:

$$
Q_B=w_tH_{\mathrm{tex}}+w_eD_e+w_hE_{\mathrm{high}}+w_pP_F.
$$

The weights are normalized internally. A higher value of $Q_B$ corresponds to stronger visual activity and therefore allows a longer composition.

The application maps $Q_B$ into valid ranges:

$$
B_{\min}=\operatorname{round}\left(\operatorname{interp}\left(Q_B,[0,1],[B_{\min}^{lo},B_{\min}^{hi}]\right)\right),
$$

$$
B_{\max}=\operatorname{round}\left(\operatorname{interp}\left(Q_B,[0,1],[B_{\max}^{lo},B_{\max}^{hi}]\right)\right),
$$

$$
B_0=\operatorname{round}\left(\operatorname{interp}\left(Q_B,[0,1],[B_0^{lo},B_0^{hi}]\right)\right).
$$

The engine enforces

$$
B_{\max}>B_{\min},
\qquad
B_0\in[B_{\min},B_{\max}].
$$

---

## 14. Tonality, Scale and Tempo

This section introduces the minimal musical conventions used by the application. Tonality defines a harmonic center of gravity. The scale defines the allowed pitches around this center. The tempo defines the temporal speed of the composition. These choices remain intentionally simple so that the link with the visual descriptors remains readable.

### 14.1 Key from Hue

The dominant hue is associated with one of the twelve pitch classes:

$$
k=\operatorname{round}(12\bar{h})\bmod 12.
$$

The pitch-class set is

$$
\{C,C\#,D,D\#,E,F,F\#,G,G\#,A,A\#,B\}.
$$

The MIDI root note is shifted according to brightness:

$$
\mathrm{root}=\operatorname{clip}\left(
48+k+\operatorname{round}\left(\operatorname{interp}(\mu_Y,[0,1],[-5,7])\right),
38,58
\right).
$$

Darker images tend to use lower registers. Brighter images tend to use higher registers.

### 14.2 Scale Selection

The application uses the following scale families.

| Scale | Intervals in semitones |
|---|---|
| Major pentatonic | $0,2,4,7,9$ |
| Minor pentatonic | $0,3,5,7,10$ |
| Major | $0,2,4,5,7,9,11$ |
| Natural minor | $0,2,3,5,7,8,10$ |
| Dorian | $0,2,3,5,7,9,10$ |
| Lydian | $0,2,4,6,7,9,11$ |

When Scale is set to Automatic, the selection depends on brightness, chromatic warmth, saturation and contrast. Bright warm images tend toward major-like or Lydian colors. Darker images tend toward natural minor or Dorian colors.

This rule should be understood as a design choice, not as a universal theory of the relation between color and harmony.

### 14.3 Tempo Modes

The application offers four tempo modes.

Scientific mode gives strong weight to structural descriptors:

$$
T=\operatorname{clip}\left(
50+70D_e+58\sigma_Y+42P_F+34E_{\mathrm{high}}+22\rho_c-20s,
T_{lo},T_{hi}
\right).
$$

Balanced mode reduces the influence of the descriptors:

$$
T=\operatorname{clip}\left(
62+38D_e+28\sigma_Y+20P_F+10E_{\mathrm{high}}-8s,
T_{lo},T_{hi}
\right).
$$

Musical mode is smoother and mostly color-based:

$$
T=\operatorname{clip}\left(
82+10\overline{\mathrm{Sat}}+8\mu_Y-6s+4w_{\mathrm{warm}},
T_{lo},T_{hi}
\right).
$$

Manual mode uses the BPM selected by the user.

The beat duration is

$$
\Delta t=\frac{60}{T}.
$$

For a $4/4$ composition with $B_{\mathrm{bars}}$ bars, the approximate duration is

$$
T_{\mathrm{dur}}=4B_{\mathrm{bars}}\Delta t.
$$

---

## 15. Harmony and Chord Progression

Harmony is represented here by chords, that is, groups of notes played simultaneously or almost simultaneously. A chord progression is a sequence of chords that repeats or evolves over the bars. The application uses simple progressions to provide a stable harmonic basis for the Main, Pad, Chord and Bass layers.

Let the selected scale be

$$
I=[i_0,i_1,\ldots,i_{n-1}],
$$

where $i_j$ is an interval in semitones from the root.

A triad on scale degree $d$ is built by stacking every other scale degree:

$$
\operatorname{chord}(d)=\{i_d,i_{d+2},i_{d+4}\},
$$

with periodic wrapping in the scale when an index exceeds the scale length.

The application selects a chord progression from a small deterministic set. For seven-note scales, examples include

$$
[0,4,5,3],\qquad [0,5,3,4],\qquad [0,2,5,4],\qquad [0,3,1,4].
$$

The selected progression depends on image descriptors through a deterministic seed:

$$
\mathrm{seed}=\operatorname{round}\left(997\bar{h}+113P_F+71H_{\mathrm{tex}}+53c_x^{\mathcal{S}}\right).
$$

If variation strength is high enough, the second half of the composition shifts the progression index. This creates a simple A/B form: the first half establishes the loop, and the second half moves it slightly.

---

## 16. Musical Layers

The composition is organized into layers in order to separate musical roles. This separation makes the result easier to read: the melody carries the main trajectory, the bass gives low-register anchoring, the pad sustains harmony, the chords mark the structure, the texture adds fast details and the solo highlights salient regions of the image.

### 16.1 Main Melody

The image is read from left to right. For $B_{\mathrm{bars}}$ bars, the image is divided into

$$
N_{\mathrm{slices}}=8B_{\mathrm{bars}}
$$

vertical slices.

For slice $i$, the application computes local luminance statistics and a vertical brightness centroid. A percentile-trimmed weight is used:

$$
w_i(y)=\max\left(Y_i(y)-P_{35}(Y_i),0\right).
$$

The normalized melodic position is

$$
\operatorname{pos}_i=\operatorname{clip}\left(1-c_{y,i}+0.18(\bar{Y}_i-\mu_Y),0,1\right).
$$

A bright region located near the top gives a higher pitch. A dark region located near the bottom gives a lower pitch. The selected position is quantized to the current scale.

Melodic density depends on Complexity. Low-complexity settings skip more slices. High-complexity settings allow more slices to produce notes.

### 16.2 Melodic Variation

The composition is divided into broad sections. A section-dependent offset is applied to the melody:

$$
\Delta m\in\{0,2,-2,5\}.
$$

The final pitch is

$$
m_{\mathrm{final}}=m_{\mathrm{base}}+\operatorname{round}(V\Delta m),
$$

where $V$ is the variation strength.

This keeps the melody tied to the image while avoiding strictly mechanical repetition.

### 16.3 Pad Layer

The Pad layer sustains the current chord over the bar. Its velocity increases with low-frequency energy:

$$
v_{\mathrm{pad}}=\operatorname{clip}\left(0.07+0.18E_{\mathrm{low}}+0.04(1-E_{\mathrm{high}}),0.04,0.28\right).
$$

A smooth image therefore creates a stronger sustained background.

### 16.4 Chord Layer

The Chord layer plays harmonic hits based on the current chord progression. If high-frequency energy exceeds the double-hit threshold, a second chord is added halfway through the bar.

This links visual detail to harmonic activity.

### 16.5 Bass Layer

The Bass layer uses a root/fifth pattern, usually placing the root on beat 1 and the fifth on beat 3.

Its velocity is

$$
v_{\mathrm{bass}}=\operatorname{clip}\left(0.30+0.55s+0.25E_{\mathrm{low}},0.22,0.86\right).
$$

Dark smooth images therefore produce stronger bass support.

### 16.6 Texture Layer

Texture density is estimated by

$$
\rho_{\mathrm{tex}}=\operatorname{clip}\left(0.20+0.80C+0.75E_{\mathrm{high}}+0.45B_F,0,1\right),
$$

where $C$ is the user-controlled complexity.

If $\rho_{\mathrm{tex}}$ exceeds the texture activation threshold, the application adds arpeggio-like events. If it exceeds a fast threshold, the arpeggio rate increases.

A separate short tick layer can also activate when texture density is high. In the MIDI export, these events are placed on the percussion channel.

### 16.7 Saliency-Driven Solo Layer

The Solo layer is available in GeneralUser GS mode. It converts salient image points into sparse melodic accents.

A saliency strength score is

$$
\eta=\operatorname{clip}\left(0.55\,\mathrm{peak}+0.25\,\mathrm{mean}+0.20(1-\mathrm{area}),0,1\right).
$$

The number of solo notes is interpolated from a user-controlled range and limited by a cap.

For a selected salient point $(x_k,y_k)$, the horizontal position becomes time:

$$
t_k=x_k^{\mathrm{norm}}T_{\mathrm{dur}}+0.10\Delta t\sin(1.7k).
$$

The vertical position becomes pitch:

$$
m_k=\mathrm{melody\_notes}\left[\operatorname{round}\left((1-y_k^{\mathrm{norm}})(N_{\mathrm{mel}}-1)\right)\right]+12.
$$

The solo is therefore a sparse melodic reading of the most visually dominant regions.

---

## 17. Instrument Selection

Instrument choice is not only aesthetic. It participates in the translation of the visual signal: a smooth dark image should be able to produce a softer and lower timbre, while a bright, contrasted or periodic image should be able to produce sharper attacks or more percussive timbres. Automatic selection therefore seeks coherence between visual descriptors, layer role and instrumental family.

### 17.1 Simple Synthesis Mode

Simple mode uses internal additive synthesis instruments. Typical examples include soft piano, harp, music box, bright bell, marimba, cello-like bass, warm pad and glass pad.

This mode is self-contained. It does not require an external SoundFont.

In Automatic mode, the application selects instruments from image descriptors. Examples:

| Visual condition | Instrument tendency |
|---|---|
| bright image with highlights | bell, celesta, music box |
| periodic image | kalimba, marimba, mallet-like timbres |
| dark smooth image | cello-like bass, bowed string, warm pad |
| smooth low-frequency image | pad, glass pad, soft piano |
| detailed high-frequency image | pluck, bell, arpeggiated timbres |

### 17.2 GeneralUser GS Mode

GeneralUser GS mode uses General MIDI program names. Rendering requires FluidSynth and a GeneralUser GS SoundFont. If they are unavailable, the application falls back to the Simple synthesis engine while preserving the same musical event structure.

Each General MIDI program belongs to a family: piano, chromatic percussion, organ, guitar, bass, strings, brass, reed, pipe, synth lead, synth pad and others.

For each layer, the application computes family affinities from image descriptors. For example, the smoothness score is

$$
\lambda_{\mathrm{smooth}}=\operatorname{clip}\left(E_{\mathrm{low}}+0.35(1-E_{\mathrm{high}})+0.25S,0,1\right).
$$

The brightness score is

$$
\lambda_{\mathrm{bright}}=\operatorname{clip}\left(0.55\mu_Y+0.45h,0,1\right).
$$

For the Main layer, an affinity with the piano family can be written as

$$
W_{\mathrm{main}}(\mathrm{piano})=0.35+0.35\lambda_{\mathrm{smooth}}.
$$

An affinity with the pipe family can be written as

$$
W_{\mathrm{main}}(\mathrm{pipe})=0.18+0.45\lambda_{\mathrm{bright}}+0.20\lambda_{\mathrm{smooth}}.
$$

Program-specific bonuses refine the selection. For example, bell-like programs receive bonuses from highlights, high-frequency energy and saliency. Bass programs receive bonuses from shadows and low-frequency energy.

A deterministic pseudo-random variation, or jitter, is added to avoid always selecting the same program for similar images:

$$
\operatorname{score}(p,\ell)=W_\ell(f_p)+\operatorname{bonus}(p)+0.42u(p,\ell),
$$

where $p$ is the program, $\ell$ is the layer, $f_p$ is the family of the program, and $u(p,\ell)$ is a deterministic pseudo-random value derived from the image descriptors.

This gives variety without losing reproducibility.

### 17.3 Manual Mode and Layer Gains

In Manual mode, the user selects the instrument for each layer.

Each layer also has a gain in decibels. The amplitude multiplier is

$$
g=10^{G_{\mathrm{dB}}/20}.
$$

The gain modifies note velocity before rendering. Final velocities are clipped to $[0,1]$.

---

## 18. Audio Rendering

Audio rendering transforms the symbolic composition into a sampled signal. At this stage, note events are no longer only abstract objects containing a pitch and a duration: they become waveforms placed in time, weighted by velocity, distributed in stereo, and then added into the same signal.

### 18.1 Stereo Buffer

Events are rendered into a stereo waveform at

$$
f_s=44100\ \mathrm{Hz}.
$$

For an event starting at time $t_i$, the first sample index is

$$
n_i=\operatorname{round}(t_if_s).
$$

The waveform of the event is synthesized, multiplied by its velocity, panned, then added to the stereo buffer.

### 18.2 Equal-Power Panning

Each event has a pan value

$$
p\in[-1,1].
$$

The stereo gains are

$$
g_L=\cos\left(\frac{\pi}{4}(p+1)\right),
\qquad
 g_R=\sin\left(\frac{\pi}{4}(p+1)\right).
$$

This is equal-power panning. It reduces the perceived level loss that would appear at the center with linear panning.

### 18.3 ADSR Envelope

Simple synthesis instruments use an Attack-Decay-Sustain-Release envelope:

$$
e[n]=
\begin{cases}
\dfrac{n}{N_A}, & 0\le n<N_A,\\[6pt]
1-(1-S_L)\dfrac{n-N_A}{N_D}, & N_A\le n<N_A+N_D,\\[6pt]
S_L, & N_A+N_D\le n<N-N_R,\\[6pt]
S_L\left(1-\dfrac{n-(N-N_R)}{N_R}\right), & N-N_R\le n<N.
\end{cases}
$$

Here $N_A$, $N_D$ and $N_R$ are the attack, decay and release lengths in samples, and $S_L$ is the sustain level.

### 18.4 Additive Synthesis

In Simple mode, many instruments are built by summing partials:

$$
x[n]=e[n]\sum_{q=1}^{Q}a_q\sin\left(2\pi q f_0\frac{n}{f_s}+\phi_q\right),
$$

where $f_0$ is the note frequency, $a_q$ is the amplitude of partial $q$, and $\phi_q$ is its phase.

Different instruments correspond to different partial weights, envelopes, detuning rules and noise components.

### 18.5 MIDI Pitch to Frequency

A MIDI pitch $m$ is converted to frequency by

$$
f(m)=440\cdot 2^{(m-69)/12}.
$$

This is the standard equal-tempered tuning convention with A4 at 440 Hz.

### 18.6 Output Bus

After all layers have been summed, the application applies a global gain and prevents clipping. A typical limiter can be understood as

$$
x_{\mathrm{out}}[n]=\frac{x[n]}{\max(1,\max_n |x[n]|)}.
$$

The purpose is not to master the music professionally. It is to produce a stable, playable audio file in an online application.

---

## 19. MIDI, MP3 and Analysis Outputs

The application can export the result as audio and MIDI.

The audio output is the rendered waveform. The MP3 export is useful for quick listening and sharing. The MIDI export is useful for inspection, editing and reuse in a digital audio workstation.

The analysis plots generally include:

| Plot | Meaning |
|---|---|
| waveform | amplitude in the time domain |
| spectrogram | time-frequency distribution |
| Fourier magnitude | global audio frequency content |
| per-layer spectra | contribution of each musical layer |

These plots are not decorative. They allow the user to verify whether the generated sound matches the expected structure. For example, a dense texture layer should increase high-frequency activity, while a strong bass layer should appear in the low-frequency range.

---

## 20. Random Factor

The Random Factor introduces controlled perturbations before the musical mapping. It does not replace the image analysis with a random draw: it slightly modifies some intermediate signals in order to produce another musical realization of the same image. It is therefore designed to create variation while preserving the main identity of the image.

Let $\alpha\in[0,1]$ be the normalized random factor. A spatial perturbation can be written as

$$
Y_{\mathrm{sp}}(x,y)=\operatorname{clip}\left(Y(x,y)+\alpha\sigma_r\xi(x,y),0,1\right),
$$

where $\xi(x,y)$ is a zero-mean random field and $\sigma_r$ controls its strength.

A Fourier-domain perturbation can be written as

$$
F_{\mathrm{rnd}}(u,v)=F(u,v)\left(1+\alpha\gamma(u,v)\right),
$$

where $\gamma(u,v)$ is a small random modulation.

The perturbed signal modifies the generated composition, but the displayed photo analysis can still be computed from the original image in order to keep the visual interpretation stable.

When Random Factor is zero, reproducibility is strict. When it increases, the application becomes more exploratory.

---

## 21. Parameter Reference

| Parameter group | Parameter | Effect |
|---|---|---|
| Image analysis | analysis size | controls the feature extraction resolution |
| Image analysis | luminance percentiles | define the robust dynamic range |
| Image analysis | shadow and highlight thresholds | control the dark and bright masks |
| Edge analysis | edge percentile | controls adaptive edge detection |
| Edge analysis | minimum edge threshold | prevents weak noise from becoming an edge |
| Fourier analysis | low/mid/high band limits | define the radial frequency bands |
| Fourier analysis | DC exclusion radius | removes the central average component |
| Fourier analysis | periodic peak percentiles | control the periodicity descriptor |
| Saliency | edge/color/luminance weights | control the saliency composition |
| Saliency | center bias | controls the preference for central regions |
| Music | tempo mode | Scientific, Balanced, Musical or Manual |
| Music | scale mode | automatic or fixed scale |
| Music | number of bars | controls the composition length |
| Music | complexity | controls note density and texture |
| Music | variation strength | controls section changes |
| Instruments | mode | Simple, GeneralUser GS or Manual |
| Instruments | layer gains | control the relative amplitudes of the layers |
| Output | global gain | controls the final sound level |
| Output | Random Factor | controls reproducible or exploratory random variation depending on its value |

A useful rule for parameter tuning is to change only one group at a time. If the goal is to understand the mapping, start with Random Factor at zero and automatic instruments enabled.

---

## 22. How to Interpret the Result

The application is easiest to understand by reading the output in three passes.

First, inspect the image analysis maps. A smooth luminance map and a Fourier spectrum concentrated in low frequencies should correspond to a slower, more sustained result. A marked edge map and strong high-frequency Fourier energy should correspond to more texture and attacks.

Second, inspect the musical summary. Check the tonality, scale, tempo, complexity, variation strength and selected instruments. These values form the bridge between the visual descriptors and the final audio.

Third, listen while observing the audio plots. The waveform shows amplitude over time. The spectrogram shows how energy evolves across frequency. Per-layer spectra explain which layer contributes to which part of the sound.

If the result seems surprising, trace it back to the descriptors. A dark image can generate bright accents if it contains small highlights. A simple image can generate variation if it is strongly asymmetric. A calm image can produce a regular rhythmic pattern if its Fourier spectrum contains periodic peaks.

---

## 23. Limitations

Photo Sonification is an interpretable feature-based system, not a semantic image-to-music model.

It does not understand the subject of the photo. A mountain, a face and a building may produce similar music if their luminance, texture, color and Fourier descriptors are similar.

The mapping is designed, not learned. This is a strength for transparency and a limitation for aesthetic universality. Another designer could choose other correspondence rules and obtain different musical behavior.

The relation between color and harmony is not a physical law. It is a controlled artistic convention implemented through deterministic rules.

Fourier descriptors capture global spatial structure. They do not fully represent local composition, object boundaries or depth.

The saliency model is low-level. It highlights contrast, rarity and centrality, but it does not know what is meaningful to a human observer in a semantic sense.

The synthesis engine is intentionally lightweight. It is suitable for an online educational application, but it is not a replacement for professional music production tools.

The best way to read the application is therefore not as an automatic composer, but as a signal-processing instrument: it exposes how measurable visual structure can be transformed into sound.
