# SismoCheck — évaluation du risque sismique d'un bâtiment

Application web à base de règles (Rule-Based Classification, ECA) : Python/Flask, SQLite, Bootstrap, API REST.

## Lancer l'application (Windows, PyCharm)
1. Extraire le zip, puis dans PyCharm : **File > Open** et choisir le dossier `seismic_app` (celui qui contient `app.py`).
2. Dans le Terminal de PyCharm :
```
python -m pip install -r requirements.txt
python app.py
```
3. Ouvrir http://127.0.0.1:5000

Compte administrateur créé au premier lancement : `admin` / `admin123`. Changez-le dans **Mon compte**, ou définissez `ADMIN_PASSWORD` avant le premier lancement.
Une connexion Internet est nécessaire pour l'affichage complet (Bootstrap, icônes, Chart.js, police).

## Données de démonstration (soutenance)
```
python seed_demo.py
```
Crée 4 comptes (mot de passe `demo123`) : `manager` (Domain-Manager), `itadmin` (IT_ADMIN), `client1` et `client2` (Clients), et 40 évaluations réparties sur 30 jours (zones sécurisées et exposées).

## Rôles
| Rôle | Peut |
|---|---|
| Client | Évaluer un bâtiment, voir/supprimer ses évaluations, imprimer un rapport PDF |
| Domain-Manager | Gérer les règles et les zones, voir statistiques et toutes les évaluations |
| IT_ADMIN | Gérer comptes et rôles, voir statistiques et toutes les évaluations |
| Administrateur | Tout (seul à attribuer le rôle Administrateur) |

Les comptes créés depuis la page d'inscription sont des Clients ; l'IT_ADMIN ou l'administrateur change les rôles depuis **Utilisateurs**.

## Fonctionnalités
- **Évaluation en deux étapes** : (1) le client choisit la **zone** ; si elle est sécurisée (non exposée aux séismes), le bâtiment n'est pas évalué et le risque est « faible » ; (2) si elle est exposée (Tokyo, Chlef…), il décrit le bâtiment et les règles s'appliquent.
- Table des **zones** gérée par le Domain-Manager (page **Zones** ou API `/api/zones`).
- Formulaire de 12 champs, classification faible / moyen / élevé et indice de risque sur 100.
- 12 règles ECA par défaut (Python), modifiables dans l'interface ou par l'API.
- Tableau de bord : cartes, graphique sur 30 jours, jauge de répartition, règles les plus déclenchées.
- Historique avec recherche et filtre, suppression, impression en PDF (bouton **Imprimer / PDF**).
- API REST (voir `docs/04_API.md`), sécurité : CSRF, limitation des tentatives de connexion, mots de passe hachés.

## Tests
```
python -m unittest discover -s tests -v
```
67 tests : moteur de règles, version `if / return`, zones et parcours en deux étapes, pages web, permissions, API, migration d'ancienne base.

## Structure
| Fichier | Rôle |
|---|---|
| `app.py` | Routes de l'interface web |
| `api.py` | API REST (Blueprint) |
| `engine.py` | Moteur de règles ECA, champs, score |
| `default_rules.py` | 12 règles par défaut (format ECA, données) |
| `default_zones.py` | Zones par défaut (exemples à valider) |
| `rules.py` | Les mêmes 12 règles en style `if / return` (fonction `seismic_risk`), vérifiées identiques au moteur |
| `services.py` | Logique métier partagée (évaluations, règles, statistiques) |
| `security.py` | Rôles, permissions, CSRF, limitation des tentatives |
| `database.py` | Schéma SQLite, migrations, données initiales |
| `templates/`, `static/` | Pages et style |
| `tests/` | Tests unitaires |
| `docs/` | Architecture + UML, règles ECA, user stories, API |
| `azure-pipelines.yml` | Pipeline Azure DevOps (tests automatiques) |

## Variables d'environnement (facultatives)
`SECRET_KEY` (clé de session), `ADMIN_PASSWORD` (mot de passe admin initial), `DATABASE` (chemin de la base), `FLASK_DEBUG=1` (rechargement automatique pendant le développement).
