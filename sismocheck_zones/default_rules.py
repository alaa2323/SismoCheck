"""Règles métier par défaut (écrites en Python), insérées en base au premier lancement.
Format ECA : Event -> Conditions (ET) -> Action (niveau + message)."""
from engine import EVENT_SUBMIT

def C(field, op, value):
    return {"field": field, "op": op, "value": str(value)}

DEFAULT_RULES = [
    # --- Règles du Domain-Manager (ingénieur en structure) ---
    {"points": 40, "name": "R01 - Fissures structurelles importantes", "level": "eleve", "author": "Domain-Manager",
     "conditions": [C("etat_murs", "==", "fissures_diagonales")],
     "message": "Des fissures importantes/diagonales dans les murs porteurs indiquent un danger structurel."},
    {"points": 40, "name": "R02 - Déformation structurelle", "level": "eleve", "author": "Domain-Manager",
     "conditions": [C("deformation", "==", "oui")],
     "message": "Une inclinaison ou des éléments (poteaux, poutres, planchers) déformés signalent un problème sérieux."},
    {"points": 35, "name": "R03 - Sol instable et bâtiment ancien", "level": "eleve", "author": "Domain-Manager",
     "conditions": [C("type_sol", "==", "instable"), C("age", ">=", 40)],
     "message": "Un sol instable combiné à un bâtiment de 40 ans ou plus amplifie fortement la vulnérabilité."},
    {"points": 40, "name": "R04 - Dalles affaissées", "level": "eleve", "author": "Domain-Manager",
     "conditions": [C("etat_dalles", "==", "affaissees")],
     "message": "Dalles affaissées ou béton détérioré : expertise professionnelle nécessaire."},
    {"points": 30, "name": "R05 - Non-respect des normes et forte magnitude", "level": "eleve", "author": "Domain-Manager",
     "conditions": [C("normes", "==", "non_respecte"), C("magnitude", ">=", 6)],
     "message": "Normes parasismiques non respectées face à un séisme de magnitude >= 6."},
    {"points": 35, "name": "R06 - Fondation avec signes importants", "level": "eleve", "author": "Domain-Manager",
     "conditions": [C("fondation", "==", "signes_importants")],
     "message": "Affaissement, tassement ou fissures importantes à la base du bâtiment."},
    {"points": 15, "name": "R07 - Risque d'entrechoquement", "level": "moyen", "author": "Domain-Manager",
     "conditions": [C("espace_voisins_cm", "<", 10), C("nb_etages", ">=", 4)],
     "message": "Espace insuffisant avec le voisin pour un bâtiment haut : risque de chocs pendant les secousses (à confirmer par calcul)."},
    {"points": 20, "name": "R08 - Bâtiment ancien non conforme", "level": "moyen", "author": "Domain-Manager",
     "conditions": [C("age", ">=", 30), C("normes", "!=", "respecte")],
     "message": "Bâtiment de 30 ans ou plus sans conformité parasismique confirmée."},
    {"points": 10, "name": "R09 - Toiture instable", "level": "moyen", "author": "Domain-Manager",
     "conditions": [C("etat_toiture", "==", "instable")],
     "message": "Une toiture lourde ou mal fixée peut présenter un risque pendant un séisme."},
    {"points": 15, "name": "R10 - Séisme proche et fort", "level": "moyen", "author": "Domain-Manager",
     "conditions": [C("magnitude", ">=", 5.5), C("distance_km", "<=", 30)],
     "message": "Séisme de magnitude >= 5.5 à moins de 30 km : forte sollicitation du bâtiment."},
    # --- Règles des autres participants (Customer / IT_ADMIN) ---
    {"points": 10, "name": "R11 - Fissures mineures et toiture dégradée", "level": "moyen", "author": "Customer",
     "conditions": [C("etat_murs", "==", "fissures_mineures"), C("etat_toiture", "==", "degradee")],
     "message": "Cumul de dégradations visibles : une inspection est recommandée."},
    {"points": 10, "name": "R12 - Conformité inconnue", "level": "moyen", "author": "IT_ADMIN",
     "conditions": [C("normes", "==", "inconnu"), C("age", ">=", 20)],
     "message": "La conformité aux normes est inconnue pour un bâtiment de 20 ans ou plus : à vérifier."},
]

def as_db_rows():
    import json
    for r in DEFAULT_RULES:
        yield (r["name"], EVENT_SUBMIT, json.dumps(r["conditions"]), r["level"], r["message"], r["author"], r["points"])
