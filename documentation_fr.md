## Table des matières

1. [Vue d'ensemble : de la photo à la composition musicale](#1-vue-densemble--de-la-photo-a-la-composition-musicale)
2. [Représentation de l'image et analyse de luminance](#2-representation-de-limage-et-analyse-de-luminance)
3. [Descripteurs spatiaux : contours, entropie de texture et symétrie](#3-descripteurs-spatiaux--contours-entropie-de-texture-et-symetrie)
4. [Caractéristiques chromatiques et colorimétriques](#4-caracteristiques-chromatiques-et-colorimetriques)
5. [Estimation de la saillance visuelle](#5-estimation-de-la-saillance-visuelle)
6. [Analyse de Fourier bidimensionnelle](#6-analyse-de-fourier-bidimensionnelle)
7. [Paramètres musicaux automatiques](#7-parametres-musicaux-automatiques)
8. [Progression d'accords et structure harmonique](#8-progression-daccords-et-structure-harmonique)
9. [Mélodie et composition en couches](#9-melodie-et-composition-en-couches)
10. [Sélection automatique et manuelle des instruments](#10-selection-automatique-et-manuelle-des-instruments)
11. [Synthèse additive et enveloppes ADSR](#11-synthese-additive-et-enveloppes-adsr)
12. [Couche solo pilotée par la saillance](#12-couche-solo-pilotee-par-la-saillance)
13. [Rendu stéréo et panoramique à puissance constante](#13-rendu-stereo-et-panoramique-a-puissance-constante)
14. [Traitement du bus maître](#14-traitement-du-bus-maitre)
15. [Export MIDI](#15-export-midi)
16. [Random Factor et perturbations contrôlées](#16-random-factor-et-perturbations-controlees)
17. [Graphiques d'analyse audio](#17-graphiques-danalyse-audio)
18. [Limites et interprétation](#18-limites-et-interpretation)

---

## 1. Vue d'ensemble : de la photo à la composition musicale

Cette application convertit une image fixe en une courte composition musicale multicouche. Aucun modèle entraîné n'est utilisé à aucun stade. L'ensemble de la chaîne repose sur des opérations classiques de traitement du signal et de traitement d'image, dont les sorties sont associées de manière déterministe à des décisions musicales.

L'idée centrale est la sonification : l'association d'attributs physiques ou perceptifs mesurables d'un signal non audio à des paramètres audibles. Ici, le signal source est une photographie, et la cible est une pièce musicale structurée avec mélodie, harmonie, rythme et timbre.

La chaîne de traitement est :

$$
\text{photo}
\;\xrightarrow{\text{analyse}}\;
\mathbf{f}
\;\xrightarrow{\text{mapping}}\;
\{\text{events}\}
\;\xrightarrow{\text{synthesis}}\;
\text{audio} + \text{MIDI}
$$

où $\mathbf{f}$ est un vecteur de descripteurs visuels scalaires, et $\{\text{events}\}$ est une liste ordonnée d'événements de notes. Chaque événement contient un temps de début, une durée, une hauteur MIDI, une vélocité, un identifiant d'instrument, une valeur de panoramique stéréo et un label de couche.

Le mapping est entièrement déterministe lorsque le Random Factor est fixé à zéro : une même image d'entrée et les mêmes paramètres produisent toujours la même sortie. Cette reproductibilité rend le système interprétable et vérifiable, contrairement aux systèmes audio génératifs dont l'état interne n'est pas accessible.

La composition est organisée en six couches :

| Couche | Rôle |
|---|---|
| Main | contour mélodique principal dérivé des tranches de luminance |
| Texture | arpèges, accents de hautes lumières et micro-événements rythmiques |
| Bass | fondation harmonique basse fréquence |
| Pad | longues sonorités atmosphériques soutenues |
| Chord | support harmonique et frappes d'accords |
| Solo | mélodie d'accent pilotée par la saillance visuelle, seulement en mode GeneralUser GS |

---

## 2. Représentation de l'image et analyse de luminance

### 2.1 Normalisation de l'entrée

L'image d'entrée est convertie dans l'espace colorimétrique RGB, puis normalisée de sorte que chaque canal appartienne à $[0, 1]$. Si l'image possède un quatrième canal (RGBA), le canal alpha est supprimé. On note $R, G, B : \Omega \to [0,1]$ les trois images de canaux normalisés sur la grille de pixels $\Omega$ de taille $H \times W$.

### 2.2 Luminance perceptive

Une image de luminance est calculée avec les poids perceptifs ITU-R BT.709 :

$$
Y(x,y) = 0.2126\, R(x,y) + 0.7152\, G(x,y) + 0.0722\, B(x,y)
$$

Ces coefficients reflètent la sensibilité différente du système visuel humain aux trois couleurs primaires : le vert contribue à plus de soixante-dix pour cent de la luminosité perçue, le rouge à un peu plus de vingt pour cent, et le bleu à moins de huit pour cent. Le résultat $Y$ constitue le champ scalaire principal utilisé pour la plupart des descripteurs structurels.

### 2.3 Luminosité globale et contraste

La luminosité globale est la moyenne spatiale de la luminance :

$$
\mu_Y = \frac{1}{HW} \sum_{(x,y) \in \Omega} Y(x,y)
$$

Le contraste est l'écart-type :

$$
\sigma_Y = \sqrt{\frac{1}{HW} \sum_{(x,y) \in \Omega} \bigl(Y(x,y) - \mu_Y\bigr)^2}
$$

La dynamique est estimée à partir de percentiles robustes afin d'éviter une sensibilité excessive aux pixels aberrants :

$$
D_Y = P_{95}(Y) - P_{05}(Y)
$$

où $P_q$ désigne le $q$-ième percentile calculé sur l'ensemble des pixels.

### 2.4 Régions d'ombres et de hautes lumières

Les masques d'ombres et de hautes lumières sont déduits de seuils adaptatifs basés sur les percentiles :

$$
\mathcal{S} = \bigl\{(x,y) : Y(x,y) < \max\bigl(0.18,\; P_{05}(Y) + 0.03\bigr)\bigr\}
$$

$$
\mathcal{H} = \bigl\{(x,y) : Y(x,y) > \min\bigl(0.82,\; P_{95}(Y) - 0.03\bigr)\bigr\}
$$

La proportion d'ombres et la proportion de hautes lumières sont :

$$
s = \frac{|\mathcal{S}|}{HW}, \qquad h = \frac{|\mathcal{H}|}{HW}
$$

Ces deux scalaires influencent l'ambiance musicale, le poids de la basse, le registre mélodique et la sélection automatique de la gamme.

### 2.5 Centroïdes spatiaux

Pour le panoramique musical, l'application calcule séparément le centre de masse horizontal de la région lumineuse, de la région d'ombres et de la région de hautes lumières. Étant donnée une carte de poids $w(x,y)$, le centroïde horizontal est :

$$
c_x = \frac{\sum_{(x,y)} x \cdot w(x,y)}{\sum_{(x,y)} w(x,y)}
$$

normalisé de sorte que $c_x \in [0, 1]$.

Le centroïde lumineux utilise $w = \max(Y - \mu_Y, 0)$, le centroïde des ombres utilise $w = (1-Y) \cdot \mathbf{1}_{\mathcal{S}}$, et le centroïde des hautes lumières utilise $w = Y \cdot \mathbf{1}_{\mathcal{H}}$. Ces positions contrôlent le décalage de panoramique initial de la mélodie principale, de la couche de basse et des frappes d'accords, ce qui donne à l'image stéréo une correspondance spatiale avec la photographie.

---

## 3. Descripteurs spatiaux : contours, entropie de texture et symétrie

### 3.1 Carte de contours basée sur le gradient

Les contours spatiaux sont extraits en calculant le gradient du champ de luminance. Les composantes discrètes du gradient $\partial_x Y$ et $\partial_y Y$ sont obtenues avec `numpy.gradient`, qui utilise des différences centrales d'ordre deux à l'intérieur et des différences unilatérales d'ordre un aux bords. La magnitude du contour est :

$$
G(x,y) = \sqrt{\bigl(\partial_x Y(x,y)\bigr)^2 + \bigl(\partial_y Y(x,y)\bigr)^2}
$$

La carte $G$ est ensuite normalisée dans $[0,1]$ :

$$
\hat{G}(x,y) = \frac{G(x,y) - \min G}{\max G - \min G}
$$

La densité de contours est la fraction de pixels dont la magnitude normalisée dépasse un seuil adaptatif :

$$
D_e = \frac{1}{HW}\, \bigl|\bigl\{(x,y) : \hat{G}(x,y) > \max(0.08,\; P_{75}(\hat{G}))\bigr\}\bigr|
$$

Ce seuil s'adapte à la distribution globale des contours de l'image, de sorte qu'il reste significatif pour des photographies douces comme pour des photographies nettes. Musicalement, la densité de contours contrôle l'activité rythmique, la netteté des attaques et le mode de tempo Scientific.

### 3.2 Entropie de texture

La carte de contours normalisée $\hat{G}$ est considérée comme un descripteur spatial de texture. Son histogramme sur $K = 64$ classes uniformément espacées dans $[0, 1]$ définit une loi de probabilité discrète $\{p_k\}$. L'entropie de Shannon normalisée de cette distribution est :

$$
H_{\mathrm{tex}} = -\frac{1}{\log_2 K} \sum_{k=1}^{K} p_k \log_2 p_k
$$

La normalisation par $\log_2 K$ ramène l'entropie dans $[0, 1]$ quel que soit $K$, avec $H_{\mathrm{tex}} = 0$ pour une carte de contours parfaitement uniforme (tous les pixels identiques) et $H_{\mathrm{tex}} \to 1$ pour une distribution de contours maximalement étalée.

Un arrière-plan photographique lisse donne un faible $H_{\mathrm{tex}}$. Une scène chargée, avec des structures irrégulières et des forces de contours variées, donne un $H_{\mathrm{tex}}$ plus élevé. Ce descripteur pilote deux valeurs musicales par défaut :

$$
C_{\mathrm{auto}} = \operatorname{clip}\!\bigl(0.25 + 0.65\, H_{\mathrm{tex}},\; 0.25,\; 0.90\bigr)
$$

$$
B_s = 0.40\, H_{\mathrm{tex}} + 0.25\, D_e + 0.20\, E_{\mathrm{high}} + 0.15\, P
$$

où $C_{\mathrm{auto}}$ est la complexité automatique de composition, $B_s$ le score de nombre de mesures, $E_{\mathrm{high}}$ l'énergie de la bande haute de Fourier et $P$ le score de pic périodique (définis en Section 6).

### 3.3 Symétrie gauche-droite et haut-bas

La symétrie est estimée en comparant l'image de luminance avec ses réflexions. On note $\tilde{Y}_{LR}(x,y) = Y(W-1-x, y)$ le miroir gauche-droite et $\tilde{Y}_{TB}(x,y) = Y(x, H-1-y)$ le miroir haut-bas. Les scores de similarité correspondants sont :

$$
S_{LR} = 1 - \frac{1}{HW}\sum_{(x,y)} \bigl|Y(x,y) - \tilde{Y}_{LR}(x,y)\bigr|
$$

$$
S_{TB} = 1 - \frac{1}{HW}\sum_{(x,y)} \bigl|Y(x,y) - \tilde{Y}_{TB}(x,y)\bigr|
$$

Le score de symétrie combiné pondère plus fortement la symétrie gauche-droite :

$$
S = 0.70\, S_{LR} + 0.30\, S_{TB}
$$

La force de variation automatique est alors :

$$
V_{\mathrm{auto}} = \operatorname{clip}\!\bigl(0.25 + 0.60\,(1 - S),\; 0.25,\; 0.85\bigr)
$$

Une image symétrique tend donc à produire des formes musicales stables et répétitives. Une image asymétrique tend à produire une évolution plus marquée dans la seconde moitié, davantage de déviations mélodiques et un mouvement harmonique plus riche.

---

## 4. Caractéristiques chromatiques et colorimétriques

### 4.1 Décomposition HSV

La représentation hue, saturation and value (HSV) fournit des caractéristiques chromatiques perceptivement pertinentes. À partir des valeurs RGB normalisées, la valeur (brightness) est :

$$
V_c = \max(R, G, B)
$$

Le chroma (étendue colorée) est :

$$
\delta = V_c - \min(R, G, B)
$$

La saturation est :

$$
\text{Sat} = \begin{cases} \delta / V_c & \text{if } V_c > 0 \\ 0 & \text{otherwise} \end{cases}
$$

L'angle de hue dans $[0,1)$ est calculé à partir du canal dominant, selon la formule standard avec un résultat pris modulo 1.

### 4.2 Hue dominant par moyenne circulaire pondérée

Une moyenne arithmétique directe des valeurs de hue n'a pas de sens, car la hue est une quantité circulaire définie sur le cercle unité. L'application utilise une moyenne circulaire pondérée. Le poids de chaque pixel est :

$$
w(x,y) = \mathrm{Sat}(x,y) \cdot \bigl(0.25 + Y(x,y)\bigr)
$$

de sorte que les pixels très saturés et bien éclairés contribuent davantage. L'angle de hue moyen est alors :

$$
\bar{h} = \frac{1}{2\pi} \arctan_2\!\left(\sum_{(x,y)} w \sin(2\pi h),\; \sum_{(x,y)} w \cos(2\pi h)\right) \bmod 1
$$

où $\arctan_2$ renvoie une valeur dans $(-\pi, \pi]$. Le résultat $\bar{h} \in [0,1)$ encode l'identité chromatique dominante de l'image d'une manière indépendante du placement arbitraire du rouge en $h=0$ et robuste aux distributions de hue bimodales.

### 4.3 Chaleur chromatique

Un indice scalaire de chaleur est défini comme la différence moyenne entre les canaux rouge et bleu :

$$
w_{\mathrm{arm}} = \frac{1}{HW}\sum_{(x,y)} \bigl(R(x,y) - B(x,y)\bigr)
$$

Une valeur positive indique une image chaude (plus de rouge, orange ou jaune), tandis qu'une valeur négative indique une image froide (plus de bleu ou cyan). La chaleur contribue à la sélection de la gamme et au score d'affinité des instruments.

---

## 5. Estimation de la saillance visuelle

### 5.1 Motivation

La saillance visuelle est la propriété d'une région à attirer le regard. Les régions saillantes ne sont pas simplement lumineuses ou contrastées : elles sont visuellement distinctives par rapport à leur environnement. Dans cette application, une carte de saillance guide le placement, la hauteur et l'espacement des notes d'accent de la couche solo, afin que les éléments les plus visuellement importants de l'image produisent les événements mélodiques les plus proéminents.

### 5.2 Modèle de saillance à trois composantes

La carte de saillance est construite à partir de trois composantes complémentaires.

**Rareté chromatique.** Elle mesure à quel point la couleur de chaque pixel diffère de la couleur moyenne de l'image :

$$
C_r(x,y) = \left\| \begin{pmatrix} R(x,y) \\ G(x,y) \\ B(x,y) \end{pmatrix} - \begin{pmatrix} \bar{R} \\ \bar{G} \\ \bar{B} \end{pmatrix} \right\|_2
$$

où $(\bar{R}, \bar{G}, \bar{B})$ est le vecteur RGB moyen sur tous les pixels. Les pixels éloignés de la couleur moyenne globale sont localement inhabituels et ont donc tendance à être saillants.

**Rareté de luminance.** Elle mesure à quel point la luminosité de chaque pixel diffère de la moyenne :

$$
L_r(x,y) = |Y(x,y) - \mu_Y|
$$

**Force de contour.** La quantité $\hat{G}(x,y)$ définie en Section 3 contribue également, car les frontières à fort contraste attirent l'attention.

$C_r$ et $L_r$ sont normalisés indépendamment dans $[0,1]$ avant combinaison. La saillance de base est :

$$
\mathcal{B}(x,y) = 0.42\, \hat{G}(x,y) + 0.34\, \hat{C}_r(x,y) + 0.24\, \hat{L}_r(x,y)
$$

### 5.3 Biais central

La photographie naturelle place souvent les sujets au centre, et le système visuel humain présente un biais de fixation centrale lors du regard libre. Un poids radial de type gaussien est donc ajouté :

$$
\text{CB}(x,y) = 1 - \left\|\begin{pmatrix} x/(W-1) - 0.5 \\ y/(H-1) - 0.5 \end{pmatrix}\right\|_2
$$

normalisé dans $[0,1]$.

La carte de saillance finale est :

$$
\mathcal{S}(x,y) = \mathrm{normalize}_{[0,1]}\!\bigl(0.88\,\mathcal{B}(x,y) + 0.12\,\text{CB}(x,y)\bigr)
$$

### 5.4 Descripteurs de saillance

Les 4% supérieurs des valeurs de saillance définissent le masque de premier plan $\mathcal{M}$. À partir de ce masque, l'application extrait :

| Descripteur | Formule |
|---|---|
| Pic de saillance | $\max_{(x,y)} \mathcal{S}(x,y)$ |
| Moyenne de saillance | $\frac{1}{HW}\sum \mathcal{S}(x,y)$ |
| Aire saillante | $\frac{1}{HW}|\mathcal{M}|$ |
| Centroïde de saillance | $(c_x, c_y)$ à partir du centre de masse pondéré de $\mathcal{M}$ |
| Dispersion de saillance | écart-type pondéré de la distance au centroïde, normalisé |

La dispersion est :

$$
\sigma_{\mathcal{S}} = \operatorname{clip}\!\left(\frac{1}{0.45}\sqrt{\frac{\sum_{(x,y)} w(x,y) \bigl[(x_n - c_x)^2 + (y_n - c_y)^2\bigr]}{\sum_{(x,y)} w(x,y)}},\; 0,\; 1\right)
$$

où $x_n = x/(W-1)$, $y_n = y/(H-1)$ et $w(x,y) = \mathcal{S}(x,y) \cdot \mathbf{1}_{\mathcal{M}}$.

---

## 6. Analyse de Fourier bidimensionnelle

### 6.1 Prétraitement

Avant de calculer la TFD 2D, l'image de luminance est prétraitée pour réduire les fuites spectrales. La luminance moyenne est soustraite (suppression du DC), et une fenêtre de Hanning séparable est appliquée :

$$
\tilde{Y}(x,y) = \bigl(Y(x,y) - \mu_Y\bigr) \cdot w_H(x) \cdot w_H(y)
$$

où $w_H(n) = 0.5 - 0.5\cos(2\pi n / (N-1))$ est la fenêtre de Hanning à $N$ points. Le fenêtrage réduit le phénomène de Gibbs qui apparaît lorsqu'une image finie est traitée comme un signal périodique, et évite que les fortes discontinuités aux bords ne polluent les estimations spectrales.

### 6.2 Spectre centré

La TFD 2D est calculée par l'algorithme FFT, puis immédiatement décalée en fréquence afin que la composante DC soit au centre du spectre :

$$
F(u, v) = \mathrm{FFTshift}\!\left[\,\sum_{x=0}^{W-1}\sum_{y=0}^{H-1} \tilde{Y}(x,y)\, e^{-j2\pi(ux/W + vy/H)}\right]
$$

La carte affichée est le log-magnitude :

$$
M_{\log}(u,v) = \log\!\bigl(1 + |F(u,v)|\bigr)
$$

normalisé dans $[0,1]$ pour la visualisation. Le logarithme est nécessaire car la magnitude de la TFD possède une très grande dynamique : les coefficients les plus forts peuvent être plusieurs ordres de grandeur au-dessus des plus faibles.

### 6.3 Bandes de fréquence radiale

On note $r(u,v)$ la fréquence radiale normalisée, définie comme la distance euclidienne entre le centre DC et chaque bin fréquentiel, divisée par la fréquence radiale maximale disponible. Trois bandes fréquentielles découpent le spectre hors DC :

| Bande | Intervalle radial $r$ | Signification visuelle |
|---|---|---|
| Low | $[0.025,\; 0.14)$ | grandes structures lisses, gradients lents de luminance |
| Mid | $[0.14,\; 0.34)$ | formes et transitions à échelle moyenne |
| High | $[0.34,\; 1]$ | contours, textures fines, micro-détails, bruit |

L'énergie normalisée dans une bande $\mathcal{B}$ est :

$$
E_{\mathcal{B}} = \frac{\displaystyle\sum_{(u,v)\in\mathcal{B}} |F(u,v)|^2}{\displaystyle\sum_{(u,v)\notin\mathcal{D}} |F(u,v)|^2}
$$

où $\mathcal{D}$ est la région DC $r < 0.025$, exclue de tous les calculs de bandes. L'énergie basse fréquence gouverne le poids des couches soutenues (pad, basse). L'énergie haute fréquence gouverne la densité des arpèges, la brillance de la couche texture et l'agressivité de la formule de tempo Scientific.

### 6.4 Centroïde spectral et largeur de bande

Le centroïde pondéré par la puissance du spectre hors DC est :

$$
\rho_c = \frac{\displaystyle\sum_{(u,v)\notin\mathcal{D}} r(u,v)\,|F(u,v)|^2}{\displaystyle\sum_{(u,v)\notin\mathcal{D}} |F(u,v)|^2}
$$

et la largeur de bande spectrale est l'écart-type pondéré par la puissance autour de ce centroïde :

$$
B = \sqrt{\frac{\displaystyle\sum_{(u,v)\notin\mathcal{D}} \bigl(r(u,v) - \rho_c\bigr)^2 |F(u,v)|^2}{\displaystyle\sum_{(u,v)\notin\mathcal{D}} |F(u,v)|^2}}
$$

Un centroïde élevé signifie que l'énergie spectrale est concentrée sur les échelles fines. Une grande largeur de bande signifie que le spectre est réparti sur de nombreuses échelles. Ces deux quantités contribuent à la formule de tempo Scientific et au paramètre de densité des arpèges.

### 6.5 Énergie fréquentielle directionnelle

L'angle de chaque bin fréquentiel est $\theta(u,v) = \arctan_2(v, u)$. Le spectre est séparé en :

- **énergie horizontale** : bins tels que $|\sin\theta| < 0.38$ (fréquences orientées selon des structures horizontales)
- **énergie verticale** : bins tels que $|\cos\theta| < 0.38$
- **énergie diagonale** : complément $1 - E_h - E_v$

Ces composantes directionnelles ne sont pas directement utilisées pour la génération de notes dans la version actuelle, mais elles sont calculées et exportées vers le panneau d'analyse.

### 6.6 Score de pic périodique

Le score de pic périodique estime à quel point le spectre est dominé par quelques fréquences proéminentes, par opposition à un fond large :

$$
P = \operatorname{clip}\!\left(\frac{\log\!\bigl(1 + P_{99.7}(|F|^2) / (P_{90}(|F|^2) + \varepsilon)\bigr)}{5},\; 0,\; 1\right)
$$

où $P_q$ désigne le $q$-ième percentile sur toutes les valeurs de puissance hors DC, et $\varepsilon = 10^{-12}$. Un grand $P$ indique la présence de structures périodiques régulières telles que grilles, rayures ou textures fortement répétitives. Musicalement, il favorise les motifs répétitifs, les gammes pentatoniques, les comportements harmoniques en boucle et les timbres percussifs.

---

## 7. Paramètres musicaux automatiques

### 7.1 Centre tonal

Le hue dominant $\bar{h} \in [0,1)$ est associé aux 12 classes chromatiques par :

$$
k = \operatorname{round}(12\,\bar{h}) \bmod 12
$$

Le résultat est un indice dans la séquence $\{C, C\sharp, D, D\sharp, E, F, F\sharp, G, G\sharp, A, A\sharp, B\}$.

La note MIDI de la fondamentale (la note la plus basse de la plage mélodique principale) est décalée selon la luminosité :

$$
\text{root} = \operatorname{clip}\!\Bigl(\,48 + k + \operatorname{round}\!\bigl(\operatorname{interp}(\mu_Y,\,[0,1],\,[-5,7])\bigr),\; 38,\; 58\Bigr)
$$

Les images sombres utilisent donc un registre plus grave et les images lumineuses un registre plus aigu, conformément aux associations psychoacoustiques usuelles entre luminance et hauteur perçue.

### 7.2 Sélection de la gamme

Six gammes modales sont disponibles :

| Gamme | Intervalles (demi-tons depuis la tonique) |
|---|---|
| Major pentatonic | $0, 2, 4, 7, 9$ |
| Minor pentatonic | $0, 3, 5, 7, 10$ |
| Major (Ionian) | $0, 2, 4, 5, 7, 9, 11$ |
| Natural minor (Aeolian) | $0, 2, 3, 5, 7, 8, 10$ |
| Dorian | $0, 2, 3, 5, 7, 9, 10$ |
| Lydian | $0, 2, 4, 6, 7, 9, 11$ |

En mode automatique, la sélection suit un arbre de seuils :

- $\mu_Y > 0.60$ : Lydian si $w_{\mathrm{arm}} > 0.06$, sinon Major pentatonic
- $0.42 < \mu_Y \leq 0.60$ : Dorian si ($w_{\mathrm{arm}} > 0.06$ et $\mathrm{Sat} > 0.38$) ou $\sigma_Y > 0.22$, sinon Major pentatonic
- $\mu_Y \leq 0.42$ : Dorian si $w_{\mathrm{arm}} > 0.05$ et $\mathrm{Sat} > 0.30$, sinon Natural minor

Cette logique reflète l'association standard entre luminosité et tonalités majeures, et entre obscurité et tonalités mineures ou modales, tout en laissant la chaleur et la saturation introduire des cas intermédiaires.

### 7.3 Nombre de mesures

Le score de nombre de mesures $B_s$ défini en Section 3.2 pilote trois valeurs interpolées :

$$
B_{\min} = \operatorname{round}\!\bigl(\operatorname{interp}(B_s,\,[0,1],\,[4,8])\bigr)
$$

$$
B_{\max} = \operatorname{round}\!\bigl(\operatorname{interp}(B_s,\,[0,1],\,[12,24])\bigr)
$$

$$
B_0 = \operatorname{round}\!\bigl(\operatorname{interp}(B_s,\,[0,1],\,[6,16])\bigr)
$$

$B_0$ est la valeur par défaut proposée à l'utilisateur. Les images simples suggèrent des compositions courtes ; les images complexes suggèrent des structures plus longues. L'utilisateur peut remplacer le nombre de mesures dans l'intervalle automatiquement proposé, ou entrer des valeurs différentes en sélectionnant le mode Manual.

### 7.4 Tempo

Quatre stratégies de tempo sont disponibles. On note $\Delta t = 60 / T$ la période du beat en secondes :

**Scientific** utilise l'ensemble des descripteurs spatiaux et de Fourier :

$$
T = \operatorname{clip}\!\bigl(50 + 70\,D_e + 58\,\sigma_Y + 42\,P + 34\,E_{\mathrm{high}} + 22\,\rho_c - 20\,s,\; 48,\; 152\bigr)
$$

**Balanced** est une version plus douce du même principe :

$$
T = \operatorname{clip}\!\bigl(62 + 38\,D_e + 28\,\sigma_Y + 20\,P + 10\,E_{\mathrm{high}} - 8\,s,\; 56,\; 132\bigr)
$$

**Musical** est plus lisse et plus conservateur, et s'appuie davantage sur les attributs perceptifs de couleur :

$$
T = \operatorname{clip}\!\bigl(82 + 10\,\bar{\text{Sat}} + 8\,\mu_Y - 6\,s + 4\,w_{\mathrm{arm}},\; 72,\; 108\bigr)
$$

**Manual** permet à l'utilisateur de spécifier directement $T$ en BPM.

---

## 8. Progression d'accords et structure harmonique

### 8.1 Triades à partir des degrés de gamme

Pour une gamme dont la séquence d'intervalles est $I = [i_0, i_1, \ldots, i_{n-1}]$ de longueur $n$, la triade construite sur le degré $d$ est obtenue en prenant un degré sur deux :

$$
\text{chord}(d) = \bigl\{i_{d \bmod n},\; i_{(d+2) \bmod n} + 12\cdot\mathbf{1}_{d+2 \geq n},\; i_{(d+4) \bmod n} + 12\cdot\mathbf{1}_{d+4 \geq n}\bigr\}
$$

Il s'agit de l'empilement par tierces standard utilisé dans la théorie harmonique occidentale. Pour une gamme diatonique à sept notes, cela produit des triades majeures, mineures et diminuées aux degrés appropriés. Pour une gamme pentatonique, les membres de l'accord sont plus espacés, produisant un son ouvert et modal.

### 8.2 Pool de progressions

Deux pools de progressions sont disponibles selon la longueur de la gamme. Pour les gammes à sept notes, les séquences de degrés disponibles sont $[0,4,5,3]$, $[0,5,3,4]$, $[0,2,5,4]$ et $[0,3,1,4]$. Pour les gammes plus courtes, des pools plus simples sont utilisés.

La sélection est déterministe à partir d'une graine issue des caractéristiques visuelles :

$$
\text{seed} = \operatorname{round}\!\bigl(997\,\bar{h} + 113\,P + 71\,H_{\mathrm{tex}} + 53\,c_x^{\mathcal{S}}\bigr)
$$

où $c_x^{\mathcal{S}}$ est le centroïde horizontal de saillance. Cette graine est stable sous de faibles perturbations de l'image, mais change sensiblement lorsque le contenu visuel change.

### 8.3 Décalage de progression piloté par la variation

Lorsque la force de variation dépasse 0.45, la seconde moitié de la composition utilise un indice de progression décalé. Cela signifie que la boucle harmonique évolue à mi-parcours, créant une forme A-B typique de nombreuses structures musicales sans nécessiter de section bridge programmée séparément.

---

## 9. Mélodie et composition en couches

### 9.1 Ensemble de notes disponibles

Le pool de notes mélodiques est construit en énumérant toutes les hauteurs MIDI de la forme $\text{root} + 12k + i_j$ situées dans l'intervalle $[\text{root}+10, \text{root}+31]$, où $i_j$ parcourt les intervalles de la gamme. Cela limite la mélodie à une fenêtre de deux octaves, centrée légèrement au-dessus de la fondamentale tonale. Le pool de basse utilise une fenêtre plus grave $[\text{root}-18, \text{root}+7]$.

### 9.2 Balayage par tranches de luminance

L'image est divisée en $8B$ tranches verticales (où $B$ est le nombre de mesures). Pour chaque tranche $i$, la luminance moyenne, le contraste local (écart-type) et le centroïde vertical de luminosité sont calculés. Le centroïde utilise une carte de poids tronquée par percentile :

$$
w_i(y) = \max\!\bigl(Y_i(y) - P_{35}(Y_i),\; 0\bigr)
$$

afin de se concentrer sur les valeurs de luminance les plus élevées dans la tranche.

La position mélodique dans l'ensemble des notes disponibles est calculée à partir d'une combinaison entre le centroïde vertical inversé et l'écart local d'énergie :

$$
\text{pos} = \operatorname{clip}\!\bigl(1 - c_{y,i} + 0.18\,(\bar{Y}_i - \mu_Y),\; 0,\; 1\bigr)
$$

Une région lumineuse placée haut dans l'image (petit $c_{y,i}$, grand $\bar{Y}_i$) produit une note aiguë. Une région sombre placée bas produit une note grave. Ce mapping spatial-vers-hauteur est le lien expressif central entre le contenu de l'image et le contour musical.

### 9.3 Décalage mélodique par variation

Le pool de notes est divisé en quatre sections égales. Un décalage dépendant de la section $\delta_s \in \{0, 2, -2, 5\}$ est ajouté à l'indice nominal de note et multiplié par la force de variation :

$$
\text{note}_{\mathrm{final}} = \text{note}_{\mathrm{nominal}} + \operatorname{round}(\delta_s \cdot V)
$$

Pour un $V$ faible, la mélodie reste presque identique dans les deux moitiés. Pour un $V$ élevé, le contour mélodique se déplace nettement dans la seconde moitié.

### 9.4 Couche Texture

Un paramètre de densité d'arpèges de texture est déduit de :

$$
\rho_{\mathrm{tex}} = \operatorname{clip}(0.20 + 0.80\,C + 0.75\,E_{\mathrm{high}} + 0.45\,B,\; 0,\; 1)
$$

où $C$ est la complexité de composition et $B$ la largeur de bande de Fourier. Lorsque $\rho_{\mathrm{tex}} > 0.28$, des événements d'arpèges sont générés à raison d'un par beat (ou deux par beat lorsque $\rho_{\mathrm{tex}} > 0.55$), en parcourant un motif d'accord étendu. De plus, des événements rythmiques tick (percussion non pitchée sur le canal MIDI 9) sont ajoutés sur des subdivisions du beat lorsque $\rho_{\mathrm{tex}} > 0.18$.

### 9.5 Couches Pad et Chord

Les événements Pad couvrent toute la durée de chaque mesure (quatre beats), avec une légère extension legato de 0.05 beat. Leur vélocité est proportionnelle à l'énergie de Fourier basse fréquence, ce qui rend le pad plus fort lorsque l'image contient des structures lisses et de grande échelle :

$$
v_{\mathrm{pad}} = \operatorname{clip}(0.07 + 0.18\,E_{\mathrm{low}} + 0.04\,(1 - E_{\mathrm{high}}),\; 0.04,\; 0.28)
$$

Les événements Chord sont déclenchés une fois par mesure (ou deux fois lorsque $E_{\mathrm{high}} > 0.22$), en jouant simultanément les trois notes de l'accord courant de la progression.

Les événements Bass suivent un motif fondamentale-quinte : la fondamentale au beat 1 et la quinte juste (7 demi-tons au-dessus de la fondamentale) au beat 3, avec des vélocités proportionnelles à la proportion d'ombres et à l'énergie basse fréquence.

---

## 10. Sélection automatique et manuelle des instruments

### 10.1 Mode Simple Synthesizer

En mode Simple, les instruments sont choisis parmi une palette fixe de 15 timbres synthétisés en interne au moyen de règles explicites sur les caractéristiques. Par exemple :

- Couche Main : bright bell si $h > 0.14$ et $E_{\mathrm{high}} > 0.28$ ; celesta si $\mu_Y > 0.64$ ; kalimba si $P > 0.58$ ; marimba si $P > 0.48$ ; harp si l'image est chaude et saturée ; soft piano sinon.
- Couche Pad : warm pad si l'énergie basse fréquence est forte et que l'image est chaude, ou si les ombres sont importantes ; glass pad sinon.

### 10.2 Mode GeneralUser GS : score par familles GM

En mode GeneralUser GS, chaque couche sélectionne parmi les 128 programmes General MIDI. La sélection utilise un système continu de scores d'affinité. Chaque programme GM appartient à l'une de 16 familles (piano, chromatic percussion, organ, guitar, bass, solo strings, ensemble, brass, reed, pipe, synth lead, synth pad, synth FX, ethnic, percussive, sound FX). Un poids de famille $W_{\ell}(f)$ est défini pour chaque couche $\ell$ et chaque famille $f$ comme une combinaison linéaire de caractéristiques visuelles scalaires.

Par exemple, pour la couche Main, le poids de la famille piano est :

$$
W_{\mathrm{main}}(\mathrm{piano}) = 0.35 + 0.35\,\lambda_{\mathrm{smooth}}
$$

où $\lambda_{\mathrm{smooth}} = \operatorname{clip}(E_{\mathrm{low}} + 0.35(1-E_{\mathrm{high}}) + 0.25\,S, 0, 1)$ est un score de douceur déduit de l'énergie de Fourier et de la symétrie. Le poids de la famille pipe pour la couche Main est :

$$
W_{\mathrm{main}}(\mathrm{pipe}) = 0.18 + 0.45\,\lambda_{\mathrm{bright}} + 0.20\,\lambda_{\mathrm{smooth}}
$$

avec $\lambda_{\mathrm{bright}} = \operatorname{clip}(0.55\,\mu_Y + 0.45\,h, 0, 1)$.

Pour les programmes individuels au sein d'une famille, des bonus plus fins sont ajoutés : par exemple, les programmes du groupe celesta/music-box (8-14) reçoivent un bonus proportionnel à la proportion de hautes lumières, à l'énergie de Fourier haute fréquence et au pic de saillance.

Le score final du programme $p$ pour la couche $\ell$ est :

$$
\text{score}(p, \ell) = W_\ell(f_p) + \text{program bonus}(p) + 0.42\,u(p, \ell)
$$

où $u(p, \ell)$ est un jitter pseudo-aléatoire déterministe dans $[0,1]$, dérivé d'un hash SHA-256 du vecteur de caractéristiques. Le jitter empêche les mêmes quelques programmes d'être sélectionnés dans toutes les compositions tout en gardant la sélection reproductible à paramètres fixes.

### 10.3 Gain de couche

Le gain par couche en décibels est appliqué à la vélocité de chaque événement de note de cette couche avant le rendu audio :

$$
g = 10^{G_{\mathrm{dB}} / 20}
$$

Les vélocités après application du gain sont saturées dans $[0, 1]$.

---

## 11. Synthèse additive et enveloppes ADSR

### 11.1 Modèle ADSR

Chaque note est façonnée par une enveloppe Attack-Decay-Sustain-Release. Pour une note de $n$ échantillons à la fréquence d'échantillonnage $f_s$, l'enveloppe est :

$$
e[t] = \begin{cases}
t / t_A & 0 \leq t < t_A \\
1 - (1 - S_L)(t - t_A) / t_D & t_A \leq t < t_A + t_D \\
S_L & t_A + t_D \leq t < n - t_R \\
S_L \cdot (1 - (t - (n-t_R)) / t_R) & n - t_R \leq t < n
\end{cases}
$$

où $t_A, t_D, t_R$ sont les nombres d'échantillons d'attaque, de décroissance et de relâchement, et $S_L \in (0,1]$ est le niveau de sustain. L'enveloppe est ensuite multipliée terme à terme par la forme d'onde harmonique instantanée.

### 11.2 Recettes instrumentales

Chaque instrument utilise une combinaison spécifique de contenu harmonique et de paramètres d'enveloppe.

**Soft piano.** La forme d'onde est une somme d'harmoniques d'amplitudes décroissantes :

$$
x[t] = \sum_{m \in \{1,2,3,4,5\}} a_m \sin(2\pi m f_0 t / f_s)
$$

avec $(a_1, a_2, a_3, a_4, a_5) = (1, 0.42, 0.20, 0.10, 0.04)$. Une décroissance exponentielle est appliquée en plus de l'ADSR : $e_{\mathrm{exp}}[t] = \exp(-2.7\, t / (n / f_s))$, ce qui modélise la décroissance naturelle d'une corde frappée.

**Bright bell / celesta / music box / kalimba.** Ces instruments utilisent des partiels inharmoniques dont les rapports fréquentiels s'écartent des entiers pour simuler le comportement de barres ou de plaques métalliques. Pour la bright bell :

$$
(\text{ratios, amplitudes}) = \{(1, 1),\, (2.41, 0.55),\, (3.77, 0.30),\, (5.93, 0.16),\, (8.12, 0.06)\}
$$

Ces rapports non entiers sont caractéristiques des spectres inharmoniques et produisent le timbre métallique ou vitreux typique. La décroissance exponentielle rapide ($\tau = 4.2$) renforce le sustain court des cloches physiques.

**Harp / marimba / synth pluck.** La série harmonique utilise une décroissance d'amplitude en loi de puissance :

$$
x[t] = \sum_{k=1}^{7} k^{-1.25} \sin(2\pi k f_0 t / f_s)
$$

L'exposant $-1.25$ (entre $-1$ pour une dent de scie et $-2$ pour un triangle) produit un timbre pincé modérément brillant.

**Warm pad / glass pad.** Ces instruments utilisent un vibrato, implémenté comme un oscillateur à phase continue avec modulation sinusoïdale de fréquence :

$$
\phi[t] = \frac{2\pi f_0}{f_s}\sum_{\tau=0}^{t}\!\bigl(1 + 0.0025\sin(2\pi \cdot 4.5\, \tau / f_s)\bigr)
$$

$$
x[t] = 0.75\sin(\phi[t]) + 0.24\sin(2.01\,\phi[t]) + 0.12\sin(3.98\,\phi[t])
$$

L'ADSR possède une attaque lente (jusqu'à 65% de la durée de la note) et un niveau de sustain élevé (0.78), produisant le gonflement lent caractéristique.

**Cello-like bass / bowed string.** Modèle de vibrato similaire avec une profondeur de modulation plus élevée ($0.004$) et une fréquence légèrement plus rapide ($5.1$ Hz) :

$$
x[t] = 0.75\sin(\phi[t]) + 0.33\sin(2\phi[t]) + 0.17\sin(3\phi[t])
$$

L'ADSR modélise l'attaque de l'archet ($t_A = 0.07\,\text{s}$) et un sustain long.

**Clarinet-like reed.** Le spectre de la clarinette est dominé par les harmoniques impairs. La forme d'onde $x[t] = \sin(2\pi f_0 t) - 0.33\sin(6\pi f_0 t) + 0.17\sin(10\pi f_0 t)$ approxime cette caractéristique.

Après application de l'enveloppe, chaque note est normalisée en pic puis multipliée par sa vélocité $v \in [0,1]$, de sorte que la vélocité contrôle l'amplitude sans déformer le timbre.

---

## 12. Couche solo pilotée par la saillance

### 12.1 Motivation

La couche solo, disponible uniquement en mode GeneralUser GS, place un ensemble clairsemé de notes d'accent à des positions temporelles et des hauteurs dérivées directement de la carte de saillance. L'idée est de rendre audibles les éléments visuellement les plus importants de la photographie sous forme d'événements mélodiques distincts, flottant au-dessus de la texture harmonique des autres couches.

### 12.2 Échantillonnage spatial des pixels saillants

Un scalaire composite de force de saillance est d'abord calculé :

$$
\eta = \operatorname{clip}\!\bigl(0.55\,\text{sal\_peak} + 0.25\,\text{sal\_mean} + 0.20\,(1 - \text{sal\_area}),\; 0,\; 1\bigr)
$$

Il combine l'intensité du pic, la densité spatiale et l'inverse de l'aire saillante : une région focalisée et intense donne un grand $\eta$, tandis qu'une image diffuse et faiblement saillante donne un faible $\eta$.

Le nombre de notes solo est :

$$
N_{\mathrm{solo}} = \operatorname{clip}\!\bigl(\operatorname{round}(\operatorname{interp}(\eta,\,[0,1],\,[3,18])),\; 2,\; 22\bigr)
$$

Les $N_{\mathrm{cand}}$ pixels les plus saillants (avec $N_{\mathrm{cand}} = \max(64, 18 N_{\mathrm{solo}})$) sont identifiés, puis filtrés par une règle spatiale d'inhibition of return : deux positions sélectionnées doivent être séparées d'au moins 5.5% de la diagonale de l'image. Cela évite que les notes solo se regroupent sur une seule petite région.

### 12.3 Attribution du temps et de la hauteur

La position horizontale de chaque pixel saillant sélectionné est associée au temps :

$$
t_k = x_k^{\mathrm{norm}} \cdot T_{\mathrm{dur}} + 0.10\,\Delta t\,\sin(1.7\,k)
$$

où $x_k^{\mathrm{norm}} \in [0,1]$ est la coordonnée horizontale normalisée, $T_{\mathrm{dur}}$ la durée totale de la composition et $\Delta t$ la période du beat. Le petit jitter sinusoïdal évite que toutes les notes s'alignent strictement sur la grille horizontale des pixels.

La position verticale est associée à la hauteur : les points saillants hauts (petit $y^{\mathrm{norm}}$) produisent des hauteurs plus aiguës, conformément à la convention utilisée pour la mélodie principale :

$$
\text{note}_k = \text{melody\_notes}\!\left[\operatorname{round}\bigl((1 - y_k^{\mathrm{norm}})\,(N_{\mathrm{mel}} - 1)\bigr)\right] + 12
$$

Le solo est transposé une octave au-dessus de la plage de la mélodie principale ($+12$ demi-tons). Une note sur cinq reçoit en plus une quinte juste ($+7$ demi-tons), ce qui ajoute de la variété intervallique à la ligne solo.

La durée de note est proportionnelle à la force de saillance et à la dispersion de saillance :

$$
d_k = \operatorname{clip}\!\bigl((0.32 + 0.70\,\mathcal{S}(y_k, x_k) + 0.20\,\sigma_{\mathcal{S}})\,\Delta t,\; 0.18\,\Delta t,\; 1.25\,\Delta t\bigr)
$$

---

## 13. Rendu stéréo et panoramique à puissance constante

### 13.1 Placement événement-vers-échantillons

Chaque événement de note de temps de début $t_{\mathrm{start}}$ est placé à l'indice d'échantillon $n_s = \operatorname{round}(t_{\mathrm{start}} \cdot f_s)$. La forme d'onde synthétisée, de longueur $n_{\mathrm{note}} = \operatorname{round}(d \cdot f_s)$ échantillons, est ajoutée dans un buffer stéréo préalloué de longueur $\lceil (T_{\mathrm{dur}} + 0.8) \cdot f_s \rceil$ échantillons. La queue de 0.8 seconde laisse de la place à la phase de release des notes longues proches de la fin de la composition.

### 13.2 Panoramique à puissance constante

Chaque note porte une valeur de panoramique $p \in [-1, 1]$. Le gain stéréo est attribué selon la loi standard de panoramique à puissance constante :

$$
g_L = \cos\!\left(\frac{\pi}{4}(p + 1)\right), \qquad g_R = \sin\!\left(\frac{\pi}{4}(p + 1)\right)
$$

Pour $p = -1$ (complètement à gauche) : $g_L = 1, g_R = 0$. Pour $p = 0$ (centre) : $g_L = g_R = 1/\sqrt{2}$. Pour $p = +1$ (complètement à droite) : $g_L = 0, g_R = 1$. La loi à puissance constante garantit que la sonie perçue reste constante lorsque la position panoramique se déplace de gauche à droite, contrairement à une loi linéaire qui produirait un creux au centre.

Les valeurs de panoramique sont dérivées des positions visuelles :

- Couche Main : panoramique vers la position horizontale du centroïde lumineux $c_x^{\mathrm{bright}}$, avec une oscillation sinusoïdale lente $\sin(0.37\,i)$ indexée par le numéro de tranche $i$.
- Couche Bass : panoramique vers le centroïde des ombres $c_x^{\mathrm{shadow}}$.
- Couche Chord : panoramique vers le centroïde lumineux avec un mouvement réduit.
- Arpèges Texture : panoramique progressif de gauche à droite lorsque l'indice d'arpège augmente.

---

## 14. Traitement du bus maître

Après le mélange de toutes les couches dans le buffer stéréo, une étape de normalisation du bus maître est appliquée. Elle ne modifie pas les gains individuels des couches ; elle agit uniquement sur le mixage stéréo final.

**Suppression du DC.** La valeur moyenne de chaque canal est soustraite :

$$
x_{\mathrm{dc}}[t] = x[t] - \frac{1}{N}\sum_{\tau=0}^{N-1} x[\tau]
$$

**Normalisation RMS.** Le niveau root-mean-square sur tous les échantillons et les deux canaux est calculé :

$$
\text{RMS} = \sqrt{\frac{1}{2N}\sum_{t=0}^{N-1}\!\bigl(x_L[t]^2 + x_R[t]^2\bigr)}
$$

Si $\text{RMS} > \text{RMS}_{\mathrm{target}} = 0.16$, le signal est réduit par le facteur $\text{RMS}_{\mathrm{target}} / \text{RMS}$.

**Normalisation de pic.** Si l'amplitude de pic résultante dépasse $\text{Peak}_{\mathrm{target}} = 0.86$, le signal est multiplié par $\text{Peak}_{\mathrm{target}} / \max|x|$.

**Limiteur de sécurité.** Un écrêtage final dur à $\pm 0.98$ empêche un dépassement numérique de se propager vers le convertisseur de format audio.

Ce processus en deux étapes (RMS puis pic) assure un niveau sonore cohérent d'une composition à l'autre tout en conservant une marge de sécurité pour les transitoires. Un fichier WAV est écrit à 44100 Hz, en PCM signé 16 bits, 2 canaux. L'encodage MP3 utilise un codec externe si disponible.

---

## 15. Export MIDI

### 15.1 Structure du fichier MIDI

L'export MIDI génère un fichier MIDI format 0 à piste unique. La résolution temporelle est $\text{PPQ} = 480$ pulses per quarter note. Cela donne un taux de ticks :

$$
\text{ticks/second} = \text{PPQ} \cdot T / 60
$$

où $T$ est le tempo en BPM. Le tempo est stocké dans l'en-tête du fichier en microsecondes par noire :

$$
\mu_{\text{QPB}} = \operatorname{round}(60{,}000{,}000 / T)
$$

### 15.2 Attribution des canaux

Chaque couche reçoit un canal MIDI fixe :

| Couche | Canal MIDI |
|---|---|
| Main | 0 |
| Texture | 1 |
| Bass | 2 |
| Pad | 3 |
| Chord | 4 |
| Solo | 5 |
| Percussion (texture tick) | 9 |

Des événements Program Change sont émis avant la première note de chaque canal, en utilisant le numéro de programme GM correspondant à l'instrument sélectionné. Le canal 9 est le canal percussion General MIDI et ne reçoit pas de Program Change.

### 15.3 Encodage à longueur variable

Les delta-times MIDI sont encodés au format variable-length quantity (VLQ) : la représentation binaire de la valeur est séparée en groupes de 7 bits, chaque groupe étant stocké dans un octet dont le bit de poids fort vaut 1 pour tous les octets sauf le dernier. Cela permet d'encoder des valeurs de ticks jusqu'à $2^{28} - 1$ avec au plus 4 octets, un schéma compact adapté aux événements musicaux clairsemés.

---

## 16. Random Factor et perturbations contrôlées

Le Random Factor $r \in [0, 100]$ ajoute des perturbations contrôlées à l'image et à l'analyse de Fourier utilisées pour générer la composition. Il ne remplace pas le mapping basé sur la photo par du hasard pur.

On définit $\alpha = r / 100 \in [0,1]$. Deux étapes de perturbation sont appliquées avant l'extraction des caractéristiques :

**Bruit RGB.** Un bruit gaussien additif est injecté dans l'image RGB normalisée :

$$
\tilde{R}(x,y) = \operatorname{clip}\!\bigl(R(x,y) + \eta_R(x,y),\; 0,\; 1\bigr), \qquad \eta_R \sim \mathcal{N}(0,\, \sigma_{\mathrm{img}}^2)
$$

avec $\sigma_{\mathrm{img}} = 0.045\,\alpha^2$. La loi quadratique rend la perturbation négligeable pour de petites valeurs de $r$ et significative seulement pour de grandes valeurs.

**Bruit sur la magnitude de Fourier.** Après calcul de la TFD 2D, la magnitude est perturbée par un facteur multiplicatif log-normal :

$$
|F'(u,v)| = |F(u,v)| \cdot \exp(\eta_{uv}), \qquad \eta_{uv} \sim \mathcal{N}(0,\, \sigma_{\mathrm{Fou}}^2)
$$

avec $\sigma_{\mathrm{Fou}} = 0.18\,\alpha^2$. La distribution log-normale garantit que la magnitude reste strictement positive et que la perturbation est multiplicative plutôt qu'additive, ce qui est un modèle plus naturel pour une incertitude d'amplitude spectrale.

Le panneau d'analyse photo affiche toujours l'analyse non perturbée (calculée avec $r=0$), afin que les visualisations et métriques ne soient pas contaminées par le bruit ajouté.

**Graine déterministe.** Pour une valeur donnée de Random Factor et une image chargée, la graine est dérivée du hash SHA-256 des octets de l'image et de la valeur du Random Factor. La même image et le même Random Factor produisent donc toujours la même perturbation, ce qui rend le système reproductible même dans son mode stochastique.

---

## 17. Graphiques d'analyse audio

Le panneau d'analyse audio affiche le contenu fréquentiel et la forme d'onde temporelle de la composition générée, décomposés par couche. Tous les graphiques fréquentiels utilisent la magnitude de la TFD monolatérale :

$$
|X[k]| = \left|\sum_{n=0}^{N-1} x[n]\, e^{-j2\pi kn/N}\right|, \qquad k = 0, 1, \ldots, \lfloor N/2 \rfloor
$$

L'axe horizontal est converti en fréquence en Hz par $f_k = k \cdot f_s / N$.

Graphiques disponibles :

| Graphique | Signification |
|---|---|
| Full Fourier magnitude | spectre global de la composition stéréo mixée |
| Waveform | enveloppe temporelle d'amplitude du mix |
| Main layer Fourier | contribution spectrale de la mélodie |
| Texture layer Fourier | contribution spectrale des arpèges et événements rythmiques |
| Bass layer Fourier | contribution spectrale de la ligne de basse |
| Pad layer Fourier | contribution spectrale de la couche atmosphérique soutenue |
| Chord layer Fourier | contribution spectrale des frappes harmoniques |
| Solo layer Fourier | contribution spectrale de la couche d'accent pilotée par la saillance (mode GS) |

Chaque graphique par couche est rendu en resynthétisant uniquement les événements de notes appartenant à cette couche, en les mélangeant en mono, puis en calculant la TFD. Cela permet une inspection indépendante du contenu spectral de chaque couche et vérifie que les événements de basse occupent les basses fréquences, que les événements de texture occupent les moyennes et hautes fréquences, et que les pads occupent la bande bas-médium.

---

## 18. Limites et interprétation

**Aveuglement sémantique.** L'application n'extrait que des quantités visuelles mesurables : luminance, magnitude de gradient, statistiques de couleur, contenu fréquentiel spatial et saillance dérivée de la rareté chromatique et du contraste de contours. Elle ne possède aucune représentation des objets, des scènes ou de la sémantique. Une image d'une forêt calme et une peinture abstraite ayant des distributions similaires de luminosité, densité de contours et couleurs peuvent produire des sorties musicales similaires. C'est une conséquence fondamentale de l'utilisation de caractéristiques interprétables de traitement du signal.

**Sensibilité à la résolution.** Puisque l'analyse utilise la résolution chargée complète jusqu'à la limite configurable `MAX_ANALYSIS_SIDE`, le mapping peut être sensible au bruit de caméra, aux artefacts de compression JPEG et aux petites textures haute fréquence. Ceux-ci peuvent augmenter la densité de contours et l'énergie de Fourier haute fréquence, poussant le tempo automatique et la complexité vers des valeurs plus élevées. Pour des photographies, un redimensionnement à 512 pixels sur le plus grand côté (valeur par défaut) est généralement approprié.

**Instruments synthétiques.** Le synthétiseur Simple utilise des recettes additives légères. Ce ne sont pas des modèles physiquement exacts d'instruments réels. Leur objectif est de garder le système léger, entièrement autonome et explicable. Le chemin GeneralUser GS utilise un SoundFont rendu par FluidSynth et produit des timbres nettement plus réalistes, mais il nécessite le fichier SoundFont et le paquet système FluidSynth.

**Conventions musicales.** Le générateur de progressions d'accords, les règles de sélection de gammes et les formules de tempo encodent des décisions esthétiques propres à la musique tonale occidentale. Le mapping n'est pas universel et ne représente pas une correspondance unique ou optimale entre caractéristiques visuelles et paramètres musicaux. C'est un choix de conception explicite, reproductible et inspectable parmi de nombreuses alternatives possibles.

---
