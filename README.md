# Pipeline Raman — Particules → Clustering → Zone Représentative

Analyse d'images Raman avec segmentation des particules, clustering multi-paramètres, classification physico-réaliste et sélection de zone représentative.

## 🎯 Objectifs scientifiques

Transformer une image Raman en informations quantitatives et interprétables :
1. **Particules individuelles détectées** (composantes connexes et morphologie)
2. **Clustering automatique multi-paramètres** (taille × forme × intensité)
3. **Classification physico-réaliste** (types de particules interprétables)
4. **Zone représentative** (fenêtres glissantes + score de représentativité)

## ✅ Pourquoi cette approche ?

- **Segmentation par intensité** : l'intensité Raman traduit la nature physico-chimique des zones (substrat, transition, dépôts carbonés).
- **Morphologie** : la forme (circularité, solidité, aspect ratio) est un proxy du mode de dépôt/agglomération.
- **Clustering non supervisé** : indispensable quand les types ne sont pas connus a priori et varient d'un échantillon à l'autre.
- **Zone représentative** : évite les biais d'analyse en sélectionnant une zone locale qui reflète la distribution globale.

## 📂 Structure

```
.
├── data/raw/                    # Images Raman d'entrée (.jpg, .png, .tif)
├── src/
│   └── particle_pipeline.py     # Core du pipeline (12 étapes)
├── scripts/
│   └── run_particle_pipeline.py # CLI batch processing
├── notebooks/
│   └── pipeline_particles.ipynb # Notebook principal (interactif)
├── results/particle_pipeline/   # Sorties (features, overlays, stats, ROI)
├── requirements.txt             # Dépendances
└── README.md
```

## 🚀 Démarrage rapide

### Installation des dépendances

**⚠️ CRITIQUE : NumPy 1.x required - NE PAS utiliser l'environnement Anaconda de base**

NumPy 2.x a des changements ABI incompatibles avec pandas/pyarrow. Ce projet nécessite NumPy 1.26.4.

**IMPORTANT** : Vous DEVEZ créer un environnement virtuel propre. N'utilisez PAS l'environnement Anaconda de base qui contient NumPy 2.4.1.

```powershell
# 1. Naviguer vers le projet
cd Image_RAMA\raman_project

# 2. Créer un environnement virtuel Python 3.10+ (OBLIGATOIRE)
python -m venv .venv

# 3. Activer l'environnement virtuel
.\.venv\Scripts\Activate.ps1

# 4. Vérifier que vous êtes dans le bon environnement
python -c "import sys; print(sys.prefix)"  # Doit afficher le chemin vers .venv

# 5. Installer les dépendances exactes
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 6. Vérifier NumPy (doit afficher 1.26.4)
python -c "import numpy; print(numpy.__version__)"

# 7. Vérifier tous les packages (recommandé)
python verify_environment.py
```

**Dépendances** :
- `numpy==1.26.4` (⚠️ Compatible 1.x uniquement)
- `pandas==2.2.3`
- `matplotlib==3.8.4`
- `scikit-learn==1.4.2`
- `scipy==1.11.4`
- `opencv-python==4.8.1.78`

Voir [requirements.txt](requirements.txt) pour la liste complète.

### Dépannage : Erreur NumPy 2.x

**Symptôme** : `ImportError: A module that was compiled using NumPy 1.x cannot be run in NumPy 2.4.1`

**Cause** : Vous utilisez l'environnement Anaconda de base (`c:\ProgramData\Anaconda3.python`) au lieu d'un environnement virtuel.

**Solution** :
```powershell
# 1. Désactiver Anaconda si activé
conda deactivate

# 2. Créer et activer un environnement virtuel propre
cd Image_RAMA\raman_project
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Réinstaller les dépendances
pip install -r requirements.txt

# 4. Vérifier NumPy
python -c "import numpy; print(numpy.__version__)"  # Doit afficher 1.26.4
```

**Alternative avec Conda** (si vous préférez utiliser Conda) :
```powershell
# Créer un environnement Conda dédié
conda create -n raman_project python=3.10
conda activate raman_project

# Installer avec pip (pas conda install)
pip install -r requirements.txt
```

### Exécution du pipeline

**Option 1 : Via CLI (batch)**
```powershell
cd Image_RAMA\raman_project
python scripts/run_particle_pipeline.py --input data/raw --out results/particle_pipeline
```

**Option 2 : Via Notebook (interactif)**
1. Ouvrir `notebooks/pipeline_particles.ipynb` dans VS Code
2. Exécuter la cellule 2 (Pipeline principal)

## ▶️ Utiliser et lancer le projet (pas à pas)

### 1) Préparer les images d’entrée
- Placez vos images Raman dans [data/raw/](data/raw/)
- Formats supportés : `.jpg`, `.png`, `.tif`

### 2) Lancer via la ligne de commande (recommandé pour batch)
```powershell
cd Image_RAMA\raman_project
python scripts/run_particle_pipeline.py --input data/raw --out results/particle_pipeline
```

Paramètres utiles :
- `--input` : dossier d’images d’entrée
- `--out` : dossier de sortie (créé si absent)

### 3) Lancer via notebook (analyse interactive)
1. Ouvrir [notebooks/pipeline_particles.ipynb](notebooks/pipeline_particles.ipynb)
2. Vérifier le chemin d’image `image_path`
3. Exécuter toutes les cellules dans l’ordre

### 4) Où trouver les résultats ?
- Sorties visuelles : [results/particle_pipeline/](results/particle_pipeline/)
- Tableaux CSV : [notebooks/](notebooks/) et [results/particle_pipeline/](results/particle_pipeline/)

### 5) Adapter l’analyse
- Seuils d’intensité : `thresh1`, `thresh2`
- Plage de clusters : `k_min`, `k_max`
- Fenêtres d’équilibre : `window_sizes`, `step_size`

## 📊 Sorties

Chaque image produit :
- ✅ Artefacts visuels : `*_normalized.png`, `*_clean.png`, `*_mask_particles.png`, `*_cluster_overlay.png`, `*_representativity_map.png`, `*_best_sample_region.png`
- ✅ Données : `*_features_particles.csv`, `*_particles_with_clusters.csv`, `*_global_statistics.json`, `*_window_scores.csv`, `*_top3_regions.json`

## ⚙️ Paramètres ajustables

Dans le notebook ou CLI :
- `median_ksize` : Taille filtre médian (3 par défaut)
- `gaussian_sigma` : Sigma débruitage (1.0)
- `background_kernel` : Noyau correction fond (51)
- `min_particle_area` : Aire min particule en pixels (20)
- `n_clusters` : Nombre de clusters KMeans (si imposé manuellement)
- `window_size` : Taille fenêtre représentativité (256)
- `window_step` : Pas de déplacement fenêtre (128)

## 📘 Documentation complète

Pour une description détaillée des étapes, des choix algorithmiques et des justifications scientifiques, voir :
- [PIPELINE.md](PIPELINE.md)
