"""
Envoie un email a l'equipe a chaque push sur main.

Contenu par commit :
- auteur (nom + email)
- date/heure du commit
- fichiers modifies
- diff (ce qui a change dans chaque fichier)

Declenche par le workflow .github/workflows/notify-on-push.yml
Variables d'environnement attendues (via secrets GitHub) :
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM, DEV_EMAILS
    (DEV_EMAILS = liste d'emails separes par des virgules)
"""

from __future__ import annotations

import json
import os
import smtplib
import subprocess
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

MAX_DIFF_LINES_PER_FILE = 200  # evite des emails geants sur un gros commit


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False
    )
    return result.stdout


def get_diff_for_commit(sha: str) -> str:
    """Diff complet du commit (par rapport a son parent direct)."""
    return run_git("show", "--no-color", "--pretty=format:", sha)


def get_changed_files(sha: str) -> list[str]:
    output = run_git("show", "--no-color", "--name-status", "--pretty=format:", sha)
    return [line for line in output.splitlines() if line.strip()]


def truncate_diff(diff: str) -> str:
    lines = diff.splitlines()
    if len(lines) <= MAX_DIFF_LINES_PER_FILE:
        return diff
    kept = lines[:MAX_DIFF_LINES_PER_FILE]
    kept.append(f"... (diff tronque, {len(lines) - MAX_DIFF_LINES_PER_FILE} lignes en plus)")
    return "\n".join(kept)


def build_commit_section(commit: dict, repo_url: str) -> tuple[str, str]:
    """Retourne (texte_brut, html) pour un commit."""
    sha = commit["id"]
    short_sha = sha[:7]
    author_name = commit["author"]["name"]
    author_email = commit["author"]["email"]
    timestamp = commit["timestamp"]
    message = commit["message"]
    commit_url = commit.get("url", f"{repo_url}/commit/{sha}")

    changed_files = get_changed_files(sha)
    diff = truncate_diff(get_diff_for_commit(sha))

    text = (
        f"Commit {short_sha} - {message}\n"
        f"Auteur : {author_name} <{author_email}>\n"
        f"Date   : {timestamp}\n"
        f"Lien   : {commit_url}\n"
        f"Fichiers modifies :\n"
        + "\n".join(f"  {f}" for f in changed_files)
        + "\n\nDiff :\n"
        + diff
        + "\n" + ("-" * 70) + "\n"
    )

    html = f"""
    <div style="margin-bottom:24px;padding:16px;border:1px solid #ddd;border-radius:8px;">
      <p style="margin:0 0 8px 0;"><b>Commit</b> <code>{short_sha}</code> —
         <a href="{commit_url}">{message}</a></p>
      <p style="margin:0;color:#444;">
        <b>Developpeur :</b> {author_name} ({author_email})<br>
        <b>Date :</b> {timestamp}
      </p>
      <p style="margin:8px 0 4px 0;"><b>Fichiers modifies :</b></p>
      <pre style="background:#f6f8fa;padding:8px;border-radius:6px;overflow-x:auto;">{escape(chr(10).join(changed_files))}</pre>
      <p style="margin:8px 0 4px 0;"><b>Changement :</b></p>
      <pre style="background:#0d1117;color:#c9d1d9;padding:8px;border-radius:6px;overflow-x:auto;font-size:12px;">{escape(diff)}</pre>
    </div>
    """
    return text, html


def escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> None:
    event_path = os.environ["GITHUB_EVENT_PATH"]
    with open(event_path, encoding="utf-8") as f:
        event = json.load(f)

    commits = event.get("commits", [])
    if not commits:
        print("Aucun commit dans le payload, rien a envoyer.")
        return

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo_url = f"{server_url}/{repo}"

    text_parts, html_parts = [], []
    for commit in commits:
        text, html = build_commit_section(commit, repo_url)
        text_parts.append(text)
        html_parts.append(html)

    subject = f"[{repo}] {len(commits)} nouveau(x) commit(s) sur main"
    text_body = f"Nouveaux commits sur {repo} (branche main) :\n\n" + "\n".join(text_parts)
    html_body = f"""
    <html><body style="font-family:sans-serif;">
      <h2>Nouveaux commits sur {repo} (branche main)</h2>
      {''.join(html_parts)}
    </body></html>
    """

    send_email(subject, text_body, html_body)


def send_email(subject: str, text_body: str, html_body: str) -> None:
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
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


if __name__ == "__main__":
    main()
