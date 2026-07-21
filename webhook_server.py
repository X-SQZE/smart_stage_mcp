from fastapi import FastAPI, Request, Header, HTTPException
import hmac
import hashlib
import re
import sys
import requests
import config
sys.path.insert(0, '.')
from config import GITHUB_WEBHOOK_SECRET
from mon_serveur import (
    check_merge_conflicts,
    get_ci_status,
    run_sonar_scan,
    detect_breaking_changes,
    post_pr_comment,
    traiter_merge_pr,
    jira_commenter_ticket,
)

app = FastAPI()

def notify_ticket_blocked(issue_key: str, pr_number: int, pr_url: str):
    """Informe le développeur (sur Jira ET sur GitHub) que le ticket est bloqué."""
    try:
        jira_commenter_ticket(
            issue_key=issue_key,
            commentaire=(
                f"⚠️ Ce ticket est marqué comme bloqué. La PR {pr_url} semble prête "
                f"(vérifications automatiques passées), mais la clôture automatique "
                f"a été suspendue. Un administrateur doit lever le blocage manuellement."
            ),
        )
    except Exception as e:
        print(f"[WARN] Échec du commentaire Jira sur {issue_key} : {e}")

    try:
        post_pr_comment(
            pr_number,
            f"ℹ️ Cette PR est prête à merger, mais le ticket Jira **{issue_key}** lié "
            f"est actuellement bloqué par un administrateur — la clôture automatique "
            f"a été suspendue. Contacte ton administrateur si ce blocage semble être une erreur.",
        )
    except Exception as e:
        print(f"[WARN] Échec du commentaire GitHub sur PR #{pr_number} : {e}")


def extract_issue_key(title: str, branch_name: str) -> str | None:
    """Cherche un pattern type 'KAN-123' dans le titre ou le nom de branche de la PR."""
    pattern = r"[A-Z]+-\d+"
    match = re.search(pattern, title or "") or re.search(pattern, branch_name or "")
    return match.group(0) if match else None


def process_merge_with_jira_guard(issue_key: str, pr_number: int, pr_url: str, titre_pr: str, nom_branche: str):
    """
    Enveloppe traiter_merge_pr() avec le garde-fou de blocage.
    """
    if is_ticket_blocked(issue_key):
        notify_ticket_blocked(issue_key, pr_number, pr_url)
        return {"status": "skipped", "reason": "ticket_blocked", "issue_key": issue_key}

    return traiter_merge_pr(
        nom_branche=nom_branche,
        pr_number=pr_number,
        pr_url=pr_url,
        titre_pr=titre_pr,
    )


# --- Logique de vérification de mergeabilité ---

def evaluate_pr_mergeability(pr_number: int) -> dict:
    report = {"pr_number": pr_number, "blockers": [], "warnings": [], "mergeable": None}

    conflicts = check_merge_conflicts(pr_number)
    if conflicts.get("has_conflicts"):
        report["blockers"].append("Conflits de merge non résolus")

    ci_status = get_ci_status(pr_number)
    if ci_status.get("status") not in ("success", "SUCCESS"):
        report["blockers"].append(f"CI non passante : {ci_status.get('status')}")

    sonar_result = run_sonar_scan(pr_number)
    if sonar_result.get("quality_gate") == "ERROR":
        report["blockers"].append("Quality Gate Sonar en échec")
        report["sonar_issues"] = sonar_result.get("issues", [])

    breaking = detect_breaking_changes(pr_number)
    if breaking.get("detected"):
        report["warnings"].append("Breaking changes potentiels détectés")

    report["mergeable"] = len(report["blockers"]) == 0
    return report


# --- Routes ---

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
):
    body = await request.body()
    verify_signature(body, x_hub_signature_256)
    payload = await request.json()

    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"event {x_github_event} non géré"}

    action = payload.get("action")
    print(f"[DEBUG] Événement reçu : action={action}")  # à retirer une fois le debug terminé

    pr = payload["pull_request"]
    pr_number = pr["number"]

    if action in ("opened", "synchronize", "reopened"):
        report = evaluate_pr_mergeability(pr_number)
        print(f"[DEBUG] Rapport de mergeabilité : {report}")  # à retirer une fois le debug terminé

        if report["mergeable"]:
            message = "✅ Vérification automatique : CI verte, Quality Gate Sonar OK, pas de conflits."
            if report["warnings"]:
                message += "\n\n⚠️ Points d'attention :\n- " + "\n- ".join(report["warnings"])
        else:
            message = "❌ Cette PR n'est pas mergeable en l'état :\n- " + "\n- ".join(report["blockers"])

        print(f"[DEBUG] Message qui sera posté : {message!r}")  # à retirer une fois le debug terminé
        post_pr_comment(pr_number, message)
        return {"status": "evaluated", "mergeable": report["mergeable"]}

    if action == "closed" and pr.get("merged"):
        issue_key = extract_issue_key(pr["title"], pr["head"]["ref"])

        if not issue_key:
            return {"status": "ignored", "reason": "aucun ticket Jira identifié dans cette PR"}

        result = process_merge_with_jira_guard(
            issue_key=issue_key,
            pr_number=pr_number,
            pr_url=pr["html_url"],
            titre_pr=pr["title"],
            nom_branche=pr["head"]["ref"],
        )
        return {"status": "merge_processed", "result": result}

    return {"status": "ignored", "reason": f"action {action} non gérée"}