"""Moteur de règles ECA (Event - Condition - Action) pour le risque sismique."""
from datetime import date

EVENT_SUBMIT = "soumission_formulaire"

LEVELS = {"faible": 1, "moyen": 2, "eleve": 3}
LEVEL_LABELS = {"faible": "Risque faible", "moyen": "Risque moyen", "eleve": "Risque élevé"}
LEVEL_COLORS = {"faible": "success", "moyen": "warning", "eleve": "danger"}
# Points par défaut d'une règle selon son niveau (utilisés pour l'indice de risque 0-100)
DEFAULT_POINTS = {"faible": 0, "moyen": 15, "eleve": 40}

# Champs du formulaire (basés sur le tableau de critères + paramètres sismiques)
FORM_FIELDS = [
    {"name": "annee_construction", "label": "Année de construction", "type": "int", "min": 1800, "max": date.today().year},
    {"name": "nb_etages", "label": "Nombre d'étages", "type": "int", "min": 1, "max": 100},
    {"name": "type_sol", "label": "Type de sol", "type": "choice",
     "choices": [("stable", "Stable"), ("moyen", "Moyennement stable"), ("instable", "Instable")]},
    {"name": "fondation", "label": "Fondation (affaissement, tassement, fissures à la base)", "type": "choice",
     "choices": [("normale", "Aucun signe"), ("signes_mineurs", "Signes mineurs"), ("signes_importants", "Signes importants")]},
    {"name": "etat_murs", "label": "État des murs (fissures structurelles)", "type": "choice",
     "choices": [("bon", "Bon état"), ("fissures_mineures", "Fissures mineures"), ("fissures_diagonales", "Fissures importantes / diagonales")]},
    {"name": "deformation", "label": "Déformation structurelle observée (inclinaison, poteaux/poutres déformés)", "type": "choice",
     "choices": [("non", "Non"), ("oui", "Oui")]},
    {"name": "etat_toiture", "label": "État de la toiture", "type": "choice",
     "choices": [("bon", "Bon état"), ("degradee", "Dégradée"), ("instable", "Instable / mal fixée")]},
    {"name": "etat_dalles", "label": "Stabilité des dalles", "type": "choice",
     "choices": [("bon", "Bon état"), ("fissures", "Fissurées"), ("affaissees", "Affaissées / béton détérioré")]},
    {"name": "espace_voisins_cm", "label": "Espace avec le bâtiment voisin (cm)", "type": "int", "min": 0, "max": 10000},
    {"name": "normes", "label": "Respect des normes parasismiques", "type": "choice",
     "choices": [("respecte", "Respectées"), ("non_respecte", "Non respectées"), ("inconnu", "Inconnu")]},
    {"name": "magnitude", "label": "Magnitude du séisme", "type": "float", "min": 1, "max": 10},
    {"name": "distance_km", "label": "Distance par rapport à l'épicentre (km)", "type": "float", "min": 0, "max": 20000},
]

# Champs utilisables dans les conditions des règles (formulaire + champ dérivé "age")
RULE_FIELDS = {f["name"]: f for f in FORM_FIELDS}
RULE_FIELDS["age"] = {"name": "age", "label": "Âge du bâtiment (années)", "type": "int"}
OPERATORS = ["==", "!=", ">=", "<=", ">", "<"]


def parse_form(form):
    """Valide et convertit les valeurs du formulaire. Retourne (data, erreurs)."""
    data, errors = {}, []
    for f in FORM_FIELDS:
        raw = (form.get(f["name"]) or "").strip()
        if not raw:
            errors.append(f"Champ obligatoire : {f['label']}")
            continue
        try:
            if f["type"] == "int":
                val = int(raw)
            elif f["type"] == "float":
                val = float(raw.replace(",", "."))
            else:
                val = raw
                if val not in [c[0] for c in f["choices"]]:
                    raise ValueError
            if f["type"] in ("int", "float") and not (f["min"] <= val <= f["max"]):
                errors.append(f"{f['label']} doit être entre {f['min']} et {f['max']}")
                continue
            data[f["name"]] = val
        except ValueError:
            errors.append(f"Valeur invalide : {f['label']}")
    return data, errors


def prepare(data):
    """Ajoute les champs dérivés (âge)."""
    d = dict(data)
    if "annee_construction" in d:
        d["age"] = date.today().year - int(d["annee_construction"])
    return d


def _cast(value, reference):
    if isinstance(reference, (int, float)):
        return float(value)
    return str(value)


def check_condition(cond, data):
    """Évalue une condition {field, op, value} sur les données."""
    field, op, expected = cond["field"], cond["op"], cond["value"]
    if field not in data:
        return False
    actual = data[field]
    try:
        expected = _cast(expected, actual)
        actual = _cast(actual, actual)
    except (ValueError, TypeError):
        return False
    return {
        "==": actual == expected, "!=": actual != expected,
        ">=": actual >= expected if not isinstance(actual, str) else False,
        "<=": actual <= expected if not isinstance(actual, str) else False,
        ">": actual > expected if not isinstance(actual, str) else False,
        "<": actual < expected if not isinstance(actual, str) else False,
    }.get(op, False)


def evaluate(data, rules, event=EVENT_SUBMIT):
    """Exécute les règles actives : retourne (niveau_final, règles_déclenchées).

    Event     : soumission du formulaire
    Condition : toutes les conditions de la règle (ET logique) sont vraies
    Action    : attribuer un niveau de risque + message d'explication
    Niveau final = niveau le plus grave parmi les règles déclenchées (faible par défaut).
    """
    d = prepare(data)
    triggered = []
    for r in rules:
        if not r["active"] or r["event"] != event:
            continue
        if r["conditions"] and all(check_condition(c, d) for c in r["conditions"]):
            points = r.get("points")
            if points is None:
                points = DEFAULT_POINTS[r["level"]]
            triggered.append({"name": r["name"], "level": r["level"], "message": r["message"], "points": points})
    final = "faible"
    for t in triggered:
        if LEVELS[t["level"]] > LEVELS[final]:
            final = t["level"]
    if not triggered:
        triggered.append({"name": "Aucune anomalie détectée", "level": "faible",
                          "message": "Aucune règle de risque n'a été déclenchée pour ce bâtiment.", "points": 0})
    return final, triggered


def score(triggered):
    """Indice de risque de 0 à 100 : somme des points des règles déclenchées (plafonnée à 100)."""
    return min(100, sum(int(t.get("points", 0)) for t in triggered))


def zone_result(zone):
    """Règle de zone (Event : choix de la zone, Condition : la zone est sécurisée,
    Action : risque « faible » et critères du bâtiment non évalués).
    Retourne (niveau, règles_déclenchées)."""
    return "faible", [{
        "name": "Zone sécurisée",
        "level": "faible",
        "message": (f"La zone « {zone['name']} » n'est pas exposée aux séismes : "
                    "les critères du bâtiment n'ont pas été évalués."),
        "points": 0,
    }]
