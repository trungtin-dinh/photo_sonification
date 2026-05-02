## Table des matières

1. [Vue d'ensemble : de la photo à la composition musicale](#1-vue-densemble--de-la-photo-a-la-composition-musicale)
2. [Correspondance visuel-musical en un coup d'oeil](#2-correspondance-visuel-musical-en-un-coup-doeil)
3. [Représentation de l'image et analyse de la luminance](#3-representation-de-limage-et-analyse-de-la-luminance)
4. [Descripteurs spatiaux : contours, entropie de texture et symétrie](#4-descripteurs-spatiaux--contours-entropie-de-texture-et-symetrie)
5. [Caractéristiques chromatiques et colorimétriques](#5-caracteristiques-chromatiques-et-colorimetriques)
6. [Estimation de la saillance visuelle](#6-estimation-de-la-saillance-visuelle)
7. [Analyse de Fourier bidimensionnelle](#7-analyse-de-fourier-bidimensionnelle)
8. [Paramètres musicaux automatiques](#8-parametres-musicaux-automatiques)
9. [Progression d'accords et structure harmonique](#9-progression-daccords-et-structure-harmonique)
10. [Mélodie et composition en couches](#10-melodie-et-composition-en-couches)
11. [Sélection automatique et manuelle des instruments](#11-selection-automatique-et-manuelle-des-instruments)
12. [Synthèse additive et enveloppes ADSR](#12-synthese-additive-et-enveloppes-adsr)
13. [Couche solo pilotée par la saillance](#13-couche-solo-pilotee-par-la-saillance)
14. [Rendu stéréo et panoramique à puissance constante](#14-rendu-stereo-et-panoramique-a-puissance-constante)
15. [Traitement du bus master](#15-traitement-du-bus-master)
16. [Export MIDI](#16-export-midi)
17. [Facteur aléatoire et perturbations contrôlées](#17-facteur-aleatoire-et-perturbations-controlees)
18. [Graphiques d'analyse audio](#18-graphiques-danalyse-audio)
19. [Limites et interprétation](#19-limites-et-interpretation)

---

## 1. Vue d'ensemble : de la photo à la composition musicale

Cette application convertit une image fixe en une courte composition musicale multicouche. Aucun modèle entraîné n'est utilisé, à aucune étape. Toute la chaîne de traitement repose sur des opérations classiques de traitement du signal et de traitement d'image, dont les sorties sont associées de manière déterministe à des décisions musicales.

L'idée centrale est la **sonification** : l'association d'attributs physiques ou perceptifs mesurables d'un signal non audio à des paramètres audibles. Ici, le signal source est une photographie, et la cible est une pièce musicale structurée avec mélodie, harmonie, rythme et timbre.

La chaîne de traitement est :

$$
\text{photo}
\;\xrightarrow{\text{analysis}}\;
\mathbf{f}
\;\xrightarrow{\text{mapping}}\;
\{\text{events}\}
\;\xrightarrow{\text{synthesis}}\;
\text{audio} + \text{MIDI}
$$

où $\mathbf{f}$ est un vecteur de descripteurs visuels scalaires et $\{\text{events}\}$ est une liste ordonnée d'événements de notes, chacun contenant un temps de début, une durée, une hauteur MIDI, une vélocité, un identifiant d'instrument, une valeur de panoramique stéréo et un label de couche.

La correspondance est entièrement déterministe lorsque le facteur aléatoire est réglé à zéro : une entrée identique et des paramètres identiques produisent toujours une sortie identique. Cette reproductibilité rend le système interprétable et vérifiable — un contraste délibéré avec les systèmes audio génératifs par IA dont l'état interne n'est pas accessible.

La composition est organisée en six couches :

| Couche | Rôle |
|---|---|
| Main | contour mélodique principal dérivé des tranches de luminance |
| Texture | arpèges, accents de hautes lumières et micro-événements rythmiques |
| Bass | fondation harmonique en basses fréquences |
| Pad | sons atmosphériques longs et soutenus |
| Chord | support harmonique et frappes d'accords |
| Solo | mélodie d'accent pilotée par la saillance visuelle (mode GeneralUser GS uniquement) |

---

## 2. Correspondance visuel-musical en un coup d'oeil

Avant d'entrer dans les détails mathématiques de chaque module, cette section fournit une lecture consolidée de toute la chaîne de traitement. Chaque décision musicale de la composition remonte à une quantité visuelle spécifique et nommée. Le tableau ci-dessous constitue la carte complète.

| Descripteur visuel | Mode de mesure | Ce qu'il contrôle dans la musique |
|---|---|---|
| **Luminance moyenne** (luminosité) | moyenne spatiale du champ de luminance perceptive $Y$ | registre mélodique (sombre → octave basse, lumineux → octave haute) ; poids de la basse ; label d'ambiance |
| **Contraste de luminance** | écart-type de $Y$ | tempo (modes Scientific/Balanced) ; vélocité des frappes d'accords ; dispersion de la vélocité mélodique |
| **Proportion d'ombres** | fraction des pixels sous un seuil adaptatif de bas percentile | vélocité de la basse ; tendance de la gamme vers mineur/Dorian ; poids du pad ; réduction du tempo |
| **Proportion de hautes lumières** | fraction des pixels au-dessus d'un seuil adaptatif de haut percentile | fréquence des arpèges ; affinité pour les timbres brillants (bells, celesta) ; activité des accords |
| **Densité de contours** | fraction des pixels de magnitude de gradient au-dessus d'un seuil adaptatif au 75e percentile | tempo (terme dominant en mode Scientific) ; netteté de l'attaque ; activité rythmique |
| **Entropie de texture** | entropie de Shannon normalisée de l'histogramme de magnitude des contours | complexité de composition (densité de notes) ; valeur par défaut du nombre de mesures ; affinité pour la brillance instrumentale |
| **Score de symétrie** | différence absolue moyenne entre $Y$ et ses miroirs gauche-droite / haut-bas | valeur par défaut de la force de variation (symétrique → boucle stable ; asymétrique → forte évolution) |
| **Teinte dominante** | moyenne circulaire pondérée de l'angle de teinte, pondérée par saturation et luminance | tonalité (associée aux 12 classes de hauteur chromatiques) |
| **Chaleur** | différence moyenne canal rouge moins canal bleu | préférence de gamme vers Lydian/Major ou Dorian/Natural minor ; affinité pour les timbres chauds |
| **Saturation moyenne** | moyenne du canal de saturation HSV | sélection de gamme (préférence Dorian à saturation modérée) ; affinité instrumentale liée à la richesse colorée |
| **Centroïde lumineux** (horizontal) | centre de masse des pixels lumineux sur l'axe horizontal | biais de panoramique stéréo de la mélodie principale et des couches d'accords |
| **Centroïde des ombres** (horizontal) | centre de masse des pixels d'ombre sur l'axe horizontal | biais de panoramique stéréo de la couche basse |
| **Énergie de Fourier basse** | fraction de puissance non DC dans les fréquences radiales $r < 0.14$ | vélocité et poids de sustain du pad ; force de la basse ; affinité pour les timbres lisses (strings, organ) |
| **Énergie de Fourier haute** | fraction de puissance non DC dans les fréquences radiales $r \geq 0.34$ | densité d'arpèges ; brillance de la couche texture ; boost de tempo (mode Scientific) ; affinité pour les timbres brillants |
| **Centroïde spectral** | fréquence radiale moyenne pondérée par la puissance | contribution au tempo (mode Scientific) ; densité de texture |
| **Largeur de bande spectrale** | écart-type pondéré par la puissance autour du centroïde | densité d'arpèges ; richesse de texture |
| **Score de pic périodique** | rapport entre pic de Fourier extrême et puissance de fond | tendance vers les gammes pentatoniques ; répétition mélodique ; affinité pour les timbres percussifs (kalimba, marimba) |
| **Pic / aire / étalement de saillance** | dérivés d'une carte de saillance à 3 composantes (rareté de couleur + rareté de luminance + force des contours) | nombre de notes d'accent de la couche solo ; leurs durées ; caractère clairsemé ou dense de la couche solo |
| **Positions des pixels saillants** | coordonnées horizontales et verticales des pixels les plus saillants | timing et hauteur de chaque note solo individuelle |
| **Séquence de tranches de luminance** | parcours gauche-droite des énergies de tranches verticales et des centroïdes verticaux | contour mélodique complet de la couche main : chaque colonne de l'image devient une note |
| **Trajectoire de palette de couleurs** | séquence ordonnée de clusters de couleurs dominantes, de gauche à droite | sélection de la progression d'accords : la diversité des teintes et les sauts de luminosité pilotent la variété harmonique |

Quelques principes de conception apparaissent lorsque ce tableau est lu dans son ensemble :

- **Le tempo et le rythme** sont principalement pilotés par la complexité spatiale : densité de contours, contraste et énergie de Fourier haute. Les images lisses et peu contrastées tendent à produire des rythmes lents et clairsemés ; les images nettes et détaillées tendent à produire des rythmes plus rapides et plus denses.
- **La tonalité et le mode** sont principalement pilotés par la couleur perceptive : teinte → tonalité, luminosité + chaleur → mode, saturation → nuance modale.
- **L'instrumentation** intègre tous les groupes de caractéristiques : sombre et lisse → strings et pads ; lumineux et détaillé → bells et instruments pincés ; périodique → percussion à maillets.
- **La mélodie** possède l'encodage spatial le plus direct : l'image est littéralement lue de gauche à droite et de haut en bas, les régions lumineuses placées en hauteur produisant des hauteurs plus élevées.
- **L'harmonie** relie la couleur et la structure : la palette de couleurs dominante est ordonnée spatialement, et sa diversité pilote la variété de la progression d'accords.
- **L'image stéréo** reflète la disposition spatiale de la photo : les régions lumineuses déplacent la mélodie vers le côté où la luminosité est concentrée ; les régions d'ombre ancrent la basse.

---

## 3. Représentation de l'image et analyse de la luminance

### 2.1 Normalisation de l'entrée

L'image d'entrée est convertie dans l'espace colorimétrique RGB et normalisée de sorte que chaque canal appartienne à $[0, 1]$. Si l'image possède un quatrième canal (RGBA), le canal alpha est ignoré. Soient $R, G, B : \Omega \to [0,1]$ les trois images de canaux normalisés sur la grille de pixels $\Omega$ de taille $H \times W$.

### 2.2 Luminance perceptive

Une image de luminance est calculée à l'aide des poids perceptifs ITU-R BT.709 :

$$
Y(x,y) = 0.2126\, R(x,y) + 0.7152\, G(x,y) + 0.0722\, B(x,y)
$$

Ces coefficients reflètent la sensibilité différente du système visuel humain aux trois couleurs primaires : le vert contribue à plus de soixante-dix pour cent de la luminosité perçue, le rouge à un peu plus de vingt pour cent, et le bleu à moins de huit pour cent. Le $Y$ obtenu est le champ scalaire principal utilisé pour la plupart des descripteurs structurels.

### 2.3 Luminosité globale et contraste

La luminosité globale est la moyenne spatiale de la luminance :

$$
\mu_Y = \frac{1}{HW} \sum_{(x,y) \in \Omega} Y(x,y)
$$

Le contraste est l'écart-type :

$$
\sigma_Y = \sqrt{\frac{1}{HW} \sum_{(x,y) \in \Omega} \bigl(Y(x,y) - \mu_Y\bigr)^2}
$$

La plage dynamique est estimée à partir de percentiles robustes afin d'éviter une sensibilité excessive aux pixels aberrants :

$$
D_Y = P_{95}(Y) - P_{05}(Y)
$$

où $P_q$ désigne le $q$-ième percentile calculé sur toutes les valeurs de pixels.

### 2.4 Régions d'ombre et de hautes lumières

Les masques d'ombre et de hautes lumières sont dérivés de seuils adaptatifs fondés sur les percentiles :

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

Pour le panoramique musical, l'application calcule séparément le centre de masse horizontal de la région lumineuse, de la région d'ombre et de la région de hautes lumières. Étant donnée une carte de poids $w(x,y)$, le centroïde horizontal est :

$$
c_x = \frac{\sum_{(x,y)} x \cdot w(x,y)}{\sum_{(x,y)} w(x,y)}
$$

normalisé de sorte que $c_x \in [0, 1]$.

Le centroïde lumineux utilise $w = \max(Y - \mu_Y, 0)$, le centroïde des ombres utilise $w = (1-Y) \cdot \mathbf{1}_{\mathcal{S}}$, et le centroïde des hautes lumières utilise $w = Y \cdot \mathbf{1}_{\mathcal{H}}$. Ces positions contrôlent le décalage initial de panoramique de la mélodie principale, de la couche basse et des frappes d'accords, donnant à l'image stéréo une correspondance spatiale avec la photographie.

---

## 4. Descripteurs spatiaux : contours, entropie de texture et symétrie

### 3.1 Carte de contours fondée sur le gradient

Les contours spatiaux sont extraits en calculant le gradient du champ de luminance. Les composantes discrètes du gradient $\partial_x Y$ et $\partial_y Y$ sont obtenues via `numpy.gradient`, qui utilise des différences centrales d'ordre deux à l'intérieur et des différences unilatérales d'ordre un aux frontières. La magnitude des contours est :

$$
G(x,y) = \sqrt{\bigl(\partial_x Y(x,y)\bigr)^2 + \bigl(\partial_y Y(x,y)\bigr)^2}
$$

La carte $G$ est ensuite normalisée sur $[0,1]$ :

$$
\hat{G}(x,y) = \frac{G(x,y) - \min G}{\max G - \min G}
$$

La densité de contours est la fraction de pixels dont la magnitude normalisée dépasse un seuil adaptatif :

$$
D_e = \frac{1}{HW}\, \bigl|\bigl\{(x,y) : \hat{G}(x,y) > \max(0.08,\; P_{75}(\hat{G}))\bigr\}\bigr|
$$

Ce seuil s'adapte à la distribution globale des contours de l'image, de sorte qu'il reste significatif pour les photographies à la fois douces et nettes. Musicalement, la densité de contours contrôle l'activité rythmique, la netteté des attaques et le mode de tempo Scientific.

### 3.2 Entropie de texture

La carte de contours normalisée $\hat{G}$ est traitée comme un descripteur de texture spatiale. Son histogramme sur $K = 64$ bins régulièrement espacés sur $[0, 1]$ définit une fonction de masse de probabilité $\{p_k\}$. L'entropie de Shannon normalisée de cette distribution est :

$$
H_{\mathrm{tex}} = -\frac{1}{\log_2 K} \sum_{k=1}^{K} p_k \log_2 p_k
$$

La normalisation par $\log_2 K$ ramène l'entropie dans $[0, 1]$ quel que soit $K$, avec $H_{\mathrm{tex}} = 0$ pour une carte de contours parfaitement uniforme (tous les pixels identiques) et $H_{\mathrm{tex}} \to 1$ pour une distribution de contours maximalement étalée.

Un arrière-plan photographique lisse donne un $H_{\mathrm{tex}}$ faible. Une scène chargée, avec des structures irrégulières et des forces de contours variées, donne un $H_{\mathrm{tex}}$ élevé. Ce descripteur pilote deux valeurs musicales par défaut :

$$
C_{\mathrm{auto}} = \operatorname{clip}\!\bigl(0.25 + 0.65\, H_{\mathrm{tex}},\; 0.25,\; 0.90\bigr)
$$

$$
B_s = 0.40\, H_{\mathrm{tex}} + 0.25\, D_e + 0.20\, E_{\mathrm{high}} + 0.15\, P
$$

où $C_{\mathrm{auto}}$ est la complexité automatique de composition, $B_s$ est le score de nombre de mesures, $E_{\mathrm{high}}$ est l'énergie de la bande de Fourier haute et $P$ est le score de pic périodique (tous deux définis en Section 6).

### 3.3 Symétrie gauche-droite et haut-bas

La symétrie est estimée en comparant l'image de luminance avec ses réflexions. Soit $\tilde{Y}_{LR}(x,y) = Y(W-1-x, y)$ le miroir gauche-droite et $\tilde{Y}_{TB}(x,y) = Y(x, H-1-y)$ le miroir haut-bas. Les scores de similarité correspondants sont :

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

Une image symétrique tend donc à produire des formes musicales stables et répétitives. Une image asymétrique tend à produire une évolution plus forte dans la seconde moitié, une déviation mélodique plus marquée et un mouvement harmonique plus riche.

---

## 5. Caractéristiques chromatiques et colorimétriques

### 4.1 Décomposition HSV

La représentation hue, saturation and value (HSV) fournit des caractéristiques chromatiques perceptivement significatives. À partir des valeurs RGB normalisées, la valeur (luminosité) est :

$$
V_c = \max(R, G, B)
$$

La chroma (étendue de couleur) est :

$$
\delta = V_c - \min(R, G, B)
$$

La saturation est :

$$
\text{Sat} = \begin{cases} \delta / V_c & \text{if } V_c > 0 \\ 0 & \text{otherwise} \end{cases}
$$

L'angle de teinte dans $[0,1)$ est calculé à partir du canal dominant, selon la formule standard avec un résultat pris modulo 1.

### 4.2 Teinte dominante par moyenne circulaire pondérée

Une simple moyenne arithmétique des valeurs de teinte n'a pas de sens, car la teinte est une quantité circulaire définie sur le cercle unité. L'application utilise une moyenne circulaire pondérée. Le poids de chaque pixel est :

$$
w(x,y) = \mathrm{Sat}(x,y) \cdot \bigl(0.25 + Y(x,y)\bigr)
$$

de sorte que les pixels très saturés et bien éclairés contribuent davantage. L'angle de teinte moyen est alors :

$$
\bar{h} = \frac{1}{2\pi} \arctan_2\!\left(\sum_{(x,y)} w \sin(2\pi h),\; \sum_{(x,y)} w \cos(2\pi h)\right) \bmod 1
$$

où $\arctan_2$ renvoie une valeur dans $(-\pi, \pi]$. Le $\bar{h} \in [0,1)$ obtenu encode l'identité chromatique dominante de l'image d'une manière invariante au placement arbitraire du rouge en $h=0$ et robuste aux distributions bimodales de teintes.

### 4.3 Chaleur

Un indice scalaire de chaleur est défini comme la différence moyenne entre les canaux rouge et bleu :

$$
w_{\mathrm{arm}} = \frac{1}{HW}\sum_{(x,y)} \bigl(R(x,y) - B(x,y)\bigr)
$$

Une valeur positive indique une image aux tons chauds (plus de rouge, orange ou jaune), tandis qu'une valeur négative indique une image aux tons froids (plus de bleu ou cyan). La chaleur contribue à la sélection de la gamme et au score d'affinité instrumentale.

---

## 6. Estimation de la saillance visuelle

### 5.1 Motivation

La saillance visuelle est la propriété d'une région à attirer le regard. Les régions saillantes ne sont pas simplement lumineuses ou contrastées : elles sont visuellement distinctives par rapport à leur environnement. Dans cette application, une carte de saillance guide le placement, la hauteur et l'espacement des notes d'accent de la couche solo, de sorte que les caractéristiques les plus proéminentes de l'image produisent les événements mélodiques les plus proéminents.

### 5.2 Modèle de saillance à trois composantes

La carte de saillance est construite à partir de trois composantes complémentaires.

**La rareté de couleur** mesure à quel point la couleur de chaque pixel diffère de la moyenne de l'image :

$$
C_r(x,y) = \left\| \begin{pmatrix} R(x,y) \\ G(x,y) \\ B(x,y) \end{pmatrix} - \begin{pmatrix} \bar{R} \\ \bar{G} \\ \bar{B} \end{pmatrix} \right\|_2
$$

où $(\bar{R}, \bar{G}, \bar{B})$ est le vecteur RGB moyen sur tous les pixels. Les pixels éloignés de la couleur moyenne globale apparaissent localement inhabituels et tendent donc à être saillants.

**La rareté de luminance** mesure à quel point la luminosité de chaque pixel diffère de la moyenne :

$$
L_r(x,y) = |Y(x,y) - \mu_Y|
$$

**La force des contours** $\hat{G}(x,y)$ (définie en Section 3) contribue parce que les frontières à fort contraste attirent l'attention.

$C_r$ et $L_r$ sont tous deux normalisés indépendamment sur $[0,1]$ avant combinaison. La saillance de base est :

$$
\mathcal{B}(x,y) = 0.42\, \hat{G}(x,y) + 0.34\, \hat{C}_r(x,y) + 0.24\, \hat{L}_r(x,y)
$$

### 5.3 Biais central

La photographie naturelle tend à centrer les sujets, et le système visuel humain présente un biais documenté de regard vers le centre lors de l'exploration libre. Un poids radial de type gaussien est donc ajouté :

$$
\text{CB}(x,y) = 1 - \left\|\begin{pmatrix} x/(W-1) - 0.5 \\ y/(H-1) - 0.5 \end{pmatrix}\right\|_2
$$

normalisé sur $[0,1]$.

La carte de saillance finale est :

$$
\mathcal{S}(x,y) = \mathrm{normalize}_{[0,1]}\!\bigl(0.88\,\mathcal{B}(x,y) + 0.12\,\text{CB}(x,y)\bigr)
$$

### 5.4 Descripteurs de saillance

Les 4 % supérieurs des valeurs de saillance définissent le masque d'avant-plan $\mathcal{M}$. À partir de ce masque, l'application extrait :

| Descripteur | Formule |
|---|---|
| Pic de saillance | $\max_{(x,y)} \mathcal{S}(x,y)$ |
| Moyenne de saillance | $\frac{1}{HW}\sum \mathcal{S}(x,y)$ |
| Aire de saillance | $\frac{1}{HW}|\mathcal{M}|$ |
| Centroïde de saillance | $(c_x, c_y)$ depuis le centre de masse pondéré de $\mathcal{M}$ |
| Étalement de saillance | écart-type pondéré de la distance au centroïde, normalisé |

L'étalement est :

$$
\sigma_{\mathcal{S}} = \operatorname{clip}\!\left(\frac{1}{0.45}\sqrt{\frac{\sum_{(x,y)} w(x,y) \bigl[(x_n - c_x)^2 + (y_n - c_y)^2\bigr]}{\sum_{(x,y)} w(x,y)}},\; 0,\; 1\right)
$$

où $x_n = x/(W-1)$, $y_n = y/(H-1)$ et $w(x,y) = \mathcal{S}(x,y) \cdot \mathbf{1}_{\mathcal{M}}$.

---

## 7. Analyse de Fourier bidimensionnelle

### 6.1 Prétraitement

Avant de calculer la TFD 2D, l'image de luminance est prétraitée pour réduire la fuite spectrale. La luminance moyenne est soustraite (suppression DC), et une fenêtre de Hanning séparable est appliquée :

$$
\tilde{Y}(x,y) = \bigl(Y(x,y) - \mu_Y\bigr) \cdot w_H(x) \cdot w_H(y)
$$

où $w_H(n) = 0.5 - 0.5\cos(2\pi n / (N-1))$ est la fenêtre de Hanning à $N$ points. Le fenêtrage réduit le phénomène de Gibbs qui apparaît lorsqu'une image finie est traitée comme un signal périodique, et empêche les fortes discontinuités aux frontières de polluer les estimations spectrales.

### 6.2 Spectre centré

La TFD 2D est calculée par l'algorithme FFT et immédiatement décalée en fréquence afin que la composante DC soit au centre du spectre :

$$
F(u, v) = \mathrm{FFTshift}\!\left[\,\sum_{x=0}^{W-1}\sum_{y=0}^{H-1} \tilde{Y}(x,y)\, e^{-j2\pi(ux/W + vy/H)}\right]
$$

La carte affichée est la log-magnitude :

$$
M_{\log}(u,v) = \log\!\bigl(1 + |F(u,v)|\bigr)
$$

normalisée sur $[0,1]$ pour la visualisation. Le logarithme est nécessaire parce que la magnitude de la TFD possède une très grande plage dynamique : les coefficients les plus forts peuvent être des ordres de grandeur plus grands que les plus faibles.

### 6.3 Bandes de fréquences radiales

Soit $r(u,v)$ la fréquence radiale normalisée, définie comme la distance euclidienne entre le centre DC et chaque bin fréquentiel, divisée par la fréquence radiale maximale disponible. Trois bandes de fréquences partitionnent le spectre non DC :

| Bande | Plage radiale $r$ | Signification visuelle |
|---|---|---|
| Low | $[0.025,\; 0.14)$ | grandes structures lisses, gradients lents de luminance |
| Mid | $[0.14,\; 0.34)$ | formes et transitions d'échelle moyenne |
| High | $[0.34,\; 1]$ | contours, textures fines, micro-détails, bruit |

L'énergie normalisée dans une bande $\mathcal{B}$ est :

$$
E_{\mathcal{B}} = \frac{\displaystyle\sum_{(u,v)\in\mathcal{B}} |F(u,v)|^2}{\displaystyle\sum_{(u,v)\notin\mathcal{D}} |F(u,v)|^2}
$$

où $\mathcal{D}$ est la région DC $r < 0.025$, exclue de tous les calculs de bandes. L'énergie basse fréquence gouverne le poids des couches soutenues (pad, bass). L'énergie haute fréquence gouverne la densité d'arpèges, la brillance de la couche texture et l'agressivité de la formule de tempo Scientific.

### 6.4 Centroïde spectral et largeur de bande

Le centroïde pondéré par la puissance du spectre non DC est :

$$
\rho_c = \frac{\displaystyle\sum_{(u,v)\notin\mathcal{D}} r(u,v)\,|F(u,v)|^2}{\displaystyle\sum_{(u,v)\notin\mathcal{D}} |F(u,v)|^2}
$$

et la largeur de bande spectrale est l'écart-type pondéré par la puissance autour de ce centroïde :

$$
B = \sqrt{\frac{\displaystyle\sum_{(u,v)\notin\mathcal{D}} \bigl(r(u,v) - \rho_c\bigr)^2 |F(u,v)|^2}{\displaystyle\sum_{(u,v)\notin\mathcal{D}} |F(u,v)|^2}}
$$

Un centroïde élevé signifie que l'énergie spectrale est concentrée aux échelles fines. Une grande largeur de bande signifie que le spectre est réparti sur de nombreuses échelles. Ces deux quantités contribuent à la formule de tempo Scientific et au paramètre de densité des arpèges.

### 6.5 Énergie fréquentielle directionnelle

L'angle de chaque bin fréquentiel est $\theta(u,v) = \arctan_2(v, u)$. Le spectre est séparé en :

- énergie **horizontale** : bins où $|\sin\theta| < 0.38$ (fréquences orientées le long des structures horizontales)
- énergie **verticale** : bins où $|\cos\theta| < 0.38$
- énergie **diagonale** : le complément $1 - E_h - E_v$

Ces composantes directionnelles ne sont pas directement utilisées pour la génération de notes dans la version actuelle, mais elles sont calculées et exportées vers le panneau d'analyse.

### 6.6 Score de pic périodique

Le score de pic périodique estime dans quelle mesure le spectre est dominé par quelques fréquences proéminentes, par opposition à un fond large :

$$
P = \operatorname{clip}\!\left(\frac{\log\!\bigl(1 + P_{99.7}(|F|^2) / (P_{90}(|F|^2) + \varepsilon)\bigr)}{5},\; 0,\; 1\right)
$$

où $P_q$ désigne le $q$-ième percentile sur toutes les valeurs de puissance non DC et $\varepsilon = 10^{-12}$. Un $P$ élevé indique la présence de structures périodiques régulières telles que des grilles, des rayures ou de fortes textures répétitives. Musicalement, il encourage les motifs répétitifs, les gammes pentatoniques, les comportements harmoniques de type boucle et les timbres percussifs.

---

## 8. Paramètres musicaux automatiques

### 7.1 Centre tonal

La teinte dominante $\bar{h} \in [0,1)$ est associée aux 12 classes de hauteur chromatiques par :

$$
k = \operatorname{round}(12\,\bar{h}) \bmod 12
$$

Le résultat est un index dans la séquence $\{C, C\sharp, D, D\sharp, E, F, F\sharp, G, G\sharp, A, A\sharp, B\}$.

La note MIDI de la fondamentale (la note la plus basse de la plage mélodique principale) est décalée par la luminosité :

$$
\text{root} = \operatorname{clip}\!\Bigl(\,48 + k + \operatorname{round}\!\bigl(\operatorname{interp}(\mu_Y,\,[0,1],\,[-5,7])\bigr),\; 38,\; 58\Bigr)
$$

Les images plus sombres utilisent donc un registre plus grave et les images plus lumineuses un registre plus aigu, conformément aux associations psychoacoustiques courantes entre luminance et hauteur tonale.

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

$B_0$ est la valeur par défaut proposée à l'utilisateur. Les images simples suggèrent des compositions courtes ; les images complexes suggèrent des compositions plus longues. L'utilisateur peut remplacer le nombre de mesures dans la plage automatiquement suggérée, ou saisir des valeurs en dehors de celle-ci en sélectionnant le mode Manual.

### 7.4 Tempo

Quatre stratégies de tempo sont disponibles. Soit $\Delta t = 60 / T$ la période du beat en secondes :

**Scientific** mapping utilise l'ensemble complet des descripteurs de Fourier et spatiaux :

$$
T = \operatorname{clip}\!\bigl(50 + 70\,D_e + 58\,\sigma_Y + 42\,P + 34\,E_{\mathrm{high}} + 22\,\rho_c - 20\,s,\; 48,\; 152\bigr)
$$

**Balanced** mapping est une variante plus douce :

$$
T = \operatorname{clip}\!\bigl(62 + 38\,D_e + 28\,\sigma_Y + 20\,P + 10\,E_{\mathrm{high}} - 8\,s,\; 56,\; 132\bigr)
$$

**Musical** mapping est plus lisse et plus conservateur, s'appuyant sur des attributs perceptifs de couleur :

$$
T = \operatorname{clip}\!\bigl(82 + 10\,\bar{\text{Sat}} + 8\,\mu_Y - 6\,s + 4\,w_{\mathrm{arm}},\; 72,\; 108\bigr)
$$

Le mode **Manual** permet à l'utilisateur de spécifier directement $T$ en BPM.

---

## 9. Progression d'accords et structure harmonique

### 8.1 Triades à partir des degrés de gamme

Pour une gamme ayant une séquence d'intervalles $I = [i_0, i_1, \ldots, i_{n-1}]$ de longueur $n$, la triade enracinée au degré $d$ est construite en prenant un degré sur deux :

$$
\text{chord}(d) = \bigl\{i_{d \bmod n},\; i_{(d+2) \bmod n} + 12\cdot\mathbf{1}_{d+2 \geq n},\; i_{(d+4) \bmod n} + 12\cdot\mathbf{1}_{d+4 \geq n}\bigr\}
$$

Il s'agit de l'empilement par tierces standard utilisé dans toute la théorie harmonique occidentale. Pour une gamme diatonique à sept notes, cela produit des triades majeures, mineures et diminuées aux degrés appropriés. Pour une gamme pentatonique, les membres de l'accord sont plus espacés, produisant un son ouvert et modal.

### 8.2 Pool de progressions

Deux pools de progressions sont disponibles selon la longueur de la gamme. Pour les gammes à sept notes, les séquences de degrés disponibles sont $[0,4,5,3]$, $[0,5,3,4]$, $[0,2,5,4]$ et $[0,3,1,4]$. Pour les gammes plus courtes, des pools plus simples sont utilisés.

La sélection est déterministe à partir d'une graine dérivée des caractéristiques visuelles :

$$
\text{seed} = \operatorname{round}\!\bigl(997\,\bar{h} + 113\,P + 71\,H_{\mathrm{tex}} + 53\,c_x^{\mathcal{S}}\bigr)
$$

où $c_x^{\mathcal{S}}$ est le centroïde horizontal de la saillance. Cette graine est stable sous de petites perturbations de l'image, mais change substantiellement lorsque le contenu visuel change.

### 8.3 Décalage de progression piloté par la variation

Lorsque la force de variation dépasse 0.45, la seconde moitié de la composition utilise un index de progression décalé. Cela signifie que la boucle harmonique évolue au point médian, créant une forme A–B typique de nombreuses structures musicales sans nécessiter une section de pont programmée séparément.

---

## 10. Mélodie et composition en couches

### 9.1 Ensemble de notes disponibles

Le pool de notes mélodiques est construit en énumérant toutes les hauteurs MIDI de la forme $\text{root} + 12k + i_j$ qui se trouvent dans la plage $[\text{root}+10, \text{root}+31]$, où $i_j$ parcourt les intervalles de la gamme. Cela confine la mélodie à une fenêtre de deux octaves centrée légèrement au-dessus de la fondamentale. Le pool de basse utilise une fenêtre plus grave $[\text{root}-18, \text{root}+7]$.

### 9.2 Balayage des tranches de luminance

L'image est divisée en $8B$ tranches verticales (où $B$ est le nombre de mesures). Pour chaque tranche $i$, la luminance moyenne, le contraste local (écart-type) et le centroïde vertical de luminosité sont calculés. Le centroïde utilise une carte de poids tronquée par percentile :

$$
w_i(y) = \max\!\bigl(Y_i(y) - P_{35}(Y_i),\; 0\bigr)
$$

afin de se concentrer sur les valeurs de luminance les plus élevées dans la tranche.

La position mélodique dans l'ensemble de notes disponibles est obtenue à partir d'une combinaison du centroïde vertical inversé et de l'écart d'énergie locale :

$$
\text{pos} = \operatorname{clip}\!\bigl(1 - c_{y,i} + 0.18\,(\bar{Y}_i - \mu_Y),\; 0,\; 1\bigr)
$$

Une région lumineuse placée haut dans l'image (petit $c_{y,i}$, grand $\bar{Y}_i$) produit une note aiguë. Une région sombre placée bas produit une note grave. Cette correspondance espace-hauteur est le lien expressif central entre le contenu de l'image et le contour musical.

### 9.3 Décalage mélodique par la variation

Le pool de notes est divisé en quatre sections égales. Un décalage dépendant de la section $\delta_s \in \{0, 2, -2, 5\}$ est ajouté à l'index nominal de la note et pondéré par la force de variation :

$$
\text{note}_{\mathrm{final}} = \text{note}_{\mathrm{nominal}} + \operatorname{round}(\delta_s \cdot V)
$$

Pour un $V$ faible, la mélodie est presque identique dans les deux moitiés. Pour un $V$ élevé, le contour mélodique se décale significativement dans la seconde moitié.

### 9.4 Couche texture

Un paramètre de densité d'arpèges de texture est dérivé de :

$$
\rho_{\mathrm{tex}} = \operatorname{clip}(0.20 + 0.80\,C + 0.75\,E_{\mathrm{high}} + 0.45\,B,\; 0,\; 1)
$$

où $C$ est la complexité de composition et $B$ la largeur de bande de Fourier. Lorsque $\rho_{\mathrm{tex}} > 0.28$, des événements d'arpèges sont générés à une cadence d'un par beat (ou deux par beat lorsque $\rho_{\mathrm{tex}} > 0.55$), en parcourant un motif d'accord étendu. De plus, des événements de tick rythmique (percussion non pitchée sur le canal MIDI 9) sont ajoutés aux subdivisions du beat lorsque $\rho_{\mathrm{tex}} > 0.18$.

### 9.5 Couches pad et chord

Les événements pad couvrent toute la durée de chaque mesure (quatre beats) avec une légère extension legato de 0.05 beat. Leur vélocité est proportionnelle à l'énergie de Fourier basse fréquence, ce qui rend le pad plus fort lorsque l'image présente des structures lisses à grande échelle :

$$
v_{\mathrm{pad}} = \operatorname{clip}(0.07 + 0.18\,E_{\mathrm{low}} + 0.04\,(1 - E_{\mathrm{high}}),\; 0.04,\; 0.28)
$$

Les événements chord sont déclenchés une fois par mesure (ou deux fois lorsque $E_{\mathrm{high}} > 0.22$), jouant simultanément les trois notes de l'accord courant de la progression.

Les événements de basse suivent un motif fondamentale–quinte : la fondamentale sur le beat 1 et la quinte juste (7 demi-tons au-dessus de la fondamentale) sur le beat 3, avec des vélocités proportionnelles à la proportion d'ombres et à l'énergie basse fréquence.

---

## 11. Sélection automatique et manuelle des instruments

### 10.1 Mode Simple Synthesizer

En mode Simple, les instruments sont choisis dans une palette fixe de 15 timbres synthétisés en interne, à l'aide de règles de seuil explicites sur les caractéristiques. Par exemple :

- Couche main : bright bell si $h > 0.14$ et $E_{\mathrm{high}} > 0.28$ ; celesta si $\mu_Y > 0.64$ ; kalimba si $P > 0.58$ ; marimba si $P > 0.48$ ; harp si l'image est chaude et saturée ; soft piano sinon.
- Couche pad : warm pad si l'énergie basse fréquence est forte et que l'image est chaude, ou si les ombres sont prévalentes ; glass pad sinon.

### 10.2 Mode GeneralUser GS : score par familles GM

En mode GeneralUser GS, chaque couche sélectionne parmi les 128 programmes General MIDI complets. La sélection utilise un système continu de score d'affinité. Chaque programme GM appartient à l'une des 16 familles (piano, chromatic percussion, organ, guitar, bass, solo strings, ensemble, brass, reed, pipe, synth lead, synth pad, synth FX, ethnic, percussive, sound FX). Un poids de famille $W_{\ell}(f)$ est défini pour chaque couche $\ell$ et famille $f$ comme une combinaison linéaire de caractéristiques visuelles scalaires :

Par exemple, pour la couche main, le poids de la famille piano est :

$$
W_{\mathrm{main}}(\mathrm{piano}) = 0.35 + 0.35\,\lambda_{\mathrm{smooth}}
$$

où $\lambda_{\mathrm{smooth}} = \operatorname{clip}(E_{\mathrm{low}} + 0.35(1-E_{\mathrm{high}}) + 0.25\,S, 0, 1)$ est un score de lissage dérivé de l'énergie de Fourier et de la symétrie. Le poids de la famille pipe pour la couche main est :

$$
W_{\mathrm{main}}(\mathrm{pipe}) = 0.18 + 0.45\,\lambda_{\mathrm{bright}} + 0.20\,\lambda_{\mathrm{smooth}}
$$

avec $\lambda_{\mathrm{bright}} = \operatorname{clip}(0.55\,\mu_Y + 0.45\,h, 0, 1)$.

Pour les programmes individuels au sein d'une famille, des bonus fins supplémentaires sont ajoutés : par exemple, les programmes du groupe celesta/music-box (8–14) reçoivent un bonus proportionnel à la proportion de hautes lumières, à l'énergie de Fourier haute et au pic de saillance.

Le score final du programme $p$ pour la couche $\ell$ est :

$$
\text{score}(p, \ell) = W_\ell(f_p) + \text{program bonus}(p) + 0.42\,u(p, \ell)
$$

où $u(p, \ell)$ est un jitter pseudo-aléatoire déterministe dans $[0,1]$ dérivé d'un hash SHA-256 du vecteur de caractéristiques. Le jitter empêche les mêmes quelques programmes d'être sélectionnés dans toutes les compositions tout en conservant une sélection reproductible pour des entrées fixes.

### 10.3 Gain de couche

Le gain par couche en décibels est appliqué à la vélocité de chaque événement de note de cette couche avant le rendu audio :

$$
g = 10^{G_{\mathrm{dB}} / 20}
$$

Les vélocités des notes après application du gain sont limitées à $[0, 1]$.

---

## 12. Synthèse additive et enveloppes ADSR

### 11.1 Modèle ADSR

Chaque note est façonnée par une enveloppe Attack–Decay–Sustain–Release. Étant donnée une note de $n$ échantillons à la fréquence d'échantillonnage $f_s$, l'enveloppe est :

$$
e[t] = \begin{cases}
t / t_A & 0 \leq t < t_A \\
1 - (1 - S_L)(t - t_A) / t_D & t_A \leq t < t_A + t_D \\
S_L & t_A + t_D \leq t < n - t_R \\
S_L \cdot (1 - (t - (n-t_R)) / t_R) & n - t_R \leq t < n
\end{cases}
$$

où $t_A, t_D, t_R$ sont les nombres d'échantillons d'attaque, de décroissance et de relâchement, et $S_L \in (0,1]$ est le niveau de sustain. L'enveloppe est ensuite multipliée élément par élément par la forme d'onde harmonique instantanée.

### 11.2 Recettes d'instruments

Chaque instrument utilise une combinaison spécifique de contenu harmonique et de paramètres d'enveloppe.

**Soft piano.** La forme d'onde est une somme d'harmoniques d'amplitudes décroissantes :

$$
x[t] = \sum_{m \in \{1,2,3,4,5\}} a_m \sin(2\pi m f_0 t / f_s)
$$

avec $(a_1, a_2, a_3, a_4, a_5) = (1, 0.42, 0.20, 0.10, 0.04)$. Une décroissance exponentielle est appliquée au-dessus de l'ADSR : $e_{\mathrm{exp}}[t] = \exp(-2.7\, t / (n / f_s))$, modélisant la décroissance naturelle d'une corde frappée.

**Bright bell / celesta / music box / kalimba.** Ces instruments utilisent des partiels inharmoniques dont les rapports de fréquences s'écartent des entiers pour simuler le comportement de barres ou de plaques métalliques. Pour le bright bell :

$$
(\text{ratios, amplitudes}) = \{(1, 1),\, (2.41, 0.55),\, (3.77, 0.30),\, (5.93, 0.16),\, (8.12, 0.06)\}
$$

Ces rapports non entiers sont caractéristiques des spectres inharmoniques et produisent le timbre métallique ou vitreux caractéristique. La décroissance exponentielle rapide ($\tau = 4.2$) renforce le sustain court des cloches physiques.

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

L'ADSR possède une attaque lente (jusqu'à 65 % de la durée de la note) et un niveau de sustain élevé (0.78), produisant le gonflement lent caractéristique.

**Cello-like bass / bowed string.** Modèle de vibrato similaire avec une profondeur de modulation plus élevée ($0.004$) et une fréquence légèrement plus rapide ($5.1$ Hz) :

$$
x[t] = 0.75\sin(\phi[t]) + 0.33\sin(2\phi[t]) + 0.17\sin(3\phi[t])
$$

L'ADSR modélise l'attaque de l'archet ($t_A = 0.07\,\text{s}$) et un sustain long.

**Clarinet-like reed.** Le spectre de la clarinette est dominé par les harmoniques impaires. La forme d'onde $x[t] = \sin(2\pi f_0 t) - 0.33\sin(6\pi f_0 t) + 0.17\sin(10\pi f_0 t)$ approxime cette caractéristique.

Après application de l'enveloppe, chaque note est normalisée en crête et multipliée par sa vélocité $v \in [0,1]$, de sorte que la vélocité contrôle l'amplitude sans déformer le timbre.

---

## 13. Couche solo pilotée par la saillance

### 12.1 Motivation

La couche solo, disponible uniquement en mode GeneralUser GS, place un ensemble clairsemé de notes d'accent à des positions temporelles et des hauteurs dérivées directement de la carte de saillance. L'idée est de rendre audibles les éléments les plus proéminents visuellement de la photographie sous forme d'événements mélodiques distincts, flottant au-dessus de la texture harmonique des autres couches.

### 12.2 Échantillonnage spatial des pixels saillants

Un scalaire composite de force de saillance est d'abord dérivé :

$$
\eta = \operatorname{clip}\!\bigl(0.55\,\text{sal\_peak} + 0.25\,\text{sal\_mean} + 0.20\,(1 - \text{sal\_area}),\; 0,\; 1\bigr)
$$

Il combine l'intensité du pic, la densité spatiale et l'inverse de l'aire saillante : une région focalisée et intense donne un $\eta$ élevé, tandis qu'une image diffuse et faiblement saillante donne un $\eta$ faible.

Le nombre de notes solo est :

$$
N_{\mathrm{solo}} = \operatorname{clip}\!\bigl(\operatorname{round}(\operatorname{interp}(\eta,\,[0,1],\,[3,18])),\; 2,\; 22\bigr)
$$

Les $N_{\mathrm{cand}}$ pixels les plus saillants (avec $N_{\mathrm{cand}} = \max(64, 18 N_{\mathrm{solo}})$) sont identifiés, puis filtrés avec une règle spatiale d'inhibition of return : deux positions sélectionnées doivent être séparées d'au moins 5.5 % de la diagonale de l'image. Cela empêche les notes solo de se regrouper sur une seule petite région.

### 12.3 Attribution du temps et de la hauteur

La position horizontale de chaque pixel saillant sélectionné est associée au temps :

$$
t_k = x_k^{\mathrm{norm}} \cdot T_{\mathrm{dur}} + 0.10\,\Delta t\,\sin(1.7\,k)
$$

où $x_k^{\mathrm{norm}} \in [0,1]$ est la coordonnée horizontale normalisée, $T_{\mathrm{dur}}$ est la durée totale de la composition et $\Delta t$ est la période du beat. Le petit jitter sinusoïdal empêche toutes les notes de s'aligner sur la grille horizontale de pixels.

La position verticale est associée à la hauteur : les points saillants hauts (petit $y^{\mathrm{norm}}$) produisent des hauteurs plus aiguës, conformément à la convention de la mélodie principale :

$$
\text{note}_k = \text{melody\_notes}\!\left[\operatorname{round}\bigl((1 - y_k^{\mathrm{norm}})\,(N_{\mathrm{mel}} - 1)\bigr)\right] + 12
$$

Le solo est transposé une octave au-dessus de la plage de la mélodie principale ($+12$ demi-tons). Une note sur cinq reçoit une quinte juste supplémentaire ($+7$ demi-tons), ajoutant de la variété intervallique à la ligne solo.

La durée des notes est proportionnelle à la force de saillance et à l'étalement de saillance :

$$
d_k = \operatorname{clip}\!\bigl((0.32 + 0.70\,\mathcal{S}(y_k, x_k) + 0.20\,\sigma_{\mathcal{S}})\,\Delta t,\; 0.18\,\Delta t,\; 1.25\,\Delta t\bigr)
$$

---

## 14. Rendu stéréo et panoramique à puissance constante

### 13.1 Placement événement-échantillon

Chaque événement de note avec un temps de début $t_{\mathrm{start}}$ est placé à l'indice d'échantillon $n_s = \operatorname{round}(t_{\mathrm{start}} \cdot f_s)$. La forme d'onde synthétisée de longueur $n_{\mathrm{note}} = \operatorname{round}(d \cdot f_s)$ échantillons est ajoutée à un buffer stéréo préalloué de longueur $\lceil (T_{\mathrm{dur}} + 0.8) \cdot f_s \rceil$ échantillons. La queue de 0.8 seconde permet de conserver la phase de release des notes longues proches de la fin de la composition.

### 13.2 Panoramique à puissance constante

Chaque note porte une valeur de panoramique $p \in [-1, 1]$. Le gain stéréo est attribué selon la loi standard de panoramique à puissance constante :

$$
g_L = \cos\!\left(\frac{\pi}{4}(p + 1)\right), \qquad g_R = \sin\!\left(\frac{\pi}{4}(p + 1)\right)
$$

Pour $p = -1$ (extrême gauche) : $g_L = 1, g_R = 0$. Pour $p = 0$ (centre) : $g_L = g_R = 1/\sqrt{2}$. Pour $p = +1$ (extrême droite) : $g_L = 0, g_R = 1$. La loi à puissance constante garantit que la sonie perçue reste constante lorsque la position panoramique se déplace de gauche à droite, contrairement à une loi linéaire qui produirait un creux au centre.

Les valeurs de panoramique sont dérivées des positions visuelles :
- Couche main : panoramiquée vers la position horizontale du centroïde lumineux $c_x^{\mathrm{bright}}$, avec une lente oscillation sinusoïdale $\sin(0.37\,i)$ indexée par le numéro de tranche $i$.
- Couche bass : panoramiquée vers le centroïde des ombres $c_x^{\mathrm{shadow}}$.
- Couche chord : panoramiquée vers le centroïde lumineux avec un balancement réduit.
- Arpèges de texture : panoramiqués progressivement de gauche à droite lorsque l'index d'arpège augmente.

---

## 15. Traitement du bus master

Après le mixage de toutes les couches dans le buffer stéréo, une étape de normalisation du bus master est appliquée. Elle ne modifie pas les gains individuels des couches ; elle agit uniquement sur le mix stéréo final.

**Suppression DC.** La valeur moyenne de chaque canal est soustraite :

$$
x_{\mathrm{dc}}[t] = x[t] - \frac{1}{N}\sum_{\tau=0}^{N-1} x[\tau]
$$

**Normalisation RMS.** Le niveau root-mean-square sur tous les échantillons et les deux canaux est calculé :

$$
\text{RMS} = \sqrt{\frac{1}{2N}\sum_{t=0}^{N-1}\!\bigl(x_L[t]^2 + x_R[t]^2\bigr)}
$$

Si $\text{RMS} > \text{RMS}_{\mathrm{target}} = 0.16$, le signal est réduit par le facteur $\text{RMS}_{\mathrm{target}} / \text{RMS}$.

**Normalisation de crête.** Si l'amplitude crête résultante dépasse $\text{Peak}_{\mathrm{target}} = 0.86$, le signal est multiplié par $\text{Peak}_{\mathrm{target}} / \max|x|$.

**Limiteur de sécurité.** Un hard clip final à $\pm 0.98$ empêche un dépassement flottant de se propager vers le convertisseur de format audio.

Ce processus en deux étapes (RMS puis crête) assure un niveau de sonie cohérent entre les compositions tout en préservant de la marge pour les transitoires. Un fichier WAV est écrit à 44100 Hz, en PCM signé 16 bits, 2 canaux. L'encodage MP3 utilise un codec externe s'il est disponible.

---

## 16. Export MIDI

### 15.1 Structure du fichier MIDI

L'export MIDI génère un fichier MIDI single-track, format 0. La résolution temporelle est $\text{PPQ} = 480$ pulses per quarter note. Cela donne un taux de ticks de :

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

Les événements program change sont émis avant la première note de chaque canal, en utilisant le numéro de programme GM correspondant à l'instrument sélectionné. Le canal 9 est le canal de percussion General MIDI et ne reçoit pas de program changes.

### 15.3 Encodage en longueur variable

Les delta times MIDI sont encodés dans le format variable-length quantity (VLQ) : la représentation binaire de la valeur est séparée en groupes de 7 bits, chacun stocké dans un octet dont le bit de poids fort est mis à 1 pour tous les octets sauf le dernier. Cela permet d'encoder des valeurs de ticks jusqu'à $2^{28} - 1$ avec au plus 4 octets, un schéma compact adapté aux événements musicaux clairsemés.

---

## 17. Facteur aléatoire et perturbations contrôlées

Le facteur aléatoire $r \in [0, 100]$ ajoute des perturbations contrôlées à l'image et à l'analyse de Fourier utilisées pour la génération de la composition. Il ne remplace pas la correspondance fondée sur la photo par du pur hasard.

Définissons $\alpha = r / 100 \in [0,1]$. Deux étapes de perturbation sont appliquées avant l'extraction des caractéristiques :

**Bruit RGB.** Un bruit gaussien additif est injecté dans l'image RGB normalisée :

$$
\tilde{R}(x,y) = \operatorname{clip}\!\bigl(R(x,y) + \eta_R(x,y),\; 0,\; 1\bigr), \qquad \eta_R \sim \mathcal{N}(0,\, \sigma_{\mathrm{img}}^2)
$$

avec $\sigma_{\mathrm{img}} = 0.045\,\alpha^2$. La loi quadratique signifie que la perturbation est négligeable pour les petits $r$ et significative uniquement pour les grands $r$.

**Bruit de magnitude de Fourier.** Après le calcul de la TFD 2D, la magnitude est perturbée par un facteur multiplicatif log-normal :

$$
|F'(u,v)| = |F(u,v)| \cdot \exp(\eta_{uv}), \qquad \eta_{uv} \sim \mathcal{N}(0,\, \sigma_{\mathrm{Fou}}^2)
$$

avec $\sigma_{\mathrm{Fou}} = 0.18\,\alpha^2$. La distribution log-normale garantit que la magnitude reste strictement positive et que la perturbation est multiplicative plutôt qu'additive, ce qui est le modèle le plus naturel pour une incertitude d'amplitude spectrale.

Le panneau d'analyse photo affiche toujours l'analyse non perturbée (calculée avec $r=0$), afin que la visualisation et les métriques ne soient pas contaminées par le bruit ajouté.

**Graine déterministe.** Pour une valeur donnée du facteur aléatoire et une image téléversée, la graine est dérivée du hash SHA-256 des octets de l'image et de la valeur du facteur aléatoire. La même image et le même facteur aléatoire produisent toujours la même perturbation, de sorte que le système reste reproductible même dans son mode stochastique.

---

## 18. Graphiques d'analyse audio

Le panneau d'analyse audio affiche le contenu fréquentiel et la forme d'onde temporelle de la composition générée, décomposés par couche. Tous les graphiques fréquentiels utilisent la magnitude de la TFD unilatérale :

$$
|X[k]| = \left|\sum_{n=0}^{N-1} x[n]\, e^{-j2\pi kn/N}\right|, \qquad k = 0, 1, \ldots, \lfloor N/2 \rfloor
$$

L'axe horizontal est converti en fréquence en Hz à l'aide de $f_k = k \cdot f_s / N$.

Graphiques disponibles :

| Graphique | Signification |
|---|---|
| Full Fourier magnitude | spectre global de la composition stéréo mixée |
| Waveform | enveloppe d'amplitude temporelle du mix |
| Main layer Fourier | contribution spectrale de la mélodie |
| Texture layer Fourier | contribution spectrale des arpèges et événements rythmiques |
| Bass layer Fourier | contribution spectrale de la ligne de basse |
| Pad layer Fourier | contribution spectrale de la couche atmosphérique soutenue |
| Chord layer Fourier | contribution spectrale des frappes harmoniques |
| Solo layer Fourier | contribution spectrale de la couche d'accent de saillance (mode GS) |

Chaque graphique par couche est rendu en resynthétisant uniquement les événements de notes appartenant à cette couche, mixés en mono, puis en calculant la TFD. Cela permet une inspection indépendante du contenu spectral de chaque couche et vérifie que les événements de basse occupent les basses fréquences, les événements de texture occupent les fréquences moyennes à hautes, et les pads occupent la bande bas-médium.

---

## 19. Limites et interprétation

**Cécité sémantique.** L'application extrait uniquement des quantités visuelles mesurables : luminance, magnitude du gradient, statistiques de couleur, contenu en fréquences spatiales et saillance dérivée de la rareté de couleur et du contraste des contours. Elle n'a aucune représentation des objets, des scènes ou de la sémantique. Une image d'une forêt calme et une peinture abstraite ayant une luminosité, une densité de contours et une distribution de couleurs similaires produiront des sorties musicales similaires. C'est une conséquence fondamentale de l'utilisation de caractéristiques interprétables de traitement du signal.

**Sensibilité à la résolution.** Comme l'analyse utilise toute la résolution téléversée (jusqu'à la limite configurable `MAX_ANALYSIS_SIDE`), la correspondance peut être sensible au bruit de caméra, aux artefacts de compression JPEG et aux petites textures haute fréquence. Ceux-ci peuvent gonfler la densité de contours et l'énergie de Fourier haute fréquence, poussant le tempo et la complexité automatiques vers des valeurs plus élevées. Pour les photographies, un sous-échantillonnage à 512 pixels sur le côté le plus long (valeur par défaut) est généralement approprié.

**Instruments synthétiques.** Le Simple synthesizer utilise des recettes additives légères. Il ne s'agit pas de modèles physiquement exacts d'instruments réels. Leur but est de garder le système léger, entièrement autonome et explicable. Le chemin GeneralUser GS utilise une SoundFont rendue par FluidSynth et produit des timbres nettement plus réalistes, mais nécessite que le fichier SoundFont et le package système FluidSynth soient installés.

**Conventions musicales.** Le générateur de progressions d'accords, les règles de sélection de gamme et les formules de tempo encodent tous des décisions esthétiques propres à la musique tonale occidentale. La correspondance n'est pas universelle et ne représente pas une correspondance unique ou optimale entre les caractéristiques visuelles et les paramètres musicaux. Elle constitue un choix de conception explicite, reproductible et inspectable parmi de nombreuses alternatives possibles.

---