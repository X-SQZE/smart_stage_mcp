# Notification email a chaque push sur main

## Fichiers a ajouter au repo
- `.github/workflows/notify-on-push.yml`
- `scripts/notify_commit_email.py`

## Secrets GitHub a configurer
Dans **Settings > Secrets and variables > Actions** du repo `smart_stage_mcp` :

| Secret        | Exemple                          |
|---------------|-----------------------------------|
| `SMTP_HOST`   | `smtp.gmail.com`                  |
| `SMTP_PORT`   | `587`                             |
| `SMTP_USER`   | `votre.compte@gmail.com`          |
| `SMTP_PASS`   | mot de passe d'application (pas le mot de passe normal) |
| `EMAIL_FROM`  | `notifications@elyora.dev`        |
| `DEV_EMAILS`  | `dev1@mail.com,dev2@mail.com,dev3@mail.com` |

Pour Gmail, il faut un "mot de passe d'application" (App Password), pas le mot de passe du compte.

## Ce que recoit l'equipe
Un email par push, avec une section par commit :
- developpeur (nom + email)
- date/heure
- fichiers modifies
- diff (le code avant/apres)

## A savoir
- Le diff est tronque a 200 lignes par commit pour eviter des emails enormes — ajustable via `MAX_DIFF_LINES_PER_FILE` dans le script.
- Marche pour un push avec plusieurs commits d'un coup (boucle sur `event["commits"]`).

## Remarque de securite (hors sujet de cette demande)
`config/__init__.py` contient un `SONAR_TOKEN` en clair, commite dans le repo public. Ce token devrait etre revoque et deplace dans un secret / `.env` non versionne.
