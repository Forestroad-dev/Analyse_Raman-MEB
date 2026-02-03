# filepath: c:\Users\marwa\OneDrive\Desktop\Analyse_Raman\Image_RAMA\raman_project\notebooks\analyse_raman.py
import argparse
import json
import time
import warnings
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from scipy.stats import entropy, wasserstein_distance
from scipy.ndimage import gaussian_filter


def setup_warnings():
    warnings.filterwarnings("ignore")


def get_image_files(raw_folder: Path):
    image_files = sorted([f for f in raw_folder.glob("*.jpg") if f.is_file()])
    print(f"📷 {len(image_files)} images trouvées dans {raw_folder}:")
    for i, img_file in enumerate(image_files, 1):
        print(f"   {i}. {img_file.name}")
    return image_files


def ensure_results_folder(results_folder: Path):
    results_folder.mkdir(parents=True, exist_ok=True)
    print(f"\n✓ Dossier résultats créé: {results_folder}")
    return results_folder


def process_single_image(image_path: Path):
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"   ❌ Erreur: impossible de charger {image_path.name}")
        return None, None, None
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img, img_rgb, gray


def compute_quality_metrics(gray: np.ndarray):
    print("\n📊 QUALITÉ DE L'IMAGE (avant prétraitement):")
    print("=" * 70)

    contrast = np.std(gray)
    print(f"  • Contraste (écart-type): {contrast:.2f}")

    dynamic_range = gray.max() - gray.min()
    print(f"  • Plage dynamique: {dynamic_range} (min: {gray.min()}, max: {gray.max()})")

    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = laplacian.var()
    print(f"  • Netteté (variance Laplacien): {sharpness:.2f}")

    mean_intensity = gray.mean()
    std_intensity = gray.std()
    snr_estimate = mean_intensity / std_intensity if std_intensity > 0 else 0
    print(f"  • SNR estimé: {snr_estimate:.2f}")

    hist, _ = np.histogram(gray.ravel(), bins=256, range=(0, 256))
    hist_normalized = hist / hist.sum()
    image_entropy = entropy(hist_normalized + 1e-10)
    print(f"  • Entropie: {image_entropy:.2f}")

    cv = (std_intensity / mean_intensity) * 100 if mean_intensity > 0 else 0
    print(f"  • Coefficient de variation: {cv:.2f}%")

    print("\n✓ Qualité image évaluée")


def preprocess_and_segment(gray: np.ndarray, thresh1=85, thresh2=170):
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray_eq = clahe.apply(gray)

    mask_type3 = gray_eq < thresh1
    mask_type2 = (gray_eq >= thresh1) & (gray_eq < thresh2)
    mask_type1 = gray_eq >= thresh2

    segmentation_img = np.zeros_like(gray_eq)
    segmentation_img[mask_type1] = 240
    segmentation_img[mask_type2] = 150
    segmentation_img[mask_type3] = 60

    return gray_eq, mask_type1, mask_type2, mask_type3, segmentation_img, thresh1, thresh2


def detect_particles_in_mask(mask, gray_image, type_name, min_area=5):
    mask_uint8 = (mask * 255).astype(np.uint8)
    kernel = np.ones((2, 2), np.uint8)
    mask_clean = cv2.morphologyEx(mask_uint8, cv2.MORPH_OPEN, kernel, iterations=1)
    contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    features = []
    valid_contours = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue

        perimeter = cv2.arcLength(cnt, True)
        circularity = (4 * np.pi * area) / (perimeter**2 + 1e-6)

        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = w / h if h > 0 else 0

        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0

        mask_particle = np.zeros_like(gray_image, dtype=np.uint8)
        cv2.drawContours(mask_particle, [cnt], -1, 255, -1)
        mean_intensity = cv2.mean(gray_image, mask=mask_particle)[0]

        M = cv2.moments(cnt)
        if M["m00"] > 0:
            center_x = int(M["m10"] / M["m00"])
            center_y = int(M["m01"] / M["m00"])
        else:
            center_x = x + w // 2
            center_y = y + h // 2

        features.append({
            "Type": type_name,
            "Area_px2": area,
            "Perimeter_px": perimeter,
            "Circularity": circularity,
            "AspectRatio": aspect_ratio,
            "Solidity": solidity,
            "MeanIntensity": mean_intensity,
            "Center_X": center_x,
            "Center_Y": center_y,
        })
        valid_contours.append(cnt)

    return features, valid_contours


def extract_particles(gray_eq, mask_type1, mask_type2, mask_type3):
    features_type1, contours_type1 = detect_particles_in_mask(mask_type1, gray_eq, "Type_1_Blanc")
    features_type2, contours_type2 = detect_particles_in_mask(mask_type2, gray_eq, "Type_2_Gris")
    features_type3, contours_type3 = detect_particles_in_mask(mask_type3, gray_eq, "Type_3_Noir")

    all_features = features_type1 + features_type2 + features_type3
    df_particles = pd.DataFrame(all_features)

    return df_particles, contours_type1, contours_type2, contours_type3


def add_scores(df_particles: pd.DataFrame):
    df_particles["Size_Score"] = df_particles["Area_px2"]
    df_particles["Shape_Score"] = (
        df_particles["Circularity"] * 0.4
        + df_particles["Solidity"] * 0.4
        + (1 / (1 + df_particles["AspectRatio"])) * 0.2
    )
    df_particles["Intensity_Score"] = df_particles["MeanIntensity"]
    return df_particles


