## Table of Contents

1. [Overview](#1-overview)
2. [What the App Does](#2-what-the-app-does)
3. [Pipeline at a Glance](#3-pipeline-at-a-glance)
4. [Notation](#4-notation)
5. [Image Analysis](#5-image-analysis)
6. [Fourier Analysis of the Photo](#6-fourier-analysis-of-the-photo)
7. [Visual Saliency](#7-visual-saliency)
8. [From Visual Features to Musical Decisions](#8-from-visual-features-to-musical-decisions)
9. [Automatic Structure: Bars, Complexity and Variation](#9-automatic-structure-bars-complexity-and-variation)
10. [Tonality, Scale and Tempo](#10-tonality-scale-and-tempo)
11. [Harmony and Chord Progression](#11-harmony-and-chord-progression)
12. [Melody, Texture, Bass, Pad, Chord and Solo Layers](#12-melody-texture-bass-pad-chord-and-solo-layers)
13. [Instrument Selection](#13-instrument-selection)
14. [Audio Rendering and Synthesis](#14-audio-rendering-and-synthesis)
15. [Master Bus, Exports and Audio Analysis](#15-master-bus-exports-and-audio-analysis)
16. [Random Factor](#16-random-factor)
17. [Parameter Reference](#17-parameter-reference)
18. [Limitations](#18-limitations)

---

## 1. Overview

Photo Sonification Lab converts a still image into a short musical composition. The app does not use a trained neural network and it does not try to recognize objects in the image. Instead, it measures visual quantities such as brightness, contrast, edge density, color, spatial frequency content and saliency, then maps them to musical quantities such as key, scale, tempo, note density, instrument choice, stereo position and layer balance.

The idea is simple: a photo is treated as a signal. The app analyses that signal, extracts a feature vector, converts this feature vector into a list of musical note events, then renders those events as audio and MIDI.

$$
\text{photo}
\;\xrightarrow{\text{image analysis}}\;
\mathbf{f}
\;\xrightarrow{\text{musical mapping}}\;
\{\text{note events}\}
\;\xrightarrow{\text{synthesis}}\;
\text{audio} + \text{MIDI}
$$

The output is not meant to be the unique correct music for a photo. It is one explicit and reproducible mapping from visual structure to musical structure. With Random factor set to 0, the same image and the same parameters always produce the same composition.

---

## 2. What the App Does

From a user point of view, the app follows this order.

First, the image is loaded and resized for analysis. The app keeps the visual content but limits the longest analysis side so that Fourier analysis, saliency extraction and feature computation remain fast enough for an online app.

Second, the app computes several maps from the photo:

| Map | What it shows | Why it matters musically |
|---|---|---|
| Luminance map | perceived brightness at each pixel | pitch register, shadows, highlights, melody shape |
| Edge strength map | local spatial changes in brightness | rhythmic activity and texture density |
| 2D Fourier log-magnitude | global spatial frequency content | smoothness, detail, periodicity, tempo and instruments |
| Shadow/highlight map | dark and bright pixel regions | bass weight, bright accents, mood |
| Saliency map | visually dominant regions | solo/accent notes in GeneralUser GS mode |

Third, the app turns the image features into musical defaults. A smooth symmetric photo tends to create a stable and slower piece. A sharp asymmetric photo tends to create stronger variation, more notes and a denser texture. A bright colorful photo tends to select brighter registers and timbres. A dark low-frequency image tends to give more weight to bass, strings and pads.

Finally, the app generates a layered composition. The result contains up to six layers:

| Layer | Role in the composition |
|---|---|
| Main | principal melody derived from left-to-right luminance slices |
| Texture | arpeggios and small rhythmic events derived from detail and high frequencies |
| Bass | low register root/fifth support, influenced by shadows and low frequencies |
| Pad | sustained harmonic background, stronger for smooth low-frequency images |
| Chord | harmonic hits following the selected chord progression |
| Solo | saliency-driven accent melody, available in GeneralUser GS mode |

The interface exposes both musical controls and lower-level analysis thresholds. The range sliders used for min/max values are ordered, and the backend also sorts and clamps them. This prevents invalid settings such as a low Fourier band limit above the high Fourier band limit.

---

## 3. Pipeline at a Glance

| Stage | Main output | Used for |
|---|---|---|
| RGB normalization | normalized image $R,G,B \in [0,1]$ | all later analysis |
| Luminance computation | scalar image $Y$ | brightness, contrast, melody, shadows, highlights |
| Gradient analysis | edge map $\hat{G}$ and edge density $D_e$ | texture, tempo, rhythm |
| Entropy analysis | texture entropy $H_{\mathrm{tex}}$ | complexity and bar defaults |
| Symmetry analysis | symmetry score $S$ | variation strength |
| HSV color analysis | dominant hue, saturation, warmth | key, scale, instruments |
| 2D Fourier analysis | low/mid/high energy, centroid, bandwidth, periodic peak score | tempo, instruments, texture, pad/bass balance |
| Saliency analysis | saliency map and salient coordinates | solo/accent layer |
| Musical mapping | key, scale, tempo, bars, layer instruments | event generation |
| Event generation | ordered note events | audio synthesis and MIDI export |
| Rendering | stereo waveform at 44100 Hz | audio player, WAV/MP3 export, plots |

A note event has the form:

$$
e_i = (t_i, d_i, m_i, v_i, I_i, p_i, \ell_i)
$$

where $t_i$ is the start time, $d_i$ the duration, $m_i$ the MIDI pitch, $v_i$ the velocity, $I_i$ the instrument, $p_i$ the stereo pan and $\ell_i$ the layer label.

---

## 4. Notation

| Symbol | Meaning |
|---|---|
| $R,G,B$ | normalized RGB channels of the image |
| $Y$ | perceptual luminance image |
| $H,W$ | image height and width after analysis resizing |
| $\Omega$ | pixel grid of size $H \times W$ |
| $P_q(X)$ | $q$-th percentile of array $X$ |
| $\mu_Y$ | mean luminance |
| $\sigma_Y$ | luminance contrast |
| $D_Y$ | robust luminance dynamic range |
| $\hat{G}$ | normalized gradient magnitude map |
| $D_e$ | edge density |
| $H_{\mathrm{tex}}$ | texture entropy |
| $S$ | symmetry score |
| $F(u,v)$ | centered 2D Fourier transform of luminance |
| $r(u,v)$ | normalized radial spatial frequency |
| $E_{\mathrm{low}}, E_{\mathrm{mid}}, E_{\mathrm{high}}$ | Fourier energy proportions in the low, mid and high bands |
| $\rho_c$ | Fourier radial centroid |
| $B_F$ | Fourier radial bandwidth |
| $P_F$ | periodic peak score |
| $\mathcal{S}$ | saliency map |
| $T$ | tempo in beats per minute |
| $\Delta t$ | beat period, $\Delta t = 60/T$ |
| $B$ | number of bars |

---

## 5. Image Analysis

### 5.1 RGB normalization

The input photo is converted to RGB, corrected for EXIF orientation, resized if necessary and normalized to floating-point values in $[0,1]$:

$$
R(x,y),G(x,y),B(x,y) \in [0,1]
$$

The analysis resize does not change the file exported by the user; it only controls the computational resolution of the feature extraction. A larger analysis side preserves finer details but increases the cost of Fourier and saliency computations.

### 5.2 Perceptual luminance

Most structural descriptors are computed from luminance rather than directly from RGB. The app uses the ITU-R BT.709 weights:

$$
Y(x,y) = 0.2126R(x,y) + 0.7152G(x,y) + 0.0722B(x,y)
$$

These weights reflect human brightness perception: green contributes much more strongly than blue.

The global brightness is:

$$
\mu_Y = \frac{1}{HW}\sum_{(x,y)\in\Omega}Y(x,y)
$$

The contrast is:

$$
\sigma_Y = \sqrt{\frac{1}{HW}\sum_{(x,y)\in\Omega}\bigl(Y(x,y)-\mu_Y\bigr)^2}
$$

The dynamic range uses user-controlled luminance percentiles $p_L$ and $p_H$, defaulting to $5\%$ and $95\%$:

$$
D_Y = P_{p_H}(Y) - P_{p_L}(Y)
$$

Using percentiles avoids letting a few isolated pixels dominate the range.

### 5.3 Shadows and highlights

The app defines two masks. The shadow mask is:

$$
\mathcal{M}_{\mathrm{shadow}} = \left\{(x,y):Y(x,y) < \max\bigl(\tau_s, P_{p_L}(Y)+\delta_s\bigr)\right\}
$$

The highlight mask is:

$$
\mathcal{M}_{\mathrm{highlight}} = \left\{(x,y):Y(x,y) > \min\bigl(\tau_h, P_{p_H}(Y)-\delta_h\bigr)\right\}
$$

The defaults are $\tau_s=0.18$, $\delta_s=0.03$, $\tau_h=0.82$ and $\delta_h=0.03$. The resulting proportions are:

$$
s = \frac{|\mathcal{M}_{\mathrm{shadow}}|}{HW},
\qquad
h = \frac{|\mathcal{M}_{\mathrm{highlight}}|}{HW}
$$

Musically, shadows strengthen bass and darker timbres. Highlights strengthen bright timbres, arpeggios and accent layers.

### 5.4 Edge strength

Edges are extracted from the luminance gradient:

$$
G(x,y) = \sqrt{\bigl(\partial_xY(x,y)\bigr)^2 + \bigl(\partial_yY(x,y)\bigr)^2}
$$

The gradient magnitude is normalized to $[0,1]$:

$$
\hat{G}(x,y) = \frac{G(x,y)-\min G}{\max G-\min G}
$$

The edge density is the fraction of pixels above a threshold. The threshold combines a percentile and a fixed minimum:

$$
D_e = \frac{1}{HW}\left|\left\{(x,y):\hat{G}(x,y)>\max\bigl(\tau_e,P_{q_e}(\hat{G})\bigr)\right\}\right|
$$

The default values are $q_e=75\%$ and $\tau_e=0.08$. This makes the detector adaptive: it can still find relevant edges in soft images while avoiding excessive detections in noisy images.

### 5.5 Texture entropy

The edge map is also used as a texture descriptor. A histogram with $K$ bins is computed over $\hat{G}$, then normalized into probabilities $p_k$. The texture entropy is:

$$
H_{\mathrm{tex}} = -\frac{1}{\log_2K}\sum_{k=1}^{K}p_k\log_2p_k
$$

The default is $K=64$ bins. Low entropy means the image is visually uniform or smooth. High entropy means the image contains many different edge strengths and therefore a more complex texture. The app uses this value to set the automatic composition complexity and to influence the number of bars.

### 5.6 Symmetry

The symmetry score compares the luminance image to its left-right and top-bottom reflections:

$$
S_{LR}=1-\frac{1}{HW}\sum_{(x,y)}|Y(x,y)-Y(W-1-x,y)|
$$

$$
S_{TB}=1-\frac{1}{HW}\sum_{(x,y)}|Y(x,y)-Y(x,H-1-y)|
$$

The final score gives more importance to left-right symmetry:

$$
S=0.70S_{LR}+0.30S_{TB}
$$

A high score gives a stable composition with lower variation. A low score increases the default variation strength.

### 5.7 Color features

The RGB image is converted internally into HSV-like features. Saturation is computed from the RGB chroma:

$$
\mathrm{Sat}(x,y)=
\begin{cases}
\dfrac{\max(R,G,B)-\min(R,G,B)}{\max(R,G,B)}, & \max(R,G,B)>0 \\
0, & \text{otherwise}
\end{cases}
$$

Hue is circular, so a simple arithmetic average is not valid. The app computes a weighted circular mean. Each pixel weight is:

$$
w(x,y)=\mathrm{Sat}(x,y)\cdot(0.25+Y(x,y))
$$

The dominant hue is:

$$
\bar{h}=\frac{1}{2\pi}\operatorname{atan2}\left(
\sum w\sin(2\pi h),
\sum w\cos(2\pi h)
\right)\bmod 1
$$

This hue controls the tonal center. The mean saturation influences scale choice and instrument scoring. Warmth is measured as:

$$
w_{\mathrm{arm}}=\frac{1}{HW}\sum_{(x,y)}\bigl(R(x,y)-B(x,y)\bigr)
$$

Positive values indicate a warmer photo; negative values indicate a cooler photo.

### 5.8 Spatial centroids

The horizontal position of bright, shadowed and highlighted regions is used for stereo placement. For any non-negative weight map $W_m(x,y)$, the horizontal center of mass is:

$$
c_x=\frac{\sum xW_m(x,y)}{\sum W_m(x,y)}
$$

normalized to $[0,1]$. The main melody and chords follow the bright centroid, while the bass follows the shadow centroid. This gives the stereo image a relation to the spatial layout of the photo.

---

## 6. Fourier Analysis of the Photo

The Fourier analysis describes the image in terms of spatial frequency. Large smooth structures correspond to low frequencies. Fine texture, edges and noise correspond to high frequencies.

### 6.1 Preprocessing before the FFT

The mean luminance is removed, then a separable Hanning window is applied:

$$
\tilde{Y}(x,y)=\bigl(Y(x,y)-\mu_Y\bigr)w_H(x)w_H(y)
$$

with:

$$
w_H(n)=0.5-0.5\cos\left(\frac{2\pi n}{N-1}\right)
$$

The window reduces boundary discontinuities. Without it, the FFT would interpret the finite image as a periodic tile and introduce artificial high-frequency content at the borders.

### 6.2 Centered 2D Fourier transform

The 2D Fourier transform is:

$$
F(u,v)=\sum_{x=0}^{W-1}\sum_{y=0}^{H-1}\tilde{Y}(x,y)e^{-j2\pi(ux/W+vy/H)}
$$

The spectrum is shifted so that the DC component is displayed at the center. The photo analysis panel shows:

$$
M_{\log}(u,v)=\log(1+|F(u,v)|)
$$

normalized to $[0,1]$. The logarithm is used because Fourier magnitudes usually have a very large dynamic range.

### 6.3 Radial frequency bands

For each frequency bin, the normalized radial frequency is:

$$
r(u,v)=\frac{\sqrt{u^2+v^2}}{\max\sqrt{u^2+v^2}}
$$

A small DC radius $r_{DC}$ is excluded from energy measurements. The remaining spectrum is split into three user-controlled bands:

| Band | Default radial range | Interpretation |
|---|---|---|
| Low | $[r_{DC},0.14)$ | large smooth structures |
| Mid | $[0.14,0.34)$ | medium shapes and transitions |
| High | $[0.34,1]$ | fine texture, edges, micro-details |

The low and high band limits are controlled by an ordered range slider. If needed, the backend also sorts and clamps the values.

The energy of a band $\mathcal{B}$ is:

$$
E_{\mathcal{B}}=\frac{\sum_{(u,v)\in\mathcal{B}}|F(u,v)|^2}{\sum_{r(u,v)\ge r_{DC}}|F(u,v)|^2}
$$

Low-frequency energy supports pads and bass. High-frequency energy increases texture density, bright timbres and tempo in the Scientific mapping mode.

### 6.4 Fourier centroid and bandwidth

The radial centroid is:

$$
\rho_c=\frac{\sum r(u,v)|F(u,v)|^2}{\sum |F(u,v)|^2}
$$

and the radial bandwidth is:

$$
B_F=\sqrt{\frac{\sum (r(u,v)-\rho_c)^2|F(u,v)|^2}{\sum |F(u,v)|^2}}
$$

A high centroid means the image is dominated by fine-scale structures. A large bandwidth means energy is spread across several scales.

### 6.5 Directional energies

The angle of a frequency bin is:

$$
\theta(u,v)=\operatorname{atan2}(v,u)
$$

The app measures horizontal and vertical directional energies with a user-controlled orientation bandwidth $\omega_o$:

$$
E_{\mathrm{horizontal}}=\frac{\sum_{|\sin\theta|<\omega_o}|F|^2}{\sum |F|^2},
\qquad
E_{\mathrm{vertical}}=\frac{\sum_{|\cos\theta|<\omega_o}|F|^2}{\sum |F|^2}
$$

The diagonal energy is the remaining part:

$$
E_{\mathrm{diagonal}}=1-E_{\mathrm{horizontal}}-E_{\mathrm{vertical}}
$$

These values are displayed as descriptors of image structure. They are less central to the musical mapping than radial low/mid/high energies.

### 6.6 Periodic peak score

Some images contain regular patterns: stripes, grids, repeated windows, tiles or periodic textures. Such images produce a Fourier spectrum with isolated strong peaks. The app estimates this with:

$$
P_F=\operatorname{clip}\left(
\frac{\log\left(1+\dfrac{P_{p_H}(|F|^2)}{P_{p_L}(|F|^2)+\varepsilon}\right)}{d_F},0,1
\right)
$$

The default percentile range is $(p_L,p_H)=(90,99.7)$ and the default divisor is $d_F=5$. The percentile range is also an ordered range slider. A high periodic peak score encourages loop-like structure, mallet-like timbres and more regular motifs.

---

## 7. Visual Saliency

Saliency estimates which regions of the photo are likely to attract attention. In this app, saliency does not depend on object recognition. It is built from three measurable cues: edge strength, color rarity and luminance rarity.

### 7.1 Color rarity

Let $\bar{\mathbf{c}}=(\bar{R},\bar{G},\bar{B})$ be the mean RGB color of the image. The color rarity is:

$$
C_r(x,y)=\left\|\begin{bmatrix}R(x,y)\\G(x,y)\\B(x,y)\end{bmatrix}-\bar{\mathbf{c}}\right\|_2
$$

Pixels with colors far from the global average become more salient.

### 7.2 Luminance rarity

The luminance rarity is:

$$
L_r(x,y)=|Y(x,y)-\mu_Y|
$$

Very bright and very dark pixels can both be salient if they are unusual compared with the rest of the image.

### 7.3 Saliency combination

The three components are normalized and blended with user-controlled weights:

$$
B_s(x,y)=w_e\hat{G}(x,y)+w_c\hat{C}_r(x,y)+w_l\hat{L}_r(x,y)
$$

The default weights are $w_e=0.42$, $w_c=0.34$ and $w_l=0.24$, normalized internally so their sum is 1.

A small center bias is added because many photographs place the subject near the center:

$$
C_B(x,y)=1-\left\|\begin{bmatrix}x/(W-1)-0.5\\y/(H-1)-0.5\end{bmatrix}\right\|_2
$$

The final saliency map is:

$$
\mathcal{S}(x,y)=\operatorname{normalize}_{[0,1]}\left((1-\lambda_c)B_s(x,y)+\lambda_cC_B(x,y)\right)
$$

where $\lambda_c$ is the center-bias weight, defaulting to 0.12.

### 7.4 Saliency mask and descriptors

A salient mask is defined with a percentile threshold and a minimum threshold:

$$
\mathcal{M}_{\mathcal{S}}=\left\{(x,y):\mathcal{S}(x,y)\ge\max\bigl(\tau_{\mathcal{S}},P_{q_{\mathcal{S}}}(\mathcal{S})\bigr)\right\}
$$

The defaults are $q_{\mathcal{S}}=96\%$ and $\tau_{\mathcal{S}}=0.20$. From this mask, the app computes saliency peak, mean, area, centroid and spread. These values are used by the solo/accent layer.

---

## 8. From Visual Features to Musical Decisions

This table is the practical map between image descriptors and musical behavior.

| Visual feature | Musical effect |
|---|---|
| Mean brightness $\mu_Y$ | root register, scale tendency, mood |
| Contrast $\sigma_Y$ | tempo, melodic velocity, chord energy |
| Shadow proportion $s$ | bass strength, darker timbres, slower tempo |
| Highlight proportion $h$ | bright instruments, accents, chord activity |
| Edge density $D_e$ | tempo, attacks, rhythm density |
| Texture entropy $H_{\mathrm{tex}}$ | complexity and number of bars |
| Symmetry $S$ | variation strength |
| Dominant hue $\bar{h}$ | tonal center / key |
| Saturation | scale and instrument colorfulness |
| Warmth | scale tendency and warm/cool instrument affinity |
| Low Fourier energy $E_{\mathrm{low}}$ | pads, bass, smooth instruments |
| High Fourier energy $E_{\mathrm{high}}$ | arpeggios, bright timbres, fast texture |
| Fourier centroid $\rho_c$ | Scientific tempo contribution |
| Fourier bandwidth $B_F$ | texture richness |
| Periodic peak score $P_F$ | repetitive motifs, mallet/percussive affinity |
| Saliency peak/area/spread | solo note count, spacing and duration |
| Saliency positions | solo timing and pitch |
| Bright centroid | main/chord stereo pan |
| Shadow centroid | bass stereo pan |
| Luminance slices | main melody contour |

This table is also a useful way to interpret the result. For example, if a photo produces a dense fast texture, the cause is usually a combination of edge density, high Fourier energy and texture entropy. If it produces a dark slow piece, the cause is usually low brightness, high shadow proportion and low high-frequency energy.

---

## 9. Automatic Structure: Bars, Complexity and Variation

### 9.1 Complexity

The automatic complexity is derived from texture entropy. In the current app, the user controls the output range:

$$
C_{\mathrm{auto}}=C_{\min}+(C_{\max}-C_{\min})H_{\mathrm{tex}}
$$

The default range is $[0.25,0.90]$. The final Complexity slider controls note density, melodic step rate and texture activation.

### 9.2 Variation strength

Variation is derived from lack of symmetry:

$$
V_{\mathrm{auto}}=V_{\min}+(V_{\max}-V_{\min})(1-S)
$$

The default range is $[0.25,0.85]$. A symmetric image gives lower variation. An asymmetric image gives stronger variation, especially in the second half of the piece.

### 9.3 Number of bars

The bar estimator uses a weighted score:

$$
Q_B=w_tH_{\mathrm{tex}}+w_eD_e+w_hE_{\mathrm{high}}+w_pP_F
$$

The default weights are $w_t=0.40$, $w_e=0.25$, $w_h=0.20$ and $w_p=0.15$, normalized internally.

The app maps this score into three ranges:

$$
B_{\min}=\operatorname{round}\bigl(\operatorname{interp}(Q_B,[0,1],[B_{\min}^{lo},B_{\min}^{hi}])\bigr)
$$

$$
B_{\max}=\operatorname{round}\bigl(\operatorname{interp}(Q_B,[0,1],[B_{\max}^{lo},B_{\max}^{hi}])\bigr)
$$

$$
B_0=\operatorname{round}\bigl(\operatorname{interp}(Q_B,[0,1],[B_0^{lo},B_0^{hi}])\bigr)
$$

The default ranges are $[4,8]$ for minimum bars, $[12,24]$ for maximum bars and $[6,16]$ for the default value. The backend ensures $B_{\max}>B_{\min}$ and clamps $B_0$ inside the valid interval.

---

## 10. Tonality, Scale and Tempo

### 10.1 Key from dominant hue

The dominant hue is mapped to one of 12 pitch classes:

$$
k=\operatorname{round}(12\bar{h})\bmod 12
$$

with the pitch classes:

$$
\{C,C\#,D,D\#,E,F,F\#,G,G\#,A,A\#,B\}
$$

The root MIDI note is shifted by image brightness:

$$
\text{root}=\operatorname{clip}\left(48+k+\operatorname{round}\bigl(\operatorname{interp}(\mu_Y,[0,1],[-5,7])\bigr),38,58\right)
$$

Darker images therefore tend to use lower registers, while brighter images tend to use higher registers.

### 10.2 Scale selection

The available scales are:

| Scale | Intervals in semitones |
|---|---|
| Major pentatonic | $0,2,4,7,9$ |
| Minor pentatonic | $0,3,5,7,10$ |
| Major | $0,2,4,5,7,9,11$ |
| Natural minor | $0,2,3,5,7,8,10$ |
| Dorian | $0,2,3,5,7,9,10$ |
| Lydian | $0,2,4,6,7,9,11$ |

If Scale is set to Automatic, the app uses brightness, warmth, saturation and contrast. Bright warm images tend toward Lydian or major-like scales. Darker images tend toward Dorian or natural minor.

### 10.3 Tempo mapping

The app offers four tempo modes.

Scientific mode uses spatial structure and Fourier descriptors:

$$
T=\operatorname{clip}\bigl(50+70D_e+58\sigma_Y+42P_F+34E_{\mathrm{high}}+22\rho_c-20s,T_{lo},T_{hi}\bigr)
$$

The default Scientific range is $[48,152]$ BPM.

Balanced mode is a softer version:

$$
T=\operatorname{clip}\bigl(62+38D_e+28\sigma_Y+20P_F+10E_{\mathrm{high}}-8s,T_{lo},T_{hi}\bigr)
$$

The default Balanced range is $[56,132]$ BPM.

Musical mode is smoother and mostly color-based:

$$
T=\operatorname{clip}\bigl(82+10\overline{\mathrm{Sat}}+8\mu_Y-6s+4w_{\mathrm{arm}},T_{lo},T_{hi}\bigr)
$$

The default Musical range is $[72,108]$ BPM.

Manual mode lets the user set the BPM directly.

---

## 11. Harmony and Chord Progression

A chord is built from the selected scale by stacking every other scale degree. For a scale interval list:

$$
I=[i_0,i_1,\ldots,i_{n-1}]
$$

then a triad on degree $d$ is:

$$
\operatorname{chord}(d)=\{i_d,i_{d+2},i_{d+4}\}
$$

with octave wrapping when the index exceeds the scale length.

The app chooses a progression from a small pool. For seven-note scales, examples include:

$$
[0,4,5,3],\quad [0,5,3,4],\quad [0,2,5,4],\quad [0,3,1,4]
$$

The selected progression depends on dominant hue, periodic peak score, texture entropy and saliency centroid:

$$
\text{seed}=\operatorname{round}(997\bar{h}+113P_F+71H_{\mathrm{tex}}+53c_x^{\mathcal{S}})
$$

If variation strength is greater than 0.45, the second half of the composition shifts the progression index. This produces a simple A/B form: the first half establishes a loop, and the second half moves it slightly.

---

## 12. Melody, Texture, Bass, Pad, Chord and Solo Layers

### 12.1 Main melody from luminance slices

The image is read from left to right. For a composition of $B$ bars, the image is divided into $8B$ vertical slices. For each slice, the app computes local energy, contrast and vertical brightness centroid.

The vertical centroid uses a percentile-trimmed weight:

$$
w_i(y)=\max\bigl(Y_i(y)-P_{35}(Y_i),0\bigr)
$$

The position inside the melody note pool is:

$$
\operatorname{pos}_i=\operatorname{clip}\bigl(1-c_{y,i}+0.18(\bar{Y}_i-\mu_Y),0,1\bigr)
$$

High bright areas produce higher notes. Low dark areas produce lower notes.

The melody density depends on the Complexity slider. If complexity is above the melody density threshold, every slice can generate a note. Otherwise, every second slice is used. Very dark slices can be skipped unless they fall on a structural beat; the threshold is controlled by the Melody energy gate.

### 12.2 Melodic variation

The piece is divided into four broad sections. A small section-dependent offset is added to the melody:

$$
\Delta m \in \{0,2,-2,5\}
$$

scaled by the variation strength:

$$
m_{\mathrm{final}}=m_{\mathrm{base}}+\operatorname{round}(V\Delta m)
$$

This keeps the melody close to the image contour while preventing long outputs from becoming too repetitive.

### 12.3 Pad, chord and bass layers

Pad notes sustain the current chord across the bar. Their velocity increases with low-frequency energy:

$$
v_{\mathrm{pad}}=\operatorname{clip}(0.07+0.18E_{\mathrm{low}}+0.04(1-E_{\mathrm{high}}),0.04,0.28)
$$

Chord hits play the current triad once per bar. If high-frequency energy exceeds the Chord double-hit threshold, a second chord hit is added halfway through the bar.

Bass uses a root/fifth pattern: root on beat 1 and fifth on beat 3. Bass velocity increases with shadow proportion and low-frequency energy:

$$
v_{\mathrm{bass}}=\operatorname{clip}(0.30+0.55s+0.25E_{\mathrm{low}},0.22,0.86)
$$

### 12.4 Texture and percussion

Texture density is:

$$
\rho_{\mathrm{tex}}=\operatorname{clip}(0.20+0.80C+0.75E_{\mathrm{high}}+0.45B_F,0,1)
$$

where $C$ is the user-controlled complexity. If $\rho_{\mathrm{tex}}$ is above the texture activation threshold, the app adds arpeggio-like events. If it is above the fast threshold, the arpeggio rate doubles.

A separate percussion-like tick layer activates when $\rho_{\mathrm{tex}}$ exceeds the percussion activation threshold. These ticks are short events placed on MIDI percussion channel 9 in the MIDI export.

### 12.5 Saliency solo layer

The solo layer is available in GeneralUser GS mode. It selects salient points in the image and converts their positions to time and pitch.

A saliency strength score is:

$$
\eta=\operatorname{clip}\bigl(0.55\,\text{peak}+0.25\,\text{mean}+0.20(1-\text{area}),0,1\bigr)
$$

The number of solo notes is interpolated from a user-controlled note-count range, then limited by the Solo note cap. Candidate points are selected from the strongest saliency pixels, with a minimum distance constraint so that notes do not all collapse onto the same visual region.

The horizontal coordinate becomes time:

$$
t_k=x_k^{\mathrm{norm}}T_{\mathrm{dur}}+0.10\Delta t\sin(1.7k)
$$

The vertical coordinate becomes pitch:

$$
m_k=\operatorname{melody\_notes}\left[\operatorname{round}\bigl((1-y_k^{\mathrm{norm}})(N_{\mathrm{mel}}-1)\bigr)\right]+12
$$

The solo therefore behaves like a sparse melodic reading of the most visually important image regions.

---

## 13. Instrument Selection

### 13.1 Simple mode

Simple mode uses internal additive synthesis instruments such as soft piano, harp, music box, bright bell, marimba, cello-like bass, warm pad and glass pad. It is fully self-contained and does not require a SoundFont.

In Automatic mode, the app chooses instruments using explicit feature rules. For example, bright images with many highlights favor bells or celesta; periodic images favor kalimba or marimba; dark smooth images favor cello-like bass, bowed strings or pads.

### 13.2 GeneralUser GS mode

GeneralUser GS mode uses the 128 General MIDI program names. Rendering requires FluidSynth and a GeneralUser GS SoundFont. If they are not available, the app falls back to the Simple synthesis backend while keeping the musical event structure.

Each General MIDI program belongs to a family such as piano, chromatic percussion, organ, guitar, bass, strings, brass, reed, pipe, synth lead or synth pad. For each layer, the app assigns a score to each family using image features.

For example, a smoothness score is:

$$
\lambda_{\mathrm{smooth}}=\operatorname{clip}(E_{\mathrm{low}}+0.35(1-E_{\mathrm{high}})+0.25S,0,1)
$$

A brightness score is:

$$
\lambda_{\mathrm{bright}}=\operatorname{clip}(0.55\mu_Y+0.45h,0,1)
$$

For the main layer, piano affinity includes smoothness:

$$
W_{\mathrm{main}}(\mathrm{piano})=0.35+0.35\lambda_{\mathrm{smooth}}
$$

Pipe instruments receive brightness and smoothness contributions:

$$
W_{\mathrm{main}}(\mathrm{pipe})=0.18+0.45\lambda_{\mathrm{bright}}+0.20\lambda_{\mathrm{smooth}}
$$

Additional program-level bonuses are added. For instance, celesta, music box and bell-like programs receive bonuses from highlights, high-frequency energy and saliency peak. Bass programs receive bonuses from shadows and low-frequency energy.

A deterministic pseudo-random jitter is added:

$$
\operatorname{score}(p,\ell)=W_\ell(f_p)+\operatorname{bonus}(p)+0.42u(p,\ell)
$$

where $u(p,\ell)$ is derived from a SHA-256 hash of the image features. This gives variety while remaining reproducible.

### 13.3 Manual mode and gains

In Manual instrument mode, the user chooses the instrument for each layer. Each layer also has a gain in decibels:

$$
g=10^{G_{\mathrm{dB}}/20}
$$

The gain multiplies note velocity before rendering. Velocities are clipped to $[0,1]$.

---

## 14. Audio Rendering and Synthesis

### 14.1 Event rendering

The generated events are placed into a stereo buffer at sample rate $f_s=44100$ Hz. An event starting at time $t_i$ begins at sample:

$$
n_i=\operatorname{round}(t_if_s)
$$

Each event waveform is synthesized, multiplied by its velocity, panned, and added to the buffer.

### 14.2 Equal-power panning

Each event has a pan value $p\in[-1,1]$. The stereo gains are:

$$
g_L=\cos\left(\frac{\pi}{4}(p+1)\right),
\qquad
g_R=\sin\left(\frac{\pi}{4}(p+1)\right)
$$

This is equal-power panning. It avoids a perceived loudness drop at the center.

### 14.3 ADSR envelope

Simple synthesis instruments use an Attack-Decay-Sustain-Release envelope:

$$
e[n]=
\begin{cases}
n/N_A, & 0\le n<N_A \\
1-(1-S_L)(n-N_A)/N_D, & N_A\le n<N_A+N_D \\
S_L, & N_A+N_D\le n<N-N_R \\
S_L(1-(n-(N-N_R))/N_R), & N-N_R\le n<N
\end{cases}
$$

The envelope gives each note a more realistic amplitude shape than an abrupt rectangular window.

### 14.4 Additive synthesis examples

Soft piano uses harmonic partials:

$$
x[n]=\sum_{m\in\{1,2,3,4,5\}}a_m\sin(2\pi mf_0n/f_s)
$$

with amplitudes:

$$
(a_1,a_2,a_3,a_4,a_5)=(1,0.42,0.20,0.10,0.04)
$$

Bright bell, celesta and music box use inharmonic partials to create a metallic sound. Harp, marimba and synth pluck use a power-law harmonic decay. Pads and bowed strings use slow envelopes and a light vibrato model.

---

## 15. Master Bus, Exports and Audio Analysis

### 15.1 Master bus processing

After all layers are mixed, the master bus is processed in three steps.

First, the DC offset is removed from each channel:

$$
x_{dc}[n]=x[n]-\frac{1}{N}\sum_{m=0}^{N-1}x[m]
$$

Second, RMS level is limited. The stereo RMS is:

$$
\operatorname{RMS}=\sqrt{\frac{1}{2N}\sum_{n=0}^{N-1}\bigl(x_L[n]^2+x_R[n]^2\bigr)}
$$

If it exceeds the target RMS, the signal is scaled down. Third, the peak level is limited to the target peak. A final safety clip prevents overflow.

The default target peak is 0.86 and the default target RMS is 0.16, but both are exposed in the Parameters panel.

### 15.2 Export formats

The app exports:

| Export | Content |
|---|---|
| WAV playback | rendered stereo audio at 44100 Hz |
| MP3 | compressed audio, generated with `lameenc` or `ffmpeg` if available |
| MIDI | note events, tempo, channels and program changes |

The MIDI export uses one track, 480 pulses per quarter note and fixed channels for the musical layers:

| Layer | MIDI channel |
|---|---|
| Main | 0 |
| Texture | 1 |
| Bass | 2 |
| Pad | 3 |
| Chord | 4 |
| Solo | 5 |
| Percussion tick | 9 |

### 15.3 Audio analysis plots

The Audio analysis panel computes a one-sided Fourier magnitude for the full mix and for individual layers. For a mono signal $x[n]$, the magnitude is:

$$
|X[k]|=\left|\sum_{n=0}^{N-1}x[n]e^{-j2\pi kn/N}\right|
$$

The frequency axis is:

$$
f_k=\frac{kf_s}{N}
$$

The layer plots are generated by re-rendering only the events from one layer. This helps verify that bass, pad, main melody, texture and chord layers occupy different spectral regions.

---

## 16. Random Factor

Random factor adds controlled perturbation to the analysis. It does not replace the image-based mapping with pure randomness.

Let:

$$
\alpha=\frac{r}{100}
$$

where $r$ is the Random factor slider value.

Spatial RGB noise is:

$$
R'(x,y)=\operatorname{clip}(R(x,y)+\eta_R(x,y),0,1)
$$

with:

$$
\eta_R\sim\mathcal{N}(0,\sigma_{img}^2),
\qquad
\sigma_{img}=c_{img}\alpha^2
$$

The default coefficient is $c_{img}=0.045$.

Fourier magnitude noise is multiplicative:

$$
|F'(u,v)|=|F(u,v)|\exp(\eta_F(u,v))
$$

with:

$$
\eta_F\sim\mathcal{N}(0,\sigma_F^2),
\qquad
\sigma_F=c_F\alpha^2
$$

The default coefficient is $c_F=0.18$.

The square law makes low random values subtle and high values more audible. The seed depends on the image hash, the random factor and the parameter signature, so a fixed image and fixed settings remain reproducible.

The Photo analysis panel displays the unperturbed analysis maps. When Random factor is nonzero, the generated composition can use the perturbed analysis, but the displayed maps remain a clean reference for the original image.

---

## 17. Parameter Reference

The Parameters box is organized into mini-pages, following the same style as the Audio Visualization app.

### 17.1 Structure

| Parameter | Default | Role |
|---|---|---|
| Number of bars | photo-adaptive | total duration in 4/4 bars |
| Variation strength | photo-adaptive | second-half melodic and harmonic change |
| Composition complexity | photo-adaptive | note density and texture activity |
| Random factor | 0 | controlled perturbation of image/Fourier analysis |
| Auto complexity range | 0.25-0.90 | maps texture entropy to complexity |
| Auto variation range | 0.25-0.85 | maps $1-S$ to variation |
| Auto min-bars range | 4-8 | low/high range for automatic minimum bar count |
| Auto max-bars range | 12-24 | low/high range for automatic maximum bar count |
| Auto default-bars range | 6-16 | low/high range for automatic default bar count |
| Bar weights | 0.40 / 0.25 / 0.20 / 0.15 | relative role of texture, edges, high frequencies and periodicity |

### 17.2 Image analysis

| Parameter | Default | Role |
|---|---|---|
| Analysis max side | 512 px | maximum side length for feature extraction |
| Spatial noise coefficient | 0.045 | strength of Random factor in RGB space |
| Entropy histogram bins | 64 | resolution of texture entropy histogram |
| Edge threshold percentile | 75% | adaptive edge threshold |
| Minimum edge threshold | 0.08 | fixed lower bound for edge threshold |
| Luminance percentile range | 5%-95% | dynamic range and shadow/highlight percentiles |
| Shadow floor | 0.18 | minimum threshold for dark regions |
| Shadow percentile offset | 0.03 | offset added to low luminance percentile |
| Highlight floor | 0.82 | upper reference threshold for bright regions |
| Highlight percentile offset | 0.03 | offset subtracted from high luminance percentile |

### 17.3 Fourier and saliency

| Parameter | Default | Role |
|---|---|---|
| DC exclusion radius | 0.025 | removes near-DC energy from Fourier descriptors |
| Low/mid/high radial limits | 0.14 / 0.34 | separates spatial frequency bands |
| Orientation bandwidth | 0.38 | angular width for horizontal/vertical energies |
| Peak-score percentile range | 90%-99.7% | compares strong peaks to background power |
| Peak-score log divisor | 5.0 | compresses periodic peak score |
| Fourier noise coefficient | 0.18 | strength of Random factor in Fourier magnitude |
| Saliency weights | 0.42 / 0.34 / 0.24 | edge, color rarity and luminance rarity contributions |
| Center-bias weight | 0.12 | weight of central composition bias |
| Saliency threshold percentile | 96% | selects strongest saliency regions |
| Minimum saliency threshold | 0.20 | fixed lower bound for saliency mask |
| Solo note-count range | 3-18 | maps saliency strength to solo note count |
| Solo note cap | 22 | maximum number of solo notes |
| Minimum saliency-point distance | 0.055 | prevents solo notes from clustering |
| Solo duration range | 0.18-1.25 beats | duration clamp for solo notes |

### 17.4 Tonality and tempo

| Parameter | Default | Role |
|---|---|---|
| Scale | Automatic | choose or override the modal scale |
| Mapping style | Scientific | tempo mapping formula |
| Manual BPM | 90 | fixed tempo when Manual is selected |
| Scientific BPM range | 48-152 | clamp range for Scientific formula |
| Balanced BPM range | 56-132 | clamp range for Balanced formula |
| Musical BPM range | 72-108 | clamp range for Musical formula |

### 17.5 Synth and mix

| Parameter | Default | Role |
|---|---|---|
| Synthesizer type | GeneralUser GS | rendering backend |
| Instrument layer selection | Automatic | automatic or manual instrument choices |
| Target peak | 0.86 | master peak limit |
| Target RMS | 0.16 | master RMS limit |
| Maximum render duration | 120 s | safety cap for long outputs |
| FluidSynth master gain | 0.45 | gain sent to FluidSynth |
| Chord double-hit high-frequency threshold | 0.22 | activates second chord hit per bar |
| Melody density threshold | 0.52 | controls melody slice step |
| Melody energy gate | 0.10 | skips very low-energy melody slices |
| Texture activation threshold | 0.28 | activates arpeggio texture |
| Percussion activation threshold | 0.18 | activates short tick events |

### 17.6 Instruments

In Manual instrument mode, the Instruments page lets the user select the instrument and gain for each layer. Gains are expressed in dB over the range $[-24,12]$ dB. In Automatic mode, this page displays the photo-selected instruments instead.

---

## 18. Limitations

The app is feature-based, not semantic. It does not know whether the photo contains a person, a landscape, a city or an abstract painting. Two different images with similar luminance, color, edge and Fourier statistics may produce similar music.

The mapping is designed for interpretability, not for universal aesthetics. The scale choices, chord progressions and instrument affinities follow a Western tonal framework. They are explicit design choices, not general laws of visual music.

The Simple synthesizer is lightweight and explainable, but it is not a physical model of real instruments. GeneralUser GS mode gives more realistic timbres, but it depends on FluidSynth and a SoundFont.

High-resolution noisy photos can produce high edge density and high Fourier energy, which may lead to fast and dense compositions. The analysis resize and threshold parameters are provided so the user can control this behavior.

Random factor is deterministic for fixed settings, but it still changes the analysis used for composition. The displayed photo maps remain unperturbed so that the user can distinguish between the original visual analysis and the randomized composition behavior.

---
