# API Endpoints — SmartStage

> Documentation interactive complète via Swagger UI : `http://localhost:8080/swagger-ui.html`

## Authentification

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/auth/register` | Inscription (stagiaire) |
| POST | `/api/auth/login` | Connexion → `{accessToken, refreshToken}` |
| POST | `/api/auth/refresh` | Renouveler le token |
| POST | `/api/auth/logout` | Déconnexion |

## Utilisateurs & Profils

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/users/me` | Profil connecté |
| PUT | `/api/users/me` | Modifier son profil |
| POST | `/api/users/me/cv` | Upload CV (PDF) |
| GET | `/api/users` | Liste utilisateurs (RH uniquement) |

## Sujets PFA

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/subjects` | Liste des sujets disponibles |
| POST | `/api/subjects` | Créer un sujet (Employé) |
| GET | `/api/subjects/{id}` | Détail d'un sujet |
| PUT | `/api/subjects/{id}` | Modifier un sujet |
| PATCH | `/api/subjects/{id}/validate` | Valider un sujet (RH) |
| POST | `/api/subjects/{id}/vote` | Voter pour un sujet (Employé) |
| DELETE | `/api/subjects/{id}/vote` | Retirer son vote |

## Candidatures

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/applications` | Mes candidatures / toutes (RH) |
| POST | `/api/applications` | Postuler à un sujet |
| GET | `/api/applications/{id}` | Détail d'une candidature |
| PATCH | `/api/applications/{id}` | Changer le statut (accept/reject — RH) |

## Tests Techniques

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/tests` | Liste des tests configurés |
| POST | `/api/tests` | Créer un test (RH) |
| POST | `/api/tests/{id}/start` | Démarrer une session de test |
| POST | `/api/tests/{id}/submit` | Soumettre les réponses |
| GET | `/api/tests/{id}/result` | Voir son résultat et rapport |

## Archives

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/archives` | Base de connaissances complète |
| GET | `/api/archives/{subjectId}` | Archive d'un sujet |
| POST | `/api/archives/{subjectId}/documents` | Uploader un document/vidéo |
