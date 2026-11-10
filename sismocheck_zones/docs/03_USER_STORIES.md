# User stories, features, sprints et tâches (Azure DevOps)

Les user stories sont classées sous les **3 features** : Frontend (présentation), Backend (logique métier) et Persistence (données).
Sprint 1 : US1 à US5. Sprint 2 : US6 à US12. Chaque user story a 3 tâches de développement et 1 tâche de tests unitaires.
Chaque développeur et chaque testeur saisit ses tâches sous son nom dans Azure DevOps, puis met à jour *Remaining* et *Completed* chaque jour.

## Feature : Frontend

### US2 — Remplir le formulaire d'évaluation d'un bâtiment

**En tant que** client, **je veux** décrire mon bâtiment (âge, sol, fissures, normes, magnitude, distance…).
**Sprint 1** · Feature Frontend · 11 h estimées

Critères d'acceptation :
- 12 champs affichés avec listes de choix et bornes
- Les valeurs saisies sont conservées en cas d'erreur
- Les erreurs indiquent le champ à corriger

| Tâche | Type | Estimation (h) | Remaining (h) | Completed (h) | Assignée à |
|---|---|---|---|---|---|
| Page evaluate.html avec Bootstrap (12 champs) | Développement | 4 | 4 | 0 | À assigner |
| Validation côté serveur (bornes, choix autorisés) | Développement | 3 | 3 | 0 | À assigner |
| Messages d'erreur et conservation des valeurs | Développement | 2 | 2 | 0 | À assigner |
| Tests de validation du formulaire | Tests unitaires | 2 | 2 | 0 | À assigner |

### US4 — Voir le résultat avec les explications

**En tant que** client, **je veux** comprendre pourquoi mon bâtiment est classé à ce niveau.
**Sprint 1** · Feature Frontend · 12 h estimées

Critères d'acceptation :
- Le niveau est affiché avec une jauge colorée
- Chaque règle déclenchée est listée avec son message
- L'indice de risque sur 100 est affiché

| Tâche | Type | Estimation (h) | Remaining (h) | Completed (h) | Assignée à |
|---|---|---|---|---|---|
| Page result.html : niveau et jauge | Développement | 4 | 4 | 0 | À assigner |
| Liste des règles déclenchées avec explications | Développement | 3 | 3 | 0 | À assigner |
| Indice de risque 0-100 et barre de progression | Développement | 3 | 3 | 0 | À assigner |
| Tests d'affichage du résultat | Tests unitaires | 2 | 2 | 0 | À assigner |

### US8 — Consulter un tableau de bord de statistiques

**En tant que** administrateur, **je veux** suivre l'activité et la répartition des risques.
**Sprint 2** · Feature Frontend · 13 h estimées

Critères d'acceptation :
- Cartes : évaluations, risque élevé, utilisateurs, règles actives
- Graphique des évaluations sur 30 jours
- Jauge de répartition faible / moyen / élevé
- Règles les plus déclenchées

| Tâche | Type | Estimation (h) | Remaining (h) | Completed (h) | Assignée à |
|---|---|---|---|---|---|
| Calcul des statistiques (compute_stats) | Développement | 3 | 3 | 0 | À assigner |
| Cartes avec mini-courbes | Développement | 4 | 4 | 0 | À assigner |
| Graphique 30 jours et jauge de répartition | Développement | 4 | 4 | 0 | À assigner |
| Tests de rendu du tableau de bord et des statistiques | Tests unitaires | 2 | 2 | 0 | À assigner |

## Feature : Backend

### US1 — Créer un compte et me connecter

**En tant que** visiteur, **je veux** accéder à l'application de façon sécurisée.
**Sprint 1** · Feature Backend · 11 h estimées

Critères d'acceptation :
- Nom d'utilisateur de 3 à 30 caractères et mot de passe d'au moins 6 caractères
- Mot de passe stocké haché
- Après 5 échecs, la connexion est bloquée temporairement

| Tâche | Type | Estimation (h) | Remaining (h) | Completed (h) | Assignée à |
|---|---|---|---|---|---|
| Route d'inscription avec validation | Développement | 3 | 3 | 0 | À assigner |
| Connexion / déconnexion avec session et hachage du mot de passe | Développement | 3 | 3 | 0 | À assigner |
| Limitation des tentatives de connexion | Développement | 2 | 2 | 0 | À assigner |
| Tests unitaires inscription, connexion et blocage | Tests unitaires | 3 | 3 | 0 | À assigner |

