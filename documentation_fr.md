## Table des matières

1. [Vue d'ensemble : de la photo à la composition musicale](#1-vue-densemble--de-la-photo-à-la-composition-musicale)
2. [Représentation de l'image et analyse de luminance](#2-représentation-de-limage-et-analyse-de-luminance)
3. [Descripteurs spatiaux : contraste, contours, texture et symétrie](#3-descripteurs-spatiaux--contraste-contours-texture-et-symétrie)
4. [Descripteurs de Fourier de la photo](#4-descripteurs-de-fourier-de-la-photo)
5. [Trajectoire de palette de couleurs et diversité harmonique](#5-trajectoire-de-palette-de-couleurs-et-diversité-harmonique)
6. [Paramètres musicaux automatiques](#6-paramètres-musicaux-automatiques)
7. [Mélodie, accords et composition par couches](#7-mélodie-accords-et-composition-par-couches)
8. [Synthèse instrumentale sans modèles appris](#8-synthèse-instrumentale-sans-modèles-appris)
9. [Facteur aléatoire et perturbations contrôlées](#9-facteur-aléatoire-et-perturbations-contrôlées)
10. [Rendu audio, export MIDI et graphes d'analyse](#10-rendu-audio-export-midi-et-graphes-danalyse)
11. [Guide des paramètres](#11-guide-des-paramètres)
12. [Limites et interprétation](#12-limites-et-interprétation)

---

## 1. Vue d'ensemble : de la photo à la composition musicale

Cette application transforme une image fixe en une courte composition musicale en extrayant des descripteurs visuels déterministes de la photo et en les associant à des décisions musicales.

L'objectif n'est pas de classifier le contenu sémantique de l'image, ni d'utiliser un modèle appris pour deviner ce que l'image représente.
L'app utilise plutôt des outils classiques de traitement du signal et de l'image : analyse de luminance, gradients, contraste local, entropie de texture, symétrie, extraction de palette de couleurs dominante et analyse de Fourier bidimensionnelle.

Le pipeline général est :

$$
\text{photo} \rightarrow \text{descripteurs visuels} \rightarrow \text{paramètres musicaux} \rightarrow \text{événements de notes} \rightarrow \text{audio et MIDI}
$$

Le mapping est déterministe lorsque le facteur aléatoire vaut zéro : la même photo d'entrée et les mêmes paramètres produisent la même sortie musicale.
Cela rapproche l'app d'un système de sonification interprétable plutôt que d'un générateur musical aléatoire.

La composition est organisée en cinq couches musicales :

| Couche | Rôle |
|---|---|
| Main | contour mélodique principal |
| Texture | arpèges, hautes lumières et petits éléments rythmiques |
| Bass | fondation harmonique grave |
| Pad | sons longs, atmosphériques et soutenus |
| Chord | soutien harmonique et accents d'accords |

L'utilisateur peut laisser l'app choisir automatiquement les instruments à partir des caractéristiques de l'image, ou sélectionner manuellement les instruments et ajuster le gain de chaque couche en décibels.
Une image par défaut peut être chargée uniquement pour rendre l'app immédiatement testable ; l'utilisateur peut la remplacer par n'importe quelle photo chargée.

---

## 2. Représentation de l'image et analyse de luminance

L'image d'entrée est d'abord convertie en RGB, puis normalisée dans $[0,1]$.
Dans la version actuelle, l'analyse conserve la résolution originale de l'image, donc les descripteurs globaux sont calculés à partir de la taille de l'image chargée.
Ce choix préserve les détails fins de l'image, mais peut ralentir la première analyse pour les très grandes photos.

L'image de luminance est calculée à partir des canaux RGB avec une pondération perceptive :

$$
Y(x,y) = 0.2126 R(x,y) + 0.7152 G(x,y) + 0.0722 B(x,y)
$$

L'image de luminance est la représentation centrale utilisée pour la plupart des descripteurs structurels.
Elle est aussi affichée dans le panneau Photo analysis comme carte de luminance.

La luminosité globale est la luminance moyenne :

$$
\mu_Y = \frac{1}{HW}\sum_{x,y} Y(x,y)
$$

Le contraste est l'écart type de la luminance :

$$
\sigma_Y = \sqrt{\frac{1}{HW}\sum_{x,y}(Y(x,y)-\mu_Y)^2}
$$

La dynamique est estimée avec des percentiles robustes :

$$
D_Y = P_{95}(Y) - P_{5}(Y)
$$

Cela évite que la dynamique soit trop sensible à quelques pixels isolés.
L'app détecte aussi les zones d'ombre et de haute lumière à partir de seuils de luminance dérivés des percentiles bas et hauts.
La proportion d'ombres et la proportion de hautes lumières influencent l'ambiance musicale, le poids de la basse, les événements de texture et le choix automatique de l'échelle.

---

## 3. Descripteurs spatiaux : contraste, contours, texture et symétrie

### 3.1 Gradient et force de contour

Les contours sont extraits de l'image de luminance avec des gradients spatiaux.
Soient $\partial_x Y$ et $\partial_y Y$ les dérivées horizontale et verticale.
La magnitude de contour est :

$$
G(x,y) = \sqrt{(\partial_x Y(x,y))^2 + (\partial_y Y(x,y))^2}
$$

La carte de magnitude est normalisée dans $[0,1]$ et affichée comme carte de force de contour.
La densité de contours est la proportion de pixels dont la magnitude de gradient normalisée dépasse un seuil adaptatif.
Elle est utilisée musicalement pour contrôler l'activité rythmique, la netteté des attaques et le tempo.

### 3.2 Entropie de texture

L'app calcule une entropie de texture à partir de l'histogramme de la carte de contours normalisée.
Si $p_k$ désigne la probabilité du bin $k$ dans l'histogramme de contours, l'entropie normalisée est :

$$
H_{\text{tex}} = -\frac{1}{\log_2 K}\sum_{k=1}^{K} p_k \log_2(p_k)
$$

où $K$ est le nombre de bins de l'histogramme.
Une image lisse possède une faible entropie de texture, tandis qu'une image très irrégulière possède une entropie plus élevée.

La complexité de composition par défaut est calculée à partir de ce descripteur :

$$
C = \operatorname{clip}\left(0.25 + 0.65 H_{\text{tex}},\;0.25,\;0.90\right)
$$

Ainsi, les images plus texturées produisent naturellement une matière musicale plus dense.

### 3.3 Symétrie

L'app calcule la symétrie gauche-droite et haut-bas à partir de l'image de luminance :

$$
S_{LR} = 1 - \frac{1}{HW}\sum_{x,y}\left|Y(x,y)-Y(W-1-x,y)\right|
$$

$$
S_{TB} = 1 - \frac{1}{HW}\sum_{x,y}\left|Y(x,y)-Y(x,H-1-y)\right|
$$

Le score final de symétrie est :

$$
S = 0.70S_{LR} + 0.30S_{TB}
$$

La force de variation par défaut est ensuite :

$$
V = \operatorname{clip}\left(0.25 + 0.60(1-S),\;0.25,\;0.85\right)
$$

Une image symétrique tend donc à générer une composition stable et répétitive, tandis qu'une image asymétrique tend à générer une évolution musicale plus forte.

### 3.4 Orientation des gradients et accents spatiaux

L'app estime aussi si l'image contient principalement des structures de gradient horizontales, verticales ou diagonales.
Les structures horizontales tendent à favoriser des durées plus longues, proches d'un comportement legato.
Les structures verticales et diagonales tendent à favoriser des attaques plus nettes, des événements décalés et des textures plus articulées.

L'image est aussi divisée en quatre quadrants.
La luminosité moyenne de chaque quadrant est utilisée comme profil d'accentuation faible pour les frappes d'accords et les variations dynamiques à l'intérieur de chaque mesure.

---

## 4. Descripteurs de Fourier de la photo

### 4.1 Transformée de Fourier bidimensionnelle

L'image de luminance est analysée dans le domaine de Fourier.
Après soustraction de la luminance moyenne et application d'une fenêtre de Hanning séparable, la transformée de Fourier 2D centrée est calculée :

$$
F(u,v) = \mathcal{F}\left\{(Y(x,y)-\mu_Y)w(x,y)\right\}
$$

La carte de Fourier affichée est :

$$
\log(1+|F(u,v)|)
$$

normalisée pour la visualisation.
Le logarithme est nécessaire car le spectre de magnitude possède généralement une très grande dynamique.

### 4.2 Bandes de fréquences

Soit $r(u,v)$ la fréquence radiale normalisée, où $r=0$ correspond au centre du plan de Fourier et $r=1$ correspond à la fréquence radiale maximale disponible.
L'app sépare l'énergie de Fourier en trois bandes :

| Bande | Intervalle radial | Signification visuelle |
|---|---:|---|
| Basses fréquences | $0.025 \leq r < 0.14$ | grandes structures lisses et variations d'illumination |
| Moyennes fréquences | $0.14 \leq r < 0.34$ | formes et transitions d'échelle intermédiaire |
| Hautes fréquences | $r \geq 0.34$ | contours, détails fins, micro-textures et bruit |

L'énergie normalisée dans une bande $\mathcal{B}$ est :

$$
E_{\mathcal{B}} = \frac{\sum_{(u,v)\in\mathcal{B}} |F(u,v)|^2}{\sum_{(u,v)} |F(u,v)|^2}
$$

L'énergie basse fréquence influence les couches soutenues comme le pad et la basse.
L'énergie haute fréquence influence la densité des arpèges, la brillance des textures et l'activité rythmique.

### 4.3 Centroïde et largeur spectrale de Fourier

Le centroïde de Fourier est calculé par :

$$
\rho_c = \frac{\sum_{u,v} r(u,v)|F(u,v)|^2}{\sum_{u,v}|F(u,v)|^2}
$$

et la largeur spectrale de Fourier par :

$$
B = \sqrt{\frac{\sum_{u,v}(r(u,v)-\rho_c)^2|F(u,v)|^2}{\sum_{u,v}|F(u,v)|^2}}
$$

Le centroïde indique si l'énergie spectrale est concentrée près des basses ou des hautes fréquences spatiales.
La largeur spectrale mesure l'étalement du spectre.
Ces deux quantités participent au mapping musical, en particulier en mode Scientific.

### 4.4 Score de pic périodique

L'app estime un score de pic périodique à partir des percentiles élevés de la puissance de Fourier hors composante continue.
Une valeur élevée signifie que quelques fréquences dominent le spectre, ce qui correspond souvent à des motifs répétés, des grilles, des stries, des textures ou des structures périodiques.
Musicalement, cela encourage des motifs plus répétitifs et un comportement harmonique plus proche d'une boucle.

---

## 5. Trajectoire de palette de couleurs et diversité harmonique

Une teinte moyenne unique est souvent trop pauvre pour décrire une photo.
Par exemple, un coucher de soleil peut contenir de l'orange, du violet sombre, du bleu pâle et des hautes lumières blanches.
Réduire cela à une seule teinte supprimerait une grande partie de l'identité visuelle de l'image.

Pour cette raison, l'app extrait une palette de couleurs dominante avec une procédure de k-means déterministe dans un espace RGB-luminance.
La méthode est non apprise : aucun réseau de neurones ni modèle pré-entraîné n'est utilisé.

L'extraction de palette suit les étapes suivantes :

1. représenter chaque pixel par ses valeurs RGB et sa luminance ;
2. initialiser les centres de couleur de façon déterministe avec une règle de point le plus éloigné ;
3. exécuter un petit nombre d'itérations de k-means ;
4. affecter tous les pixels au cluster de couleur le plus proche ;
5. calculer la teinte, la saturation, la luminosité, le poids et le centroïde spatial de chaque cluster ;
6. ordonner les clusters de couleur significatifs de gauche à droite.

La palette ordonnée définit une trajectoire de couleurs :

$$
\mathcal{C}_1 \rightarrow \mathcal{C}_2 \rightarrow \cdots \rightarrow \mathcal{C}_K
$$

Cette trajectoire pilote la diversité de la progression d'accords.
Des régions de couleurs avec des teintes, luminosités ou saturations différentes produisent des degrés d'accords différents, des niveaux de tension différents et des comportements de cadence différents.

L'entropie de palette est calculée à partir des poids normalisés des clusters :

$$
H_{\text{pal}} = -\frac{1}{\log_2 K}\sum_{k=1}^{K} w_k\log_2(w_k)
$$

Une palette simple tend à générer des boucles harmoniques stables.
Une palette diversifiée tend à générer des progressions plus longues et plus variées.

L'app mesure aussi l'étalement des teintes et la tension de transition entre régions de palette consécutives.
De grandes distances de teinte et de forts sauts de luminosité tendent à créer un mouvement harmonique plus marqué, tandis que de petites transitions tendent à stabiliser la progression.

---

## 6. Paramètres musicaux automatiques

### 6.1 Centre tonal

Le centre tonal est dérivé de la teinte dominante.
L'angle de teinte est projeté sur les 12 classes chromatiques :

$$
\text{indice tonal} = \operatorname{round}(12h) \bmod 12
$$

où $h \in [0,1)$ est la teinte dominante.
Le résultat est associé aux noms chromatiques usuels :

$$
C, C\#, D, D\#, E, F, F\#, G, G\#, A, A\#, B
$$

Le registre de hauteur est ensuite déplacé selon la luminosité.
Les images sombres tendent à utiliser un registre plus grave, tandis que les images lumineuses tendent à utiliser un registre plus aigu.

### 6.2 Choix de l'échelle

Si le menu Scale est réglé sur Automatic, l'app choisit l'échelle à partir de la luminosité, de la chaleur, de la saturation et du contraste.
Les échelles disponibles sont :

| Échelle | Intervalles depuis la tonique |
|---|---|
| Major pentatonic | $0,2,4,7,9$ |
| Minor pentatonic | $0,3,5,7,10$ |
| Major | $0,2,4,5,7,9,11$ |
| Natural minor | $0,2,3,5,7,8,10$ |
| Dorian | $0,2,3,5,7,9,10$ |
| Lydian | $0,2,4,6,7,9,11$ |

Les images lumineuses et chaudes tendent à sélectionner des modes plus clairs.
Les images plus sombres tendent à sélectionner des modes plus sombres comme Natural minor.
L'utilisateur peut remplacer le choix automatique en sélectionnant manuellement une échelle.

### 6.3 Nombre de mesures

L'app n'utilise pas une durée cible exacte en secondes.
Elle génère plutôt une composition avec un nombre de mesures musicales.
Les limites automatiques et la valeur par défaut sont dérivées d'un score de complexité visuelle :

$$
B_s = 0.40H_{\text{tex}} + 0.25D_e + 0.20E_{\text{high}} + 0.15P
$$

où $H_{\text{tex}}$ est l'entropie de texture, $D_e$ la densité de contours, $E_{\text{high}}$ l'énergie de Fourier haute fréquence et $P$ le score de pic périodique.

Les réglages de nombre de mesures sont obtenus par interpolation :

$$
B_{\min} = \operatorname{round}\left(\operatorname{interp}(B_s,[0,1],[4,8])\right)
$$

$$
B_{\max} = \operatorname{round}\left(\operatorname{interp}(B_s,[0,1],[12,24])\right)
$$

$$
B_0 = \operatorname{round}\left(\operatorname{interp}(B_s,[0,1],[6,16])\right)
$$

Les images simples suggèrent donc des compositions plus courtes, tandis que les images détaillées suggèrent des structures plus longues.

### 6.4 Tempo

Le Mapping style contrôle la façon dont le tempo est déduit.
En mode Scientific, le tempo est fortement piloté par la densité de contours, le contraste, les pics de Fourier et l'énergie haute fréquence :

$$
T = 50 + 70D_e + 58\sigma_Y + 42P + 34E_{\text{high}} + 22\rho_c - 20S_h
$$

où $S_h$ est la proportion d'ombres.
Cette valeur est ensuite limitée à une plage musicalement exploitable.

Le mode Balanced utilise une version plus modérée du même principe.
Le mode Musical est plus doux et plus conservateur, en s'appuyant davantage sur la saturation, la luminosité, les ombres et la chaleur.
Le mode Manual permet à l'utilisateur de choisir directement le BPM.

---

## 7. Mélodie, accords et composition par couches

### 7.1 Progression d'accords

La progression d'accords est générée à partir de la tonalité, de l'échelle sélectionnée et de la trajectoire de palette de couleurs.
Pour une échelle donnée, l'app construit des triades en prenant un degré sur deux :

$$
\text{accord}(d) = \{s_d, s_{d+2}, s_{d+4}\}
$$

où $s_d$ désigne l'intervalle de l'échelle au degré $d$.

Le premier accord part du centre tonal, afin de donner à l'auditeur une référence harmonique claire.
Les accords suivants suivent le mouvement visuel de la couleur dans la photo.
Les différences de teinte, la saturation, les sauts de luminosité, les poids de palette, les ombres et les hautes lumières contribuent aux degrés d'accords sélectionnés.

### 7.2 Mélodie issue des tranches de luminance

L'image est divisée en tranches verticales.
Chaque tranche est résumée par sa luminance moyenne, son contraste local et son centroïde vertical de luminosité.
Cela crée un balayage visuel de gauche à droite de l'image.

Une région claire située haut dans l'image tend à produire des notes plus aiguës, tandis qu'une région plus sombre ou plus basse tend à produire des notes plus graves.
La hauteur mélodique est choisie parmi les notes disponibles de l'échelle sélectionnée.

La mélodie n'est donc pas une séquence aléatoire : elle est pilotée par la distribution spatiale de la luminosité dans la photo.

### 7.3 Variation musicale

La force de variation modifie la seconde partie de la composition en changeant les offsets mélodiques, l'indexation de progression d'accords et les durées locales des notes.
Ce n'est pas un bruit blanc.
C'est un paramètre d'évolution musicale structurée.

Une faible force de variation garde la composition stable et proche d'une boucle.
Une forte force de variation introduit des changements plus marqués dans la seconde moitié, des déviations mélodiques et un mouvement harmonique plus important.

### 7.4 Organisation des couches

Les événements de notes finaux sont associés à des couches :

| Couche | Contenu généré |
|---|---|
| Main | mélodie principale issue des tranches de luminance |
| Texture | arpèges, hautes lumières, petits ticks et détails haute fréquence |
| Bass | motifs de basse sur fondamentale, quinte et octave |
| Pad | tons d'accords soutenus issus des contenus lisses et basse fréquence |
| Chord | frappes harmoniques et soutien d'accords |

La sortie est donc une composition de complexité moyenne, et non une simple succession de notes isolées.

---

## 8. Synthèse instrumentale sans modèles appris

L'app n'utilise pas de soundfonts, de bibliothèques d'échantillons ou de modèles audio neuronaux.
Chaque instrument est synthétisé à partir de recettes acoustiques simples : harmoniques additives, partiels inharmoniques, vibrato, enveloppes ADSR et lois de décroissance.

Les instruments disponibles incluent :

| Instrument | Idée de synthèse |
|---|---|
| Soft piano | partiels harmoniques avec décroissance exponentielle |
| Music box | partiels inharmoniques brillants avec décroissance courte |
| Bright bell | spectre métallique inharmonique |
| Celesta | spectre de cloche brillant mais plus doux |
| Kalimba | spectre pincé inharmonique |
| Marimba | partiels boisés et percussifs |
| Harp | pincement harmonique avec décroissance douce |
| Synth pluck | forme d'onde riche en harmoniques avec décroissance rapide |
| Warm pad | attaque lente, couche harmonique soutenue et vibrato |
| Glass pad | pad soutenu plus lisse avec vibrato léger |
| Cello-like bass | registre grave frotté avec vibrato |
| Soft bass | fondation basse sinusoïdale |
| Bowed string | son harmonique soutenu de type corde |
| Flute-like lead | lead presque sinusoïdal avec vibrato |
| Clarinet-like reed | spectre de type anche riche en harmoniques impairs |

En mode Automatic, l'app choisit les instruments à partir des descripteurs de l'image.
Les images lumineuses et détaillées tendent à favoriser des instruments de type cloche.
Les images périodiques peuvent favoriser kalimba ou marimba.
Les images sombres ou riches en ombres tendent à renforcer les couches de type violoncelle ou basse.
Les images lisses et basse fréquence tendent à renforcer les couches de type pad.

En mode Manual, l'utilisateur peut choisir l'instrument de chaque couche et ajuster son gain.
Le gain en décibels est converti en facteur linéaire par :

$$
g = 10^{G_{\text{dB}}/20}
$$

et appliqué à la vélocité de tous les événements de notes de cette couche avant le rendu audio.

---

## 9. Facteur aléatoire et perturbations contrôlées

Le Random factor ne remplace pas le mapping photo-vers-musique par un hasard pur.
Il ajoute des perturbations contrôlées avant l'extraction des caractéristiques utilisées pour la génération.

Soit $r$ le Random factor dans $[0,100]$ et :

$$
\alpha = \frac{r}{100}
$$

La perturbation spatiale de l'image a pour écart type :

$$
\sigma_{\text{image}} = 0.045\alpha^2
$$

et elle est ajoutée aux valeurs RGB avant clipping dans $[0,1]$.
La perturbation dans le domaine de Fourier a pour écart type :

$$
\sigma_{\text{Fourier}} = 0.18\alpha^2
$$

et multiplie la magnitude de Fourier par une perturbation log-normale :

$$
|F'(u,v)| = |F(u,v)|\exp(\eta(u,v)), \qquad \eta(u,v) \sim \mathcal{N}(0,\sigma_{\text{Fourier}}^2)
$$

La loi quadratique rend les petites valeurs très douces, tandis que les valeurs élevées deviennent expérimentales.
Le panneau Photo analysis reste basé sur la photo originale, donc les cartes et métriques affichées ne sont pas visuellement polluées par la perturbation ajoutée.

---

## 10. Rendu audio, export MIDI et graphes d'analyse

Les événements de notes générés sont rendus sous forme d'onde stéréo à :

$$
f_s = 44100\text{ Hz}
$$

Chaque note possède une hauteur MIDI, une durée, une vélocité, un instrument, une position panoramique et un label de couche.
Le panoramique utilise une loi à puissance constante :

$$
L = \cos\left(\frac{\pi}{4}(p+1)\right), \qquad R = \sin\left(\frac{\pi}{4}(p+1)\right)
$$

où $p \in [-1,1]$ est la position panoramique.

L'app exporte :

| Sortie | Description |
|---|---|
| MP3 | fichier audio stéréo rendu |
| MIDI | représentation symbolique des événements de notes générés |

Le panneau Audio analysis affiche :

| Graphe | Signification |
|---|---|
| Full Fourier magnitude | spectre global de l'audio généré |
| Waveform | amplitude audio dans le domaine temporel |
| Main layer Fourier | spectre de la couche mélodique principale |
| Texture layer Fourier | spectre de la couche de texture |
| Bass layer Fourier | spectre de la couche de basse |
| Pad layer Fourier | spectre de la couche pad |
| Chord layer Fourier | spectre de la couche d'accords |

Ces graphes aident à distinguer ce qui est entendu globalement de ce que chaque couche musicale apporte spectralement.

---

## 11. Guide des paramètres

| Paramètre | Signification | Relation automatique avec l'image |
|---|---|---|
| Number of bars | longueur musicale de la composition | valeur par défaut et limites à partir de l'entropie de texture, des contours, de l'énergie de Fourier haute fréquence et de la périodicité |
| Variation strength | évolution structurée au cours de la composition | valeur par défaut issue de la symétrie de l'image |
| Composition complexity | densité des notes et des événements de texture | valeur par défaut issue de l'entropie de texture |
| Random factor | perturbation contrôlée des descripteurs d'image et de Fourier | uniquement contrôlé par l'utilisateur |
| Scale | ensemble des notes autorisées | mode automatique à partir de la luminosité, de la chaleur, de la saturation et du contraste |
| Mapping style (BPM) | comportement du mapping de tempo | Scientific, Balanced et Musical utilisent différentes formules image-vers-BPM |
| Instrument layer selection | timbres automatiques ou manuels des couches | mode automatique à partir de la luminosité, des ombres, des hautes lumières, des descripteurs de Fourier et des couleurs |
| Layer gain | volume manuel de chaque couche en dB | visible uniquement en mode Manual pour les instruments |

Le bouton Run est volontairement nécessaire.
Changer un paramètre ne régénère pas immédiatement l'audio.
Cela évite les recalculs coûteux et rend l'interaction plus contrôlée.

---

## 12. Limites et interprétation

L'app est conçue comme un système de sonification artistique et pédagogique.
Elle ne comprend pas le contenu sémantique d'une photo.
Par exemple, elle ne sait pas si l'image contient un visage, un paysage ou un objet.
Elle utilise uniquement des caractéristiques visuelles mesurables.

Ce choix est volontaire.
Le résultat reste interprétable du point de vue du traitement du signal : luminosité, contraste, contours, trajectoire de couleurs et énergie de Fourier ont tous des rôles explicites dans la musique générée.

L'utilisation de la résolution originale peut révéler des détails plus riches, mais elle peut aussi ralentir l'analyse sur de grandes photos.
Elle peut également rendre le mapping plus sensible au bruit de caméra, aux artefacts de compression et aux micro-textures.

Les instruments générés sont des approximations synthétiques basées sur des recettes harmoniques.
Ils ne visent pas à remplacer des soundfonts professionnels ou des instruments échantillonnés.
Leur objectif est de garder l'app légère, déterministe et entièrement explicable.
