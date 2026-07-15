# SmartStage

Plateforme web full-stack de gestion du cycle de vie complet des stages PFA (Projets de Fin d'Année) : candidatures, tests techniques, proposition/vote de sujets, suivi et archivage.

## 🌍 Contexte & Problématique

Les entreprises manquent d'outils centralisés pour :
- Collecter et évaluer objectivement les candidatures de stagiaires
- Impliquer les équipes techniques dans la proposition et la sélection des sujets PFA
- Archiver et capitaliser sur les travaux des promotions précédentes

**Problématique centrale** : Comment concevoir une plateforme unifiée qui permette de gérer, de manière transparente et efficace, l'ensemble du cycle de vie des candidatures de stage et des sujets PFA — depuis la soumission jusqu'à l'archivage — tout en impliquant les différentes parties prenantes ?

## 🎯 Objectifs

| # | Objectif | Description |
|---|----------|--------------|
| O1 | Centraliser | Gestion des candidatures sur une plateforme unique |
| O2 | Automatiser | Évaluation des candidats via tests techniques configurables |
| O3 | Démocratiser | Proposition des sujets PFA via vote collaboratif |
| O4 | Archiver | Capitaliser sur les projets des années précédentes |
| O5 | Assurer | Suivi en temps réel de l'avancement des stages |

## 🛠️ Stack Technologique

| Couche | Technologie | Justification |
|--------|-------------|----------------|
| Backend | Spring Boot 3.x | Robuste, sécurisé, écosystème Java mature |
| Frontend | Angular 17+ | SPA puissante, typage TypeScript, RxJS |
| Base de données | PostgreSQL 15 | Relationnel, performant, JSONB flexible |
| Authentification | Spring Security + JWT | Gestion des rôles, tokens sans état |
| Stockage fichiers | MinIO / AWS S3 | Stockage objet pour vidéos et PDFs |
| Temps réel | WebSocket (STOMP) | Notifications live sans polling |
| Cache | Redis | Sessions, rate limiting des tests |
| Conteneurisation | Docker + Compose | Portabilité, déploiement simplifié |
| Tests Backend | JUnit 5 + Mockito | Couverture unitaire et intégration |
| Tests Frontend | Jasmine + Karma | Tests de composants Angular |

## 🚀 Installation & Lancement

### Prérequis
- Java 17+
- Node.js 18+ & npm 9+
- Docker & Docker Compose
- Maven 3.8+

### Option 1 — Docker Compose (Recommandé)
```bash
git clone https://github.com/votre-username/smartstage.git
cd smartstage

cp .env.example .env
# Éditer .env selon votre configuration

docker compose up -d
```
- Frontend → http://localhost:4200
- Backend → http://localhost:8080
- Swagger → http://localhost:8080/swagger-ui.html
- MinIO → http://localhost:9001

### Option 2 — Lancement Manuel
```bash
# Backend — Spring Boot
cd backend
docker compose -f docker-compose.dev.yml up -d postgres redis minio
./mvnw spring-boot:run -Dspring-boot.run.profiles=dev

# Frontend — Angular
cd frontend
npm install
ng serve --open   # → http://localhost:4200
```

## 🔐 Variables d'Environnement

```env
# Base de données
POSTGRES_DB=smartstage_db
POSTGRES_USER=smartstage_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_PORT=5432

# JWT
JWT_SECRET=your_very_long_jwt_secret_key_minimum_256_bits
JWT_EXPIRATION=900000            # 15 minutes (ms)
JWT_REFRESH_EXPIRATION=604800000 # 7 jours (ms)

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# MinIO
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET=smartstage-files

# Email (SMTP)
MAIL_HOST=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your@email.com
MAIL_PASSWORD=your_app_password

# Application
APP_BASE_URL=http://localhost:4200
BACKEND_PORT=8080
FRONTEND_PORT=4200
```

## 🧪 Tests

```bash
# Tests backend (JUnit 5 + Mockito)
cd backend
./mvnw test
./mvnw verify   # Rapport JaCoCo → target/site/jacoco/index.html

# Tests frontend (Jasmine + Karma)
cd frontend
ng test
```

## 📚 Documentation associée

- [ARCHITECTURE.md](./ARCHITECTURE.md) — architecture technique, structure projet, modèle de données, sécurité
- [ROLES_UTILISATEURS.md](./ROLES_UTILISATEURS.md) — rôles et fonctionnalités par utilisateur
- [MODULES_FONCTIONNELS.md](./MODULES_FONCTIONNELS.md) — description détaillée des modules
- [MODELE_DONNEES.md](./MODELE_DONNEES.md) — entités, relations, diagrammes UML
- [API_ENDPOINTS.md](./API_ENDPOINTS.md) — liste des endpoints REST
- [PLANNING_LIVRABLES.md](./PLANNING_LIVRABLES.md) — planning, livrables, valeur ajoutée

## ⭐ Valeur Ajoutée & Originalité

| Fonctionnalité | Apport concret |
|-----------------|------------------|
| Tests automatisés | Évaluation objective et standardisée, sans biais humain |
| Matching automatique | Recommandation candidat-sujet selon le profil déclaré |
| Vote collaboratif | Implication des équipes techniques dans le choix des sujets |
| Archivage enrichi | Vidéo + docs + état d'avancement pour capitaliser le savoir |
| Suivi temps réel | WebSocket pour un suivi instantané sans rechargement |
| Multi-rôles | Interface adaptée à chaque profil utilisateur |

## 👤 Auteur

[Votre Nom] — Étudiant en Génie Logiciel — Promotion [Année]
📧 votre.email@etudiant.ma · 🔗 LinkedIn · GitHub

**Encadrant** : [Nom de l'encadrant]
**Établissement** : [Nom de l'établissement]
**Année universitaire** : 2024 – 2025
