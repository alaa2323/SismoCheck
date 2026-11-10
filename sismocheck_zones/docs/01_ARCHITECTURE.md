# Document d'architecture — SismoCheck (évaluation du risque sismique d'un bâtiment)

## 1. Présentation du projet

SismoCheck est une application web **à base de règles (Rule-Based Classification)** qui évalue le niveau de risque d'un bâtiment face aux séismes : **faible**, **moyen** ou **élevé**.
Le client indique d'abord la **zone** : si elle n'est pas exposée aux séismes, le bâtiment n'est pas évalué ; sinon, il remplit un formulaire décrivant son bâtiment et le séisme considéré. Un **moteur de règles ECA** (Event – Condition – Action) applique les règles métier définies par le Domain-Manager, puis l'application affiche le niveau de risque, un indice de 0 à 100 et les règles qui l'expliquent.

Les critères viennent du document « Critères de sécurité sismique des bâtiments » : fondation et sol, murs, déformation, toiture, nombre d'étages, ancienneté, espace entre bâtiments, stabilité des dalles. Les paramètres sismiques (magnitude, distance à l'épicentre) et le respect des normes parasismiques complètent le formulaire.

## 2. Acteurs et rôles (RBAC)

| Acteur | Rôle dans l'application | Permissions |
|---|---|---|
| Client (Customer) | Évalue ses bâtiments | Formulaire, résultat, historique, suppression de ses évaluations |
| Domain-Manager | Ingénieur en structure : définit les règles | Gérer les règles, statistiques, voir toutes les évaluations, évaluer |
| IT_ADMIN | Administrateur informatique | Gérer les comptes et les rôles, statistiques, voir toutes les évaluations |
| Administrateur | Tous les droits | Toutes les permissions, seul à attribuer le rôle Administrateur |

## 3. Architecture en trois niveaux

| Niveau (feature) | Rôle | Fichiers |
|---|---|---|
| **Présentation (Frontend)** | Pages HTML, Bootstrap, graphiques Chart.js | `templates/`, `static/style.css` |
| **Logique métier (Backend)** | Moteur de règles, services, sécurité, API REST | `engine.py`, `services.py`, `security.py`, `api.py`, `app.py`, `default_rules.py` |
| **Persistance (Persistence)** | Base SQLite, schéma, migrations | `database.py`, `seismic.db` |

Technologies : Python 3, Flask, SQLite, HTML/CSS/Bootstrap 5, Chart.js.

## 4. Modèle de classes UML

Le diagramme est écrit en Mermaid : il s'affiche directement dans le Wiki d'Azure DevOps (syntaxe `::: mermaid`). Sur GitHub ou dans un éditeur Markdown, remplacez `::: mermaid` par une ligne ` ```mermaid ` et le `:::` final par ` ``` `.

::: mermaid
classDiagram
    class User {
        +int id
        +String username
        -String passwordHash
        +Role role
        +DateTime createdAt
        +register(username, password)
        +login(username, password) bool
        +logout()
        +changePassword(old, new)
        +changeRole(role)
    }
    class Role {
        <<enumeration>>
        ADMIN
        DOMAIN_MANAGER
        IT_ADMIN
        CLIENT
        +hasPermission(permission) bool
    }
    class Zone {
        +int id
        +String name
        +String country
        +bool secure
        +String note
        +isSecure() bool
    }
    class Building {
        +int id
        +String name
        +int anneeConstruction
        +int nbEtages
        +String typeSol
        +String fondation
        +String etatMurs
        +String deformation
        +String etatToiture
        +String etatDalles
        +int espaceVoisinsCm
        +String normes
        +age() int
    }
    class Evaluation {
        +int id
        +float magnitude
        +float distanceKm
        +Level level
        +int score
        +DateTime createdAt
        +delete()
    }
    class Level {
        <<enumeration>>
        FAIBLE
        MOYEN
        ELEVE
    }
    class Rule {
        +int id
        +String name
        +String event
        +Level level
        +int points
        +String message
        +String author
        +bool active
        +matches(data) bool
        +activate()
        +deactivate()
    }
    class Condition {
        +String field
        +String operator
        +String value
        +check(data) bool
    }
    class RuleEngine {
        +evaluate(data, rules) Result
        +score(triggeredRules) int
    }
    User "1" --> "0..*" Building : possède
    Zone "1" --> "0..*" Building : contient
    User "1" --> "0..*" Evaluation : réalise
    Building "1" --> "0..*" Evaluation : est évalué par
    Evaluation "0..*" --> "0..*" Rule : règles déclenchées
    Rule "1" *-- "1..*" Condition : contient
    User --> Role : a un
    Evaluation --> Level : classé
    Rule --> Level : attribue
    RuleEngine ..> Rule : applique
    RuleEngine ..> Evaluation : produit
