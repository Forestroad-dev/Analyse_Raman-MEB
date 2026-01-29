#!/usr/bin/env python3
"""
Script de vérification de l'environnement pour le projet Raman
Vérifie que toutes les dépendances sont correctement installées avec les bonnes versions
"""

import sys
from pathlib import Path

def check_python_version():
    """Vérifie la version de Python"""
    version = sys.version_info
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("  ⚠️  Python 3.10+ recommandé")
        return False
    return True

def check_virtual_env():
    """Vérifie si un environnement virtuel est activé"""
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if in_venv:
        print(f"✓ Environnement virtuel actif: {sys.prefix}")
    else:
        print("✗ ATTENTION: Vous n'êtes PAS dans un environnement virtuel!")
        print(f"  Environnement actuel: {sys.prefix}")
        if "Anaconda" in sys.prefix or "conda" in sys.prefix:
            print("  ⚠️  Vous utilisez l'environnement Anaconda de base!")
            print("  → Créez un environnement virtuel avec: python -m venv .venv")
        return False
    return True

def check_package(package_name, expected_version=None, import_name=None):
    """Vérifie qu'un package est installé avec la bonne version"""
    try:
        import_name = import_name or package_name
        module = __import__(import_name)
        version = getattr(module, '__version__', 'unknown')
        
        if expected_version:
            if version.startswith(expected_version):
                print(f"✓ {package_name} {version}")
                return True
            else:
                print(f"✗ {package_name} {version} (attendu: {expected_version})")
                return False
        else:
            print(f"✓ {package_name} {version}")
            return True
            
    except ImportError:
        print(f"✗ {package_name} NON INSTALLÉ")
        return False

def main():
    """Fonction principale de vérification"""
    print("=" * 60)
    print("Vérification de l'environnement Raman Project")
    print("=" * 60)
    print()
    
    all_checks = []
    
    # Vérification Python
    print("1. Version Python:")
    all_checks.append(check_python_version())
    print()
    
    # Vérification environnement virtuel
    print("2. Environnement virtuel:")
    all_checks.append(check_virtual_env())
    print()
    
    # Vérification des packages critiques
    print("3. Packages Python:")
    packages = [
        ("numpy", "1.26", "numpy"),
        ("pandas", "2.2", "pandas"),
        ("matplotlib", "3.8", "matplotlib"),
        ("scikit-learn", "1.4", "sklearn"),
        ("scipy", "1.11", "scipy"),
        ("opencv-python", "4.8", "cv2"),
    ]
    
    for package_name, expected_version, import_name in packages:
        all_checks.append(check_package(package_name, expected_version, import_name))
    
    print()
    print("=" * 60)
    
    if all(all_checks):
        print("✓ SUCCÈS : Environnement correctement configuré!")
        print()
        print("Vous pouvez maintenant exécuter le notebook:")
        print("  notebooks/analyse_raman_structured.ipynb")
        return 0
    else:
        print("✗ ÉCHEC : Certaines vérifications ont échoué")
        print()
        print("Solutions recommandées:")
        print("1. Créer un environnement virtuel propre:")
        print("   python -m venv .venv")
        print("   .venv\\Scripts\\Activate.ps1  (Windows)")
        print()
        print("2. Installer les dépendances:")
        print("   pip install -r requirements.txt")
        print()
        print("3. Vérifier NumPy:")
        print("   python -c \"import numpy; print(numpy.__version__)\"")
        return 1

if __name__ == "__main__":
    sys.exit(main())
