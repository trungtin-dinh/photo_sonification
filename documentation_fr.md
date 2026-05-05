## Table des matières

1. [Objectif de l'application](#1-objectif-de-lapplication)
2. [Principe conceptuel](#2-principe-conceptuel)
3. [Pipeline](#3-pipeline)
4. [Notation et opérateurs](#4-notation-et-opérateurs)
5. [Prétraitement de l'image](#5-prétraitement-de-limage)
6. [Luminance, contraste, ombres et hautes lumières](#6-luminance-contraste-ombres-et-hautes-lumières)
7. [Contours, texture et symétrie](#7-contours-texture-et-symétrie)
8. [Descripteurs de couleur](#8-descripteurs-de-couleur)
9. [Analyse de Fourier de l'image](#9-analyse-de-fourier-de-limage)
10. [Saillance visuelle](#10-saillance-visuelle)
11. [Vecteur de descripteurs](#11-vecteur-de-descripteurs)
12. [Des descripteurs d'image aux décisions musicales](#12-des-descripteurs-dimage-aux-décisions-musicales)
13. [Structure automatique : complexité, variation et nombre de mesures](#13-structure-automatique--complexité-variation-et-nombre-de-mesures)
14. [Tonalité, gamme et tempo](#14-tonalité-gamme-et-tempo)
15. [Harmonie et progression d'accords](#15-harmonie-et-progression-daccords)
16. [Couches musicales](#16-couches-musicales)
17. [Sélection des instruments](#17-sélection-des-instruments)
18. [Rendu audio](#18-rendu-audio)
19. [Sorties MIDI, MP3 et analyse](#19-sorties-midi-mp3-et-analyse)
20. [Random Factor](#20-random-factor)
21. [Référence des paramètres](#21-référence-des-paramètres)
22. [Comment interpréter le résultat](#22-comment-interpréter-le-résultat)
23. [Limites](#23-limites)

---

## 1. Objectif de l'application

Photo Sonification convertit une image fixe en une courte composition musicale.

L'application ne réalise pas de reconnaissance sémantique. Elle ne détecte pas les visages, les objets, les lieux, les émotions ou les scènes. Elle considère l'image comme un signal bidimensionnel et extrait des descripteurs visuels mesurables : luminance, contraste, densité de contours, entropie de texture, symétrie, statistiques de couleur, distribution d'énergie de Fourier et saillance.

Ces descripteurs sont ensuite associés à des variables musicales : tonalité, gamme, tempo, registre, densité de notes, équilibre des couches, choix des instruments, placement stéréo et contour mélodique.

L'objectif n'est pas d'obtenir la seule musique correcte pour une photographie. Une telle réponse unique n'existe pas. L'objectif est de construire une correspondance déterministe et interprétable entre structure visuelle et structure musicale.

Lorsque le paramètre Random factor vaut zéro, la même image et les mêmes paramètres produisent le même résultat.

L'idée centrale peut s'écrire sous la forme

$$
\text{image}
\xrightarrow{\text{extraction de descripteurs}}
\mathbf{f}
\xrightarrow{\text{mapping musical}}
\mathcal{E}
\xrightarrow{\text{synthèse audio}}
\text{audio} + \text{MIDI},
$$

où $\mathbf{f}$ est le vecteur de descripteurs et $\mathcal{E}$ est l'ensemble des événements de notes générés.

Une manière personnelle de résumer l'application est la suivante : la photo n'est pas traduite comme une phrase; elle est lue comme un signal. La musique est la trace laissée par cette lecture.

---

## 2. Principe conceptuel

Une image numérique peut être étudiée comme une fonction discrète. Pour une image RGB, chaque pixel contient trois valeurs. Après normalisation, l'image peut s'écrire

$$
I(x,y)=\bigl(R(x,y),G(x,y),B(x,y)\bigr),
$$

avec

$$
R(x,y),G(x,y),B(x,y) \in [0,1].
$$

L'application ne convertit pas directement les valeurs RGB en son. Elle commence par calculer des descripteurs qui possèdent un sens clair en traitement du signal.

Par exemple :

| Propriété de l'image | Interprétation en traitement du signal | Rôle musical possible |
|---|---|---|
| Luminance moyenne | niveau moyen du signal | registre, couleur générale, tendance de gamme |
| Contraste | dispersion autour de la moyenne | énergie, tempo, vélocité |
| Densité de contours | variation spatiale locale | densité rythmique, attaques |
| Énergie de Fourier haute fréquence | détails fins et changements spatiaux rapides | texture, brillance, tempo |
| Énergie de Fourier basse fréquence | grandes structures lisses | pads, basse, couches soutenues |
| Symétrie | similarité par réflexion | stabilité ou variation |
| Saillance | régions visuellement dominantes | accents solo |

Le mapping est volontairement explicite. Cela distingue l'application d'un modèle génératif de type boîte noire. L'utilisateur peut inspecter les descripteurs et comprendre pourquoi une image donnée produit un résultat lent, sombre et lisse, ou au contraire un résultat rapide, brillant et dense.

---

## 3. Pipeline

Le pipeline complet est divisé en quatre étapes.

| Étape | Entrée | Sortie | Rôle |
|---|---|---|---|
| Analyse d'image | image RGB | descripteurs et cartes visuelles | décrire l'image comme un signal |
| Mapping musical | vecteur de descripteurs | tonalité, tempo, couches, instruments | convertir les grandeurs visuelles en décisions musicales |
| Génération d'événements | réglages musicaux | événements de notes | construire une composition symbolique |
| Rendu | événements de notes | waveform, MIDI, MP3, graphiques | synthétiser et exporter le résultat |

Un événement de note est représenté par

$$
e_i=(t_i,d_i,m_i,v_i,I_i,p_i,\ell_i),
$$

où :

| Symbole | Signification |
|---|---|
| $t_i$ | instant de début en secondes |
| $d_i$ | durée en secondes |
| $m_i$ | hauteur MIDI |
| $v_i$ | vélocité ou amplitude normalisée |
| $I_i$ | instrument ou modèle de synthèse |
| $p_i$ | panoramique stéréo dans $[-1,1]$ |
| $\ell_i$ | label de couche |

L'application génère plusieurs couches. La couche Main porte la mélodie principale. Texture ajoute des événements courts et des arpèges. Bass fournit un support dans le registre grave. Pad fournit un fond harmonique soutenu. Chord ajoute des impacts harmoniques. Solo ajoute des accents pilotés par la saillance lorsque le mode GeneralUser GS est utilisé.

---

## 4. Notation et opérateurs

| Symbole | Définition |
|---|---|
| $H,W$ | hauteur et largeur de l'image après redimensionnement pour l'analyse |
| $\Omega$ | grille des pixels, $\Omega=\{0,\ldots,W-1\}\times\{0,\ldots,H-1\}$ |
| $R,G,B$ | canaux de couleur normalisés |
| $Y$ | image de luminance |
| $P_q(X)$ | percentile d'ordre $q$ du tableau $X$ |
| $\mu_Y$ | luminance moyenne |
| $\sigma_Y$ | écart-type de la luminance |
| $D_Y$ | plage dynamique robuste de la luminance |
| $\hat{G}$ | magnitude du gradient normalisée |
| $D_e$ | densité de contours |
| $H_{\mathrm{tex}}$ | entropie de texture |
| $S$ | score de symétrie |
| $\bar{h}$ | teinte dominante |
| $\overline{\mathrm{Sat}}$ | saturation moyenne |
| $w_{\mathrm{warm}}$ | score de chaleur chromatique |
| $F(u,v)$ | transformée de Fourier 2D centrée de la luminance |
| $r(u,v)$ | fréquence spatiale radiale normalisée |
| $E_{\mathrm{low}},E_{\mathrm{mid}},E_{\mathrm{high}}$ | proportions d'énergie de Fourier |
| $\rho_c$ | centroïde radial de Fourier |
| $B_F$ | largeur de bande radiale de Fourier |
| $P_F$ | score de pic périodique |
| $\mathcal{S}$ | carte de saillance |
| $T$ | tempo en battements par minute |
| $\Delta t$ | durée d'un temps, $\Delta t=60/T$ |
| $B_{\mathrm{bars}}$ | nombre de mesures musicales |

L'opérateur

$$
\operatorname{clip}(x,a,b)
$$

limite $x$ à l'intervalle $[a,b]$.

L'opérateur

$$
\operatorname{interp}(x,[a,b],[c,d])
$$

réalise une interpolation linéaire de l'intervalle $[a,b]$ vers l'intervalle $[c,d]$.

La notation

$$
\operatorname{normalize}_{[0,1]}(X)
$$

désigne une normalisation min-max :

$$
\operatorname{normalize}_{[0,1]}(X)=\frac{X-\min(X)}{\max(X)-\min(X)+\varepsilon},
$$

où $\varepsilon>0$ évite la division par zéro.

---

## 5. Prétraitement de l'image

Le fichier d'entrée est chargé comme une image RGB. L'orientation EXIF est corrigée lorsqu'elle est disponible. Si l'image est trop grande, elle est redimensionnée pour l'analyse. Ce redimensionnement affecte seulement l'extraction des descripteurs et le temps de calcul. Il ne redéfinit pas le modèle conceptuel de l'image.

Les canaux RGB normalisés sont

$$
R(x,y),G(x,y),B(x,y) \in [0,1].
$$

Les grandes images contiennent plus de détails, mais elles augmentent aussi le coût de l'analyse de Fourier et du calcul de saillance. Pour une application en ligne, la résolution d'analyse est donc un compromis entre précision et réactivité.

---

## 6. Luminance, contraste, ombres et hautes lumières

### 6.1 Luminance perceptuelle

De nombreuses structures d'image sont décrites plus clairement dans la luminance que dans les canaux RGB bruts. L'application utilise la formule de luminance BT.709 :

$$
Y(x,y)=0.2126R(x,y)+0.7152G(x,y)+0.0722B(x,y).
$$

Le canal vert possède le coefficient le plus élevé parce que la perception humaine de la luminosité est plus sensible au vert qu'au bleu.

### 6.2 Luminance moyenne

La luminance moyenne est

$$
\mu_Y=\frac{1}{HW}\sum_{(x,y)\in\Omega}Y(x,y).
$$

Une faible valeur de $\mu_Y$ indique une image globalement sombre. Une valeur élevée indique une image globalement lumineuse. Dans le mapping musical, cette grandeur influence le registre et la tendance de gamme.

### 6.3 Contraste

Le contraste de luminance est mesuré par l'écart-type :

$$
\sigma_Y=\sqrt{\frac{1}{HW}\sum_{(x,y)\in\Omega}\left(Y(x,y)-\mu_Y\right)^2}.
$$

Une valeur élevée signifie que l'image contient de fortes variations d'intensité. Elle conduit généralement à un résultat musical plus énergique.

### 6.4 Plage dynamique robuste

La plage dynamique robuste est calculée à partir de percentiles :

$$
D_Y=P_{p_H}(Y)-P_{p_L}(Y),
$$

où $p_L$ et $p_H$ sont des percentiles inférieur et supérieur contrôlés par l'utilisateur. Les valeurs par défaut sont généralement proches de $5\%$ et $95\%$.

Les percentiles sont utilisés à la place du minimum et du maximum absolus, car un pixel noir ou blanc isolé ne doit pas dominer le descripteur.

### 6.5 Masques d'ombre et de haute lumière

Le masque d'ombre est défini par

$$
\mathcal{M}_{\mathrm{shadow}}=
\left\{(x,y):Y(x,y)<\max\left(\tau_s,P_{p_L}(Y)+\delta_s\right)\right\}.
$$

Le masque de haute lumière est défini par

$$
\mathcal{M}_{\mathrm{highlight}}=
\left\{(x,y):Y(x,y)>\min\left(\tau_h,P_{p_H}(Y)-\delta_h\right)\right\}.
$$

Les proportions correspondantes sont

$$
s=\frac{|\mathcal{M}_{\mathrm{shadow}}|}{HW},
\qquad
h=\frac{|\mathcal{M}_{\mathrm{highlight}}|}{HW}.
$$

La proportion d'ombre renforce la basse et les timbres sombres. La proportion de hautes lumières renforce les attaques brillantes, les cloches, les arpèges et les accents.

---

## 7. Contours, texture et symétrie

### 7.1 Magnitude du gradient

Les contours sont des changements locaux de luminance. La magnitude du gradient est

$$
G(x,y)=\sqrt{\left(\partial_xY(x,y)\right)^2+\left(\partial_yY(x,y)\right)^2}.
$$

Elle est normalisée selon

$$
\hat{G}(x,y)=\frac{G(x,y)-\min(G)}{\max(G)-\min(G)+\varepsilon}.
$$

### 7.2 Densité de contours

La densité de contours est la proportion de pixels dont le gradient normalisé dépasse un seuil adaptatif :

$$
D_e=\frac{1}{HW}\left|\left\{(x,y):\hat{G}(x,y)>\max\left(\tau_e,P_{q_e}(\hat{G})\right)\right\}\right|.
$$

Le terme percentile adapte le seuil à l'image. Le seuil fixe empêche de très faibles fluctuations d'être comptées comme des contours.

Musicalement, $D_e$ augmente l'activité rythmique et peut augmenter le tempo dans les modes Scientific et Balanced.

### 7.3 Entropie de texture

La carte de gradient normalisée est résumée par un histogramme à $K$ bins. Soit $p_k$ la probabilité du bin $k$. L'entropie de texture est

$$
H_{\mathrm{tex}}=-\frac{1}{\log_2K}\sum_{k=1}^{K}p_k\log_2(p_k+\varepsilon).
$$

La division par $\log_2K$ normalise approximativement la valeur dans $[0,1]$.

Une image lisse produit une faible entropie. Une image visuellement complexe produit une entropie élevée. L'application utilise ce descripteur pour estimer la complexité de la composition et le nombre de mesures.

### 7.4 Symétrie

L'image est comparée avec ses réflexions gauche-droite et haut-bas :

$$
S_{LR}=1-\frac{1}{HW}\sum_{(x,y)\in\Omega}|Y(x,y)-Y(W-1-x,y)|,
$$

$$
S_{TB}=1-\frac{1}{HW}\sum_{(x,y)\in\Omega}|Y(x,y)-Y(x,H-1-y)|.
$$

Le score final donne plus de poids à la symétrie gauche-droite :

$$
S=0.70S_{LR}+0.30S_{TB}.
$$

Un score de symétrie élevé correspond à une stabilité visuelle. Dans l'application, cela réduit la variation automatique. Un score de symétrie faible correspond à un déséquilibre plus marqué ou à une structure directionnelle. Cela augmente la variation, surtout dans la seconde moitié de la musique.

---

## 8. Descripteurs de couleur

### 8.1 Saturation

Pour chaque pixel, la saturation est calculée à partir de la chroma RGB :

$$
\mathrm{Sat}(x,y)=
\begin{cases}
\dfrac{\max(R,G,B)-\min(R,G,B)}{\max(R,G,B)}, & \max(R,G,B)>0,\\
0, & \max(R,G,B)=0.
\end{cases}
$$

La saturation moyenne est

$$
\overline{\mathrm{Sat}}=\frac{1}{HW}\sum_{(x,y)\in\Omega}\mathrm{Sat}(x,y).
$$

Une saturation élevée favorise des choix musicaux plus brillants ou plus colorés. Une saturation faible favorise des choix plus doux ou plus neutres.

### 8.2 Moyenne circulaire de la teinte

La teinte est circulaire. Une moyenne arithmétique directe est incorrecte, car les valeurs de teinte proches de 0 et de 1 représentent des couleurs voisines, et non des couleurs opposées.

L'application calcule une moyenne circulaire pondérée. Soit $h(x,y)\in[0,1)$ la teinte. Chaque pixel reçoit le poids

$$
w(x,y)=\mathrm{Sat}(x,y)\left(0.25+Y(x,y)\right).
$$

La teinte dominante est

$$
\bar{h}=\frac{1}{2\pi}\operatorname{atan2}\left(
\sum w(x,y)\sin(2\pi h(x,y)),
\sum w(x,y)\cos(2\pi h(x,y))
\right) \bmod 1.
$$

Les pixels saturés et lumineux contribuent plus fortement au centre tonal.

### 8.3 Chaleur chromatique

Le score de chaleur est

$$
w_{\mathrm{warm}}=\frac{1}{HW}\sum_{(x,y)\in\Omega}\left(R(x,y)-B(x,y)\right).
$$

Les valeurs positives indiquent une image plus chaude. Les valeurs négatives indiquent une image plus froide. Cette grandeur influence la tendance de gamme et l'affinité instrumentale.

---

## 9. Analyse de Fourier de l'image

L'analyse de Fourier décrit la manière dont l'énergie de l'image de luminance est distribuée selon les fréquences spatiales.

Les basses fréquences spatiales correspondent aux grandes structures lisses. Les hautes fréquences spatiales correspondent aux détails fins, aux contours, aux textures et au bruit.

### 9.1 Luminance fenêtrée

Avant le calcul de la FFT, la luminance moyenne est retirée et une fenêtre de Hann séparable est appliquée :

$$
\tilde{Y}(x,y)=\left(Y(x,y)-\mu_Y\right)w_H(x)w_H(y),
$$

avec

$$
w_H(n)=0.5-0.5\cos\left(\frac{2\pi n}{N-1}\right).
$$

La fenêtre réduit les discontinuités aux bords. Sans cette étape, la FFT traiterait implicitement l'image comme une tuile périodique et introduirait du contenu fréquentiel artificiel aux frontières.

### 9.2 Transformée de Fourier bidimensionnelle

La transformée de Fourier discrète bidimensionnelle est

$$
F(u,v)=\sum_{x=0}^{W-1}\sum_{y=0}^{H-1}\tilde{Y}(x,y)
\exp\left[-j2\pi\left(\frac{ux}{W}+\frac{vy}{H}\right)\right].
$$

Le spectre affiché utilise le logarithme de la magnitude

$$
M_{\log}(u,v)=\log\left(1+|F(u,v)|\right),
$$

puis le normalise dans $[0,1]$ pour la visualisation. Le logarithme est nécessaire parce que les magnitudes de Fourier ont souvent une grande plage dynamique.

### 9.3 Fréquence radiale

Pour chaque bin fréquentiel, la fréquence radiale normalisée est

$$
r(u,v)=\frac{\sqrt{u^2+v^2}}{\max\sqrt{u^2+v^2}}.
$$

La région DC centrale est exclue des calculs d'énergie par bande, car elle contient surtout la composante moyenne, et non la structure spatiale.

### 9.4 Énergies basse, moyenne et haute fréquence

Le spectre est divisé en bandes radiales :

| Bande | Plage typique | Interprétation |
|---|---|---|
| Basse | $[r_{DC},0.14)$ | grandes structures lisses |
| Moyenne | $[0.14,0.34)$ | formes de taille intermédiaire |
| Haute | $[0.34,1]$ | contours, textures fines, micro-détails |

Pour une bande $\mathcal{B}$, l'énergie normalisée est

$$
E_{\mathcal{B}}=
\frac{\sum_{(u,v)\in\mathcal{B}}|F(u,v)|^2}
{\sum_{r(u,v)\ge r_{DC}}|F(u,v)|^2+\varepsilon}.
$$

Les trois proportions vérifient approximativement

$$
E_{\mathrm{low}}+E_{\mathrm{mid}}+E_{\mathrm{high}}\approx 1.
$$

L'énergie basse fréquence favorise les couches soutenues comme le pad et la basse. L'énergie haute fréquence augmente la texture, les attaques, les timbres brillants et parfois le tempo.

### 9.5 Centroïde et largeur de bande de Fourier

Le centroïde radial est

$$
\rho_c=\frac{\sum r(u,v)|F(u,v)|^2}{\sum |F(u,v)|^2+\varepsilon}.
$$

La largeur de bande radiale est

$$
B_F=\sqrt{\frac{\sum \left(r(u,v)-\rho_c\right)^2|F(u,v)|^2}{\sum |F(u,v)|^2+\varepsilon}}.
$$

Un centroïde élevé signifie que l'image contient de nombreuses structures fines. Une largeur de bande élevée signifie que l'énergie est répartie sur plusieurs échelles spatiales.

### 9.6 Énergies directionnelles

L'angle d'un bin fréquentiel est

$$
\theta(u,v)=\operatorname{atan2}(v,u).
$$

Avec une tolérance d'orientation $\omega_o$, les énergies directionnelles horizontale et verticale sont estimées par

$$
E_{\mathrm{horizontal}}=
\frac{\sum_{|\sin\theta|<\omega_o}|F|^2}{\sum |F|^2+\varepsilon},
$$

$$
E_{\mathrm{vertical}}=
\frac{\sum_{|\cos\theta|<\omega_o}|F|^2}{\sum |F|^2+\varepsilon}.
$$

Le résidu diagonal est

$$
E_{\mathrm{diagonal}}=1-E_{\mathrm{horizontal}}-E_{\mathrm{vertical}}.
$$

Ces descripteurs aident à interpréter le panneau d'analyse photo. Ils sont moins centraux que les énergies radiales par bande pour le mapping musical.

### 9.7 Score de pic périodique

Les motifs visuels répétés produisent des pics isolés et forts dans le spectre de Fourier. L'application résume cette propriété par un rapport de percentiles :

$$
P_F=\operatorname{clip}\left(
\frac{\log\left(1+\dfrac{P_{p_H}(|F|^2)}{P_{p_L}(|F|^2)+\varepsilon}\right)}{d_F},0,1
\right).
$$

Une valeur élevée indique un motif régulier, par exemple des rayures, des carreaux, des fenêtres ou une texture répétée. Musicalement, elle favorise un comportement de boucle, des motifs répétés et des timbres de type maillet.

---

## 10. Saillance visuelle

La saillance estime quelles régions de l'image sont visuellement dominantes. Dans cette application, la saillance n'est pas sémantique. Elle est calculée à partir de l'intensité des contours, de la rareté de couleur, de la rareté de luminance et d'un léger biais central.

### 10.1 Rareté de couleur

Soit le vecteur RGB moyen

$$
\bar{\mathbf{c}}=(\bar{R},\bar{G},\bar{B}).
$$

La rareté de couleur est

$$
C_r(x,y)=\left\|\begin{bmatrix}R(x,y)\\G(x,y)\\B(x,y)\end{bmatrix}
-\bar{\mathbf{c}}\right\|_2.
$$

Un pixel est saillant par sa couleur si sa couleur diffère fortement de la moyenne globale.

### 10.2 Rareté de luminance

La rareté de luminance est

$$
L_r(x,y)=|Y(x,y)-\mu_Y|.
$$

Les pixels très lumineux comme les pixels très sombres peuvent être saillants lorsqu'ils sont inhabituels par rapport à l'ensemble de l'image.

### 10.3 Combinaison de la saillance

L'application normalise les cartes de contours, de rareté de couleur et de rareté de luminance. La saillance de base est

$$
B_s(x,y)=w_e\hat{G}(x,y)+w_c\hat{C}_r(x,y)+w_l\hat{L}_r(x,y),
$$

où les poids sont normalisés en interne afin que

$$
w_e+w_c+w_l=1.
$$

Un biais central est ajouté :

$$
C_B(x,y)=1-\left\|\begin{bmatrix}
\dfrac{x}{W-1}-0.5\\[3pt]
\dfrac{y}{H-1}-0.5
\end{bmatrix}\right\|_2.
$$

La carte de saillance finale est

$$
\mathcal{S}(x,y)=\operatorname{normalize}_{[0,1]}\left((1-\lambda_c)B_s(x,y)+\lambda_cC_B(x,y)\right).
$$

Le biais central est volontairement faible. Il reflète la tendance photographique courante à placer les sujets près du centre, sans effacer la structure réelle de l'image.

### 10.4 Masque de saillance

Un masque saillant est défini par

$$
\mathcal{M}_{\mathcal{S}}=
\left\{(x,y):\mathcal{S}(x,y)\ge\max\left(\tau_{\mathcal{S}},P_{q_{\mathcal{S}}}(\mathcal{S})\right)\right\}.
$$

À partir de ce masque, l'application calcule le pic de saillance, la saillance moyenne, l'aire de saillance, le centroïde de saillance et l'étalement de la saillance. Ces descripteurs pilotent la couche Solo.

---

## 11. Vecteur de descripteurs

Après analyse, l'application peut être comprise comme ayant construit le vecteur de descripteurs

$$
\mathbf{f}=\left[
\mu_Y,\sigma_Y,D_Y,s,h,D_e,H_{\mathrm{tex}},S,
\bar{h},\overline{\mathrm{Sat}},w_{\mathrm{warm}},
E_{\mathrm{low}},E_{\mathrm{mid}},E_{\mathrm{high}},\rho_c,B_F,P_F,
\eta_{\mathcal{S}},c_x^{\mathcal{S}},c_y^{\mathcal{S}}
\right].
$$

Ici, $\eta_{\mathcal{S}}$ désigne un score compact de force de saillance, et $(c_x^{\mathcal{S}},c_y^{\mathcal{S}})$ désigne le centroïde de saillance.

Le reste de l'application est une fonction déterministe de ce vecteur et des paramètres utilisateur :

$$
\mathcal{E}=\Phi(\mathbf{f},\mathbf{p}),
$$

où $\mathbf{p}$ représente les paramètres contrôlés par l'utilisateur, comme le mode de tempo, le mode de gamme, le nombre de mesures, la complexité, la force de variation, le mode d'instrumentation et les gains de couches.

---

## 12. Des descripteurs d'image aux décisions musicales

Le tableau suivant donne le mapping pratique utilisé pour interpréter la sortie.

| Descripteur | Conséquence musicale |
|---|---|
| $\mu_Y$ | registre, déplacement de fondamentale, tendance clair/sombre |
| $\sigma_Y$ | énergie, vélocité, contribution au tempo |
| $s$ | force de la basse, timbres plus sombres, réduction du tempo |
| $h$ | timbres brillants, accents, activité des accords |
| $D_e$ | densité rythmique, attaques, contribution au tempo |
| $H_{\mathrm{tex}}$ | complexité automatique et estimation du nombre de mesures |
| $S$ | contrôle inverse de la force de variation |
| $\bar{h}$ | centre tonal |
| $\overline{\mathrm{Sat}}$ | couleur des gammes et des instruments |
| $w_{\mathrm{warm}}$ | tendance chaud/froid |
| $E_{\mathrm{low}}$ | poids du pad, poids de la basse, timbres lisses |
| $E_{\mathrm{high}}$ | activité de texture, instruments brillants, événements rapides |
| $\rho_c$ | contribution des détails fins au tempo Scientific |
| $B_F$ | richesse de la texture |
| $P_F$ | motifs répétitifs et affinité avec les timbres de type maillet |
| pic et aire de saillance | nombre et force des accents solo |
| position de saillance | timing et hauteur des accents solo |
| centroïde lumineux | panoramique stéréo des couches main et chord |
| centroïde d'ombre | panoramique stéréo de la couche bass |

Ce tableau doit être lu comme une carte causale interne à l'application. Par exemple, si la sortie est rapide et dense, les causes probables sont une densité de contours élevée, une forte énergie haute fréquence et une entropie de texture élevée. Si la sortie est lente et lourde, les causes probables sont une forte proportion d'ombre, une faible énergie haute fréquence et un contenu basse fréquence important.

---

## 13. Structure automatique : complexité, variation et nombre de mesures

### 13.1 Complexité automatique

La complexité automatique est dérivée de l'entropie de texture :

$$
C_{\mathrm{auto}}=C_{\min}+(C_{\max}-C_{\min})H_{\mathrm{tex}}.
$$

L'utilisateur contrôle la plage autorisée. La complexité obtenue affecte la densité de notes, l'activité mélodique et l'activation de la texture.

### 13.2 Force de variation automatique

La variation est dérivée du manque de symétrie :

$$
V_{\mathrm{auto}}=V_{\min}+(V_{\max}-V_{\min})(1-S).
$$

Une image symétrique donne une force de variation plus faible. Une image asymétrique donne une force de variation plus élevée. Cette règle est musicalement utile, car la symétrie correspond souvent à la stabilité, tandis que l'asymétrie suggère souvent un mouvement ou une tension.

### 13.3 Nombre de mesures

Le nombre de mesures est estimé à partir d'un score d'activité pondéré :

$$
Q_B=w_tH_{\mathrm{tex}}+w_eD_e+w_hE_{\mathrm{high}}+w_pP_F.
$$

Les poids sont normalisés en interne. Une valeur plus élevée de $Q_B$ correspond à une activité visuelle plus forte et autorise donc une composition plus longue.

L'application projette $Q_B$ vers des plages valides :

$$
B_{\min}=\operatorname{round}\left(\operatorname{interp}\left(Q_B,[0,1],[B_{\min}^{lo},B_{\min}^{hi}]\right)\right),
$$

$$
B_{\max}=\operatorname{round}\left(\operatorname{interp}\left(Q_B,[0,1],[B_{\max}^{lo},B_{\max}^{hi}]\right)\right),
$$

$$
B_0=\operatorname{round}\left(\operatorname{interp}\left(Q_B,[0,1],[B_0^{lo},B_0^{hi}]\right)\right).
$$

Le backend impose

$$
B_{\max}>B_{\min},
\qquad
B_0\in[B_{\min},B_{\max}].
$$

---

## 14. Tonalité, gamme et tempo

### 14.1 Tonalité à partir de la teinte

La teinte dominante est associée à l'une des douze classes de hauteur :

$$
k=\operatorname{round}(12\bar{h})\bmod 12.
$$

L'ensemble des classes de hauteur est

$$
\{C,C\#,D,D\#,E,F,F\#,G,G\#,A,A\#,B\}.
$$

La note fondamentale MIDI est décalée selon la luminosité :

$$
\mathrm{root}=\operatorname{clip}\left(
48+k+\operatorname{round}\left(\operatorname{interp}(\mu_Y,[0,1],[-5,7])\right),
38,58
\right).
$$

Les images sombres tendent à utiliser des registres plus graves. Les images lumineuses tendent à utiliser des registres plus aigus.

### 14.2 Sélection de la gamme

L'application utilise les familles de gammes suivantes.

| Gamme | Intervalles en demi-tons |
|---|---|
| Pentatonique majeure | $0,2,4,7,9$ |
| Pentatonique mineure | $0,3,5,7,10$ |
| Majeure | $0,2,4,5,7,9,11$ |
| Mineure naturelle | $0,2,3,5,7,8,10$ |
| Dorienne | $0,2,3,5,7,9,10$ |
| Lydienne | $0,2,4,6,7,9,11$ |

Lorsque Scale est réglé sur Automatic, la sélection dépend de la luminosité, de la chaleur chromatique, de la saturation et du contraste. Les images lumineuses et chaudes tendent vers des couleurs majeures ou lydiennes. Les images plus sombres tendent vers des couleurs mineures naturelles ou doriennes.

Cette règle doit être comprise comme un choix de conception, et non comme une théorie universelle des relations entre couleur et harmonie.

### 14.3 Modes de tempo

L'application propose quatre modes de tempo.

Le mode Scientific donne un poids fort aux descripteurs structurels :

$$
T=\operatorname{clip}\left(
50+70D_e+58\sigma_Y+42P_F+34E_{\mathrm{high}}+22\rho_c-20s,
T_{lo},T_{hi}
\right).
$$

Le mode Balanced réduit l'influence des descripteurs :

$$
T=\operatorname{clip}\left(
62+38D_e+28\sigma_Y+20P_F+10E_{\mathrm{high}}-8s,
T_{lo},T_{hi}
\right).
$$

Le mode Musical est plus doux et principalement lié à la couleur :

$$
T=\operatorname{clip}\left(
82+10\overline{\mathrm{Sat}}+8\mu_Y-6s+4w_{\mathrm{warm}},
T_{lo},T_{hi}
\right).
$$

Le mode Manual utilise le BPM choisi par l'utilisateur.

La durée d'un temps est

$$
\Delta t=\frac{60}{T}.
$$

Pour une composition en $4/4$ avec $B_{\mathrm{bars}}$ mesures, la durée approximative est

$$
T_{\mathrm{dur}}=4B_{\mathrm{bars}}\Delta t.
$$

---

## 15. Harmonie et progression d'accords

Soit la gamme sélectionnée

$$
I=[i_0,i_1,\ldots,i_{n-1}],
$$

où $i_j$ est un intervalle en demi-tons par rapport à la fondamentale.

Un accord de trois sons sur le degré $d$ est construit en empilant un degré sur deux :

$$
\operatorname{chord}(d)=\{i_d,i_{d+2},i_{d+4}\},
$$

avec un retour d'octave lorsqu'un indice dépasse la longueur de la gamme.

L'application sélectionne une progression d'accords dans un petit ensemble déterministe. Pour les gammes à sept notes, on trouve par exemple

$$
[0,4,5,3],\qquad [0,5,3,4],\qquad [0,2,5,4],\qquad [0,3,1,4].
$$

La progression sélectionnée dépend des descripteurs de l'image au moyen d'une seed déterministe :

$$
\mathrm{seed}=\operatorname{round}\left(997\bar{h}+113P_F+71H_{\mathrm{tex}}+53c_x^{\mathcal{S}}\right).
$$

Si la force de variation est suffisamment élevée, la seconde moitié de la composition décale l'indice de progression. Cela crée une forme A/B simple : la première moitié établit la boucle, et la seconde la déplace légèrement.

---

## 16. Couches musicales

### 16.1 Mélodie principale

L'image est lue de gauche à droite. Pour $B_{\mathrm{bars}}$ mesures, l'image est divisée en

$$
N_{\mathrm{slices}}=8B_{\mathrm{bars}}
$$

tranches verticales.

Pour la tranche $i$, l'application calcule des statistiques locales de luminance et un centroïde vertical de luminosité. Un poids tronqué par percentile est utilisé :

$$
w_i(y)=\max\left(Y_i(y)-P_{35}(Y_i),0\right).
$$

La position mélodique normalisée est

$$
\operatorname{pos}_i=\operatorname{clip}\left(1-c_{y,i}+0.18(\bar{Y}_i-\mu_Y),0,1\right).
$$

Une région lumineuse située en haut donne une hauteur plus élevée. Une région sombre située en bas donne une hauteur plus basse. La position sélectionnée est quantifiée dans la gamme courante.

La densité mélodique dépend de Complexity. Les réglages de faible complexité sautent davantage de tranches. Les réglages de forte complexité autorisent davantage de tranches à produire des notes.

### 16.2 Variation mélodique

La composition est divisée en grandes sections. Un décalage dépendant de la section est appliqué à la mélodie :

$$
\Delta m\in\{0,2,-2,5\}.
$$

La hauteur finale est

$$
m_{\mathrm{final}}=m_{\mathrm{base}}+\operatorname{round}(V\Delta m),
$$

où $V$ est la force de variation.

Cela permet de garder la mélodie liée à l'image tout en évitant une répétition strictement mécanique.

### 16.3 Couche Pad

La couche Pad soutient l'accord courant sur la mesure. Sa vélocité augmente avec l'énergie basse fréquence :

$$
v_{\mathrm{pad}}=\operatorname{clip}\left(0.07+0.18E_{\mathrm{low}}+0.04(1-E_{\mathrm{high}}),0.04,0.28\right).
$$

Une image lisse crée donc un fond soutenu plus fort.

### 16.4 Couche Chord

La couche Chord joue des impacts harmoniques basés sur la progression d'accords courante. Si l'énergie haute fréquence dépasse le seuil de double impact, un second accord est ajouté à mi-mesure.

Cela relie le détail visuel à l'activité harmonique.

### 16.5 Couche Bass

La couche Bass utilise un motif fondamentale/quinte, en plaçant généralement la fondamentale sur le premier temps et la quinte sur le troisième temps.

Sa vélocité est

$$
v_{\mathrm{bass}}=\operatorname{clip}\left(0.30+0.55s+0.25E_{\mathrm{low}},0.22,0.86\right).
$$

Les images sombres et lisses produisent donc un support de basse plus marqué.

### 16.6 Couche Texture

La densité de texture est estimée par

$$
\rho_{\mathrm{tex}}=\operatorname{clip}\left(0.20+0.80C+0.75E_{\mathrm{high}}+0.45B_F,0,1\right),
$$

où $C$ est la complexité contrôlée par l'utilisateur.

Si $\rho_{\mathrm{tex}}$ dépasse le seuil d'activation de texture, l'application ajoute des événements de type arpège. Si elle dépasse un seuil rapide, le débit d'arpège augmente.

Une couche de ticks courts peut aussi s'activer lorsque la densité de texture est élevée. Dans l'export MIDI, ces événements sont placés sur le canal de percussion.

### 16.7 Couche solo pilotée par la saillance

La couche Solo est disponible en mode GeneralUser GS. Elle convertit des points saillants de l'image en accents mélodiques épars.

Un score de force de saillance est

$$
\eta=\operatorname{clip}\left(0.55\,\mathrm{peak}+0.25\,\mathrm{mean}+0.20(1-\mathrm{area}),0,1\right).
$$

Le nombre de notes solo est interpolé à partir d'une plage contrôlée par l'utilisateur et limité par un plafond.

Pour un point saillant sélectionné $(x_k,y_k)$, la position horizontale devient le temps :

$$
t_k=x_k^{\mathrm{norm}}T_{\mathrm{dur}}+0.10\Delta t\sin(1.7k).
$$

La position verticale devient la hauteur :

$$
m_k=\mathrm{melody\_notes}\left[\operatorname{round}\left((1-y_k^{\mathrm{norm}})(N_{\mathrm{mel}}-1)\right)\right]+12.
$$

Le solo est donc une lecture mélodique éparse des régions les plus visuellement dominantes.

---

## 17. Sélection des instruments

### 17.1 Mode de synthèse Simple

Le mode Simple utilise des instruments internes de synthèse additive. Les exemples typiques incluent soft piano, harp, music box, bright bell, marimba, cello-like bass, warm pad et glass pad.

Ce mode est autonome. Il ne nécessite pas de SoundFont externe.

En mode Automatic, l'application sélectionne les instruments à partir des descripteurs de l'image. Exemples :

| Condition visuelle | Tendance instrumentale |
|---|---|
| image lumineuse avec hautes lumières | bell, celesta, music box |
| image périodique | kalimba, marimba, timbres de type maillet |
| image sombre et lisse | cello-like bass, bowed string, warm pad |
| image lisse à basse fréquence | pad, glass pad, soft piano |
| image détaillée à haute fréquence | pluck, bell, timbres arpégés |

### 17.2 Mode GeneralUser GS

Le mode GeneralUser GS utilise des noms de programmes General MIDI. Le rendu nécessite FluidSynth et une SoundFont GeneralUser GS. S'ils ne sont pas disponibles, l'application revient au backend de synthèse Simple tout en conservant la même structure d'événements musicaux.

Chaque programme General MIDI appartient à une famille : piano, chromatic percussion, organ, guitar, bass, strings, brass, reed, pipe, synth lead, synth pad et autres.

Pour chaque couche, l'application calcule des affinités de familles à partir des descripteurs de l'image. Par exemple, le score de lissage est

$$
\lambda_{\mathrm{smooth}}=\operatorname{clip}\left(E_{\mathrm{low}}+0.35(1-E_{\mathrm{high}})+0.25S,0,1\right).
$$

Le score de brillance est

$$
\lambda_{\mathrm{bright}}=\operatorname{clip}\left(0.55\mu_Y+0.45h,0,1\right).
$$

Pour la couche Main, une affinité avec la famille piano peut s'écrire

$$
W_{\mathrm{main}}(\mathrm{piano})=0.35+0.35\lambda_{\mathrm{smooth}}.
$$

Une affinité avec la famille pipe peut s'écrire

$$
W_{\mathrm{main}}(\mathrm{pipe})=0.18+0.45\lambda_{\mathrm{bright}}+0.20\lambda_{\mathrm{smooth}}.
$$

Des bonus propres à certains programmes affinent la sélection. Par exemple, les programmes de type cloche reçoivent des bonus provenant des hautes lumières, de l'énergie haute fréquence et de la saillance. Les programmes de basse reçoivent des bonus provenant des ombres et de l'énergie basse fréquence.

Un jitter déterministe est ajouté pour éviter de toujours sélectionner le même programme pour des images similaires :

$$
\operatorname{score}(p,\ell)=W_\ell(f_p)+\operatorname{bonus}(p)+0.42u(p,\ell),
$$

où $p$ est le programme, $\ell$ est la couche, $f_p$ est la famille du programme, et $u(p,\ell)$ est une valeur pseudo-aléatoire déterministe dérivée des descripteurs de l'image.

Cela donne de la variété sans perdre la reproductibilité.

### 17.3 Mode Manual et gains de couches

En mode Manual, l'utilisateur sélectionne l'instrument de chaque couche.

Chaque couche possède aussi un gain en décibels. Le multiplicateur d'amplitude est

$$
g=10^{G_{\mathrm{dB}}/20}.
$$

Le gain modifie la vélocité des notes avant le rendu. Les vélocités finales sont limitées à $[0,1]$.

---

## 18. Rendu audio

### 18.1 Buffer stéréo

Les événements sont rendus dans une waveform stéréo à

$$
f_s=44100\ \mathrm{Hz}.
$$

Pour un événement commençant au temps $t_i$, le premier indice d'échantillon est

$$
n_i=\operatorname{round}(t_if_s).
$$

La waveform de l'événement est synthétisée, multipliée par sa vélocité, panoramiquée, puis ajoutée au buffer stéréo.

### 18.2 Panoramique à puissance constante

Chaque événement possède une valeur de pan

$$
p\in[-1,1].
$$

Les gains stéréo sont

$$
g_L=\cos\left(\frac{\pi}{4}(p+1)\right),
\qquad
 g_R=\sin\left(\frac{\pi}{4}(p+1)\right).
$$

Il s'agit d'un panoramique à puissance constante. Il réduit la perte de niveau perçu qui apparaîtrait au centre avec un panoramique linéaire.

### 18.3 Enveloppe ADSR

Les instruments de synthèse Simple utilisent une enveloppe Attack-Decay-Sustain-Release :

$$
e[n]=
\begin{cases}
\dfrac{n}{N_A}, & 0\le n<N_A,\\[6pt]
1-(1-S_L)\dfrac{n-N_A}{N_D}, & N_A\le n<N_A+N_D,\\[6pt]
S_L, & N_A+N_D\le n<N-N_R,\\[6pt]
S_L\left(1-\dfrac{n-(N-N_R)}{N_R}\right), & N-N_R\le n<N.
\end{cases}
$$

Ici, $N_A$, $N_D$ et $N_R$ sont les longueurs d'attaque, de décroissance et de relâchement en échantillons, et $S_L$ est le niveau de sustain.

### 18.4 Synthèse additive

En mode Simple, de nombreux instruments sont construits en sommant des partiels :

$$
x[n]=e[n]\sum_{q=1}^{Q}a_q\sin\left(2\pi q f_0\frac{n}{f_s}+\phi_q\right),
$$

où $f_0$ est la fréquence de la note, $a_q$ est l'amplitude du partiel $q$, et $\phi_q$ est sa phase.

Les différents instruments correspondent à différents poids de partiels, enveloppes, règles de désaccordage et composantes de bruit.

### 18.5 Hauteur MIDI vers fréquence

Une hauteur MIDI $m$ est convertie en fréquence par

$$
f(m)=440\cdot 2^{(m-69)/12}.
$$

Il s'agit de la convention standard du tempérament égal avec A4 à 440 Hz.

### 18.6 Bus master

Après sommation de toutes les couches, l'application applique un gain master et évite le clipping. Un limiteur typique peut être compris comme

$$
x_{\mathrm{out}}[n]=\frac{x[n]}{\max(1,\max_n |x[n]|)}.
$$

Le but n'est pas de masteriser la musique de manière professionnelle. Il s'agit de produire un fichier audio stable et lisible dans une application en ligne.

---

## 19. Sorties MIDI, MP3 et analyse

L'application peut exporter le résultat en audio et en MIDI.

La sortie audio est la waveform rendue. L'export MP3 est utile pour une écoute rapide et le partage. L'export MIDI est utile pour l'inspection, l'édition et la réutilisation dans une station audionumérique.

Les graphiques d'analyse incluent généralement :

| Graphique | Signification |
|---|---|
| waveform | amplitude dans le domaine temporel |
| spectrogramme | distribution temps-fréquence |
| magnitude de Fourier | contenu fréquentiel audio global |
| spectres par couche | contribution de chaque couche musicale |

Ces graphiques ne sont pas décoratifs. Ils permettent à l'utilisateur de vérifier si le son généré correspond à la structure attendue. Par exemple, une couche de texture dense doit augmenter l'activité haute fréquence, tandis qu'une couche de basse forte doit apparaître dans les basses fréquences.

---

## 20. Random Factor

Le Random factor introduit des perturbations contrôlées avant le mapping musical. Il est conçu pour créer de la variation tout en conservant l'identité principale de l'image.

Soit $\alpha\in[0,1]$ le facteur aléatoire normalisé. Une perturbation spatiale peut s'écrire

$$
Y_{\mathrm{sp}}(x,y)=\operatorname{clip}\left(Y(x,y)+\alpha\sigma_r\xi(x,y),0,1\right),
$$

où $\xi(x,y)$ est un champ aléatoire de moyenne nulle et $\sigma_r$ contrôle son intensité.

Une perturbation dans le domaine de Fourier peut s'écrire

$$
F_{\mathrm{rnd}}(u,v)=F(u,v)\left(1+\alpha\gamma(u,v)\right),
$$

où $\gamma(u,v)$ est une petite modulation aléatoire.

Le signal perturbé modifie la composition générée, mais l'analyse photo affichée peut toujours être calculée à partir de l'image originale afin de garder l'interprétation visuelle stable.

Lorsque Random factor vaut zéro, la reproductibilité est stricte. Lorsqu'il augmente, l'application devient plus exploratoire.

---

## 21. Référence des paramètres

| Groupe de paramètres | Paramètre | Effet |
|---|---|---|
| Analyse d'image | analysis size | contrôle la résolution d'extraction des descripteurs |
| Analyse d'image | luminance percentiles | définissent la plage dynamique robuste |
| Analyse d'image | shadow/highlight thresholds | contrôlent les masques sombre et lumineux |
| Analyse de contours | edge percentile | contrôle la détection adaptative des contours |
| Analyse de contours | edge minimum threshold | empêche un bruit faible de devenir un contour |
| Analyse de Fourier | low/mid/high band limits | définit les bandes de fréquence radiale |
| Analyse de Fourier | DC exclusion radius | retire la composante moyenne centrale |
| Analyse de Fourier | periodic peak percentiles | contrôle le descripteur de périodicité |
| Saillance | edge/color/luminance weights | contrôlent la composition de la saillance |
| Saillance | center bias | contrôle la préférence pour les régions centrales |
| Musique | tempo mode | Scientific, Balanced, Musical ou Manual |
| Musique | scale mode | gamme automatique ou fixe |
| Musique | number of bars | contrôle la longueur de la composition |
| Musique | complexity | contrôle la densité de notes et la texture |
| Musique | variation strength | contrôle les changements de sections |
| Instruments | mode | Simple, GeneralUser GS ou Manual |
| Instruments | layer gains | contrôlent les amplitudes relatives des couches |
| Sortie | master gain | contrôle le niveau sonore final |
| Sortie | Random factor | contrôle la variation stochastique |

Une règle utile pour régler les paramètres est de ne modifier qu'un seul groupe à la fois. Si l'objectif est de comprendre le mapping, commencez avec Random factor à zéro et les instruments automatiques activés.

---

## 22. Comment interpréter le résultat

L'application est plus facile à comprendre en lisant la sortie en trois passes.

Premièrement, inspectez les cartes d'analyse d'image. Une carte de luminance lisse et un spectre de Fourier concentré en basse fréquence doivent correspondre à un résultat plus lent et plus soutenu. Une carte de contours marquée et une forte énergie de Fourier haute fréquence doivent correspondre à davantage de texture et d'attaques.

Deuxièmement, inspectez le résumé musical. Vérifiez la tonalité, la gamme, le tempo, la complexité, la force de variation et les instruments sélectionnés. Ces valeurs constituent le pont entre les descripteurs visuels et l'audio final.

Troisièmement, écoutez en observant les graphiques audio. La waveform montre l'amplitude au cours du temps. Le spectrogramme montre l'évolution de l'énergie selon la fréquence. Les spectres par couche expliquent quelle couche contribue à quelle partie du son.

Si le résultat paraît surprenant, remontez aux descripteurs. Une image sombre peut générer des accents brillants si elle contient de petites hautes lumières. Une image simple peut générer de la variation si elle est fortement asymétrique. Une image calme peut produire un motif rythmique régulier si son spectre de Fourier contient des pics périodiques.

---

## 23. Limites

Photo Sonification est un système interprétable fondé sur des descripteurs, et non un modèle sémantique image-vers-musique.

Il ne comprend pas le sujet de la photo. Une montagne, un visage et un bâtiment peuvent produire des musiques similaires si leurs descripteurs de luminance, de texture, de couleur et de Fourier sont similaires.

Le mapping est conçu, et non appris. C'est une force pour la transparence et une limite pour l'universalité esthétique. Un autre concepteur pourrait choisir d'autres mappings et obtenir un autre comportement musical.

La relation entre couleur et harmonie n'est pas une loi physique. C'est une convention artistique contrôlée, implémentée par des règles déterministes.

Les descripteurs de Fourier capturent la structure spatiale globale. Ils ne représentent pas complètement la composition locale, les frontières d'objets ou la profondeur.

Le modèle de saillance est bas niveau. Il met en évidence le contraste, la rareté et la centralité, mais il ne sait pas ce qui est significatif pour un observateur humain au sens sémantique.

Le backend de synthèse est volontairement léger. Il convient à une application pédagogique en ligne, mais il ne remplace pas des outils professionnels de production musicale.

La meilleure manière de lire l'application n'est donc pas de la considérer comme un compositeur automatique, mais comme un instrument de traitement du signal : elle expose comment une structure visuelle mesurable peut être transformée en son.
