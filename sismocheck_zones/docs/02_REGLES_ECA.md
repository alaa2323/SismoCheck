# Règles métier au format ECA (Event – Condition – Action)

Les règles R01 à R12 sont déclenchées par l'**événement** `soumission_formulaire` (le client soumet les critères du bâtiment, étape 2). La règle de zone Z01 est contrôlée avant, à l'étape 1.
Les conditions d'une règle sont reliées par **ET**. L'**action** attribue un niveau de risque, des points (indice de risque 0-100) et un message d'explication.
Le niveau final est le plus grave des niveaux déclenchés ; l'indice est la somme des points, plafonnée à 100.

Champ dérivé : `age` = année en cours − `annee_construction`.

## Règle de zone (contrôlée en premier)

| N° | Règle | Event | Condition | Action | Message affiché |
|---|---|---|---|---|---|
| Z01 | Zone sécurisée | choix de la zone (étape 1) | `zone.secure = vrai` | Niveau faible, 0 point, **les critères du bâtiment ne sont pas demandés ni évalués** | La zone n'est pas exposée aux séismes : les critères du bâtiment n'ont pas été évalués. |

Si la zone est **exposée** aux séismes (par exemple Tokyo ou Chlef), Z01 ne se déclenche pas et on passe à l'étape 2 : les règles R01 à R12 ci-dessous s'appliquent aux critères du bâtiment.

```
ON    choix_de_la_zone
IF    zone.secure == vrai
DO    niveau = faible ; points = 0 ; bâtiment non évalué
```

## Règles du Domain-Manager (ingénieur en structure)

| N° | Règle | Event | Condition(s) | Action (niveau, points) | Message affiché |
|---|---|---|---|---|---|
| R01 | Fissures structurelles importantes | soumission_formulaire | `etat_murs == fissures_diagonales` | Risque élevé, +40 pts | Des fissures importantes/diagonales dans les murs porteurs indiquent un danger structurel. |
| R02 | Déformation structurelle | soumission_formulaire | `deformation == oui` | Risque élevé, +40 pts | Une inclinaison ou des éléments (poteaux, poutres, planchers) déformés signalent un problème sérieux. |
| R03 | Sol instable et bâtiment ancien | soumission_formulaire | `type_sol == instable` ET `age >= 40` | Risque élevé, +35 pts | Un sol instable combiné à un bâtiment de 40 ans ou plus amplifie fortement la vulnérabilité. |
| R04 | Dalles affaissées | soumission_formulaire | `etat_dalles == affaissees` | Risque élevé, +40 pts | Dalles affaissées ou béton détérioré : expertise professionnelle nécessaire. |
| R05 | Non-respect des normes et forte magnitude | soumission_formulaire | `normes == non_respecte` ET `magnitude >= 6` | Risque élevé, +30 pts | Normes parasismiques non respectées face à un séisme de magnitude >= 6. |
| R06 | Fondation avec signes importants | soumission_formulaire | `fondation == signes_importants` | Risque élevé, +35 pts | Affaissement, tassement ou fissures importantes à la base du bâtiment. |
| R07 | Risque d'entrechoquement | soumission_formulaire | `espace_voisins_cm < 10` ET `nb_etages >= 4` | Risque moyen, +15 pts | Espace insuffisant avec le voisin pour un bâtiment haut : risque de chocs pendant les secousses (à confirmer par calcul). |
| R08 | Bâtiment ancien non conforme | soumission_formulaire | `age >= 30` ET `normes != respecte` | Risque moyen, +20 pts | Bâtiment de 30 ans ou plus sans conformité parasismique confirmée. |
| R09 | Toiture instable | soumission_formulaire | `etat_toiture == instable` | Risque moyen, +10 pts | Une toiture lourde ou mal fixée peut présenter un risque pendant un séisme. |
| R10 | Séisme proche et fort | soumission_formulaire | `magnitude >= 5.5` ET `distance_km <= 30` | Risque moyen, +15 pts | Séisme de magnitude >= 5.5 à moins de 30 km : forte sollicitation du bâtiment. |

## Règles des autres participants (Customer, IT_ADMIN)

| N° | Règle | Auteur | Event | Condition(s) | Action (niveau, points) | Message affiché |
|---|---|---|---|---|---|---|
| R11 | Fissures mineures et toiture dégradée | Customer | soumission_formulaire | `etat_murs == fissures_mineures` ET `etat_toiture == degradee` | Risque moyen, +10 pts | Cumul de dégradations visibles : une inspection est recommandée. |
| R12 | Conformité inconnue | IT_ADMIN | soumission_formulaire | `normes == inconnu` ET `age >= 20` | Risque moyen, +10 pts | La conformité aux normes est inconnue pour un bâtiment de 20 ans ou plus : à vérifier. |

## Exemple de règle écrite en pseudo-code ECA

```
ON    soumission_formulaire
IF    type_sol == instable ET age >= 40
DO    niveau = eleve ; points += 35 ; message = "Sol instable et bâtiment ancien"
```

## Gestion des règles

- Le Domain-Manager (ou l'administrateur) ajoute, modifie, désactive ou supprime les règles depuis l'application ou via l'API `/api/rules`, sans modifier le code.
- Les règles par défaut sont définies en Python dans `default_rules.py` et insérées en base au premier lancement.
- **Les seuils (30/40 ans, magnitude 5,5 / 6, 10 cm d'espace…) sont des valeurs de départ à faire valider par le Domain-Manager ou le règlement parasismique (RPA).**
