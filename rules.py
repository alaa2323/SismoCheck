"""Version « if / return » des règles de risque sismique (même style que fire_risk).

Cette fonction applique les mêmes 12 règles que le moteur ECA (default_rules.py + engine.py).
Elle sert de version simple à lire et à présenter. Le moteur ECA, lui, permet de modifier
les règles sans toucher au code et d'expliquer le résultat.

Valeurs retournées : "eleve", "moyen" ou "faible" (mêmes clés que le moteur).
"""
import engine


def seismic_risk(age, type_sol, fondation, etat_murs, deformation, etat_toiture,
                 etat_dalles, nb_etages, espace_voisins_cm, normes, magnitude, distance_km):
    # ---- Risque élevé : une seule règle suffit (R01 à R06)
    if etat_murs == "fissures_diagonales":                       # R01
        return "eleve"
    if deformation == "oui":                                     # R02
        return "eleve"
    if type_sol == "instable" and age >= 40:                     # R03
        return "eleve"
    if etat_dalles == "affaissees":                              # R04
        return "eleve"
    if normes == "non_respecte" and magnitude >= 6:              # R05
        return "eleve"
    if fondation == "signes_importants":                         # R06
        return "eleve"

    # ---- Risque moyen (R07 à R12)
    if espace_voisins_cm < 10 and nb_etages >= 4:                # R07
        return "moyen"
    if age >= 30 and normes != "respecte":                       # R08
        return "moyen"
    if etat_toiture == "instable":                               # R09
        return "moyen"
    if magnitude >= 5.5 and distance_km <= 30:                   # R10
        return "moyen"
    if etat_murs == "fissures_mineures" and etat_toiture == "degradee":   # R11
        return "moyen"
    if normes == "inconnu" and age >= 20:                        # R12
        return "moyen"

    # ---- Sinon
    return "faible"


def seismic_risk_from_form(data):
    """Même calcul à partir des données du formulaire (dictionnaire de 12 champs)."""
    d = engine.prepare(data)  # ajoute l'âge du bâtiment
    return seismic_risk(
        age=d["age"], type_sol=d["type_sol"], fondation=d["fondation"], etat_murs=d["etat_murs"],
        deformation=d["deformation"], etat_toiture=d["etat_toiture"], etat_dalles=d["etat_dalles"],
        nb_etages=d["nb_etages"], espace_voisins_cm=d["espace_voisins_cm"], normes=d["normes"],
        magnitude=d["magnitude"], distance_km=d["distance_km"])


def seismic_risk_with_zone(zone_secure, **building):
    """Étape 1 : la zone. Zone sécurisée -> « faible », les critères du bâtiment ne sont pas regardés.
    Zone exposée -> étape 2 : seismic_risk(...) avec les critères du bâtiment."""
    if zone_secure:
        return "faible"
    return seismic_risk(**building)


def seismic_risk_with_zone_from_form(zone_secure, data=None):
    """Même chose à partir des données du formulaire (data est ignoré si la zone est sécurisée)."""
    if zone_secure:
        return "faible"
    return seismic_risk_from_form(data)
