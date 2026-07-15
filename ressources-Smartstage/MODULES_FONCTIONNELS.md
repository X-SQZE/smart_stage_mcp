# Modules Fonctionnels — SmartStage

## Module 1 — Gestion des Profils et Candidatures

Point d'entrée pour les stagiaires, via un formulaire de profil riche et structuré :

| Champ | Description |
|-------|-------------|
| Informations personnelles | Nom, prénom, email, téléphone, photo |
| Formation | Niveau d'études, établissement, spécialité, année |
| Compétences | Langages, frameworks, outils (avec niveau de maîtrise) |
| Langues | Français, anglais, arabe (niveau CECRL) |
| Expériences | Stages précédents, projets académiques |
| Portfolio | Lien GitHub, site personnel |
| Documents | Upload CV (PDF), lettre de motivation |

Un algorithme de matching analyse le profil du candidat et calcule un score de compatibilité avec chaque sujet PFA disponible.

## Module 2 — Tests Techniques et Scoring

Cœur différenciateur de la plateforme :

- **Types de questions** : QCM, vrai/faux, questions ouvertes courtes, exercices de code (pseudo-code)
- **Domaines configurables** : Développement Web, Base de données, Algorithmique, Génie Logiciel, IA/ML
- **Paramètres du test** : Durée limitée, nombre de questions, score minimal requis par domaine
- **Sécurité anti-triche** : Détection du changement d'onglet, plein écran obligatoire, randomisation des questions
- **Résultats** : Score global, score par compétence, rapport PDF exportable, classement anonymisé

### Exemple de rapport de score — Test Développement Web Full-Stack

```
Score global : 78/100
Frontend (Angular/React) : 85/100
Backend (Java/Spring) : 72/100
Base de données (SQL) : 77/100
Rang : 3e / 24 candidats
```

## Module 3 — Gestion Collaborative des Sujets PFA

Dimension participative et démocratique dans la sélection des sujets :

1. **Proposition** — Tout employé peut soumettre un sujet via une fiche structurée (titre, description, objectifs, stack technologique, niveau requis, nombre de places, encadrant proposé)
2. **Vote** — Les employés disposent d'un système de vote (upvote + commentaires) pour plébisciter les sujets les plus pertinents
3. **Validation** — La RH examine les sujets, peut les modifier et les valide officiellement
4. **Publication** — Les sujets validés sont publiés et visibles par les candidats
5. **Attribution** — Après analyse des candidatures et scores, la RH assigne un stagiaire à chaque sujet

### Cycle de vie d'un sujet

```
Proposé → En vote → Validé → En cours → Terminé → Archivé
```

## Module 4 — Archivage et Base de Connaissances

Pour chaque sujet terminé ou en cours, un dossier numérique complet est maintenu :

| Document | Contenu |
|----------|---------|
| Rapport d'avancement | Document PDF uploadé périodiquement par le stagiaire |
| Vidéo démo | Démonstration vidéo des fonctionnalités développées |
| Cahier des charges | Spécification initiale validée par l'encadrant |
| Code source | Lien vers le dépôt Git (GitHub, GitLab) |
| Jalons (Gantt) | État d'avancement en pourcentage avec dates clés |
| Évaluation finale | Note et feedback de l'encadrant |

## Module 5 — Notifications et Communication

- Notifications in-app en temps réel (WebSocket / STOMP)
- Emails automatiques à chaque changement de statut
- Rappels automatiques avant expiration des délais
- Système de messagerie interne entre encadrant et stagiaire