### US3 — Classer automatiquement le bâtiment avec le moteur de règles ECA

**En tant que** client, **je veux** obtenir un niveau de risque faible, moyen ou élevé.
**Sprint 1** · Feature Backend · 14 h estimées

Critères d'acceptation :
- Les conditions d'une règle sont reliées par ET
- Le niveau final est le plus grave des règles déclenchées
- Les règles désactivées sont ignorées

| Tâche | Type | Estimation (h) | Remaining (h) | Completed (h) | Assignée à |
|---|---|---|---|---|---|
| Modéliser une règle ECA (event, conditions, action) | Développement | 3 | 3 | 0 | À assigner |
| Évaluer une condition avec les opérateurs ==, !=, >, <, >=, <= | Développement | 3 | 3 | 0 | À assigner |
| Fonction evaluate : niveau final et règles déclenchées | Développement | 4 | 4 | 0 | À assigner |
| Tests des règles et des cas limites | Tests unitaires | 4 | 4 | 0 | À assigner |

### US6 — Gérer les règles métier

**En tant que** Domain-Manager, **je veux** ajouter, modifier, désactiver ou supprimer des règles sans toucher au code.
**Sprint 2** · Feature Backend · 13 h estimées

Critères d'acceptation :
- Une règle valide est appliquée dès l'évaluation suivante
- Une règle invalide (champ, valeur ou opérateur incorrect) est refusée avec un message
- Les points de la règle sont modifiables (0 à 100)

| Tâche | Type | Estimation (h) | Remaining (h) | Completed (h) | Assignée à |
|---|---|---|---|---|---|
| Routes créer, modifier, supprimer, activer | Développement | 4 | 4 | 0 | À assigner |
| Validation des règles (validate_rule) | Développement | 3 | 3 | 0 | À assigner |
| Formulaire de règle avec 5 conditions et points | Développement | 3 | 3 | 0 | À assigner |
| Tests CRUD et validation des règles | Tests unitaires | 3 | 3 | 0 | À assigner |

### US7 — Gérer les comptes et les rôles

**En tant que** IT_ADMIN, **je veux** contrôler qui peut faire quoi (RBAC).
**Sprint 2** · Feature Backend · 12 h estimées

Critères d'acceptation :
- 4 rôles : Administrateur, Domain-Manager, IT_ADMIN, Client
- Un utilisateur ne peut pas modifier son propre rôle
- Seul un administrateur attribue le rôle Administrateur
- Accès interdit (403) sans la permission

| Tâche | Type | Estimation (h) | Remaining (h) | Completed (h) | Assignée à |
|---|---|---|---|---|---|
| Matrice rôles / permissions | Développement | 3 | 3 | 0 | À assigner |
| Page de gestion des utilisateurs (rôle, suppression) | Développement | 3 | 3 | 0 | À assigner |
| Contrôles de sécurité sur les changements de rôle | Développement | 2 | 2 | 0 | À assigner |
| Tests des permissions pour les 4 rôles | Tests unitaires | 4 | 4 | 0 | À assigner |

### US9 — Exposer les services en REST

**En tant que** développeur d'une application cliente, **je veux** appeler les services de règles, d'évaluations, d'utilisateurs et de statistiques.
**Sprint 2** · Feature Backend · 15 h estimées

Critères d'acceptation :
- Authentification HTTP Basic
- Codes HTTP corrects : 200, 201, 204, 401, 403, 404, 422
- Les mots de passe ne sont jamais renvoyés

| Tâche | Type | Estimation (h) | Remaining (h) | Completed (h) | Assignée à |
|---|---|---|---|---|---|
| Blueprint API et authentification Basic | Développement | 3 | 3 | 0 | À assigner |
| Endpoints règles et évaluations | Développement | 5 | 5 | 0 | À assigner |
| Endpoints utilisateurs et statistiques | Développement | 3 | 3 | 0 | À assigner |
| Tests de l'API (codes et permissions) | Tests unitaires | 4 | 4 | 0 | À assigner |

### US11 — Contrôler la zone avant d'évaluer le bâtiment

**En tant que** client, **je veux** indiquer d'abord la zone **afin que** le bâtiment ne soit évalué que si la zone est exposée aux séismes.
**Sprint 2** · Feature Backend · 14 h estimées

