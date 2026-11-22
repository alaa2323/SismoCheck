import random
import unittest
from datetime import date

import helpers  # noqa: F401  (configure le chemin d'import)
import engine
import rules
from default_rules import DEFAULT_RULES
from helpers import SAFE

ENGINE_RULES = [{**r, "event": engine.EVENT_SUBMIT, "active": True} for r in DEFAULT_RULES]


class IfStyleRulesTests(unittest.TestCase):
    def test_safe_building(self):
        self.assertEqual(rules.seismic_risk_from_form(SAFE), "faible")

    def test_high_risk_cases(self):
        self.assertEqual(rules.seismic_risk_from_form({**SAFE, "etat_murs": "fissures_diagonales"}), "eleve")
        self.assertEqual(rules.seismic_risk_from_form({**SAFE, "type_sol": "instable", "annee_construction": 1970}), "eleve")
        self.assertEqual(rules.seismic_risk_from_form({**SAFE, "normes": "non_respecte", "magnitude": 6.5}), "eleve")

    def test_medium_risk_cases(self):
        self.assertEqual(rules.seismic_risk_from_form({**SAFE, "etat_toiture": "instable"}), "moyen")
        self.assertEqual(rules.seismic_risk_from_form({**SAFE, "magnitude": 5.5, "distance_km": 30}), "moyen")

    def test_boundaries(self):
        year = date.today().year
        self.assertEqual(rules.seismic_risk_from_form({**SAFE, "type_sol": "instable", "annee_construction": year - 40}), "eleve")
        self.assertNotEqual(rules.seismic_risk_from_form({**SAFE, "type_sol": "instable", "annee_construction": year - 39}), "eleve")
        self.assertEqual(rules.seismic_risk_from_form({**SAFE, "espace_voisins_cm": 9, "nb_etages": 4}), "moyen")
        self.assertEqual(rules.seismic_risk_from_form({**SAFE, "espace_voisins_cm": 10, "nb_etages": 4}), "faible")

    def test_same_result_as_eca_engine(self):
        """La version if/return donne exactement le même niveau que le moteur ECA (3000 cas)."""
        rng, year = random.Random(42), date.today().year
        choices = {f["name"]: [v for v, _ in f["choices"]] for f in engine.FORM_FIELDS if f["type"] == "choice"}
        for _ in range(3000):
            data = {name: rng.choice(values) for name, values in choices.items()}
            data.update(
                annee_construction=year - rng.choice([2, 19, 20, 29, 30, 39, 40, 60]),
                nb_etages=rng.choice([1, 3, 4, 8]),
                espace_voisins_cm=rng.choice([0, 9, 10, 50]),
                magnitude=rng.choice([3.0, 5.4, 5.5, 5.9, 6.0, 7.0]),
                distance_km=rng.choice([5, 29.9, 30, 30.1, 100]))
            expected = engine.evaluate(data, ENGINE_RULES)[0]
            self.assertEqual(rules.seismic_risk_from_form(data), expected, data)

    def test_secure_zone_ignores_the_building(self):
        ruined = {**SAFE, "etat_murs": "fissures_diagonales", "deformation": "oui"}
        self.assertEqual(rules.seismic_risk_with_zone_from_form(True, ruined), "faible")
        self.assertEqual(rules.seismic_risk_with_zone_from_form(True), "faible")
        self.assertEqual(rules.seismic_risk_with_zone_from_form(False, ruined), "eleve")
        self.assertEqual(rules.seismic_risk_with_zone_from_form(False, SAFE), "faible")

    def test_zone_gate_same_as_service(self):
        """La version if/return avec zone donne le même niveau que l'application (zone sécurisée ou exposée)."""
        import database, services
        from helpers import app, make_user, zone_id
        make_user("rules_zone_user", "user")
        ruined = {**SAFE, "etat_murs": "fissures_diagonales"}
        with app.app_context():
            db = database.get_db()
            uid = db.execute("SELECT id FROM users WHERE username = 'rules_zone_user'").fetchone()["id"]
            for zone_name, secure in (("Adrar", True), ("Chlef", False)):
                eval_id = services.create_evaluation(db, uid, "B", zone_id(zone_name), None if secure else ruined)
                level = services.get_evaluation(db, eval_id)["level"]
                self.assertEqual(rules.seismic_risk_with_zone_from_form(secure, ruined), level)


if __name__ == "__main__":
    unittest.main()
