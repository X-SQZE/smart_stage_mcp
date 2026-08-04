"""
auto_sync_index.py — Synchronise automatiquement la base Chroma locale
avec la branche 'chroma-index' du repo distant, à intervalle régulier.

Lance ce script en arrière-plan (ou dans un terminal dédié) pendant que
tu travailles — il vérifie toutes les X secondes s'il y a du nouveau.

Usage: python auto_sync_index.py
"""

import subprocess
import shutil
import time
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import configu

CHECK_INTERVAL_SECONDS = 30  # fréquence de vérification

# Dossier séparé où on garde un clone de la branche chroma-index
SYNC_REPO_DIR = os.path.join(
    os.path.dirname(configu.BASE_DIR), "..", "PFA_chroma"
)
SYNC_REPO_DIR = os.path.abspath(SYNC_REPO_DIR)

REPO_URL = f"https://github.com/{configu.REPO_OWNER}/{configu.REPO_NAME}.git"


def ensure_repo_cloned():
    """Clone le repo (branche chroma-index) s'il n'existe pas encore localement."""
    if not os.path.exists(SYNC_REPO_DIR):
        print(f"[sync] Premier lancement — clonage de la branche chroma-index...")
        subprocess.run(
            ["git", "clone", "--branch", "chroma-index", REPO_URL, SYNC_REPO_DIR],
            check=True,
        )
    else:
        print(f"[sync] Repo de sync déjà présent : {SYNC_REPO_DIR}")


def get_local_commit():
    result = subprocess.run(
        ["git", "-C", SYNC_REPO_DIR, "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def pull_latest():
    # Force un état propre avant chaque pull, pour éviter les blocages
    # dus à des modifications locales accidentelles (ex: lecture chromadb)
    subprocess.run(
        ["git", "-C", SYNC_REPO_DIR, "reset", "--hard", "HEAD"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", SYNC_REPO_DIR, "pull", "origin", "chroma-index"],
        check=True,
    )

def sync_storage():
    """Copie le storage synchronisé vers l'emplacement lu par le serveur MCP."""
    src = os.path.join(SYNC_REPO_DIR, "llamaindex_pipeline", "storage")
    dst = configu.STORAGE_DIR

    if not os.path.exists(src):
        print(f"[sync] Aucun dossier storage trouvé dans le repo distant ({src})")
        return

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"[sync] Base Chroma locale mise à jour ({dst})")
            return
        except PermissionError:
            print(f"[sync] Fichier verrouillé (tentative {attempt}/{max_retries}), "
                  f"fermez mon_serveur.py ou Claude Desktop si le problème persiste...")
            time.sleep(3)

    print(f"[sync] Échec de la synchronisation après {max_retries} tentatives — "
          f"un processus garde le fichier ouvert.")


def main():
    ensure_repo_cloned()
    last_commit = get_local_commit()
    sync_storage()  # sync initial au démarrage
    print(f"[sync] Surveillance active — vérification toutes les {CHECK_INTERVAL_SECONDS}s")
    print(f"[sync] Commit actuel : {last_commit[:8]}")

    while True:
        time.sleep(CHECK_INTERVAL_SECONDS)
        try:
            pull_latest()
            new_commit = get_local_commit()
            if new_commit != last_commit:
                print(f"[sync] Nouveau commit détecté : {new_commit[:8]}")
                sync_storage()
                last_commit = new_commit
            else:
                print(f"[sync] Aucun changement (commit {new_commit[:8]})")
        except subprocess.CalledProcessError as e:
            print(f"[sync] Erreur pendant la synchronisation : {e}")


if __name__ == "__main__":
    main()