:::

Remarque : dans l'implémentation, les caractéristiques du bâtiment et les paramètres du séisme sont enregistrés ensemble (JSON) dans la table `buildings`, et la table `evaluations` garde le niveau, l'indice et les règles déclenchées.

## 5. Des classes aux web services (framework à base de règles)

Chaque classe participante est exposée comme un **web service REST** (JSON, authentification HTTP Basic). Les mêmes services sont utilisés par l'interface web (`services.py`).

| Classe participante | Web service | Opérations principales | Qui l'utilise |
|---|---|---|---|
| Zone | **ZoneService** `/api/zones` | GET (liste, détail), POST, PUT, DELETE | Domain-Manager, administrateur |
| Rule, Condition | **RuleService** `/api/rules` | GET (liste, détail), POST, PUT, DELETE | Domain-Manager, administrateur |
| Building, Evaluation, RuleEngine | **EvaluationService** `/api/evaluations` | POST (évaluer), GET (liste filtrée, détail), DELETE | Client |
| User, Role | **UserService** `/api/users` | GET, PATCH (rôle), DELETE | IT_ADMIN, administrateur |
| Statistiques | **StatsService** `/api/stats` | GET | Domain-Manager, IT_ADMIN, administrateur |
| — | **Service public** `/api/health`, `/api/fields` | GET | Tout client |

Le détail des appels est dans `04_API.md`.

## 6. Fonctionnement d'une évaluation en deux étapes (séquence)

1. **Étape 1, la zone** : le client indique le nom du bâtiment et choisit une zone. Si la zone est **sécurisée** (non exposée aux séismes), les critères du bâtiment ne sont pas demandés et le niveau est « faible ».
2. **Étape 2, le bâtiment** : si la zone est **exposée** (par exemple Tokyo ou Chlef), le client décrit le bâtiment et les règles ECA sont appliquées.

::: mermaid
sequenceDiagram
    actor C as Client
    participant UI as Interface web / API
    participant ES as EvaluationService
    participant RE as RuleEngine
    participant DB as Base SQLite
    C->>UI: Étape 1, nom du bâtiment et zone
    UI->>ES: zone choisie
    ES->>DB: lire la zone
    DB-->>ES: zone sécurisée ou exposée
    alt zone sécurisée
        ES->>DB: enregistrer l'évaluation (niveau faible)
        ES-->>UI: résultat sans critères du bâtiment
    else zone exposée aux séismes
        UI-->>C: Étape 2, critères du bâtiment
        C->>UI: Soumet les critères
        UI->>ES: données validées
        ES->>DB: lire les règles actives
        DB-->>ES: règles et conditions
        ES->>RE: evaluate(données, règles)
        RE-->>ES: niveau, règles déclenchées, indice
        ES->>DB: enregistrer bâtiment et évaluation
        ES-->>UI: résultat
    end
    UI-->>C: niveau de risque et explications
:::

## 7. Modèle de données

| Table | Colonnes principales |
|---|---|
| `users` | id, username, password_hash, role, created_at |
| `rules` | id, name, event, conditions (JSON), level, message, author, active, points |
| `zones` | id, name, country, secure, note |
| `buildings` | id, user_id → users, zone_id → zones, name, data (JSON), created_at |
| `evaluations` | id, building_id → buildings, user_id → users, level, score, triggered (JSON), created_at |

Une zone utilisée par des bâtiments ne peut pas être supprimée. Les suppressions sont en cascade : supprimer un utilisateur supprime ses bâtiments et ses évaluations.

## 8. Sécurité

- Mots de passe hachés (Werkzeug), jamais renvoyés par l'API.
- Contrôle d'accès par rôle sur chaque page et chaque endpoint.
- Protection CSRF sur tous les formulaires.
- Limitation des tentatives de connexion (5 échecs en 5 minutes).
- Mot de passe administrateur par défaut modifiable (page « Mon compte » ou variable `ADMIN_PASSWORD`).

## 9. DevOps

- Dépôt Git et pipeline `azure-pipelines.yml` : les tests unitaires s'exécutent à chaque modification de la branche `main`.
- 67 tests unitaires (moteur de règles, version `if / return` des règles, zones et parcours en deux étapes, pages web, API, permissions, migration de base).
- User stories, tâches et sprints : voir `03_USER_STORIES.md`. Règles : voir `02_REGLES_ECA.md`.
