# Notification email sur PR mergee (main)

## Fichiers a ajouter au repo
- `.github/workflows/notify-on-pr-merged.yml`
- `scripts/notify_pr_merged_email.py`
(supprime les anciens `notify-on-push.yml` / `notify_commit_email.py` si presents)

## Declencheur
`pull_request` avec `types: [closed]` + condition `if: github.event.pull_request.merged == true`.
Une PR fermee sans merge (rejetee) ne declenche rien — le job entier est skip.

## Secrets GitHub a configurer
| Secret          | Usage                                    |
|------------------|-------------------------------------------|
| `SMTP_HOST`     | serveur SMTP (ex. `smtp.gmail.com`)       |
| `SMTP_PORT`     | ex. `587`                                 |
| `SMTP_USER`     | compte SMTP                                |
| `SMTP_PASS`     | mot de passe d'application                 |
| `EMAIL_FROM`    | adresse d'expedition                       |
| `DEV_EMAILS`    | emails de l'equipe, separes par des virgules |
| `GEMINI_API_KEY`| optionnel, pour le resume IA (deja utilise ailleurs dans le projet) |

`GITHUB_TOKEN` est fourni automatiquement par GitHub Actions, rien a configurer.

## Comportement du resume IA
Le script appelle Gemini pour generer 2-4 phrases a partir du titre, de la description
et des fichiers modifies. Si `GEMINI_API_KEY` est absent ou l'appel echoue, un resume
de secours (sans IA) est genere automatiquement — le workflow ne casse jamais pour ca.

## Structure du script
`notify_pr_merged_email.py` est decoupe en etapes independantes :
`load_pr_event` -> `extract_pr_info` -> `get_changed_files` -> `generate_summary`
-> `build_email` -> `send_email`.
