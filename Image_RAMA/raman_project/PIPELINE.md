# 📊 Pipeline Complet d'Analyse Raman - Documentation

## 📋 Table des Matières
1. [Vue d'ensemble du projet](#vue-densemble)
2. [Architecture du pipeline](#architecture)
3. [Étapes détaillées](#étapes-détaillées)
4. [Fichiers de sortie](#fichiers-de-sortie)
5. [Guide d'utilisation](#guide-dutilisation)
6. [Résultats et interprétation](#résultats-et-interprétation)

---

## 🎯 Vue d'ensemble du projet

### Objectif
Analyser une image Raman pour **détecter, caractériser et interpréter** les particules selon leurs signatures **morphologiques** (taille, forme) et **optiques** (intensité Raman), puis sélectionner une **zone représentative** pour l'analyse statistique.

### Contexte
- **Domaine** : Spectroscopie Raman / Analyse d'image scientifique
- **Application** : Identification de particules, classification physico-réaliste, contrôle de procédés (ex. bain électrochimique)
- **Type de données** : Image microscopique en niveaux de gris (intensité Raman)
- **Format d'entrée** : JPG/PNG/TIF haute résolution
- **Approche** : Segmentation multi-critères + clustering non supervisé + classification rule-based + validation spatiale

### Pourquoi cette méthode ?
- **Raman** fournit une intensité corrélée à la nature chimique locale (carbone, substrat, transitions).
- **La morphologie** capture des mécanismes de dépôt (compact, poreux, anguleux).
- **Le clustering** révèle des groupes émergents sans imposer de classes a priori.
- **La zone représentative** limite le biais d'échantillonnage et permet des comparaisons robustes.

---

## 📚 Définitions clés

- **Circularity** : $4\pi\cdot \text{Area} / \text{Perimeter}^2$ (1 = cercle parfait).
- **Solidity** : $\text{Area} / \text{Area}_{\text{convex hull}}$ (proche de 1 = compact).
- **AspectRatio** : ratio longueur/largeur (forme allongée si élevé).
- **Intensity_Score** : intensité moyenne Raman d'une particule (proxy de composition).
- **Size_Score** : surface en pixels (proxy de taille).

Ces indicateurs sont standard en vision scientifique car ils sont **stables**, **interprétables** et **comparables** entre images.

---

## 🏗️ Architecture du Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  1. CHARGEMENT ET PRÉ-TRAITEMENT                            │
├─────────────────────────────────────────────────────────────┤
│  • Lecture image (RGB + niveaux de gris)                    │
│  • Évaluation qualité (contraste, netteté, SNR, entropie)   │
│  • Amélioration contraste (CLAHE)                           │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  2. SEGMENTATION PAR INTENSITÉ (3 TYPES)                    │
├─────────────────────────────────────────────────────────────┤
│  • Type 1 (Blanc) : intensité ≥ 170                         │
│  • Type 2 (Gris)  : 85 ≤ intensité < 170                   │
│  • Type 3 (Noir)  : intensité < 85                          │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  3. DÉTECTION DES PARTICULES                                │
├─────────────────────────────────────────────────────────────┤
│  • Morphologie mathématique (ouverture)                     │
│  • Détection des contours                                   │
│  • Extraction des caractéristiques pour chaque particule    │
│    → Area, Perimeter, Circularity, AspectRatio, Solidity   │
│    → MeanIntensity, Center (X,Y)                            │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  4. CLUSTERING COMBINÉ (TAILLE × FORME × INTENSITÉ)        │
├─────────────────────────────────────────────────────────────┤
│  • Normalisation StandardScaler                             │
│  • Pondération des paramètres                               │
│  • KMeans clustering (6-10 clusters)                        │
│  • Interprétation physique des clusters                     │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  5. CLUSTERING 3D NORMALISÉ                                 │
├─────────────────────────────────────────────────────────────┤
│  • Espace 3D : (Taille_Norm, Forme_Norm, Intensité_Norm)   │
│  • 7-10 clusters dans l'espace normalisé                    │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  6. CLASSIFICATION PHYSIQUE COMBINÉE                        │
├─────────────────────────────────────────────────────────────┤
│  • Règles basées sur les 3 paramètres                       │
│  • Types identifiés :                                       │
│    → Carbone_Amorphe_Fin                                    │
│    → Carbone_Cristallin_Dense                               │
│    → Agglomérat_Carbone                                     │
│    → Particule_Transition_*                                 │
│    → Dépôt_Poreux                                           │
│    → etc.                                                   │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  7. ANALYSE PCA 3D                                          │
├─────────────────────────────────────────────────────────────┤
│  • Réduction dimensionnelle (6D → 3D)                       │
│  • Variance expliquée par composante                        │
│  • Visualisations PCA 3D colorées par cluster/type          │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  8. IDENTIFICATION DE LA ZONE ÉQUILIBRÉE                    │
├─────────────────────────────────────────────────────────────┤
│  • Balayage systématique avec fenêtres carrées              │
│  • Critère : TOUS les clusters présents                     │
│  • Score : équilibre + similitude distribution globale      │
│  • Validation : affichage avec carré vert + distribution    │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  9. VISUALISATIONS ET RAPPORTS                              │
├─────────────────────────────────────────────────────────────┤
│  • Scatter plots multi-niveaux                              │
│  • Heat maps paramétriques                                  │
│  • Tableaux croisés et matrices de confusion                │
│  • Rapport statistique complet                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📍 Étapes Détaillées

### **ÉTAPE 1 : Chargement et Pré-traitement**

#### Objectif
- Charger l'image Raman
- Évaluer sa qualité
- Améliorer le contraste

**Pourquoi ?**
- Les images Raman présentent souvent une **variabilité d'intensité** et un **bruit de fond**.
- Les métriques de qualité (SNR, entropie, netteté) permettent de **documenter la fiabilité** des analyses.
- CLAHE améliore les contrastes locaux sans surexposer le bruit.

#### Processus
```python
1. Lecture image RGB et conversion en niveaux de gris
2. Calcul métriques qualité :
   - Contraste (std des intensités)
   - Plage dynamique (max - min)
   - Netteté (variance Laplacien)
   - SNR estimé (rapport signal/bruit)
   - Entropie (richesse information)
   - Coefficient de variation
3. Application CLAHE (Contrast Limited Adaptive Histogram Equalization)
   - Améliore localement le contraste
   - Évite sur-amplification du bruit
```

#### Sorties
- Image améliorée `gray_eq`
- Métriques qualité affichées

---

### **ÉTAPE 2 : Segmentation par Intensité (3 Types)**

#### Objectif
Diviser l'image en 3 zones selon l'intensité Raman

**Justification des seuils (85, 170)**
- Ces seuils séparent **zones sombres** (carbone/dépôts), **intermédiaires** (transitions) et **claires** (substrat/artefacts).
- Ils sont suffisamment robustes pour des images en 8 bits tout en restant ajustables selon l'instrumentation.

#### Seuils
- **Type 1 (Blanc)** : intensité ≥ 170 (régions claires/substrat)
- **Type 2 (Gris)** : 85 ≤ intensité < 170 (transitions/mélanges)
- **Type 3 (Noir)** : intensité < 85 (régions sombres/carbone)

#### Résultat
Trois masques binaires séparant l'image

---

### **ÉTAPE 3 : Détection des Particules**

#### Processus
1. **Nettoyage morphologique** : ouverture pour éliminer bruit
2. **Détection contours** : identifie les frontières des particules
3. **Filtrage** : exclut particules < 5 pixels²

**Pourquoi ces choix ?**
- L'ouverture supprime le bruit ponctuel sans déformer les particules.
- Le seuil d'aire évite d'intégrer des artefacts optiques ultra-petits.
- Les contours permettent d'extraire des métriques robustes (circularity, solidity).

#### Caractéristiques extraites par particule
| Paramètre | Signification |
|-----------|---------------|
| `Area_px2` | Surface en pixels² |
| `Perimeter_px` | Périmètre |
| `Circularity` | 4π·Area/Perimeter² (0=ligne, 1=cercle) |
| `AspectRatio` | Ratio longueur/largeur |
| `Solidity` | Area/ConvexHull_Area (compacité) |
| `MeanIntensity` | Intensité moyenne intra-particule |
| `Center_X, Center_Y` | Centroïde |

#### Résultat
DataFrame `df_particles` avec ~200-1000 particules selon image

---

### **ÉTAPE 4 : Clustering Combiné Multi-Paramètres**

#### Concept
Combiner **3 dimensions** : Taille × Forme × Intensité

**Pourquoi cette combinaison ?**
- La **taille** reflète la croissance des particules.
- La **forme** distingue dépôt compact, poreux ou anguleux.
- L'**intensité** est un proxy de composition (carbone vs substrat).

#### Paramètres utilisés
```
Features combinées :
- Size_Score = Area_px2
- Shape_Score = 0.4×Circularity + 0.4×Solidity + 0.2×(1/(1+AspectRatio))
- Intensity_Score = MeanIntensity

Pondération : [1.2, 1.0, 1.0, 1.0, 1.3] pour [Size, Circ, AR, Solid, Intensity]
```

#### Algorithme
1. Normalisation StandardScaler
2. Pondération manuelle
3. KMeans avec **6-10 clusters** (auto-sélection)
4. Interprétation physique basée sur moyennes des clusters

**Pourquoi KMeans ?**
- Rapide et stable sur de grands volumes de particules.
- Interprétable via les centroïdes moyens.
- Compatible avec une sélection automatique du nombre de clusters.

**Sélection automatique de $k$**
- Recherche dans une plage physiquement réaliste (6–10).
- Score combiné : **70% silhouette** (séparation) + **30% inertie normalisée** (compacité).
- Objectif : équilibre entre séparation des types et cohérence intra-cluster.

#### Résultat
Colonne `Cluster_Combined` : ID cluster pour chaque particule

---

### **ÉTAPE 5 : Clustering 3D Normalisé**

#### Concept
Réduire les 3 paramètres à l'espace [0,1] et reclustering

**Pourquoi une seconde vue ?**
- La normalisation supprime l'effet d'échelle entre taille et intensité.
- Elle permet de vérifier si la structure des clusters persiste sans pondération.

#### Espace 3D
```
X = [Size_Normalized, Shape_Normalized, Intensity_Normalized]
Size_Normalized = (Size - min_size) / (max_size - min_size)
Intensity_Normalized = MeanIntensity / 255
```

#### Résultat
Colonne `Cluster_3D` : clustering pur dans l'espace normalisé

---

### **ÉTAPE 6 : Classification Physique Combinée**

#### Logique
Classification hiérarchique basée sur intensité → taille → forme

**Pourquoi une classification rule-based ?**
- Donne des labels **interprétables** par un expert métier.
- Permet de **contraster** les clusters mathématiques avec des types physico-réalistes.
- Met en évidence des **types rares** souvent absorbés par le clustering.

```
IF intensité < 85 (Noir) :
    ├─ taille < 80 & circ > 0.7 → "Carbone_Amorphe_Fin"
    ├─ solidity > 0.85 & size > 200 → "Carbone_Cristallin_Dense"
    ├─ size > 500 → "Agglomérat_Carbone"
    └─ sinon → "Carbone_Dispersé"
    
ELSE IF 85 ≤ intensité < 170 (Gris) :
    ├─ taille < 100 & circ > 0.7 → "Particule_Transition_Ronde"
    ├─ taille < 100 & circ ≤ 0.7 → "Particule_Transition_Anguleuse"
    ├─ solidity < 0.7 → "Dépôt_Poreux"
    └─ sinon → "Mélange_Intermédiaire"
    
ELSE (intensité ≥ 170, Blanc) :
    ├─ taille < 50 → "Bruit_Optique"
    ├─ circ < 0.5 & size > 200 → "Substrat_Exposé"
    └─ sinon → "Particule_Claire"
```

#### Résultat
Colonne `Particle_Type_Combined` : label physique pour chaque particule

---

### **ÉTAPE 7 : Analyse PCA 3D**

#### Objectif
Réduire les 6 features à 3 composantes principales

**Pourquoi PCA ?**
- Résume l'information tout en conservant la variance dominante.
- Permet d'évaluer la séparabilité des clusters dans un espace visuel compact.

#### Features PCA
- Size_Score
- Circularity
- AspectRatio
- Solidity
- Intensity_Score
- Perimeter_px

#### Résultat
- PC1, PC2, PC3 (variance expliquée typiquement 70-85%)
- Visualisation 3D avec rotation/projection

---

### **ÉTAPE 8 : Identification de la Zone Équilibrée (NOUVELLE)**

#### 🎯 **Critère Principal : TOUS les clusters doivent être présents**

#### Algorithme
```
Pour chaque taille de fenêtre (300-800px) :
    Pour chaque position de balayage :
        1. Extraire particules dans fenêtre
        2. Vérifier : nombre_clusters_uniques == nombre_clusters_total
        3. SI OUI :
            a. Calculer distribution locale des clusters
            b. Distance Wasserstein vs distribution globale
            c. Équilibre (entropie normalisée)
            d. Minimum de particules par cluster
            e. Score combiné = 0.3×similarity + 0.5×balance + 0.2×min_count
        4. Conserver les meilleurs candidats
```

    **Pourquoi ces métriques ?**
    - **Wasserstein** compare les distributions de manière robuste aux classes rares.
    - **Entropie** favorise un mélange équilibré des types.
    - **Min_count** évite une zone dominée par un seul cluster.

#### Scores et Sélection
- **Meilleur score** : zone la plus représentative
- **Top 5 candidats** : affichés comme alternatives
- **Visualisation** : carré vert + histogramme distribution

#### Garanties
✅ Tous les clusters présents  
✅ Proportions proches de la distribution globale  
✅ Zone visuellement représentative  

---

### **ÉTAPE 9 : Visualisations et Rapports**

#### Sorties graphiques
1. **Vue d'ensemble** : image + segmentation + particules détectées
2. **Scatter plots** : Taille vs Forme, Intensité vs Forme, etc.
3. **Heat maps** : distribution spatiale intensité/densité
4. **Heatmaps paramétriques** : moyennes Cluster × Type
5. **Visualisation 3D** : clusters dans l'espace combiné
6. **Zone équilibrée** : carré vert + distribution par cluster
7. **Matrice de corrélation** : relations entre paramètres

**Pourquoi plusieurs visualisations ?**
- Chaque vue répond à une question scientifique différente (morphologie, composition, spatialité).
- La convergence de plusieurs indicateurs renforce la confiance dans l'interprétation.

#### Sorties de données (CSV)
Voir section [Fichiers de sortie](#fichiers-de-sortie)

---

## 📁 Fichiers de Sortie

### Fichiers CSV Générés

| Fichier | Contenu |
|---------|---------|
| `particles_by_intensity_types.csv` | Toutes les particules avec features |
| `cluster_combined_summary.csv` | Résumé stats par cluster combiné |
| `cluster_3d_summary.csv` | Résumé stats par cluster 3D |
| `cluster_detailed_analysis.csv` | Analyse détaillée clusters combinés |
| `particle_types_combined_distribution.csv` | Count types de particules |
| `confusion_matrix_types.csv` | Crosstab Type intensité vs Type physique |
| `crosstab_clusters_vs_intensity.csv` | Crosstab Cluster vs Type intensité |
| `crosstab_clusters_vs_particle_types.csv` | Crosstab Cluster vs Type physique |
| `pivot_taille_cluster_type.csv` | Pivot Taille moy par Cluster × Type |
| `pivot_forme_cluster_type.csv` | Pivot Forme moy par Cluster × Type |
| `pivot_intensite_cluster_type.csv` | Pivot Intensité moy par Cluster × Type |
| `pivot_count_cluster_type.csv` | Pivot Count par Cluster × Type |
| `pca_3d_results.csv` | Résultats PCA 3D |
| **`zone_equilibree_info.csv`** | **Infos zone équilibrée avec count clusters** |
| **`best_representative_sample.csv`** | **Résumé échantillon représentatif** |

---

## 🚀 Guide d'Utilisation

### Prérequis
```bash
pip install opencv-python numpy pandas matplotlib scikit-learn scipy
```

### Exécution
1. Ouvrir le notebook `test.ipynb` dans Jupyter ou VS Code
2. Exécuter cellule par cellule ou tout le notebook
3. Les fichiers CSV sont sauvegardés dans le dossier `notebooks/`
4. Les graphiques s'affichent dans le notebook

### Changer l'image
Modifier la ligne :
```python
image_path = "chemin/vers/votre/image.jpg"
```

### Ajuster les paramètres
| Paramètre | Ligne | Effet |
|-----------|-------|-------|
| Seuils intensité | `thresh1=85, thresh2=170` | Divise les 3 types |
| Nombre clusters | `n_main_clusters = ...` | Granularité classification |
| Tailles fenêtres | `window_sizes = [...]` | Résolution balayage zone |

---

## 📊 Résultats et Interprétation

### Métriques Clés

#### 1. Distribution des Clusters
```
Cluster 0: 45 particules (15.2%)
Cluster 1: 52 particules (17.5%)
...
Cluster 7: 38 particules (12.8%)
```
**Interprétation** : clusters équilibrés → bonne couverture chimique

#### 2. Types de Particules Dominants
```
Carbone_Amorphe_Fin:     120 (40.5%)
Mélange_Intermédiaire:    85 (28.6%)
Particule_Transition:     60 (20.2%)
```
**Interprétation** : types composants et leur abondance

#### 3. Zone Équilibrée
```
Position: (2050, 1800)
Taille: 600×600px
Particules: 185

Cluster 0: 24 particules (12.9%)  vs 15.2% global [Δ -2.3%]
Cluster 1: 31 particules (16.7%)  vs 17.5% global [Δ -0.8%]
...
```
**Interprétation** : zone représentative de l'ensemble

#### 4. Corrélations Paramètres
```
Corrélation (Taille, Intensité): +0.32
Corrélation (Forme, Taille):     -0.15
```
**Interprétation** : particules plus sombres → légèrement plus grandes

---

## ✅ Validation, Robustesse et Limites

### Validation interne
- Cohérence **clustering vs classification** (écart entre k optimal et types physiques observés).
- Indicateurs de qualité : silhouette, inertie normalisée, entropie locale.
- Vérification que la zone équilibrée contient **tous** les clusters.

### Robustesse méthodologique
- Normalisation StandardScaler pour réduire l'effet d'échelle.
- Pondération contrôlée des features pour refléter l'importance physique.
- Double vue de clustering (pondéré + 3D normalisé) pour éviter les biais.

### Limites connues
- Seuils d'intensité dépendants de la calibration instrumentale.
- Types rares susceptibles d'être fusionnés par KMeans.
- Sensibilité aux artefacts optiques pour les très petites particules.

### Recommandations
- Ajuster les seuils (85, 170) si l'histogramme d'intensité change.
- Revalider la plage de $k$ si le contexte physico-chimique évolue.
- Conserver les images brutes pour audit et reproductibilité.

## 🔬 Cas d'Usage et Extensions

### Extensions Possibles
1. **Analyse spatio-temporelle** : suivi particules dans série d'images
2. **Machine Learning** : entraîner classifier supervisé sur les clusters
3. **Chimie quantitative** : corréler clusters avec XRD/FTIR
4. **Dynamique cristallisation** : animation processus au fil temps
5. **Comparaison multi-échantillons** : clustering hiérarchique entre images

### Validation Résultats
- Comparer clusters obtenus vs expertise domaine
- Valider types physiques via microscopie électronique
- Mesurer reproductibilité sur images identiques

---

## 📝 Notes Techniques

### Choix Algorithme
- **KMeans vs Hierarchical** : KMeans plus rapide, idéal pour 200-1000 particules
- **StandardScaler vs MinMaxScaler** : StandardScaler pour normaliser différentes échelles
- **Wasserstein Distance** : métrique robuste pour comparer distributions

### Limitations
- Segmentation seuil intensité manuelle (adapter si texture différente)
- Clusters détectés automatiquement (parfois < ou > nombre réel)
- Zone équilibrée optimale pour comparaison (non exhaustive)

### Hypothèses
- Particules bien séparées (pas d'agglomération extrême)
- Intensité Raman corrélée à composition chimique
- Distribution clusters représente composition globale

---

## 👤 Contact et Documentation

**Auteur** : Marwa  
**Date** : Janvier 2026  
**Langage** : Python 3.8+  
**Dépôt** : `Image_RAMA/raman_project/`

Pour questions ou améliorations, consulter le code source du notebook.

---

## 📚 Références et Ressources

### Spectroscopie Raman
- [Raman Spectroscopy Basics](https://en.wikipedia.org/wiki/Raman_spectroscopy)
- Dieterle, Butz & Ern. (2007) - Multivariate Raman analysis

### Computer Vision
- OpenCV Documentation : morphological operations, contour detection
- scikit-image : advanced image processing

### Machine Learning
- scikit-learn KMeans : unsupervised clustering
- PCA for dimensionality reduction : feature analysis

---

**Version** : 1.0  
**Dernière mise à jour** : 28 Janvier 2026