Critères d'acceptation :
- L'étape 1 demande seulement le nom du bâtiment et la zone, sans critères du bâtiment
- Zone sécurisée : résultat « faible » immédiat, le bâtiment n'est pas évalué, même s'il est en mauvais état
- Zone exposée (par exemple Tokyo ou Chlef) : l'étape 2 demande les critères du bâtiment et applique les règles
- Le résultat indique la zone et, si besoin, que le bâtiment n'a pas été évalué

| Tâche | Type | Estimation (h) | Remaining (h) | Completed (h) | Assignée à |
|---|---|---|---|---|---|
| Règle de zone dans le moteur (zone_result) et logique en deux étapes | Développement | 4 | 4 | 0 | À assigner |
| Étape 1 du formulaire (choix de la zone) et étape 2 conditionnelle | Développement | 4 | 4 | 0 | À assigner |
| Résultat adapté à la zone sécurisée (message, données masquées) | Développement | 2 | 2 | 0 | À assigner |
| Tests des deux étapes (zone sécurisée, zone exposée, API) | Tests unitaires | 4 | 4 | 0 | À assigner |

## Feature : Persistence

### US5 — Enregistrer les bâtiments et les évaluations

**En tant que** client, **je veux** retrouver mes données plus tard.
**Sprint 1** · Feature Persistence · 11 h estimées

Critères d'acceptation :
- Tables users, rules, buildings, evaluations avec clés étrangères
- Chaque évaluation enregistre niveau, indice et règles déclenchées
- Au premier lancement, l'admin et les 12 règles sont créés

| Tâche | Type | Estimation (h) | Remaining (h) | Completed (h) | Assignée à |
|---|---|---|---|---|---|
| Schéma SQLite et connexion | Développement | 3 | 3 | 0 | À assigner |
| Enregistrer bâtiment et évaluation (create_evaluation) | Développement | 3 | 3 | 0 | À assigner |
| Données initiales et migration des anciennes bases | Développement | 2 | 2 | 0 | À assigner |
| Tests de persistance et de migration | Tests unitaires | 3 | 3 | 0 | À assigner |

### US10 — Rechercher, supprimer et imprimer mes évaluations

**En tant que** client, **je veux** gérer mon historique et garder un rapport.
**Sprint 2** · Feature Persistence · 10 h estimées

Critères d'acceptation :
- Recherche par nom de bâtiment et filtre par niveau
- Suppression d'une évaluation avec son bâtiment
- Impression ou enregistrement en PDF depuis le navigateur

| Tâche | Type | Estimation (h) | Remaining (h) | Completed (h) | Assignée à |
|---|---|---|---|---|---|
| Requête de recherche et de filtre (search_evaluations) | Développement | 3 | 3 | 0 | À assigner |
| Suppression en cascade bâtiment → évaluation | Développement | 2 | 2 | 0 | À assigner |
| Page historique avec filtres et bouton imprimer / PDF | Développement | 3 | 3 | 0 | À assigner |
| Tests de filtres et de suppression | Tests unitaires | 2 | 2 | 0 | À assigner |

### US12 — Gérer la table des zones

**En tant que** Domain-Manager, **je veux** gérer la liste des zones et leur statut (sécurisée ou exposée) **afin que** le contrôle de zone reste à jour.
**Sprint 2** · Feature Persistence · 13 h estimées

Critères d'acceptation :
- Une table `zones` contient le nom, le pays, le statut sécurisée / exposée et une note
- Chaque bâtiment évalué est relié à sa zone
- Une zone utilisée par des bâtiments ne peut pas être supprimée
- Les anciennes bases sont mises à jour sans perte de données

| Tâche | Type | Estimation (h) | Remaining (h) | Completed (h) | Assignée à |
|---|---|---|---|---|---|
| Table zones, clé étrangère buildings.zone_id et migration | Développement | 3 | 3 | 0 | À assigner |
| Pages de gestion des zones (créer, modifier, supprimer) | Développement | 4 | 4 | 0 | À assigner |
| Service REST /api/zones | Développement | 3 | 3 | 0 | À assigner |
| Tests des zones (CRUD, suppression, migration) | Tests unitaires | 3 | 3 | 0 | À assigner |

## Récapitulatif

| Sprint | User stories | Heures estimées |
|---|---|---|
| Sprint 1 | US1 à US5 | 59 h |
| Sprint 2 | US6 à US12 | 90 h |

Vidéo de référence du professeur pour les tâches de tests unitaires : https://www.youtube.com/watch?v=EIV_ixKGPmc
