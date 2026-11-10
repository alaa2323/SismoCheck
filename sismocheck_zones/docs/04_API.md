# API REST — SismoCheck

Adresse de base : `http://127.0.0.1:5000/api`. Réponses en JSON.
Authentification : **HTTP Basic** (nom d'utilisateur et mot de passe d'un compte existant), sauf `/health` et `/fields` qui sont publics.

## Endpoints

| Méthode | URL | Permission | Description |
|---|---|---|---|
| GET | `/health` | publique | Vérifie que le service fonctionne |
| GET | `/fields` | publique | Champs attendus pour une évaluation |
| GET | `/zones` | connecté | Liste des zones (statut sécurisée ou exposée) |
| GET | `/zones/{id}` | connecté | Détail d'une zone |
| POST | `/zones` | rules | Crée une zone (201) |
| PUT | `/zones/{id}` | rules | Modifie une zone (champs partiels acceptés) |
| DELETE | `/zones/{id}` | rules | Supprime une zone inutilisée (204), sinon 409 |
| GET | `/rules` | connecté | Liste des règles |
| GET | `/rules/{id}` | connecté | Détail d'une règle |
| POST | `/rules` | rules | Crée une règle (201) |
| PUT | `/rules/{id}` | rules | Modifie une règle (champs partiels acceptés, `active` possible) |
| DELETE | `/rules/{id}` | rules | Supprime une règle (204) |
| POST | `/evaluations` | evaluate | Contrôle la zone (`zone`), puis évalue le bâtiment si la zone est exposée ; enregistre le résultat (201) |
| GET | `/evaluations?q=&level=` | evaluate | Liste (les siennes, ou toutes selon le rôle) |
| GET | `/evaluations/{id}` | connecté | Détail d'une évaluation |
| DELETE | `/evaluations/{id}` | propriétaire / admin | Supprime une évaluation (204) |
| GET | `/users` | users | Liste des comptes |
| PATCH | `/users/{id}` | users | Change le rôle : `{"role": "domain_manager"}` |
| DELETE | `/users/{id}` | users | Supprime un compte (204) |
| GET | `/stats` | stats | Statistiques et données des graphiques |

Permissions par rôle : voir `01_ARCHITECTURE.md`. Codes d'erreur : 400 corps invalide, 401 non authentifié, 403 droits insuffisants, 404 introuvable, 409 conflit (zone utilisée), 422 données invalides, 429 trop de tentatives.

## Exemples (PowerShell : utilisez `curl.exe`, pas `curl`)

```
curl.exe http://127.0.0.1:5000/api/health
curl.exe -u admin:admin123 http://127.0.0.1:5000/api/rules
curl.exe -u admin:admin123 http://127.0.0.1:5000/api/stats
```

## Exemple en Python (créer une évaluation)

```python
import requests

r = requests.post(
    "http://127.0.0.1:5000/api/evaluations",
    auth=("client1", "demo123"),          # compte créé par seed_demo.py
    json={
        "building_name": "Immeuble A",
        "zone": "Chlef",                      # zone exposée : les critères du bâtiment sont obligatoires
        "annee_construction": 1975, "nb_etages": 6, "type_sol": "instable",
        "fondation": "normale", "etat_murs": "fissures_mineures", "deformation": "non",
        "etat_toiture": "bon", "etat_dalles": "bon", "espace_voisins_cm": 5,
        "normes": "non_respecte", "magnitude": 6.2, "distance_km": 18,
    },
)
print(r.status_code, r.json()["level"], r.json()["score"])
```

## Exemple : créer une règle (Domain-Manager)

```python
requests.post("http://127.0.0.1:5000/api/rules", auth=("manager", "demo123"), json={
    "name": "R13 - Immeuble très haut", "level": "moyen", "points": 15,
    "message": "Bâtiment de 10 étages ou plus : étude spécifique recommandée.",
    "conditions": [{"field": "nb_etages", "op": ">=", "value": "10"}],
})
```

## Exemple : zone sécurisée (le bâtiment n'est pas évalué)

```python
r = requests.post("http://127.0.0.1:5000/api/evaluations", auth=("client1", "demo123"),
                  json={"building_name": "Maison", "zone": "Tamanrasset"})   # aucun critère de bâtiment nécessaire
print(r.json()["level"], r.json()["building_evaluated"])   # faible False
```

Le champ `zone` accepte le nom ou l'identifiant d'une zone (liste : `GET /api/zones`). Pour une zone exposée, les critères du bâtiment sont obligatoires ; pour une zone sécurisée, ils sont ignorés.
