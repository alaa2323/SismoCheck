"""Zones par défaut (exemples de démonstration), insérées en base au premier lancement.

secure = 1 : zone non exposée aux séismes -> le bâtiment n'est pas évalué, le risque est « faible ».
secure = 0 : zone exposée aux séismes     -> on passe aux critères du bâtiment.

Ces classements sont des exemples : le Domain-Manager doit les valider (zonage sismique officiel).
"""

NOTE = "Exemple de démonstration : à valider par le Domain-Manager."

DEFAULT_ZONES = [
    {"name": "Chlef", "country": "Algérie", "secure": 0, "note": NOTE},
    {"name": "Boumerdès", "country": "Algérie", "secure": 0, "note": NOTE},
    {"name": "Alger", "country": "Algérie", "secure": 0, "note": NOTE},
    {"name": "Tokyo", "country": "Japon", "secure": 0, "note": NOTE},
    {"name": "Istanbul", "country": "Turquie", "secure": 0, "note": NOTE},
    {"name": "Tamanrasset", "country": "Algérie", "secure": 1, "note": NOTE},
    {"name": "Adrar", "country": "Algérie", "secure": 1, "note": NOTE},
]
