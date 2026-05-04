## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Ce que fait l'application](#2-ce-que-fait-lapplication)
3. [Pipeline général](#3-pipeline-general)
4. [Notation](#4-notation)
5. [Analyse de l'image](#5-analyse-de-limage)
6. [Analyse de Fourier de la photo](#6-analyse-de-fourier-de-la-photo)
7. [Saillance visuelle](#7-saillance-visuelle)
8. [Descripteurs visuels et décisions musicales](#8-descripteurs-visuels-et-decisions-musicales)
9. [Structure automatique : mesures, complexité et variation](#9-structure-automatique--mesures-complexite-et-variation)
10. [Tonalité, gamme et tempo](#10-tonalite-gamme-et-tempo)
11. [Harmonie et progression d'accords](#11-harmonie-et-progression-daccords)
12. [Couches mélodique, texture, basse, pad, accord et solo](#12-couches-melodique-texture-basse-pad-accord-et-solo)
13. [Sélection des instruments](#13-selection-des-instruments)
14. [Rendu audio et synthèse](#14-rendu-audio-et-synthese)
15. [Bus principal, exports et analyse audio](#15-bus-principal-exports-et-analyse-audio)
16. [Random factor](#16-random-factor)
17. [Référence des paramètres](#17-reference-des-parametres)
18. [Limites](#18-limites)

---

## 1. Vue d'ensemble

Photo Sonification Lab convertit une image fixe en une courte composition musicale. L'application n'utilise pas de réseau de neurones entraîné et ne cherche pas à reconnaître les objets présents dans l'image. Elle mesure plutôt des grandeurs visuelles comme la luminosité, le contraste, la densité de contours, la couleur, le contenu fréquentiel spatial et la saillance, puis les associe à des grandeurs musicales comme la tonalité, la gamme, le tempo, la densité de notes, le choix des instruments, la position stéréo et l'équilibre entre les couches.

L'idée est simple : une photo est traitée comme un signal. L'application analyse ce signal, extrait un vecteur de caractéristiques, transforme ce vecteur en une liste d'événements musicaux, puis rend ces événements sous forme d'audio et de MIDI.

$$
\text{photo}
\;\xrightarrow{\text{analyse d'image}}\;
\mathbf{f}
\;\xrightarrow{\text{mapping musical}}\;
\{\text{événements de notes}\}
\;\xrightarrow{\text{synthèse}}\;
\text{audio} + \text{MIDI}
$$

Le résultat n'est pas censé être la seule musique correcte pour une photo. C'est un mapping explicite et reproductible entre une structure visuelle et une structure musicale. Quand le paramètre Random factor vaut 0, la même image et les mêmes paramètres produisent toujours la même composition.

---

## 2. Ce que fait l'application

Du point de vue de l'utilisateur, l'application suit l'ordre suivant.

D'abord, l'image est chargée et redimensionnée pour l'analyse. L'application conserve le contenu visuel, mais limite le plus grand côté utilisé pour l'analyse afin que l'analyse de Fourier, l'extraction de saillance et le calcul des caractéristiques restent assez rapides pour une application en ligne.

Ensuite, l'application calcule plusieurs cartes à partir de la photo :

| Carte | Ce qu'elle montre | Pourquoi elle compte musicalement |
|---|---|---|
| Carte de luminance | luminosité perçue à chaque pixel | registre de hauteur, ombres, hautes lumières, forme mélodique |
| Carte de force des contours | variations locales de luminosité | activité rythmique et densité de texture |
| Log-magnitude de Fourier 2D | contenu fréquentiel spatial global | lissage, détails, périodicité, tempo et instruments |
| Carte ombres/hautes lumières | régions sombres et lumineuses | poids de la basse, accents brillants, humeur |
| Carte de saillance | régions visuellement dominantes | notes de solo/accent en mode GeneralUser GS |

Ensuite, l'application transforme les caractéristiques de l'image en valeurs musicales par défaut. Une photo lisse et symétrique tend à créer une pièce stable et plus lente. Une photo nette et asymétrique tend à créer plus de variation, plus de notes et une texture plus dense. Une photo lumineuse et colorée tend à sélectionner des registres et des timbres plus brillants. Une image sombre et dominée par les basses fréquences tend à donner plus de poids aux basses, aux cordes et aux pads.

Enfin, l'application génère une composition en plusieurs couches. Le résultat peut contenir jusqu'à six couches :

| Couche | Rôle dans la composition |
|---|---|
| Main | mélodie principale dérivée des tranches de luminance lues de gauche à droite |
| Texture | arpèges et petits événements rythmiques dérivés des détails et des hautes fréquences |
| Bass | support grave racine/quinte, influencé par les ombres et les basses fréquences |
| Pad | arrière-plan harmonique soutenu, plus marqué pour les images lisses à basse fréquence |
| Chord | impacts harmoniques suivant la progression d'accords sélectionnée |
| Solo | mélodie d'accents pilotée par la saillance, disponible en mode GeneralUser GS |

L'interface expose à la fois des contrôles musicaux et des seuils d'analyse de plus bas niveau. Les sliders de plage utilisés pour les valeurs min/max sont ordonnés, et le backend trie et borne aussi ces valeurs. Cela empêche les réglages invalides, par exemple une limite basse de bande de Fourier supérieure à la limite haute.

---

## 3. Pipeline général

| Étape | Sortie principale | Utilisation |
|---|---|---|
| Normalisation RGB | image normalisée $R,G,B \in [0,1]$ | toutes les analyses suivantes |
| Calcul de la luminance | image scalaire $Y$ | luminosité, contraste, mélodie, ombres, hautes lumières |
| Analyse du gradient | carte de contours $\hat{G}$ et densité de contours $D_e$ | texture, tempo, rythme |
| Analyse d'entropie | entropie de texture $H_{\mathrm{tex}}$ | complexité et valeurs par défaut des mesures |
| Analyse de symétrie | score de symétrie $S$ | force de variation |
| Analyse couleur HSV | teinte dominante, saturation, chaleur | tonalité, gamme, instruments |
| Analyse de Fourier 2D | énergie basse/moyenne/haute, centroïde, largeur de bande, score de pic périodique | tempo, instruments, texture, équilibre pad/basse |
| Analyse de saillance | carte de saillance et coordonnées saillantes | couche solo/accent |
| Mapping musical | tonalité, gamme, tempo, mesures, instruments de couche | génération des événements |
| Génération des événements | événements de notes ordonnés | synthèse audio et export MIDI |
| Rendu | forme d'onde stéréo à 44100 Hz | lecteur audio, export WAV/MP3, graphiques |

Un événement de note a la forme :

$$
e_i = (t_i, d_i, m_i, v_i, I_i, p_i, \ell_i)
$$

où $t_i$ est le temps de début, $d_i$ la durée, $m_i$ la hauteur MIDI, $v_i$ la vélocité, $I_i$ l'instrument, $p_i$ le panoramique stéréo et $\ell_i$ le label de couche.

---

## 4. Notation

| Symbole | Signification |
|---|---|
| $R,G,B$ | canaux RGB normalisés de l'image |
| $Y$ | image de luminance perceptuelle |
| $H,W$ | hauteur et largeur de l'image après redimensionnement d'analyse |
| $\Omega$ | grille de pixels de taille $H \times W$ |
| $P_q(X)$ | percentile d'ordre $q$ du tableau $X$ |
| $\mu_Y$ | luminance moyenne |
| $\sigma_Y$ | contraste de luminance |
| $D_Y$ | plage dynamique robuste de luminance |
| $\hat{G}$ | carte normalisée de magnitude du gradient |
| $D_e$ | densité de contours |
| $H_{\mathrm{tex}}$ | entropie de texture |
| $S$ | score de symétrie |
| $F(u,v)$ | transformée de Fourier 2D centrée de la luminance |
| $r(u,v)$ | fréquence spatiale radiale normalisée |
| $E_{\mathrm{low}}, E_{\mathrm{mid}}, E_{\mathrm{high}}$ | proportions d'énergie de Fourier dans les bandes basse, moyenne et haute |
| $\rho_c$ | centroïde radial de Fourier |
| $B_F$ | largeur de bande radiale de Fourier |
| $P_F$ | score de pic périodique |
| $\mathcal{S}$ | carte de saillance |
| $T$ | tempo en battements par minute |
| $\Delta t$ | période d'un battement, $\Delta t = 60/T$ |
| $B$ | nombre de mesures |

---

## 5. Analyse de l'image

### 5.1 Normalisation RGB

La photo d'entrée est convertie en RGB, corrigée selon l'orientation EXIF, redimensionnée si nécessaire, puis normalisée en valeurs flottantes dans $[0,1]$ :

$$
R(x,y),G(x,y),B(x,y) \in [0,1]
$$

Le redimensionnement d'analyse ne change pas le fichier exporté par l'utilisateur ; il contrôle seulement la résolution de calcul utilisée pour l'extraction des caractéristiques. Un plus grand côté d'analyse préserve davantage de détails fins, mais augmente le coût des calculs de Fourier et de saillance.

### 5.2 Luminance perceptuelle

La plupart des descripteurs structurels sont calculés à partir de la luminance plutôt que directement à partir de RGB. L'application utilise les poids ITU-R BT.709 :

$$
Y(x,y) = 0.2126R(x,y) + 0.7152G(x,y) + 0.0722B(x,y)
$$

Ces poids reflètent la perception humaine de la luminosité : le vert contribue beaucoup plus fortement que le bleu.

La luminosité globale est :

$$
\mu_Y = \frac{1}{HW}\sum_{(x,y)\in\Omega}Y(x,y)
$$

Le contraste est :

$$
\sigma_Y = \sqrt{\frac{1}{HW}\sum_{(x,y)\in\Omega}\bigl(Y(x,y)-\mu_Y\bigr)^2}
$$

La plage dynamique utilise des percentiles de luminance contrôlés par l'utilisateur, $p_L$ et $p_H$, valant par défaut $5\%$ et $95\%$ :

$$
D_Y = P_{p_H}(Y) - P_{p_L}(Y)
$$

L'utilisation de percentiles évite qu'un petit nombre de pixels isolés domine la plage.

### 5.3 Ombres et hautes lumières

L'application définit deux masques. Le masque d'ombre est :

$$
\mathcal{M}_{\mathrm{shadow}} = \left\{(x,y):Y(x,y) < \max\bigl(\tau_s, P_{p_L}(Y)+\delta_s\bigr)\right\}
$$

Le masque de hautes lumières est :

$$
\mathcal{M}_{\mathrm{highlight}} = \left\{(x,y):Y(x,y) > \min\bigl(\tau_h, P_{p_H}(Y)-\delta_h\bigr)\right\}
$$

Les valeurs par défaut sont $\tau_s=0.18$, $\delta_s=0.03$, $\tau_h=0.82$ et $\delta_h=0.03$. Les proportions obtenues sont :

$$
s = \frac{|\mathcal{M}_{\mathrm{shadow}}|}{HW},
\qquad
h = \frac{|\mathcal{M}_{\mathrm{highlight}}|}{HW}
$$

Musicalement, les ombres renforcent la basse et les timbres plus sombres. Les hautes lumières renforcent les timbres brillants, les arpèges et les couches d'accent.

### 5.4 Force des contours

Les contours sont extraits à partir du gradient de luminance :

$$
G(x,y) = \sqrt{\bigl(\partial_xY(x,y)\bigr)^2 + \bigl(\partial_yY(x,y)\bigr)^2}
$$

La magnitude du gradient est normalisée dans $[0,1]$ :

$$
\hat{G}(x,y) = \frac{G(x,y)-\min G}{\max G-\min G}
$$

La densité de contours est la fraction de pixels au-dessus d'un seuil. Ce seuil combine un percentile et un minimum fixe :

$$
D_e = \frac{1}{HW}\left|\left\{(x,y):\hat{G}(x,y)>\max\bigl(\tau_e,P_{q_e}(\hat{G})\bigr)\right\}\right|
$$

Les valeurs par défaut sont $q_e=75\%$ et $\tau_e=0.08$. Cela rend le détecteur adaptatif : il peut encore trouver des contours pertinents dans les images douces tout en évitant des détections excessives dans les images bruitées.

### 5.5 Entropie de texture

La carte de contours est aussi utilisée comme descripteur de texture. Un histogramme avec $K$ classes est calculé sur $\hat{G}$, puis normalisé en probabilités $p_k$. L'entropie de texture est :

$$
H_{\mathrm{tex}} = -\frac{1}{\log_2K}\sum_{k=1}^{K}p_k\log_2p_k
$$

La valeur par défaut est $K=64$ classes. Une faible entropie signifie que l'image est visuellement uniforme ou lisse. Une forte entropie signifie que l'image contient beaucoup de forces de contours différentes, donc une texture plus complexe. L'application utilise cette valeur pour fixer la complexité automatique de composition et influencer le nombre de mesures.

### 5.6 Symétrie

Le score de symétrie compare l'image de luminance à ses réflexions gauche-droite et haut-bas :

$$
S_{LR}=1-\frac{1}{HW}\sum_{(x,y)}|Y(x,y)-Y(W-1-x,y)|
$$

$$
S_{TB}=1-\frac{1}{HW}\sum_{(x,y)}|Y(x,y)-Y(x,H-1-y)|
$$

Le score final donne plus d'importance à la symétrie gauche-droite :

$$
S=0.70S_{LR}+0.30S_{TB}
$$

Un score élevé donne une composition stable avec moins de variation. Un score faible augmente la force de variation par défaut.

### 5.7 Caractéristiques de couleur

L'image RGB est convertie en interne en caractéristiques de type HSV. La saturation est calculée à partir du chroma RGB :

$$
\mathrm{Sat}(x,y)=
\begin{cases}
\dfrac{\max(R,G,B)-\min(R,G,B)}{\max(R,G,B)}, & \max(R,G,B)>0 \\
0, & \text{otherwise}
\end{cases}
$$

La teinte est circulaire ; une simple moyenne arithmétique n'est donc pas valide. L'application calcule une moyenne circulaire pondérée. Le poids de chaque pixel est :

$$
w(x,y)=\mathrm{Sat}(x,y)\cdot(0.25+Y(x,y))
$$

La teinte dominante est :

$$
\bar{h}=\frac{1}{2\pi}\operatorname{atan2}\left(
\sum w\sin(2\pi h),
\sum w\cos(2\pi h)
\right)\bmod 1
$$

Cette teinte contrôle le centre tonal. La saturation moyenne influence le choix de gamme et le score des instruments. La chaleur est mesurée par :

$$
w_{\mathrm{arm}}=\frac{1}{HW}\sum_{(x,y)}\bigl(R(x,y)-B(x,y)\bigr)
$$

Des valeurs positives indiquent une photo plus chaude ; des valeurs négatives indiquent une photo plus froide.

### 5.8 Centroïdes spatiaux

La position horizontale des régions lumineuses, ombrées et très claires est utilisée pour le placement stéréo. Pour toute carte de poids non négative $W_m(x,y)$, le centre de masse horizontal est :

$$
c_x=\frac{\sum xW_m(x,y)}{\sum W_m(x,y)}
$$

normalisé dans $[0,1]$. La mélodie principale et les accords suivent le centroïde lumineux, tandis que la basse suit le centroïde d'ombre. Cela donne à l'image stéréo un lien avec la disposition spatiale de la photo.

---

## 6. Analyse de Fourier de la photo

L'analyse de Fourier décrit l'image en termes de fréquences spatiales. Les grandes structures lisses correspondent aux basses fréquences. Les textures fines, les contours et le bruit correspondent aux hautes fréquences.

### 6.1 Prétraitement avant la FFT

La luminance moyenne est retirée, puis une fenêtre de Hanning séparable est appliquée :

$$
\tilde{Y}(x,y)=\bigl(Y(x,y)-\mu_Y\bigr)w_H(x)w_H(y)
$$

avec :

$$
w_H(n)=0.5-0.5\cos\left(\frac{2\pi n}{N-1}\right)
$$

La fenêtre réduit les discontinuités aux bords. Sans elle, la FFT interpréterait l'image finie comme une tuile périodique et introduirait du contenu haute fréquence artificiel aux frontières.

### 6.2 Transformée de Fourier 2D centrée

La transformée de Fourier 2D est :

$$
F(u,v)=\sum_{x=0}^{W-1}\sum_{y=0}^{H-1}\tilde{Y}(x,y)e^{-j2\pi(ux/W+vy/H)}
$$

Le spectre est décalé afin que la composante DC soit affichée au centre. Le panneau d'analyse de la photo affiche :

$$
M_{\log}(u,v)=\log(1+|F(u,v)|)
$$

normalisé dans $[0,1]$. Le logarithme est utilisé parce que les magnitudes de Fourier ont généralement une très grande plage dynamique.

### 6.3 Bandes de fréquence radiale

Pour chaque bin fréquentiel, la fréquence radiale normalisée est :

$$
r(u,v)=\frac{\sqrt{u^2+v^2}}{\max\sqrt{u^2+v^2}}
$$

Un petit rayon DC $r_{DC}$ est exclu des mesures d'énergie. Le reste du spectre est divisé en trois bandes contrôlées par l'utilisateur :

| Bande | Plage radiale par défaut | Interprétation |
|---|---|---|
| Basse | $[r_{DC},0.14)$ | grandes structures lisses |
| Moyenne | $[0.14,0.34)$ | formes et transitions de taille moyenne |
| Haute | $[0.34,1]$ | texture fine, contours, micro-détails |

Les limites entre bandes basse et haute sont contrôlées par un slider de plage ordonné. Si nécessaire, le backend trie et borne aussi les valeurs.

L'énergie d'une bande $\mathcal{B}$ est :

$$
E_{\mathcal{B}}=\frac{\sum_{(u,v)\in\mathcal{B}}|F(u,v)|^2}{\sum_{r(u,v)\ge r_{DC}}|F(u,v)|^2}
$$

L'énergie basse fréquence soutient les pads et la basse. L'énergie haute fréquence augmente la densité de texture, les timbres brillants et le tempo dans le mode de mapping Scientific.

### 6.4 Centroïde et largeur de bande de Fourier

Le centroïde radial est :

$$
\rho_c=\frac{\sum r(u,v)|F(u,v)|^2}{\sum |F(u,v)|^2}
$$

et la largeur de bande radiale est :

$$
B_F=\sqrt{\frac{\sum (r(u,v)-\rho_c)^2|F(u,v)|^2}{\sum |F(u,v)|^2}}
$$

Un centroïde élevé signifie que l'image est dominée par des structures fines. Une grande largeur de bande signifie que l'énergie est répartie sur plusieurs échelles.

### 6.5 Énergies directionnelles

L'angle d'un bin fréquentiel est :

$$
\theta(u,v)=\operatorname{atan2}(v,u)
$$

L'application mesure les énergies directionnelles horizontale et verticale avec une largeur d'orientation contrôlée par l'utilisateur, $\omega_o$ :

$$
E_{\mathrm{horizontal}}=\frac{\sum_{|\sin\theta|<\omega_o}|F|^2}{\sum |F|^2},
\qquad
E_{\mathrm{vertical}}=\frac{\sum_{|\cos\theta|<\omega_o}|F|^2}{\sum |F|^2}
$$

L'énergie diagonale est la partie restante :

$$
E_{\mathrm{diagonal}}=1-E_{\mathrm{horizontal}}-E_{\mathrm{vertical}}
$$

Ces valeurs sont affichées comme descripteurs de structure d'image. Elles sont moins centrales dans le mapping musical que les énergies radiales basse/moyenne/haute.

### 6.6 Score de pic périodique

Certaines images contiennent des motifs réguliers : rayures, grilles, fenêtres répétées, tuiles ou textures périodiques. Ces images produisent un spectre de Fourier avec de forts pics isolés. L'application estime cela avec :

$$
P_F=\operatorname{clip}\left(
\frac{\log\left(1+\dfrac{P_{p_H}(|F|^2)}{P_{p_L}(|F|^2)+\varepsilon}\right)}{d_F},0,1
\right)
$$

La plage de percentiles par défaut est $(p_L,p_H)=(90,99.7)$ et le diviseur par défaut est $d_F=5$. Cette plage de percentiles est aussi un slider de plage ordonné. Un score de pic périodique élevé encourage une structure en boucle, des timbres de type maillet et des motifs plus réguliers.

---

## 7. Saillance visuelle

La saillance estime quelles régions de la photo sont susceptibles d'attirer l'attention. Dans cette application, la saillance ne dépend pas d'une reconnaissance d'objets. Elle est construite à partir de trois indices mesurables : force des contours, rareté de couleur et rareté de luminance.

### 7.1 Rareté de couleur

Soit $\bar{\mathbf{c}}=(\bar{R},\bar{G},\bar{B})$ la couleur RGB moyenne de l'image. La rareté de couleur est :

$$
C_r(x,y)=\left\|\begin{bmatrix}R(x,y)\\G(x,y)\\B(x,y)\end{bmatrix}-\bar{\mathbf{c}}\right\|_2
$$

Les pixels dont la couleur est éloignée de la moyenne globale deviennent plus saillants.

### 7.2 Rareté de luminance

La rareté de luminance est :

$$
L_r(x,y)=|Y(x,y)-\mu_Y|
$$

Des pixels très clairs et très sombres peuvent tous deux être saillants s'ils sont inhabituels par rapport au reste de l'image.

### 7.3 Combinaison de saillance

Les trois composantes sont normalisées et mélangées avec des poids contrôlés par l'utilisateur :

$$
B_s(x,y)=w_e\hat{G}(x,y)+w_c\hat{C}_r(x,y)+w_l\hat{L}_r(x,y)
$$

Les poids par défaut sont $w_e=0.42$, $w_c=0.34$ et $w_l=0.24$, normalisés en interne pour que leur somme vaille 1.

Un léger biais central est ajouté parce que beaucoup de photographies placent le sujet près du centre :

$$
C_B(x,y)=1-\left\|\begin{bmatrix}x/(W-1)-0.5\\y/(H-1)-0.5\end{bmatrix}\right\|_2
$$

La carte de saillance finale est :

$$
\mathcal{S}(x,y)=\operatorname{normalize}_{[0,1]}\left((1-\lambda_c)B_s(x,y)+\lambda_cC_B(x,y)\right)
$$

où $\lambda_c$ est le poids du biais central, valant 0.12 par défaut.

### 7.4 Masque de saillance et descripteurs

Un masque saillant est défini avec un seuil percentile et un seuil minimum :

$$
\mathcal{M}_{\mathcal{S}}=\left\{(x,y):\mathcal{S}(x,y)\ge\max\bigl(\tau_{\mathcal{S}},P_{q_{\mathcal{S}}}(\mathcal{S})\bigr)\right\}
$$

Les valeurs par défaut sont $q_{\mathcal{S}}=96\%$ et $\tau_{\mathcal{S}}=0.20$. À partir de ce masque, l'application calcule le pic, la moyenne, l'aire, le centroïde et la dispersion de saillance. Ces valeurs sont utilisées par la couche solo/accent.

---

## 8. Descripteurs visuels et décisions musicales

Ce tableau donne le lien pratique entre les descripteurs d'image et le comportement musical.

| Caractéristique visuelle | Effet musical |
|---|---|
| Luminosité moyenne $\mu_Y$ | registre de la racine, tendance de gamme, humeur |
| Contraste $\sigma_Y$ | tempo, vélocité mélodique, énergie des accords |
| Proportion d'ombre $s$ | force de la basse, timbres plus sombres, tempo plus lent |
| Proportion de hautes lumières $h$ | instruments brillants, accents, activité des accords |
| Densité de contours $D_e$ | tempo, attaques, densité rythmique |
| Entropie de texture $H_{\mathrm{tex}}$ | complexité et nombre de mesures |
| Symétrie $S$ | force de variation |
| Teinte dominante $\bar{h}$ | centre tonal / tonalité |
| Saturation | gamme et colorfulness instrumentale |
| Chaleur | tendance de gamme et affinité d'instruments chauds/froids |
| Énergie de Fourier basse $E_{\mathrm{low}}$ | pads, basse, instruments doux |
| Énergie de Fourier haute $E_{\mathrm{high}}$ | arpèges, timbres brillants, texture rapide |
| Centroïde de Fourier $\rho_c$ | contribution au tempo Scientific |
| Largeur de bande de Fourier $B_F$ | richesse de texture |
| Score de pic périodique $P_F$ | motifs répétitifs, affinité maillet/percussive |
| Pic/aire/dispersion de saillance | nombre de notes solo, espacement et durée |
| Positions de saillance | timing et hauteur du solo |
| Centroïde lumineux | panoramique stéréo main/chord |
| Centroïde d'ombre | panoramique stéréo de la basse |
| Tranches de luminance | contour de la mélodie principale |

Ce tableau est aussi une manière utile d'interpréter le résultat. Par exemple, si une photo produit une texture dense et rapide, la cause est généralement une combinaison de densité de contours, d'énergie haute fréquence de Fourier et d'entropie de texture. Si elle produit une pièce sombre et lente, la cause est généralement une faible luminosité, une forte proportion d'ombre et une faible énergie haute fréquence.

---

## 9. Structure automatique : mesures, complexité et variation

### 9.1 Complexité

La complexité automatique est dérivée de l'entropie de texture. Dans la version actuelle de l'application, l'utilisateur contrôle la plage de sortie :

$$
C_{\mathrm{auto}}=C_{\min}+(C_{\max}-C_{\min})H_{\mathrm{tex}}
$$

La plage par défaut est $[0.25,0.90]$. Le slider Complexity final contrôle la densité de notes, la vitesse de parcours mélodique et l'activation de la texture.

### 9.2 Force de variation

La variation est dérivée du manque de symétrie :

$$
V_{\mathrm{auto}}=V_{\min}+(V_{\max}-V_{\min})(1-S)
$$

La plage par défaut est $[0.25,0.85]$. Une image symétrique donne une variation plus faible. Une image asymétrique donne une variation plus forte, surtout dans la seconde moitié de la pièce.

### 9.3 Nombre de mesures

L'estimateur du nombre de mesures utilise un score pondéré :

$$
Q_B=w_tH_{\mathrm{tex}}+w_eD_e+w_hE_{\mathrm{high}}+w_pP_F
$$

Les poids par défaut sont $w_t=0.40$, $w_e=0.25$, $w_h=0.20$ et $w_p=0.15$, normalisés en interne.

L'application projette ce score dans trois plages :

$$
B_{\min}=\operatorname{round}\bigl(\operatorname{interp}(Q_B,[0,1],[B_{\min}^{lo},B_{\min}^{hi}])\bigr)
$$

$$
B_{\max}=\operatorname{round}\bigl(\operatorname{interp}(Q_B,[0,1],[B_{\max}^{lo},B_{\max}^{hi}])\bigr)
$$

$$
B_0=\operatorname{round}\bigl(\operatorname{interp}(Q_B,[0,1],[B_0^{lo},B_0^{hi}])\bigr)
$$

Les plages par défaut sont $[4,8]$ pour le minimum de mesures, $[12,24]$ pour le maximum de mesures et $[6,16]$ pour la valeur par défaut. Le backend garantit $B_{\max}>B_{\min}$ et borne $B_0$ à l'intérieur de l'intervalle valide.

---

## 10. Tonalité, gamme et tempo

### 10.1 Tonalité à partir de la teinte dominante

La teinte dominante est associée à l'une des 12 classes de hauteur :

$$
k=\operatorname{round}(12\bar{h})\bmod 12
$$

avec les classes de hauteur :

$$
\{C,C\#,D,D\#,E,F,F\#,G,G\#,A,A\#,B\}
$$

La note MIDI racine est décalée par la luminosité de l'image :

$$
\text{root}=\operatorname{clip}\left(48+k+\operatorname{round}\bigl(\operatorname{interp}(\mu_Y,[0,1],[-5,7])\bigr),38,58\right)
$$

Les images plus sombres tendent donc à utiliser des registres plus graves, tandis que les images plus lumineuses tendent à utiliser des registres plus aigus.

### 10.2 Sélection de la gamme

Les gammes disponibles sont :

| Gamme | Intervalles en demi-tons |
|---|---|
| Pentatonique majeure | $0,2,4,7,9$ |
| Pentatonique mineure | $0,3,5,7,10$ |
| Majeure | $0,2,4,5,7,9,11$ |
| Mineure naturelle | $0,2,3,5,7,8,10$ |
| Dorienne | $0,2,3,5,7,9,10$ |
| Lydienne | $0,2,4,6,7,9,11$ |

Si Scale est réglé sur Automatic, l'application utilise la luminosité, la chaleur, la saturation et le contraste. Les images lumineuses et chaudes tendent vers des gammes lydiennes ou de type majeur. Les images plus sombres tendent vers le dorien ou la mineure naturelle.

### 10.3 Mapping du tempo

L'application propose quatre modes de tempo.

Le mode Scientific utilise la structure spatiale et les descripteurs de Fourier :

$$
T=\operatorname{clip}\bigl(50+70D_e+58\sigma_Y+42P_F+34E_{\mathrm{high}}+22\rho_c-20s,T_{lo},T_{hi}\bigr)
$$

La plage Scientific par défaut est $[48,152]$ BPM.

Le mode Balanced est une version plus douce :

$$
T=\operatorname{clip}\bigl(62+38D_e+28\sigma_Y+20P_F+10E_{\mathrm{high}}-8s,T_{lo},T_{hi}\bigr)
$$

La plage Balanced par défaut est $[56,132]$ BPM.

Le mode Musical est plus lisse et principalement fondé sur la couleur :

$$
T=\operatorname{clip}\bigl(82+10\overline{\mathrm{Sat}}+8\mu_Y-6s+4w_{\mathrm{arm}},T_{lo},T_{hi}\bigr)
$$

La plage Musical par défaut est $[72,108]$ BPM.

Le mode Manual permet à l'utilisateur de fixer directement le BPM.

---

## 11. Harmonie et progression d'accords

Un accord est construit à partir de la gamme sélectionnée en empilant un degré sur deux. Pour une liste d'intervalles de gamme :

$$
I=[i_0,i_1,\ldots,i_{n-1}]
$$

alors une triade sur le degré $d$ est :

$$
\operatorname{chord}(d)=\{i_d,i_{d+2},i_{d+4}\}
$$

avec un retour à l'octave lorsque l'indice dépasse la longueur de la gamme.

L'application choisit une progression dans un petit ensemble. Pour les gammes à sept notes, quelques exemples sont :

$$
[0,4,5,3],\quad [0,5,3,4],\quad [0,2,5,4],\quad [0,3,1,4]
$$

La progression sélectionnée dépend de la teinte dominante, du score de pic périodique, de l'entropie de texture et du centroïde de saillance :

$$
\text{seed}=\operatorname{round}(997\bar{h}+113P_F+71H_{\mathrm{tex}}+53c_x^{\mathcal{S}})
$$

Si la force de variation est supérieure à 0.45, la seconde moitié de la composition décale l'indice de progression. Cela produit une forme A/B simple : la première moitié établit une boucle, et la seconde la déplace légèrement.

---

## 12. Couches mélodique, texture, basse, pad, accord et solo

### 12.1 Mélodie principale à partir des tranches de luminance

L'image est lue de gauche à droite. Pour une composition de $B$ mesures, l'image est divisée en $8B$ tranches verticales. Pour chaque tranche, l'application calcule l'énergie locale, le contraste et le centroïde vertical de luminosité.

Le centroïde vertical utilise un poids tronqué par percentile :

$$
w_i(y)=\max\bigl(Y_i(y)-P_{35}(Y_i),0\bigr)
$$

La position dans le pool de notes mélodiques est :

$$
\operatorname{pos}_i=\operatorname{clip}\bigl(1-c_{y,i}+0.18(\bar{Y}_i-\mu_Y),0,1\bigr)
$$

Les zones hautes et lumineuses produisent des notes plus aiguës. Les zones basses et sombres produisent des notes plus graves.

La densité mélodique dépend du slider Complexity. Si la complexité dépasse le seuil de densité mélodique, chaque tranche peut générer une note. Sinon, une tranche sur deux est utilisée. Les tranches très sombres peuvent être ignorées sauf si elles tombent sur un temps structurel ; ce seuil est contrôlé par Melody energy gate.

### 12.2 Variation mélodique

La pièce est divisée en quatre grandes sections. Un petit décalage dépendant de la section est ajouté à la mélodie :

$$
\Delta m \in \{0,2,-2,5\}
$$

pondéré par la force de variation :

$$
m_{\mathrm{final}}=m_{\mathrm{base}}+\operatorname{round}(V\Delta m)
$$

Cela garde la mélodie proche du contour de l'image tout en évitant que les sorties longues deviennent trop répétitives.

### 12.3 Couches pad, accord et basse

Les notes de pad soutiennent l'accord courant pendant toute la mesure. Leur vélocité augmente avec l'énergie basse fréquence :

$$
v_{\mathrm{pad}}=\operatorname{clip}(0.07+0.18E_{\mathrm{low}}+0.04(1-E_{\mathrm{high}}),0.04,0.28)
$$

Les impacts d'accord jouent la triade courante une fois par mesure. Si l'énergie haute fréquence dépasse le seuil Chord double-hit, un second impact d'accord est ajouté au milieu de la mesure.

La basse utilise un motif racine/quinte : racine sur le temps 1 et quinte sur le temps 3. La vélocité de la basse augmente avec la proportion d'ombre et l'énergie basse fréquence :

$$
v_{\mathrm{bass}}=\operatorname{clip}(0.30+0.55s+0.25E_{\mathrm{low}},0.22,0.86)
$$

### 12.4 Texture et percussion

La densité de texture est :

$$
\rho_{\mathrm{tex}}=\operatorname{clip}(0.20+0.80C+0.75E_{\mathrm{high}}+0.45B_F,0,1)
$$

où $C$ est la complexité contrôlée par l'utilisateur. Si $\rho_{\mathrm{tex}}$ est au-dessus du seuil d'activation de texture, l'application ajoute des événements de type arpège. Si elle est au-dessus du seuil rapide, la vitesse d'arpège double.

Une couche séparée de ticks de type percussion s'active lorsque $\rho_{\mathrm{tex}}$ dépasse le seuil d'activation de percussion. Ces ticks sont des événements courts placés sur le canal de percussion MIDI 9 dans l'export MIDI.

### 12.5 Couche solo de saillance

La couche solo est disponible en mode GeneralUser GS. Elle sélectionne des points saillants dans l'image et convertit leurs positions en temps et en hauteur.

Un score de force de saillance est :

$$
\eta=\operatorname{clip}\bigl(0.55\,\text{peak}+0.25\,\text{mean}+0.20(1-\text{area}),0,1\bigr)
$$

Le nombre de notes solo est interpolé à partir d'une plage de nombre de notes contrôlée par l'utilisateur, puis limité par le Solo note cap. Les points candidats sont sélectionnés parmi les pixels de saillance les plus forts, avec une contrainte de distance minimale pour éviter que les notes se concentrent toutes sur la même région visuelle.

La coordonnée horizontale devient le temps :

$$
t_k=x_k^{\mathrm{norm}}T_{\mathrm{dur}}+0.10\Delta t\sin(1.7k)
$$

La coordonnée verticale devient la hauteur :

$$
m_k=\operatorname{melody\_notes}\left[\operatorname{round}\bigl((1-y_k^{\mathrm{norm}})(N_{\mathrm{mel}}-1)\bigr)\right]+12
$$

Le solo se comporte donc comme une lecture mélodique parcimonieuse des régions les plus importantes visuellement.

---

## 13. Sélection des instruments

### 13.1 Mode Simple

Le mode Simple utilise des instruments de synthèse additive internes, comme soft piano, harp, music box, bright bell, marimba, cello-like bass, warm pad et glass pad. Il est entièrement autonome et ne nécessite pas de SoundFont.

En mode Automatic, l'application choisit les instruments avec des règles explicites fondées sur les caractéristiques. Par exemple, les images lumineuses avec beaucoup de hautes lumières favorisent bells ou celesta ; les images périodiques favorisent kalimba ou marimba ; les images sombres et lisses favorisent cello-like bass, bowed strings ou pads.

### 13.2 Mode GeneralUser GS

Le mode GeneralUser GS utilise les 128 noms de programmes General MIDI. Le rendu nécessite FluidSynth et une SoundFont GeneralUser GS. S'ils ne sont pas disponibles, l'application revient au backend de synthèse Simple tout en conservant la structure des événements musicaux.

Chaque programme General MIDI appartient à une famille, par exemple piano, chromatic percussion, organ, guitar, bass, strings, brass, reed, pipe, synth lead ou synth pad. Pour chaque couche, l'application attribue un score à chaque famille à partir des caractéristiques de l'image.

Par exemple, un score de lissage est :

$$
\lambda_{\mathrm{smooth}}=\operatorname{clip}(E_{\mathrm{low}}+0.35(1-E_{\mathrm{high}})+0.25S,0,1)
$$

Un score de luminosité est :

$$
\lambda_{\mathrm{bright}}=\operatorname{clip}(0.55\mu_Y+0.45h,0,1)
$$

Pour la couche principale, l'affinité piano inclut le lissage :

$$
W_{\mathrm{main}}(\mathrm{piano})=0.35+0.35\lambda_{\mathrm{smooth}}
$$

Les instruments de type pipe reçoivent des contributions de luminosité et de lissage :

$$
W_{\mathrm{main}}(\mathrm{pipe})=0.18+0.45\lambda_{\mathrm{bright}}+0.20\lambda_{\mathrm{smooth}}
$$

Des bonus au niveau des programmes individuels sont ajoutés. Par exemple, les programmes de type celesta, music box et bell reçoivent des bonus liés aux hautes lumières, à l'énergie haute fréquence et au pic de saillance. Les programmes de basse reçoivent des bonus liés aux ombres et à l'énergie basse fréquence.

Un jitter pseudo-aléatoire déterministe est ajouté :

$$
\operatorname{score}(p,\ell)=W_\ell(f_p)+\operatorname{bonus}(p)+0.42u(p,\ell)
$$

où $u(p,\ell)$ est dérivé d'un hash SHA-256 des caractéristiques de l'image. Cela apporte de la variété tout en restant reproductible.

### 13.3 Mode manuel et gains

En mode d'instrument Manual, l'utilisateur choisit l'instrument pour chaque couche. Chaque couche possède aussi un gain en décibels :

$$
g=10^{G_{\mathrm{dB}}/20}
$$

Le gain multiplie la vélocité des notes avant le rendu. Les vélocités sont bornées dans $[0,1]$.

---

## 14. Rendu audio et synthèse

### 14.1 Rendu des événements

Les événements générés sont placés dans un buffer stéréo à la fréquence d'échantillonnage $f_s=44100$ Hz. Un événement commençant au temps $t_i$ démarre à l'échantillon :

$$
n_i=\operatorname{round}(t_if_s)
$$

Chaque forme d'onde d'événement est synthétisée, multipliée par sa vélocité, spatialisée par panoramique, puis ajoutée au buffer.

### 14.2 Panoramique à puissance constante

Chaque événement possède une valeur de panoramique $p\in[-1,1]$. Les gains stéréo sont :

$$
g_L=\cos\left(\frac{\pi}{4}(p+1)\right),
\qquad
g_R=\sin\left(\frac{\pi}{4}(p+1)\right)
$$

C'est un panoramique à puissance constante. Il évite une baisse de niveau perçu au centre.

### 14.3 Enveloppe ADSR

Les instruments de synthèse Simple utilisent une enveloppe Attack-Decay-Sustain-Release :

$$
e[n]=
\begin{cases}
n/N_A, & 0\le n<N_A \\
1-(1-S_L)(n-N_A)/N_D, & N_A\le n<N_A+N_D \\
S_L, & N_A+N_D\le n<N-N_R \\
S_L(1-(n-(N-N_R))/N_R), & N-N_R\le n<N
\end{cases}
$$

L'enveloppe donne à chaque note une forme d'amplitude plus réaliste qu'une fenêtre rectangulaire abrupte.

### 14.4 Exemples de synthèse additive

Soft piano utilise des partiels harmoniques :

$$
x[n]=\sum_{m\in\{1,2,3,4,5\}}a_m\sin(2\pi mf_0n/f_s)
$$

avec les amplitudes :

$$
(a_1,a_2,a_3,a_4,a_5)=(1,0.42,0.20,0.10,0.04)
$$

Bright bell, celesta et music box utilisent des partiels inharmoniques pour créer un son métallique. Harp, marimba et synth pluck utilisent une décroissance harmonique en loi de puissance. Les pads et les cordes frottées utilisent des enveloppes lentes et un léger modèle de vibrato.

---

## 15. Bus principal, exports et analyse audio

### 15.1 Traitement du bus principal

Après le mixage de toutes les couches, le bus principal est traité en trois étapes.

D'abord, l'offset DC est retiré de chaque canal :

$$
x_{dc}[n]=x[n]-\frac{1}{N}\sum_{m=0}^{N-1}x[m]
$$

Ensuite, le niveau RMS est limité. Le RMS stéréo est :

$$
\operatorname{RMS}=\sqrt{\frac{1}{2N}\sum_{n=0}^{N-1}\bigl(x_L[n]^2+x_R[n]^2\bigr)}
$$

S'il dépasse le RMS cible, le signal est atténué. Enfin, le niveau de crête est limité à la crête cible. Un clip de sécurité final évite les dépassements.

La crête cible par défaut est 0.86 et le RMS cible par défaut est 0.16, mais les deux valeurs sont exposées dans le panneau Parameters.

### 15.2 Formats d'export

L'application exporte :

| Export | Contenu |
|---|---|
| Lecture WAV | audio stéréo rendu à 44100 Hz |
| MP3 | audio compressé, généré avec `lameenc` ou `ffmpeg` si disponible |
| MIDI | événements de notes, tempo, canaux et changements de programme |

L'export MIDI utilise une piste, 480 pulses per quarter note et des canaux fixes pour les couches musicales :

| Couche | Canal MIDI |
|---|---|
| Main | 0 |
| Texture | 1 |
| Bass | 2 |
| Pad | 3 |
| Chord | 4 |
| Solo | 5 |
| Percussion tick | 9 |

### 15.3 Graphiques d'analyse audio

Le panneau Audio analysis calcule une magnitude de Fourier unilatérale pour le mix complet et pour les couches individuelles. Pour un signal mono $x[n]$, la magnitude est :

$$
|X[k]|=\left|\sum_{n=0}^{N-1}x[n]e^{-j2\pi kn/N}\right|
$$

L'axe fréquentiel est :

$$
f_k=\frac{kf_s}{N}
$$

Les graphiques par couche sont générés en rendant à nouveau uniquement les événements d'une couche. Cela aide à vérifier que les couches basse, pad, mélodie principale, texture et accords occupent des régions spectrales différentes.

---

## 16. Random factor

Random factor ajoute une perturbation contrôlée à l'analyse. Il ne remplace pas le mapping fondé sur l'image par du hasard pur.

Soit :

$$
\alpha=\frac{r}{100}
$$

où $r$ est la valeur du slider Random factor.

Le bruit spatial RGB est :

$$
R'(x,y)=\operatorname{clip}(R(x,y)+\eta_R(x,y),0,1)
$$

avec :

$$
\eta_R\sim\mathcal{N}(0,\sigma_{img}^2),
\qquad
\sigma_{img}=c_{img}\alpha^2
$$

Le coefficient par défaut est $c_{img}=0.045$.

Le bruit de magnitude de Fourier est multiplicatif :

$$
|F'(u,v)|=|F(u,v)|\exp(\eta_F(u,v))
$$

avec :

$$
\eta_F\sim\mathcal{N}(0,\sigma_F^2),
\qquad
\sigma_F=c_F\alpha^2
$$

Le coefficient par défaut est $c_F=0.18$.

La loi quadratique rend les faibles valeurs de Random factor subtiles et les fortes valeurs plus audibles. La graine dépend du hash de l'image, du Random factor et de la signature des paramètres ; ainsi, une image et des réglages fixes restent reproductibles.

Le panneau Photo analysis affiche les cartes d'analyse non perturbées. Lorsque Random factor est non nul, la composition générée peut utiliser l'analyse perturbée, mais les cartes affichées restent une référence propre pour l'image originale.

---

## 17. Référence des paramètres

La boîte Parameters est organisée en mini-pages, dans le même style que l'application Audio Visualization.

### 17.1 Structure

| Paramètre | Défaut | Rôle |
|---|---|---|
| Number of bars | adaptatif selon la photo | durée totale en mesures de 4/4 |
| Variation strength | adaptatif selon la photo | changement mélodique et harmonique dans la seconde moitié |
| Composition complexity | adaptatif selon la photo | densité de notes et activité de texture |
| Random factor | 0 | perturbation contrôlée de l'analyse image/Fourier |
| Auto complexity range | 0.25-0.90 | associe l'entropie de texture à la complexité |
| Auto variation range | 0.25-0.85 | associe $1-S$ à la variation |
| Auto min-bars range | 4-8 | plage basse/haute du minimum automatique de mesures |
| Auto max-bars range | 12-24 | plage basse/haute du maximum automatique de mesures |
| Auto default-bars range | 6-16 | plage basse/haute de la valeur par défaut automatique |
| Bar weights | 0.40 / 0.25 / 0.20 / 0.15 | rôle relatif de la texture, des contours, des hautes fréquences et de la périodicité |

### 17.2 Analyse de l'image

| Paramètre | Défaut | Rôle |
|---|---|---|
| Analysis max side | 512 px | plus grand côté utilisé pour l'extraction des caractéristiques |
| Spatial noise coefficient | 0.045 | force du Random factor dans l'espace RGB |
| Entropy histogram bins | 64 | résolution de l'histogramme d'entropie de texture |
| Edge threshold percentile | 75% | seuil adaptatif de contours |
| Minimum edge threshold | 0.08 | borne inférieure fixe du seuil de contours |
| Luminance percentile range | 5%-95% | percentiles pour la plage dynamique et les ombres/hautes lumières |
| Shadow floor | 0.18 | seuil minimum pour les régions sombres |
| Shadow percentile offset | 0.03 | offset ajouté au percentile bas de luminance |
| Highlight floor | 0.82 | seuil de référence supérieur pour les régions lumineuses |
| Highlight percentile offset | 0.03 | offset soustrait au percentile haut de luminance |

### 17.3 Fourier et saillance

| Paramètre | Défaut | Rôle |
|---|---|---|
| DC exclusion radius | 0.025 | retire l'énergie proche de DC des descripteurs de Fourier |
| Low/mid/high radial limits | 0.14 / 0.34 | sépare les bandes de fréquences spatiales |
| Orientation bandwidth | 0.38 | largeur angulaire pour les énergies horizontale/verticale |
| Peak-score percentile range | 90%-99.7% | compare les pics forts à la puissance de fond |
| Peak-score log divisor | 5.0 | compresse le score de pic périodique |
| Fourier noise coefficient | 0.18 | force du Random factor sur la magnitude de Fourier |
| Saliency weights | 0.42 / 0.34 / 0.24 | contributions contours, rareté de couleur et rareté de luminance |
| Center-bias weight | 0.12 | poids du biais de composition centrale |
| Saliency threshold percentile | 96% | sélectionne les régions de saillance les plus fortes |
| Minimum saliency threshold | 0.20 | borne inférieure fixe du masque de saillance |
| Solo note-count range | 3-18 | associe la force de saillance au nombre de notes solo |
| Solo note cap | 22 | nombre maximal de notes solo |
| Minimum saliency-point distance | 0.055 | empêche les notes solo de se regrouper |
| Solo duration range | 0.18-1.25 beats | borne de durée pour les notes solo |

### 17.4 Tonalité et tempo

| Paramètre | Défaut | Rôle |
|---|---|---|
| Scale | Automatic | choisir ou forcer la gamme modale |
| Mapping style | Scientific | formule de mapping du tempo |
| Manual BPM | 90 | tempo fixe lorsque Manual est sélectionné |
| Scientific BPM range | 48-152 | plage de clamp pour la formule Scientific |
| Balanced BPM range | 56-132 | plage de clamp pour la formule Balanced |
| Musical BPM range | 72-108 | plage de clamp pour la formule Musical |

### 17.5 Synthèse et mixage

| Paramètre | Défaut | Rôle |
|---|---|---|
| Synthesizer type | GeneralUser GS | backend de rendu |
| Instrument layer selection | Automatic | choix automatique ou manuel des instruments |
| Target peak | 0.86 | limite de crête du bus principal |
| Target RMS | 0.16 | limite RMS du bus principal |
| Maximum render duration | 120 s | limite de sécurité pour les sorties longues |
| FluidSynth master gain | 0.45 | gain envoyé à FluidSynth |
| Chord double-hit high-frequency threshold | 0.22 | active un second impact d'accord par mesure |
| Melody density threshold | 0.52 | contrôle le pas de lecture des tranches mélodiques |
| Melody energy gate | 0.10 | ignore les tranches mélodiques à très faible énergie |
| Texture activation threshold | 0.28 | active la texture en arpèges |
| Percussion activation threshold | 0.18 | active les événements courts de type tick |

### 17.6 Instruments

En mode Manual instrument, la page Instruments permet à l'utilisateur de sélectionner l'instrument et le gain de chaque couche. Les gains sont exprimés en dB sur la plage $[-24,12]$ dB. En mode Automatic, cette page affiche plutôt les instruments sélectionnés à partir de la photo.

---

## 18. Limites

L'application est fondée sur des caractéristiques, pas sur la sémantique. Elle ne sait pas si la photo contient une personne, un paysage, une ville ou une peinture abstraite. Deux images différentes mais ayant des statistiques similaires de luminance, de couleur, de contours et de Fourier peuvent produire une musique similaire.

Le mapping est conçu pour être interprétable, pas pour produire une esthétique universelle. Les choix de gammes, de progressions d'accords et d'affinités instrumentales suivent un cadre tonal occidental. Ce sont des choix de conception explicites, pas des lois générales de la musique visuelle.

Le synthétiseur Simple est léger et explicable, mais ce n'est pas un modèle physique d'instruments réels. Le mode GeneralUser GS donne des timbres plus réalistes, mais il dépend de FluidSynth et d'une SoundFont.

Les photos bruitées en haute résolution peuvent produire une forte densité de contours et une forte énergie de Fourier, ce qui peut conduire à des compositions rapides et denses. Le redimensionnement d'analyse et les paramètres de seuil sont fournis pour permettre à l'utilisateur de contrôler ce comportement.

Random factor est déterministe pour des réglages fixes, mais il modifie quand même l'analyse utilisée pour la composition. Les cartes photo affichées restent non perturbées afin que l'utilisateur puisse distinguer l'analyse visuelle originale du comportement de composition randomisé.

---
