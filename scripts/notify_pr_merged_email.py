"""
Envoie un email a l'equipe quand une Pull Request est mergee dans main.

Email court et professionnel : titre de la PR, developpeur, date de merge,
depot, lien vers la PR, fichiers modifies, et un resume genere par IA
(pas de diff, pas de code brut).

Declenche par .github/workflows/notify-on-pr-merged.yml, uniquement pour
les PR fermees avec merged == true (le workflow filtre deja les PR
fermees sans merge via sa condition `if:`, ce script revalide par securite).

Variables d'environnement attendues :
    GITHUB_EVENT_PATH, GITHUB_REPOSITORY, GITHUB_SERVER_URL, GITHUB_TOKEN
    GEMINI_API_KEY (optionnelle, pour le resume IA)
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM, DEV_EMAILS
"""

from __future__ import annotations

import json
import os
import smtplib
import sys
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

GITHUB_API = "https://api.github.com"
MAX_FILES_LISTED = 30
REQUEST_TIMEOUT = 20


@dataclass
class PullRequestInfo:
    number: int
    title: str
    url: str
    body: str
    author_login: str
    author_name: str
    author_email: str
    merged_at: str
    repo_full_name: str


# --- 1. Charger l'evenement GitHub -----------------------------------------

def load_pr_event() -> dict:
    event_path = os.environ["GITHUB_EVENT_PATH"]
    with open(event_path, encoding="utf-8") as f:
        return json.load(f)


def is_merged_pr(event: dict) -> bool:
    pr = event.get("pull_request", {})
    return bool(pr.get("merged") is True)


# --- 2. Extraire les infos de la PR -----------------------------------------

def github_headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}" if token else "",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_last_commit_identity(repo: str, pr_number: int) -> tuple[str, str]:
    """Nom/email 'git' reels du dernier commit de la PR (plus fiable que le
    profil GitHub, dont l'email public peut etre masque)."""
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/commits"
    response = requests.get(url, headers=github_headers(), timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    commits = response.json()
    if not commits:
        return "", ""
    author = commits[-1]["commit"]["author"]
    return author.get("name", ""), author.get("email", "")


def extract_pr_info(event: dict, repo: str) -> PullRequestInfo:
    pr = event["pull_request"]
    number = pr["number"]
    name, email = get_last_commit_identity(repo, number)
    return PullRequestInfo(
        number=number,
        title=pr["title"],
        url=pr["html_url"],
        body=pr.get("body") or "",
        author_login=pr["user"]["login"],
        author_name=name or pr["user"]["login"],
        author_email=email or "non renseigne",
        merged_at=pr["merged_at"],
        repo_full_name=repo,
    )


# --- 3. Recuperer les fichiers modifies -------------------------------------

def get_changed_files(repo: str, pr_number: int) -> list[str]:
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/files"
    files: list[str] = []
    page = 1
    while True:
        response = requests.get(
            url,
            headers=github_headers(),
            params={"per_page": 100, "page": page},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        files.extend(item["filename"] for item in batch)
        if len(batch) < 100:
            break
        page += 1
    return files


# --- 4. Generer le resume IA ------------------------------------------------

def generate_summary(pr_info: PullRequestInfo, files: list[str]) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        summary = _generate_summary_with_gemini(api_key, pr_info, files)
        if summary:
            return summary
    return _fallback_summary(pr_info, files)


def _generate_summary_with_gemini(
    api_key: str, pr_info: PullRequestInfo, files: list[str]
) -> str | None:
    prompt = (
        "Resume en francais, en 2 a 4 phrases maximum, ce qu'apporte cette "
        "Pull Request pour un email d'equipe. Explique le but du changement "
        "(ajout, suppression, correction, amelioration), sans citer de code.\n\n"
        f"Titre : {pr_info.title}\n"
        f"Description : {pr_info.body[:1500]}\n"
        f"Fichiers modifies : {', '.join(files[:MAX_FILES_LISTED])}"
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={api_key}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (requests.RequestException, KeyError, IndexError) as exc:
        print(f"Resume IA indisponible, fallback utilise ({exc})", file=sys.stderr)
        return None


def _fallback_summary(pr_info: PullRequestInfo, files: list[str]) -> str:
    file_count = len(files)
    plural = "s" if file_count > 1 else ""
    return (
        f"Cette Pull Request modifie {file_count} fichier{plural}. "
        f"Titre : {pr_info.title}."
    )


# --- 5. Construire l'email ---------------------------------------------------

def build_email(pr_info: PullRequestInfo, files: list[str], summary: str) -> tuple[str, str, str]:
    subject = f"[{pr_info.repo_full_name}] PR #{pr_info.number} mergee dans main"

    file_list_text = "\n".join(f"- {f}" for f in files[:MAX_FILES_LISTED])
    extra_files = len(files) - MAX_FILES_LISTED
    if extra_files > 0:
        file_list_text += f"\n... et {extra_files} autre(s) fichier(s)"

    text_body = f"""SmartStage Notification
Une Pull Request a ete mergee dans main.

Developpeur : {pr_info.author_name} ({pr_info.author_email})
Repository : {pr_info.repo_full_name}
Mergee le : {pr_info.merged_at}
Pull Request : #{pr_info.number} - {pr_info.title}
Lien : {pr_info.url}

Fichiers modifies :
{file_list_text}

Resume :
{summary}
"""

    file_list_html = "".join(f"<li>{f}</li>" for f in files[:MAX_FILES_LISTED])
    if extra_files > 0:
        file_list_html += f"<li>... et {extra_files} autre(s) fichier(s)</li>"

    html_body = f"""
    <html><body style="font-family:sans-serif;color:#1f1f1f;">
      <h2 style="margin-bottom:0;">SmartStage Notification</h2>
      <p style="color:#555;margin-top:4px;">Une Pull Request a ete mergee dans main.</p>

      <table style="border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:4px 12px 4px 0;color:#666;">Developpeur</td>
            <td>{pr_info.author_name} ({pr_info.author_email})</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666;">Repository</td>
            <td>{pr_info.repo_full_name}</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666;">Mergee</td>
            <td>{pr_info.merged_at}</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666;">Pull Request</td>
            <td><a href="{pr_info.url}">#{pr_info.number} - {pr_info.title}</a></td></tr>
      </table>

      <p style="margin-bottom:4px;"><b>Fichiers modifies :</b></p>
      <ul>{file_list_html}</ul>

      <p style="margin-bottom:4px;"><b>Resume :</b></p>
      <p style="color:#333;">{summary}</p>
    </body></html>
    """

    return subject, text_body, html_body


# --- 6. Envoyer l'email -------------------------------------------------------

def send_email(subject: str, text_body: str, html_body: str) -> None:
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT") or "587")
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    email_from = os.environ.get("EMAIL_FROM", smtp_user)
    recipients = [e.strip() for e in os.environ["DEV_EMAILS"].split(",") if e.strip()]

    if not recipients:
        print("DEV_EMAILS est vide, aucun destinataire.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(email_from, recipients, msg.as_string())

    print(f"Email envoye a : {', '.join(recipients)}")


# --- Orchestration -------------------------------------------------------------

def main() -> None:
    event = load_pr_event()

    if not is_merged_pr(event):
        print("PR fermee sans merge, aucune notification envoyee.")
        return

    repo = os.environ["GITHUB_REPOSITORY"]
    pr_info = extract_pr_info(event, repo)
    files = get_changed_files(repo, pr_info.number)
    summary = generate_summary(pr_info, files)
    subject, text_body, html_body = build_email(pr_info, files, summary)
    send_email(subject, text_body, html_body)


if __name__ == "__main__":
    main()
