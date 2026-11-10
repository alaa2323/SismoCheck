import unittest

import helpers  # noqa: F401  (configure le chemin d'import)
import engine
from default_rules import DEFAULT_RULES, C
from helpers import SAFE

RULES = [{"name": r["name"], "event": engine.EVENT_SUBMIT, "conditions": r["conditions"], "level": r["level"],
          "message": r["message"], "points": r["points"], "active": True} for r in DEFAULT_RULES]


class EngineTests(unittest.TestCase):
    def level(self, **override):
        return engine.evaluate({**SAFE, **override}, RULES)[0]

    def test_safe_building_is_low_risk(self):
        level, triggered = engine.evaluate(SAFE, RULES)
        self.assertEqual(level, "faible")
        self.assertEqual(triggered[0]["name"], "Aucune anomalie détectée")
        self.assertEqual(engine.score(triggered), 0)

    def test_structural_cracks_is_high(self):
        self.assertEqual(self.level(etat_murs="fissures_diagonales"), "eleve")

    def test_unstable_soil_and_old_is_high(self):
        self.assertEqual(self.level(type_sol="instable", annee_construction=1970), "eleve")

    def test_unstable_soil_recent_is_not_high(self):
        self.assertNotEqual(self.level(type_sol="instable", annee_construction=2020), "eleve")

    def test_old_non_compliant_is_medium(self):
        self.assertEqual(self.level(annee_construction=1980, normes="non_respecte"), "moyen")

    def test_strong_close_quake_is_medium(self):
        self.assertEqual(self.level(magnitude=6.0, distance_km=10), "moyen")

    def test_highest_level_wins(self):
        self.assertEqual(self.level(deformation="oui", etat_toiture="instable"), "eleve")

    def test_inactive_rule_ignored(self):
        rules = [{**r, "active": False} for r in RULES]
        self.assertEqual(engine.evaluate({**SAFE, "deformation": "oui"}, rules)[0], "faible")

    def test_condition_operators(self):
        d = {"age": 40, "type_sol": "stable"}
        self.assertTrue(engine.check_condition(C("age", ">=", 40), d))
        self.assertFalse(engine.check_condition(C("age", "<", 40), d))
        self.assertTrue(engine.check_condition(C("type_sol", "!=", "instable"), d))
        self.assertFalse(engine.check_condition(C("type_sol", ">", "a"), d))
        self.assertFalse(engine.check_condition(C("inconnu", "==", "x"), d))

    def test_parse_form_validation(self):
        _, errors = engine.parse_form({**{k: str(v) for k, v in SAFE.items()}, "nb_etages": "0"})
        self.assertTrue(errors)
        _, errors = engine.parse_form({k: str(v) for k, v in SAFE.items()})
        self.assertFalse(errors)

    def test_score_adds_points_and_is_capped(self):
        _, t = engine.evaluate({**SAFE, "deformation": "oui", "etat_murs": "fissures_diagonales"}, RULES)
        self.assertEqual(engine.score(t), 80)
        _, t = engine.evaluate({**SAFE, "deformation": "oui", "etat_murs": "fissures_diagonales",
                                "etat_dalles": "affaissees", "fondation": "signes_importants"}, RULES)
        self.assertEqual(engine.score(t), 100)

    def test_rule_without_points_uses_level_default(self):
        rule = {"name": "x", "event": engine.EVENT_SUBMIT, "conditions": [C("nb_etages", ">=", 2)],
                "level": "moyen", "message": "m", "active": True}
        self.assertEqual(engine.score(engine.evaluate(SAFE, [rule])[1]), engine.DEFAULT_POINTS["moyen"])


if __name__ == "__main__":
    unittest.main()
