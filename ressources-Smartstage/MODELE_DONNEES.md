# Modèle de Données — SmartStage

## Entités Principales

| Entité | Description | Relations |
|--------|-------------|-----------|
| User | Compte utilisateur (tous rôles) | Role, Profile |
| Profile | Profil détaillé du stagiaire | Skills, Experiences |
| Subject | Sujet PFA proposé | User, Votes |
| Vote | Vote d'un employé sur un sujet | User, Subject |
| Application | Candidature d'un stagiaire | User, Subject, TestResult |
| Test | Configuration d'un test | Questions |
| Question | Question du test | Test, Options |
| TestResult | Résultat d'un test | User, Test |
| Archive | Dossier d'archivage | Subject, Documents |
| Notification | Notification système | User |

## Attributs Clés

```
User                    Profile                 Subject
────────────────        ──────────────────      ──────────────────────
- id : Long             - id : Long             - id : Long
- email : String        - firstName : String    - title : String
- password : String     - lastName : String     - description : String
- role : Role           - phone : String        - stack : String
- createdAt : Date      - level : String        - status : SubjectStatus
                        - cvUrl : String        - places : int
+ login() : Token       + getMatchScore()       - voteCount : int
+ logout() : void       + uploadCV() : void     + validate() : void

TestResult              Application             Archive
──────────────────      ──────────────────      ──────────────────────
- id : Long             - id : Long             - id : Long
- score : int           - status : AppStatus    - videoUrl : String
- scoreByDomain : Map   - motivation : String   - docUrl : String
- rank : int            - submittedAt : Date    - progress : int
- passedAt : Date       + accept() : void       - updatedAt : Date
+ generateReport()      + reject() : void       + uploadMedia() : void
```

## Enums

```java
enum Role          { RH, EMPLOYEE, GUEST }
enum SubjectStatus { PROPOSED, VOTING, VALIDATED, IN_PROGRESS, DONE, ARCHIVED }
enum AppStatus     { PENDING, REVIEWED, ACCEPTED, REJECTED }
```

## Diagramme de Classes — Entités & Relations

```
User ──(has)──► Role (enum : RH | EMPLOYEE | GUEST)
 │
 ├──(1-1)──► Profile ──(1-*)──► Application ──(has)──► TestResult
 │                                    │
 ├──(proposes)──► Subject ◄──────────(targets)
 │                   │
 │           (receives)──► Vote ◄──(casts)── User
 │                   │
 │               SubjectStatus (enum)
 │
 ├──(receives)──► Notification
 │
 └── Application ──(1-0..1)──► Archive
```

## Relations et Cardinalités

| Relation | Type | Cardinalité |
|----------|------|-------------|
| User → Profile | Composition | 1 — 1 |
| Profile → Application | Association | 1 — * |
| Subject → Vote | Association | 1 — * |
| User → Vote | Association | 1 — * |
| TestEntity → TestResult | Composition | 1 — * |
| Application → Archive | Composition | 1 — 0..1 |
| User → Notification | Composition | 1 — * |