def cluster_weighted(df_particles: pd.DataFrame):
    feature_cols = ["Size_Score", "Circularity", "AspectRatio", "Solidity", "Intensity_Score"]
    X = df_particles[feature_cols].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    weights = np.array([1.3, 1.0, 0.9, 1.0, 1.4])
    X_weighted = X_scaled * weights

    if len(df_particles) >= 12:
        k_min = 6
        k_max = min(10, len(df_particles) - 1)
        silhouette_scores = {}
        inertia_scores = {}

        for k in range(k_min, k_max + 1):
            km = KMeans(n_clusters=k, random_state=42, n_init=50, max_iter=500)
            labels = km.fit_predict(X_weighted)
            silhouette_scores[k] = silhouette_score(X_weighted, labels)
            inertia_scores[k] = km.inertia_

        inertias = np.array(list(inertia_scores.values()))
        norm_inertias = 1 - (inertias - inertias.min()) / (inertias.max() - inertias.min())
        combined_scores = {}
        for i, k in enumerate(range(k_min, k_max + 1)):
            combined_scores[k] = 0.7 * silhouette_scores[k] + 0.3 * norm_inertias[i]

        best_k = max(combined_scores, key=combined_scores.get)
        n_main_clusters = best_k
    else:
        n_main_clusters = min(9, max(6, len(df_particles) // 10))

    kmeans_main = KMeans(n_clusters=n_main_clusters, random_state=42, n_init=100, max_iter=800)
    df_particles["Cluster_Combined"] = kmeans_main.fit_predict(X_weighted)

    return df_particles, n_main_clusters


def interpret_clusters(df_particles: pd.DataFrame, n_main_clusters: int):
    def interpret_combined_cluster(cluster_data):
        avg_size = cluster_data["Size_Score"].mean()
        avg_circ = cluster_data["Circularity"].mean()
        avg_intensity = cluster_data["Intensity_Score"].mean()

        if avg_size < 50:
            size_label = "Très_Petites"
        elif avg_size < 150:
            size_label = "Petites"
        elif avg_size < 400:
            size_label = "Moyennes"
        elif avg_size < 1000:
            size_label = "Grandes"
        else:
            size_label = "Très_Grandes"

        if avg_circ > 0.75:
            shape_label = "Sphériques"
        elif avg_circ > 0.6:
            shape_label = "Compactes"
        elif avg_circ < 0.4:
            shape_label = "Irrégulières"
        else:
            shape_label = "Intermédiaires"

        if avg_intensity < 90:
            intensity_label = "Sombres"
        elif avg_intensity < 160:
            intensity_label = "Grises"
        else:
            intensity_label = "Claires"

        return f"{intensity_label}_{size_label}_{shape_label}"

    cluster_labels = {}
    for cluster_id in range(n_main_clusters):
        cluster_data = df_particles[df_particles["Cluster_Combined"] == cluster_id]
        if len(cluster_data) > 0:
            cluster_labels[cluster_id] = interpret_combined_cluster(cluster_data)

    df_particles["Cluster_Label"] = df_particles["Cluster_Combined"].map(cluster_labels)
    df_particles["Cluster_Label"].fillna("Non_Classé", inplace=True)

    return df_particles, cluster_labels


def cluster_3d(df_particles: pd.DataFrame):
    df_particles["Size_Normalized"] = (
        (df_particles["Size_Score"] - df_particles["Size_Score"].min())
        / (df_particles["Size_Score"].max() - df_particles["Size_Score"].min())
    )
    df_particles["Shape_Normalized"] = df_particles["Shape_Score"]
    df_particles["Intensity_Normalized"] = df_particles["Intensity_Score"] / 255.0

    X_3d = df_particles[["Size_Normalized", "Shape_Normalized", "Intensity_Normalized"]].values
    n_3d_clusters = min(10, max(7, len(df_particles) // 15))

    kmeans_3d = KMeans(n_clusters=n_3d_clusters, random_state=42, n_init=80, max_iter=600)
    df_particles["Cluster_3D"] = kmeans_3d.fit_predict(X_3d)

    return df_particles, n_3d_clusters


def classify_particles(df_particles: pd.DataFrame):
    def classify_particle_combined(row):
        size = row["Size_Score"]
        intensity = row["Intensity_Score"]
        circ = row["Circularity"]
        solid = row["Solidity"]
        aspect = row["AspectRatio"]

        is_compact = (circ > 0.65 and solid > 0.75)
        is_porous = (solid < 0.65)
        is_angular = not is_compact and not is_porous and (aspect > 1.4 or circ < 0.55)

        if intensity < 85:
            if size < 100:
                return "Carbone_Amorphe_Fin" if is_compact else "Carbone_Dispersé"
            elif size < 400:
                return "Carbone_Cristallin_Dense" if solid > 0.85 else "Carbone_Dispersé"
            else:
                return "Agglomérat_Carbone"
        elif intensity < 170:
            if size < 100:
                if is_compact:
                    return "Particule_Transition_Compacte"
                if is_angular:
                    return "Particule_Transition_Anguleuse"
                return "Particule_Transition_Ronde"
            elif size < 400:
                if is_porous:
                    return "Dépôt_Poreux"
                if is_compact:
                    return "Particule_Transition_Compacte"
                return "Particule_Transition_Anguleuse"
            else:
                return "Dépôt_Poreux" if is_porous else "Mélange_Intermédiaire"
        else:
            if size < 50:
                return "Bruit_Optique"
            elif size < 200:
                return "Particule_Claire_Compacte" if is_compact else "Particule_Claire"
            else:
                return "Substrat_Exposé" if (circ < 0.5 or solid < 0.7) else "Particule_Claire_Compacte"

    df_particles["Particle_Type_Combined"] = df_particles.apply(classify_particle_combined, axis=1)
    return df_particles


    features_for_pca = ["Size_Score", "Circularity", "AspectRatio", "Solidity", "Intensity_Score", "Perimeter_px"]
    available_features = [feat for feat in features_for_pca if feat in df_particles.columns]
    if len(available_features) < 2:
        print("⚠️  PCA ignorée: pas assez de features disponibles")
        return df_particles, None

    X_pca = df_particles[available_features].values
    X_pca = df_particles[features_for_pca].values

    scaler_pca = StandardScaler()
    X_pca_scaled = scaler_pca.fit_transform(X_pca)

    pca = PCA(n_components=3)
    X_pca_3d = pca.fit_transform(X_pca_scaled)

    df_particles["PCA_1"] = X_pca_3d[:, 0]
    df_particles["PCA_2"] = X_pca_3d[:, 1]
    df_particles["PCA_3"] = X_pca_3d[:, 2]



def resolve_feature_columns(df_particles: pd.DataFrame):
    size_col = "Size_Score" if "Size_Score" in df_particles.columns else "Area_px2"
    shape_col = "Shape_Score" if "Shape_Score" in df_particles.columns else "Circularity"
    intensity_col = "Intensity_Score" if "Intensity_Score" in df_particles.columns else "MeanIntensity"
    return size_col, shape_col, intensity_col


def generate_basic_heatmaps(
    gray_eq: np.ndarray,
    segmentation_img: np.ndarray,
    contours_type1,
    contours_type2,
    contours_type3,
    mask_type1,
    mask_type2,
    mask_type3,
    output_dir: Path | None = None,
    show_plots: bool = True,
):
    print("\n🔥 Génération des heatmaps...\n")

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # Heatmap 1: Intensité Raman
    ax = axes[0, 0]
    im1 = ax.imshow(gray_eq, cmap="hot", vmin=0, vmax=255)
    ax.set_title("Heat Map: Intensité Raman (0-255)", fontsize=12, fontweight="bold")
    ax.axis("off")
    plt.colorbar(im1, ax=ax, fraction=0.046, pad=0.04, label="Intensité")

    # Heatmap 2: Segmentation
    ax = axes[0, 1]
    im2 = ax.imshow(segmentation_img, cmap="viridis", vmin=0, vmax=255)
    ax.set_title("Heat Map: Segmentation 3 Types", fontsize=12, fontweight="bold")
    ax.axis("off")
    plt.colorbar(im2, ax=ax, fraction=0.046, pad=0.04, label="Type")

    # Heatmap 3: Densité
    ax = axes[1, 0]
    density_map = np.zeros_like(gray_eq, dtype=np.float32)
    for contours_list in [contours_type1, contours_type2, contours_type3]:
        for cnt in contours_list:
            mask_temp = np.zeros_like(gray_eq, dtype=np.uint8)
            cv2.drawContours(mask_temp, [cnt], -1, 1, -1)
            density_map += mask_temp

    density_smooth = gaussian_filter(density_map, sigma=15)
    im3 = ax.imshow(density_smooth, cmap="jet", interpolation="bilinear")
    ax.set_title("Heat Map: Densité des Particules", fontsize=12, fontweight="bold")
    ax.axis("off")
    plt.colorbar(im3, ax=ax, fraction=0.046, pad=0.04, label="Densité")

    # Heatmap 4: Distribution types
    ax = axes[1, 1]
    composite_map = np.zeros_like(gray_eq, dtype=np.float32)
    composite_map[mask_type3] = 1.0
    composite_map[mask_type2] = 2.0
    composite_map[mask_type1] = 3.0

    im4 = ax.imshow(composite_map, cmap="RdYlBu_r", vmin=0.5, vmax=3.5)
    ax.set_title("Heat Map: Distribution des Types", fontsize=12, fontweight="bold")
    ax.axis("off")
    cbar4 = plt.colorbar(im4, ax=ax, fraction=0.046, pad=0.04, ticks=[1, 2, 3])
    cbar4.ax.set_yticklabels(["Type 3\n(Noir)", "Type 2\n(Gris)", "Type 1\n(Blanc)"])

    plt.tight_layout()
    if output_dir is not None:
        plt.savefig(output_dir / "heatmaps_base.png", dpi=300, bbox_inches="tight", facecolor="white")
    if show_plots:
        plt.show()
    else:
        plt.close(fig)

    print("✓ Heat maps générées avec succès!")


def generate_parametric_heatmaps(
    df_particles: pd.DataFrame,
    gray_eq: np.ndarray,
    output_dir: Path | None = None,
    show_plots: bool = True,
):
    print("\n🔥 GÉNÉRATION DES HEATMAPS PARAMÉTRIQUES")
    print("=" * 80)

    size_col, shape_col, intensity_col = resolve_feature_columns(df_particles)

    fig, axes = plt.subplots(1, 3, figsize=(22, 7))

    # HEATMAP 1: TAILLE
    print("\n📏 Création de la heatmap TAILLE...")
    ax = axes[0]
    heatmap_size = np.zeros_like(gray_eq, dtype=np.float32)
    for _, row in df_particles.iterrows():
        x, y = int(row["Center_X"]), int(row["Center_Y"])
        size_value = row[size_col]
        y_min, y_max = max(0, y - 30), min(gray_eq.shape[0], y + 30)
        x_min, x_max = max(0, x - 30), min(gray_eq.shape[1], x + 30)
        for yy in range(y_min, y_max):
            for xx in range(x_min, x_max):
                dist = np.sqrt((xx - x) ** 2 + (yy - y) ** 2)
                if dist < 30:
                    weight = np.exp(-(dist**2) / (2 * 15**2))
                    heatmap_size[yy, xx] += size_value * weight

    heatmap_size_smooth = gaussian_filter(heatmap_size, sigma=10)
    im1 = ax.imshow(heatmap_size_smooth, cmap="YlOrRd", interpolation="bilinear")
    ax.set_title(f"Heatmap: TAILLE des Particules\n({size_col})", fontsize=13, fontweight="bold", pad=10)
    ax.axis("off")
    cbar1 = plt.colorbar(im1, ax=ax, fraction=0.046, pad=0.04)
    cbar1.set_label("Taille (px²)", fontsize=10, fontweight="bold")

    # HEATMAP 2: INTENSITÉ
    print("💡 Création de la heatmap INTENSITÉ...")
    ax = axes[1]
    heatmap_intensity = np.zeros_like(gray_eq, dtype=np.float32)
    for _, row in df_particles.iterrows():
        x, y = int(row["Center_X"]), int(row["Center_Y"])
        intensity_value = row[intensity_col]
        y_min, y_max = max(0, y - 30), min(gray_eq.shape[0], y + 30)
        x_min, x_max = max(0, x - 30), min(gray_eq.shape[1], x + 30)
        for yy in range(y_min, y_max):
            for xx in range(x_min, x_max):
                dist = np.sqrt((xx - x) ** 2 + (yy - y) ** 2)
                if dist < 30:
                    weight = np.exp(-(dist**2) / (2 * 15**2))
                    heatmap_intensity[yy, xx] += intensity_value * weight

    heatmap_intensity_smooth = gaussian_filter(heatmap_intensity, sigma=10)
    im2 = ax.imshow(heatmap_intensity_smooth, cmap="plasma", interpolation="bilinear")
    ax.set_title(
        f"Heatmap: INTENSITÉ des Particules\n({intensity_col})",
        fontsize=13,
        fontweight="bold",
        pad=10,
    )
    ax.axis("off")
    cbar2 = plt.colorbar(im2, ax=ax, fraction=0.046, pad=0.04)
    cbar2.set_label("Intensité (0-255)", fontsize=10, fontweight="bold")

    # HEATMAP 3: FORME
    print("🔺 Création de la heatmap FORME...")
    ax = axes[2]
    heatmap_shape = np.zeros_like(gray_eq, dtype=np.float32)
    for _, row in df_particles.iterrows():
        x, y = int(row["Center_X"]), int(row["Center_Y"])
        shape_value = row[shape_col]
        y_min, y_max = max(0, y - 30), min(gray_eq.shape[0], y + 30)
        x_min, x_max = max(0, x - 30), min(gray_eq.shape[1], x + 30)
        for yy in range(y_min, y_max):
            for xx in range(x_min, x_max):
                dist = np.sqrt((xx - x) ** 2 + (yy - y) ** 2)
                if dist < 30:
                    weight = np.exp(-(dist**2) / (2 * 15**2))
                    heatmap_shape[yy, xx] += shape_value * weight

    heatmap_shape_smooth = gaussian_filter(heatmap_shape, sigma=10)
    im3 = ax.imshow(heatmap_shape_smooth, cmap="viridis", interpolation="bilinear")
    ax.set_title(f"Heatmap: FORME des Particules\n({shape_col})", fontsize=13, fontweight="bold", pad=10)
    ax.axis("off")
    cbar3 = plt.colorbar(im3, ax=ax, fraction=0.046, pad=0.04)
    cbar3.set_label("Forme (circularité)", fontsize=10, fontweight="bold")

    plt.tight_layout()
    if output_dir is not None:
        plt.savefig(output_dir / "heatmaps_parametriques_3d.png", dpi=300, bbox_inches="tight", facecolor="white")
    if show_plots:
        plt.show()
    else:
        plt.close(fig)

    print("\n" + "=" * 80)
    print("✅ HEATMAPS PARAMÉTRIQUES GÉNÉRÉES!")
    print("=" * 80)
    print("\n📊 Statistiques des heatmaps:")
    print(f"   Heatmap Taille: Min={heatmap_size_smooth.min():.2f} | Max={heatmap_size_smooth.max():.2f} | Moy={heatmap_size_smooth.mean():.2f}")
    print(f"   Heatmap Intensité: Min={heatmap_intensity_smooth.min():.2f} | Max={heatmap_intensity_smooth.max():.2f} | Moy={heatmap_intensity_smooth.mean():.2f}")
    print(f"   Heatmap Forme: Min={heatmap_shape_smooth.min():.2f} | Max={heatmap_shape_smooth.max():.2f} | Moy={heatmap_shape_smooth.mean():.2f}")


def generate_pivot_heatmaps(
    df_particles: pd.DataFrame,
    output_dir: Path | None = None,
    show_plots: bool = True,
):
    print("\n🔥 GÉNÉRATION DES PIVOTS ET HEATMAPS PARAMÉTRIQUES")
    print("=" * 80)

    if "Cluster_Combined" not in df_particles.columns or "Particle_Type_Combined" not in df_particles.columns:
        print("⚠️  Clusters ou types physiques manquants: pivots ignorés")
        return

    size_col, shape_col, intensity_col = resolve_feature_columns(df_particles)

    pivot_size = df_particles.pivot_table(
        index="Cluster_Combined",
        columns="Particle_Type_Combined",
        values=size_col,
        aggfunc="mean",
        fill_value=0,
    )
    pivot_shape = df_particles.pivot_table(
        index="Cluster_Combined",
        columns="Particle_Type_Combined",
        values=shape_col,
        aggfunc="mean",
        fill_value=0,
    )
    pivot_intensity = df_particles.pivot_table(
        index="Cluster_Combined",
        columns="Particle_Type_Combined",
        values=intensity_col,
        aggfunc="mean",
        fill_value=0,
    )
    pivot_count = df_particles.pivot_table(
        index="Cluster_Combined",
        columns="Particle_Type_Combined",
        values="Type",
        aggfunc="count",
        fill_value=0,
    )

    fig, axes = plt.subplots(2, 2, figsize=(18, 12))

    im1 = axes[0, 0].imshow(pivot_size.values, cmap="YlOrRd", aspect="auto")
    axes[0, 0].set_title("Heatmap: Taille moyenne", fontweight="bold")
    plt.colorbar(im1, ax=axes[0, 0], fraction=0.046, pad=0.04)

    im2 = axes[0, 1].imshow(pivot_shape.values, cmap="viridis", aspect="auto")
    axes[0, 1].set_title("Heatmap: Forme moyenne", fontweight="bold")
    plt.colorbar(im2, ax=axes[0, 1], fraction=0.046, pad=0.04)

    im3 = axes[1, 0].imshow(pivot_intensity.values, cmap="plasma", aspect="auto")
    axes[1, 0].set_title("Heatmap: Intensité moyenne", fontweight="bold")
    plt.colorbar(im3, ax=axes[1, 0], fraction=0.046, pad=0.04)

    im4 = axes[1, 1].imshow(pivot_count.values, cmap="Blues", aspect="auto")
    axes[1, 1].set_title("Heatmap: Nombre de particules", fontweight="bold")
    plt.colorbar(im4, ax=axes[1, 1], fraction=0.046, pad=0.04)

    for ax in axes.flat:
        ax.set_xticks(range(len(pivot_size.columns)))
        ax.set_xticklabels(pivot_size.columns, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(len(pivot_size.index)))
        ax.set_yticklabels([f"C{cid}" for cid in pivot_size.index], fontsize=9)

    plt.tight_layout()
    if output_dir is not None:
        plt.savefig(output_dir / "pivots_heatmaps.png", dpi=300, bbox_inches="tight", facecolor="white")
        pivot_size.to_csv(output_dir / "pivot_taille_cluster_type.csv")
        pivot_shape.to_csv(output_dir / "pivot_forme_cluster_type.csv")
        pivot_intensity.to_csv(output_dir / "pivot_intensite_cluster_type.csv")
        pivot_count.to_csv(output_dir / "pivot_count_cluster_type.csv")
        print("✓ Pivots sauvegardés: pivot_*.csv")

    if show_plots:
        plt.show()
    else:
        plt.close(fig)



def generate_final_report(df_particles: pd.DataFrame):
    size_col, shape_col, intensity_col = resolve_feature_columns(df_particles)

    print("\n📋 RAPPORT FINAL")
    print("=" * 80)
    print(f"Nombre total de particules: {len(df_particles)}")
    print("\n📏 Taille:")
    print(f"  • Moyenne: {df_particles[size_col].mean():.2f}")
    print(f"  • Min: {df_particles[size_col].min():.2f}")
    print(f"  • Max: {df_particles[size_col].max():.2f}")

    print("\n🔺 Forme:")
    print(f"  • Moyenne: {df_particles[shape_col].mean():.3f}")
    print(f"  • Min: {df_particles[shape_col].min():.3f}")
    print(f"  • Max: {df_particles[shape_col].max():.3f}")

    print("\n💡 Intensité:")
    print(f"  • Moyenne: {df_particles[intensity_col].mean():.2f}")
    print(f"  • Min: {df_particles[intensity_col].min():.2f}")
    print(f"  • Max: {df_particles[intensity_col].max():.2f}")

    if "Cluster_Combined" in df_particles.columns:
        cluster_counts = df_particles["Cluster_Combined"].value_counts().sort_index()
        print("\n🧩 Clusters (Combined):")
        for cid, count in cluster_counts.items():
            print(f"  • Cluster {cid}: {count} particules")

    if "Particle_Type_Combined" in df_particles.columns:
        type_counts = df_particles["Particle_Type_Combined"].value_counts()
        print("\n🧪 Types physiques:")
        for tname, count in type_counts.items():
            print(f"  • {tname}: {count}")


def export_results(df_particles: pd.DataFrame, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    size_col, shape_col, intensity_col = resolve_feature_columns(df_particles)

    df_particles.to_csv(output_dir / "particles_by_intensity_types.csv", index=False)
    df_particles.to_csv(output_dir / "particles_by_intensity_types.csv", index=False)

    # Résumé par cluster si disponible
    if "Cluster_Combined" in df_particles.columns:
        df_cluster_summary = (
            df_particles.groupby("Cluster_Combined")
            .agg(
                Count=("Cluster_Combined", "size"),
                Size_Mean=(size_col, "mean"),
                Shape_Mean=(shape_col, "mean"),
                Intensity_Mean=(intensity_col, "mean"),
                Circularity_Mean=("Circularity", "mean"),
                Solidity_Mean=("Solidity", "mean"),
                AspectRatio_Mean=("AspectRatio", "mean"),
            )
            .reset_index()
        df_cluster_summary.to_csv(output_dir / "cluster_detailed_analysis.csv", index=False)
        df_cluster_summary.to_csv(output_dir / "cluster_detailed_analysis.csv", index=False)

    # PCA
    df_particles[["PCA_1", "PCA_2", "PCA_3"]].to_csv(output_dir / "pca_3d_results.csv", index=False)
        df_particles[["PCA_1", "PCA_2", "PCA_3"]].to_csv(output_dir / "pca_3d_results.csv", index=False)

    # Crosstab clusters vs intensité
    if "Cluster_Combined" in df_particles.columns and "Type" in df_particles.columns:
        crosstab_intensity.to_csv(output_dir / "crosstab_clusters_vs_intensity.csv")
        crosstab_intensity.to_csv(output_dir / "crosstab_clusters_vs_intensity.csv")

    # Crosstab clusters vs types physiques
    if "Cluster_Combined" in df_particles.columns and "Particle_Type_Combined" in df_particles.columns:
        crosstab_physical = pd.crosstab(
            df_particles["Cluster_Combined"],
            df_particles["Particle_Type_Combined"],
        crosstab_physical.to_csv(output_dir / "crosstab_clusters_vs_particle_types.csv")
        crosstab_physical.to_csv(output_dir / "crosstab_clusters_vs_particle_types.csv")
    print("\n✓ Résultats exportés")
    print("\n✓ Résultats exportés")
    print("\n✓ Heatmaps paramétriques générées")
    return df_particles, pca


def find_balanced_zone(df_particles: pd.DataFrame, img_rgb: np.ndarray):
    total_clusters = df_particles["Cluster_Combined"].nunique()
    global_cluster_counts = df_particles["Cluster_Combined"].value_counts().sort_index()
    global_cluster_distribution = (global_cluster_counts / len(df_particles)).values

    window_sizes = [300, 400, 500, 600, 700, 800]
    step_size = 50
    img_height, img_width = img_rgb.shape[:2]

    best_score_overall = -np.inf
    best_window = None
    candidates = []

    for window_size in window_sizes:
        for y in range(0, img_height - window_size, step_size):
            for x in range(0, img_width - window_size, step_size):
                x_min, x_max = x, x + window_size
                y_min, y_max = y, y + window_size

                in_window = (
                    (df_particles["Center_X"] >= x_min)
                    & (df_particles["Center_X"] <= x_max)
                    & (df_particles["Center_Y"] >= y_min)
                    & (df_particles["Center_Y"] <= y_max)
                )
                particles_in_window = df_particles[in_window]

                if len(particles_in_window) < total_clusters * 2:
                    continue

                unique_clusters_in_window = particles_in_window["Cluster_Combined"].nunique()
                if unique_clusters_in_window == total_clusters:
                    local_cluster_counts = particles_in_window["Cluster_Combined"].value_counts().sort_index()
                    if len(local_cluster_counts) == total_clusters:
                        local_cluster_distribution = (local_cluster_counts / len(particles_in_window)).values

                        wasserstein_dist = wasserstein_distance(global_cluster_distribution, local_cluster_distribution)
                        max_entropy = -np.log(1.0 / total_clusters)
                        actual_entropy = entropy(local_cluster_distribution)
                        balance_score = actual_entropy / max_entropy

                        min_count_in_cluster = local_cluster_counts.min()
                        min_proportion_penalty = np.exp(-5.0 / (min_count_in_cluster + 1))
                        similarity_score = 1.0 / (1.0 + wasserstein_dist)

                        combined_score = (
                            similarity_score * 0.3
                            + balance_score * 0.5
                            + (1.0 - min_proportion_penalty) * 0.2
                        )

                        candidates.append({
                            "score": combined_score,
                            "x": x,
                            "y": y,
                            "size": window_size,
                            "n_particles": len(particles_in_window),
                            "distribution": local_cluster_counts.to_dict(),
                        })

                        if combined_score > best_score_overall:
                            best_score_overall = combined_score
                            best_window = {
                                "x": x,
                                "y": y,
                                "size": window_size,
                                "n_particles": len(particles_in_window),
                                "distribution": local_cluster_counts.to_dict(),
                            }

    if best_window is None:
        best_window = {
            "x": 0,
            "y": 0,
            "size": min(img_height, img_width),
            "n_particles": len(df_particles),
            "distribution": df_particles["Cluster_Combined"].value_counts().to_dict(),
        }

    x_center = best_window["x"] + best_window["size"] // 2
    y_center = best_window["y"] + best_window["size"] // 2
    square_size = best_window["size"]
    x_topleft = best_window["x"]
    y_topleft = best_window["y"]

    return best_window, best_score_overall, (x_center, y_center, x_topleft, y_topleft, square_size), candidates


def batch_process_images(image_files, results_folder):
    print("\n" + "=" * 80)
    print("🔄 LANCEMENT DU PIPELINE COMPLET SUR TOUTES LES IMAGES")
    print("=" * 80)

    batch_results = []
    start_time_global = time.time()

    for idx, image_path in enumerate(image_files, 1):
        print(f"\n{'=' * 80}")
        print(f"[{idx}/{len(image_files)}] 🔄 {image_path.name}")
        print(f"{'=' * 80}")

        start_time = time.time()

        try:
            img, img_rgb, gray = process_single_image(image_path)
            if gray is None:
                batch_results.append({"image": image_path.name, "status": "❌ Erreur chargement"})
                continue

            image_name = image_path.stem
            image_results_folder = results_folder / image_name
            image_results_folder.mkdir(parents=True, exist_ok=True)

            gray_eq, mask_type1, mask_type2, mask_type3, _, thresh1, thresh2 = preprocess_and_segment(gray)

            features_type1, _ = detect_particles_in_mask(mask_type1, gray_eq, "Type_1_Blanc")
            features_type2, _ = detect_particles_in_mask(mask_type2, gray_eq, "Type_2_Gris")
            features_type3, _ = detect_particles_in_mask(mask_type3, gray_eq, "Type_3_Noir")

            df_particles_img = pd.DataFrame(features_type1 + features_type2 + features_type3)
            n_particles = len(df_particles_img)

            if n_particles >= 5:
                df_particles_img = add_scores(df_particles_img)
                df_particles_img, n_clusters = cluster_weighted(df_particles_img)

                csv_path = image_results_folder / f"{image_name}_particles.csv"
                df_particles_img.to_csv(csv_path, index=False)

                stats = {
                    "image_name": image_path.name,
                    "dimensions": {"width": gray.shape[1], "height": gray.shape[0]},
                    "segmentation": {
                        "blanc_pixels": int(np.sum(mask_type1)),
                        "gris_pixels": int(np.sum(mask_type2)),
                        "noir_pixels": int(np.sum(mask_type3)),
                        "thresh1": int(thresh1),
                        "thresh2": int(thresh2),
                    },
                    "particles": {
                        "total": n_particles,
                        "blanc": len(features_type1),
                        "gris": len(features_type2),
                        "noir": len(features_type3),
                    },
                    "clustering": {
                        "n_clusters": n_clusters,
                        "distribution": df_particles_img["Cluster_Combined"].value_counts().to_dict(),
                    },
                }

                json_path = image_results_folder / f"{image_name}_stats.json"
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(stats, f, indent=2)

                elapsed = time.time() - start_time
                batch_results.append({
                    "image": image_path.name,
                    "status": "✓ Succès",
                    "particles": n_particles,
                    "clusters": n_clusters,
                    "time_s": elapsed,
                })
            else:
                batch_results.append({
                    "image": image_path.name,
                    "status": "⚠️  Trop peu de particules",
                    "particles": n_particles,
                })

        except Exception as e:
            batch_results.append({
                "image": image_path.name,
                "status": f"❌ Erreur: {str(e)}",
            })

    total_time = time.time() - start_time_global
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ DU TRAITEMENT BATCH")
    print("=" * 80)

    success_count = sum(1 for r in batch_results if "✓" in r.get("status", ""))
    warning_count = sum(1 for r in batch_results if "⚠️" in r.get("status", ""))
    error_count = len(batch_results) - success_count - warning_count

    print(f"✓ Images traitées avec succès: {success_count}/{len(batch_results)}")
    print(f"⚠️  Images avec avertissements: {warning_count}/{len(batch_results)}")
    print(f"❌ Images en erreur: {error_count}/{len(batch_results)}")
    print(f"⏱️  Temps total: {total_time:.2f}s ({total_time/len(image_files):.2f}s/image)")
    print(f"\n💾 Tous les résultats sauvegardés dans: {results_folder}")

    summary_df = pd.DataFrame(batch_results)
    summary_path = results_folder / "batch_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"📋 Résumé sauvegardé: {summary_path}")

    return batch_results


def analyze_single_image(image_path: Path, results_folder: Path, show_plots=True):
    img, img_rgb, gray = process_single_image(image_path)
    if gray is None:
        return

    print(f"\n🔄 Analyse détaillée: {image_path.name}")
    compute_quality_metrics(gray)

    gray_eq, mask_type1, mask_type2, mask_type3, segmentation_img, thresh1, thresh2 = preprocess_and_segment(gray)

    df_particles, contours_type1, contours_type2, contours_type3 = extract_particles(
        gray_eq, mask_type1, mask_type2, mask_type3
    )

    if len(df_particles) < 5:
        print("⚠️  Trop peu de particules pour l'analyse avancée")
        return

    df_particles = add_scores(df_particles)
    df_particles, n_main_clusters = cluster_weighted(df_particles)
    df_particles, cluster_labels = interpret_clusters(df_particles, n_main_clusters)
    df_particles, n_3d_clusters = cluster_3d(df_particles)
    df_particles = classify_particles(df_particles)

    output_dir = results_folder / image_path.stem / "single_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    df_particles, pca = run_pca(df_particles)

    best_window, best_score, coords, candidates = find_balanced_zone(df_particles, img_rgb)
    output_dir.mkdir(parents=True, exist_ok=True)

    df_particles.to_csv(output_dir / "particles_by_intensity_types.csv", index=False)

    if show_plots:
        plt.figure(figsize=(14, 6))
        plt.subplot(1, 2, 1)
        plt.imshow(img_rgb)
        plt.title("Image Originale (RGB)", fontsize=13, fontweight="bold")
        plt.axis("off")

        plt.subplot(1, 2, 2)
        plt.imshow(gray, cmap="gray")
        plt.title("Image en Niveaux de Gris (Intensité Raman)", fontsize=13, fontweight="bold")
        plt.axis("off")
        plt.tight_layout()
        plt.show()

        fig, axes = plt.subplots(1, 3, figsize=(16, 5))
        axes[0].imshow(img_rgb)
        axes[0].set_title("Image Originale", fontsize=12, fontweight="bold")
        axes[0].axis("off")

        axes[1].imshow(gray_eq, cmap="gray")
        axes[1].set_title("Image Améliorée (CLAHE)", fontsize=12, fontweight="bold")
        axes[1].axis("off")

        axes[2].imshow(segmentation_img, cmap="gray", vmin=0, vmax=255)
        axes[2].set_title(f"Segmentation (Seuils: {thresh1}, {thresh2})", fontsize=12, fontweight="bold")
        axes[2].axis("off")
        plt.tight_layout()

        generate_basic_heatmaps(
            gray_eq,
            segmentation_img,
            contours_type1,
            contours_type2,
            contours_type3,
            mask_type1,
            mask_type2,
            mask_type3,
            output_dir=output_dir,
            show_plots=show_plots,
        )

        generate_parametric_heatmaps(
            df_particles,
            gray_eq,
            output_dir=output_dir,
            show_plots=show_plots,
        )

        generate_pivot_heatmaps(
            df_particles,
            output_dir=output_dir,
            show_plots=show_plots,

    generate_final_report(df_particles)
    export_results(df_particles, output_dir)
        )
        plt.show()

        overlay = img_rgb.copy()
        for cnt in contours_type1:
            cv2.drawContours(overlay, [cnt], -1, (255, 0, 0), 2)
        for cnt in contours_type2:
            cv2.drawContours(overlay, [cnt], -1, (0, 255, 0), 2)
        for cnt in contours_type3:
            cv2.drawContours(overlay, [cnt], -1, (0, 0, 255), 2)

        fig, axes = plt.subplots(1, 2, figsize=(16, 7))
        axes[0].imshow(overlay)
        axes[0].set_title(f"Particules Détectées (Total: {len(df_particles)})", fontsize=12, fontweight="bold")
        axes[0].axis("off")

        type_counts = df_particles["Type"].value_counts()
        axes[1].bar(range(len(type_counts)), type_counts.values, color=["red", "green", "blue"][:len(type_counts)])
        axes[1].set_xticks(range(len(type_counts)))
        axes[1].set_xticklabels(type_counts.index, rotation=45, ha="right")
        axes[1].set_ylabel("Nombre de particules", fontweight="bold")
        axes[1].set_title("Distribution par Type d'Intensité", fontsize=12, fontweight="bold")
        axes[1].grid(True, alpha=0.3, axis="y")
        plt.tight_layout()
        plt.show()

        fig = plt.figure(figsize=(18, 6))
        ax1 = fig.add_subplot(131, projection="3d")
        scatter1 = ax1.scatter(
            df_particles["PCA_1"], df_particles["PCA_2"], df_particles["PCA_3"],
            c=df_particles["Cluster_Combined"], cmap="tab10", s=30, alpha=0.6, edgecolors="black", linewidth=0.3
        )
        ax1.set_title("PCA 3D - Cluster", fontsize=12, fontweight="bold")
        plt.colorbar(scatter1, ax=ax1, label="Cluster ID", shrink=0.6, pad=0.1)

        ax2 = fig.add_subplot(132, projection="3d")
        type_colors = {"Type_1_Blanc": 0, "Type_2_Gris": 1, "Type_3_Noir": 2}
        scatter2 = ax2.scatter(
            df_particles["PCA_1"], df_particles["PCA_2"], df_particles["PCA_3"],
            c=df_particles["Type"].map(type_colors), cmap="RdYlBu_r",
            s=30, alpha=0.6, edgecolors="black", linewidth=0.3
        )
        ax2.set_title("PCA 3D - Type Intensité", fontsize=12, fontweight="bold")

        ax3 = fig.add_subplot(133, projection="3d")
        unique_ptypes = df_particles["Particle_Type_Combined"].unique()
        ptype_to_num = {t: i for i, t in enumerate(unique_ptypes)}
        scatter3 = ax3.scatter(
            df_particles["PCA_1"], df_particles["PCA_2"], df_particles["PCA_3"],
            c=df_particles["Particle_Type_Combined"].map(ptype_to_num), cmap="tab20",
            s=30, alpha=0.6, edgecolors="black", linewidth=0.3
        )
        ax3.set_title("PCA 3D - Type Particule", fontsize=12, fontweight="bold")
        plt.tight_layout()
        plt.show()

        fig, axes = plt.subplots(1, 2, figsize=(20, 10))
        ax = axes[0]
        ax.imshow(img_rgb)
        green_square = Rectangle((x_topleft, y_topleft), square_size, square_size,
                                 linewidth=4, edgecolor="lime", facecolor="none")
        ax.add_patch(green_square)
        ax.plot(x_center, y_center, "g+", markersize=25, markeredgewidth=4)
        ax.set_title("Zone Équilibrée (Carré Vert)", fontsize=12, fontweight="bold")
        ax.axis("off")

        ax2 = axes[1]
        cluster_ids = sorted(df_particles["Cluster_Combined"].unique())
        in_best_window = (
            (df_particles["Center_X"] >= x_topleft)
            & (df_particles["Center_X"] <= x_topleft + square_size)
            & (df_particles["Center_Y"] >= y_topleft)
            & (df_particles["Center_Y"] <= y_topleft + square_size)
        )
        particles_in_best = df_particles[in_best_window]
        region_cluster_counts = particles_in_best["Cluster_Combined"].value_counts().sort_index()
        cluster_counts_in_zone = [region_cluster_counts.get(cid, 0) for cid in cluster_ids]
        ax2.bar(range(len(cluster_ids)), cluster_counts_in_zone, color=plt.cm.tab10(np.linspace(0, 1, len(cluster_ids))))
        ax2.set_xticks(range(len(cluster_ids)))
        ax2.set_xticklabels([f"Cluster {cid}" for cid in cluster_ids])
        ax2.set_title("Distribution des clusters (zone)", fontsize=12, fontweight="bold")
        ax2.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()
        plt.show()

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.hist(gray_eq.ravel(), bins=50, color="gray", alpha=0.7, edgecolor="black")
        ax.axvline(thresh1, color="blue", linestyle="--", linewidth=2, label=f"Seuil Noir-Gris ({thresh1})")
        ax.axvline(thresh2, color="green", linestyle="--", linewidth=2, label=f"Seuil Gris-Blanc ({thresh2})")
        ax.set_xlabel("Intensité (0-255)", fontweight="bold", fontsize=12)
        ax.set_ylabel("Nombre de pixels", fontweight="bold", fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    print("\n✅ Analyse détaillée terminée.")
    print(f"📁 Résultats détaillés: {output_dir}")


def parse_args():
    parser = argparse.ArgumentParser(description="Analyse Raman - Pipeline complet et analyse détaillée.")
    parser.add_argument(
        "--raw-folder",
        type=Path,
        default=None,
        help="Dossier contenant les images .jpg (par défaut: results/focus_stacking).",
    )
    parser.add_argument(
        "--results-folder",
        type=Path,
        default=None,
        help="Dossier de sortie des résultats (par défaut: results/batch_processing).",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Désactiver l'affichage des graphiques pour l'analyse détaillée.",
    )
    parser.add_argument(
        "--single-index",
        type=int,
        default=0,
        help="Index (0-based) de l'image pour l'analyse détaillée.",
    )
    parser.add_argument(
        "--skip-batch",
        action="store_true",
        help="Ignorer le traitement batch.",
    )
    return parser.parse_args()


def main():
    setup_warnings()
    args = parse_args()

    base_dir = Path(__file__).resolve().parent
    raw_folder = args.raw_folder if args.raw_folder is not None else base_dir / "results" / "focus_stacking"
    results_folder = args.results_folder if args.results_folder is not None else base_dir / "results" / "batch_processing"

    image_files = get_image_files(raw_folder)
    if not image_files:
        print("❌ Aucune image trouvée.")
        return

    ensure_results_folder(results_folder)

    if not args.skip_batch:
        batch_process_images(image_files, results_folder)

    if args.single_index < 0 or args.single_index >= len(image_files):
        print(f"⚠️  Index invalide: {args.single_index}. Utilisation de l'image 0.")
        single_index = 0
    else:
        single_index = args.single_index

    analyze_single_image(image_files[single_index], results_folder, show_plots=not args.no_plots)


if __name__ == "__main__":
    main()