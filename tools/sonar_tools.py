import os
import shutil
import subprocess
import time
import json
import zipfile
import io
import requests
import re
from config import SONAR_TOKEN, PROJECT_KEY, ORG_KEY, GITHUB_REPO, SONAR_HOST

CACHE_FILE = "sonar_cache.json"


# --- Cache ---
def read_from_cache(pr_number: int, commit_sha: str) -> dict | None:
    if not os.path.exists(CACHE_FILE):
        return None
    with open(CACHE_FILE) as f:
        cache = json.load(f)
    return cache.get(f"{pr_number}:{commit_sha}")


def save_to_cache(pr_number: int, commit_sha: str, result: dict):
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
    cache[f"{pr_number}:{commit_sha}"] = result
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


# --- Téléchargement du code de la PR ---
def fetch_pr_archive(head_sha: str, dest_dir: str):
    url = f"https://codeload.github.com/{GITHUB_REPO}/zip/{head_sha}"
    r = requests.get(url)
    r.raise_for_status()

    z = zipfile.ZipFile(io.BytesIO(r.content))
    z.extractall(dest_dir)

    extracted_folder = os.path.join(dest_dir, os.listdir(dest_dir)[0])
    for item in os.listdir(extracted_folder):
        shutil.move(os.path.join(extracted_folder, item), dest_dir)
    os.rmdir(extracted_folder)


# --- Génération du fichier de config ---
def prepare_sonar_config(dest_dir: str, pr_number: int, pr_branch: str):
    with open("config/sonar-project.properties.template") as f:
        template = f.read()

    config = template.format(
        PROJECT_KEY=f"{PROJECT_KEY}-pr{pr_number}",
        SONAR_TOKEN=SONAR_TOKEN,
    )

    with open(os.path.join(dest_dir, "sonar-project.properties"), "w") as f:
        f.write(config)


# --- Lancement du scan ---
def run_sonar_analysis_on_pr(pr_number: int, head_sha: str, pr_branch: str) -> dict:
    dest_dir = f"sonar_scan_{pr_number}"

    try:
        fetch_pr_archive(head_sha, dest_dir)
        prepare_sonar_config(dest_dir, pr_number, pr_branch)

        result = subprocess.run(
            ["sonar-scanner.bat"],
            cwd=dest_dir,
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode != 0:
            return {"status": "error", "message": result.stderr[-500:]}

        # Le ce_task_id se trouve dans ce fichier généré par le scanner
        report_task_path = os.path.join(dest_dir, ".scannerwork", "report-task.txt")
        ce_task_id = None
        if os.path.exists(report_task_path):
            with open(report_task_path) as f:
                for line in f:
                    if line.startswith("ceTaskId="):
                        ce_task_id = line.strip().split("=", 1)[1]
                        break

        return {"status": "scan_triggered", "ce_task_id": ce_task_id}

    finally:
        if os.path.exists(dest_dir):
            shutil.rmtree(dest_dir, ignore_errors=True)


# --- Polling du résultat, basé sur le ceTaskId (fiable, pas de comparaison de date) ---
def wait_for_sonar_analysis(pr_number: int, ce_task_id: str,
                             max_wait_seconds: int = 300, interval: int = 10) -> dict:
    project_key = f"{PROJECT_KEY}-pr{pr_number}"
    elapsed = 0

    # 1. Attendre que le rapport soit traité par le Compute Engine
    while elapsed < max_wait_seconds:
        r = requests.get(
            f"{SONAR_HOST}/api/ce/task",
            params={"id": ce_task_id},
            auth=(SONAR_TOKEN, "")
        )
        if r.status_code == 200:
            task_status = r.json()["task"]["status"]
            if task_status == "SUCCESS":
                break
            elif task_status == "FAILED":
                return {"status": "error", "message": "Le traitement du rapport a échoué côté serveur."}
        time.sleep(interval)
        elapsed += interval
    else:
        return {"status": "timeout", "result": None}

    # 2. Récupérer le quality gate une fois le traitement terminé
    r = requests.get(
        f"{SONAR_HOST}/api/qualitygates/project_status",
        params={"projectKey": project_key},
        auth=(SONAR_TOKEN, "")
    )
    if r.status_code == 200:
        return {"status": "ready", "result": r.json()["projectStatus"]}

    return {"status": "error", "message": f"Impossible de récupérer le quality gate (HTTP {r.status_code})."}


# --- Suppression d'un projet Sonar (utile pour forcer une re-baseline / re-scan propre) ---
def delete_sonar_project(pr_number: int) -> dict:
    project_key = f"{PROJECT_KEY}-pr{pr_number}"
    r = requests.post(
        f"{SONAR_HOST}/api/projects/delete",
        params={"project": project_key},
        auth=(SONAR_TOKEN, "")
    )
    if r.status_code in (200, 204):
        return {"status": "deleted", "project_key": project_key}
    return {"status": "error", "message": f"Suppression échouée (HTTP {r.status_code})."}


# --- Suppression d'une entrée du cache local ---
def clear_cache_entry(pr_number: int, commit_sha: str = None):
    if not os.path.exists(CACHE_FILE):
        return
    with open(CACHE_FILE) as f:
        cache = json.load(f)

    if commit_sha:
        cache.pop(f"{pr_number}:{commit_sha}", None)
    else:
        # Pas de commit_sha fourni : on retire toutes les entrées de cette PR
        keys_to_remove = [k for k in cache if k.startswith(f"{pr_number}:")]
        for k in keys_to_remove:
            cache.pop(k, None)

    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


# --- Issues détaillées (si Gate FAILED) ---
def get_sonar_issues(pr_number: int, severities: list[str] = None,
                      types: list[str] = None, limit: int = 10) -> list[dict]:
    """
    Liste les issues Sonar d'une PR.

    severities: filtre optionnel, ex. ["BLOCKER", "CRITICAL", "MAJOR"]
    types: filtre optionnel, ex. ["VULNERABILITY"], ["BUG"], ["CODE_SMELL"], ["SECURITY_HOTSPOT"]
    Si severities et types sont tous les deux None, retourne les issues sans filtre
    (triées par défaut par l'API Sonar).
    """
    project_key = f"{PROJECT_KEY}-pr{pr_number}"

    params = {
        "componentKeys": project_key,
        "ps": limit,
    }
    if severities:
        params["severities"] = ",".join(severities)
    if types:
        params["types"] = ",".join(types)

    r = requests.get(
        f"{SONAR_HOST}/api/issues/search",
        params=params,
        auth=(SONAR_TOKEN, "")
    )
    issues = r.json()["issues"]
    return [
        {"file": i["component"], "line": i.get("line"),
         "rule": i["rule"], "msg": i["message"][:80],
         "type": i.get("type"), "severity": i.get("severity")}
        for i in issues
    ]