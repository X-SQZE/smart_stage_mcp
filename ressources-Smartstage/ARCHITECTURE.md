# Architecture Technique — SmartStage

## Architecture en Couches (Layered Architecture)

```
┌──────────────────────────────────────────────────────┐
│        Angular 17+ — SPA (Components, Services, Guards)│
└───────────────────────┬──────────────────────────────┘
                        │  HTTP / REST + WebSocket
┌───────────────────────▼──────────────────────────────┐
│     Spring Boot — REST Controllers (API Layer)        │
├───────────────────────────────────────────────────────┤
│     Spring Boot — Services (Business Logic)           │
├───────────────────────────────────────────────────────┤
│     Spring Data JPA — Repositories (Data Access)      │
├───────────────────────────────────────────────────────┤
│     PostgreSQL — Base de Données Relationnelle         │
└──────────────┬────────────────┬──────────────────────┘
               │                │
        ┌──────▼──────┐  ┌──────▼──────┐
        │    MinIO    │  │    Redis    │
        │  (Fichiers) │  │   (Cache)   │
        └─────────────┘  └─────────────┘
```

## Structure du Projet

```
smartstage/
├── 📂 backend/                          # Spring Boot Application
│   ├── src/main/java/com/smartstage/
│   │   ├── config/                      # Security, WebSocket, Redis
│   │   ├── controller/
│   │   │   ├── AuthController.java
│   │   │   ├── UserController.java
│   │   │   ├── SubjectController.java
│   │   │   ├── ApplicationController.java
│   │   │   ├── TestController.java
│   │   │   └── ArchiveController.java
│   │   ├── service/                     # Business Logic
│   │   ├── repository/                  # Spring Data JPA
│   │   ├── model/
│   │   │   ├── User.java
│   │   │   ├── Profile.java
│   │   │   ├── Subject.java
│   │   │   ├── Vote.java
│   │   │   ├── Application.java
│   │   │   ├── TestEntity.java
│   │   │   ├── TestResult.java
│   │   │   ├── Archive.java
│   │   │   └── Notification.java
│   │   ├── dto/                         # Data Transfer Objects
│   │   ├── security/                    # JWT Filter, UserDetails
│   │   └── exception/                   # Gestion des erreurs
│   ├── src/main/resources/
│   │   ├── application.yml
│   │   └── application-dev.yml
│   ├── src/test/                        # JUnit 5 + Mockito
│   ├── Dockerfile
│   └── pom.xml
│
├── 📂 frontend/                         # Angular Application
│   ├── src/app/
│   │   ├── core/                        # Guards, Interceptors, Services globaux
│   │   ├── shared/                      # Composants et pipes partagés
│   │   └── features/
│   │       ├── auth/                    # Login, Register
│   │       ├── dashboard/               # Tableau de bord RH
│   │       ├── subjects/                # Gestion des sujets PFA
│   │       ├── applications/            # Gestion des candidatures
│   │       ├── test/                    # Passage des tests
│   │       ├── profile/                 # Profil stagiaire
│   │       └── archive/                 # Base de connaissances
│   ├── Dockerfile
│   └── package.json
│
├── 📂 docs/
│   ├── smartstage_pfa.pdf               # Document LaTeX compilé (17 pages)
│   ├── smartstage_pfa.tex               # Source LaTeX
│   └── uml/                             # Diagrammes UML
│
├── 🐳 docker-compose.yml
└── 📄 README.md
```

## Sécurité & Authentification

Sécurité assurée par **Spring Security** avec stratégie **JWT** :

- **Authentification** : Login → Access Token (15 min) + Refresh Token (7 jours)
- **Autorisation** : Contrôle basé sur les rôles (`ROLE_RH`, `ROLE_EMPLOYEE`, `ROLE_GUEST`)
- **Protection des routes** : Guards Angular côté frontend + filtres JWT côté backend
- **Mots de passe** : Chiffrement BCrypt (facteur 12)
- **Tests anti-triche** : Token de session unique par tentative, invalidé après soumission

## Diagramme de Séquence — Authentification JWT

```
Stagiaire    Angular        AuthController    SpringSecurity    PostgreSQL
    │            │                │                  │               │
    │──(1)login──►│                │                  │               │
    │            │──(2)POST /auth──►│                 │               │
    │            │                │──(3)authenticate──►               │
    │            │                │                  │──(4)SELECT ──►│
    │            │                │                  │◄──(5)UserDetails─│
    │            │                │                  │                │
    │            │                │         (6) BCrypt.verify()       │
    │            │                │                  │                │
    │            │         ┌──────[alt]──────────────────────────┐   │
    │            │         │ [succès]                            │   │
    │            │         │ (7) AuthResult OK                   │   │
    │            │◄(8)generateJWT─┤                             │   │
    │◄(9){accessToken, refreshToken}                             │   │
    │            │         ├─────────────────────────────────────┤   │
    │            │         │ [échec]                             │   │
    │◄(10) 401 Unauthorized─────────────────────────────────────┤   │
    │            │         └─────────────────────────────────────┘   │
    │◄(11) Redirection Dashboard / Erreur                             │
    │──(12) GET /api/... {Bearer Token}──────────────────────────────►│
```

> Access Token signé RS256, expiration 15 min. Refresh Token valide 7 jours.

## Diagramme de Séquence — Passage d'un Test Technique

```
Stagiaire    Angular        TestController    TestService      Redis Cache
    │            │                │                │                │
    │──(1)Clic "Démarrer"──►│     │                │                │
    │            │──(2)POST /tests/{id}/start──────►                │
    │            │                │──(3)createSession(userId,testId)►│
    │            │                │                │──(4)SET session TTL──►│
    │            │                │                │◄──(5)OK────────│
    │            │                │         (6)shuffle(questions)   │
    │            │◄──(7)SessionToken + Questions aléatoires──────────│
    │◄(8){questions, timer}──┤    │                │                │
    │                        │    │                │                │
    │  [détection changement onglet — JS events]   │                │
    │                        │    │                │                │
    │──(9)Submit answers[]───►│   │                │                │
    │            │──(10)POST /tests/{id}/submit────►                │
    │            │                │──(11)validateSession + score()──►
    │            │                │         (12)calcScore(answers)  │
    │            │◄──(13)TestResult{score, rank, details}───────────│
    │            │                │──(14)saveResult(DB)             │
    │◄(15){score, rapport PDF}───┤ │                │               │
```

## Légende UML

| Symbole | Signification |
|---------|-----------------|
| → (plein) | Association / dépendance |
| ◆→ (losange) | Composition (cycle de vie lié) |
| △→ (triangle ouvert) | Héritage / Réalisation |
| 1 — * | Cardinalité un-à-plusieurs |
| «enum» | Type énuméré |
| [alt] | Bloc alternatif (if/else) |
| Barre verticale | Période d'activation du composant |
