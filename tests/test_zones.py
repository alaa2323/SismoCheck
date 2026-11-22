import json
import os
import sqlite3
import tempfile
import unittest

from helpers import SAFE, WebClient, app, basic, form_data, make_user, zone_id
import database
import engine
import services

# Bâtiment en très mauvais état : en zone exposée, il serait classé « élevé »
RUINED = {**SAFE, "etat_murs": "fissures_diagonales", "deformation": "oui", "etat_dalles": "affaissees"}


def evaluation(eval_id):
    with app.app_context():
        return services.evaluation_to_dict(services.get_evaluation(database.get_db(), eval_id))


class ZoneTableTests(unittest.TestCase):
    def test_default_zones_are_seeded(self):
        with app.app_context():
            zones = {z["name"]: z for z in database.load_zones(database.get_db())}
        self.assertGreaterEqual(len(zones), 7)
        self.assertFalse(zones["Chlef"]["secure"])
        self.assertFalse(zones["Tokyo"]["secure"])
        self.assertTrue(zones["Tamanrasset"]["secure"])

    def test_zone_rule_in_engine(self):
        level, triggered = engine.zone_result({"name": "Adrar"})
        self.assertEqual(level, "faible")
        self.assertEqual(triggered[0]["name"], "Zone sécurisée")
        self.assertEqual(engine.score(triggered), 0)


class TwoStepEvaluationWebTests(unittest.TestCase):
    def test_step_one_does_not_ask_building_criteria(self):
        make_user("z_cl1", "user")
        c = WebClient(); c.login("z_cl1", "secret1")
        page = c.get("/evaluate").data.decode()
        self.assertIn("Zone (ville ou région)", page)
        self.assertNotIn("Type de sol", page)       # aucun critère du bâtiment à l'étape 1
        self.assertNotIn("Nombre d'étages", page)

    def test_secure_zone_skips_building_criteria(self):
        make_user("z_cl2", "user")
        c = WebClient(); c.login("z_cl2", "secret1")
        resp = c.post("/evaluate", {"building_name": "Maison désert", "zone_id": str(zone_id("Tamanrasset"))})
        self.assertEqual(resp.status_code, 302)     # résultat direct, pas d'étape 2
        page = c.get(resp.headers["Location"]).data.decode()
        self.assertIn("Risque faible", page)
        self.assertIn("Zone sécurisée", page)
        self.assertIn("critères du bâtiment n'ont pas été demandés", page)
        self.assertNotIn("Type de sol", page)

    def test_secure_zone_ignores_a_ruined_building(self):
        """Même si le bâtiment est en ruine, une zone sécurisée donne « faible » (règle demandée)."""
        make_user("z_cl3", "user")
        c = WebClient(); c.login("z_cl3", "secret1")
        resp = c.post("/evaluate/building", {**{k: str(v) for k, v in RUINED.items()}, "building_name": "Ruine", "zone_id": str(zone_id("Adrar"))})
        page = c.get(resp.headers["Location"]).data.decode()
        self.assertIn("Risque faible", page)
        self.assertNotIn("fissures_diagonales", page)

    def test_exposed_zone_shows_step_two_then_applies_rules(self):
        make_user("z_cl4", "user")
        c = WebClient(); c.login("z_cl4", "secret1")
        step2 = c.post("/evaluate", {"building_name": "Immeuble Chlef", "zone_id": str(zone_id("Chlef"))})
        self.assertEqual(step2.status_code, 200)
        self.assertIn("Type de sol", step2.data.decode())
        self.assertIn("Zone exposée aux séismes", step2.data.decode())
        res = c.post("/evaluate/building", form_data(**RUINED), follow_redirects=True).data.decode()
        self.assertIn("Risque élevé", res)
        self.assertIn("Zone : Chlef", res)

    def test_step_two_rejects_missing_criteria(self):
        make_user("z_cl5", "user")
        c = WebClient(); c.login("z_cl5", "secret1")
        r = c.post("/evaluate/building", {"building_name": "X", "zone_id": str(zone_id("Tokyo"))})
        self.assertIn("Champ obligatoire", r.data.decode())

    def test_unknown_zone_is_refused(self):
        make_user("z_cl6", "user")
        c = WebClient(); c.login("z_cl6", "secret1")
        self.assertIn("Choisissez une zone", c.post("/evaluate", {"building_name": "X", "zone_id": "9999"}).data.decode())

    def test_history_shows_zone(self):
        make_user("z_cl7", "user")
        c = WebClient(); c.login("z_cl7", "secret1")
        c.post("/evaluate", {"building_name": "Villa Sud", "zone_id": str(zone_id("Adrar"))})
        page = c.get("/history").data.decode()
        self.assertIn("Villa Sud", page)
        self.assertIn("Adrar", page)


class ZoneAdminTests(unittest.TestCase):
    def test_client_cannot_manage_zones(self):
        make_user("z_cl8", "user")
        c = WebClient(); c.login("z_cl8", "secret1")
        self.assertEqual(c.get("/admin/zones").status_code, 403)
        self.assertEqual(c.post("/admin/zones/new", {"name": "Hack"}).status_code, 403)

    def test_domain_manager_crud_and_effect_on_evaluation(self):
        make_user("z_dm1", "domain_manager"); make_user("z_cl9", "user")
        m = WebClient(); m.login("z_dm1", "secret1")
        self.assertEqual(m.get("/admin/zones").status_code, 200)
        r = m.post("/admin/zones/new", {"name": "Zone Test", "country": "Pays", "secure": "on", "note": "test"}, follow_redirects=True)
        self.assertIn("Zone enregistrée", r.data.decode())
        zid = zone_id("Zone Test")
        c = WebClient(); c.login("z_cl9", "secret1")
        self.assertEqual(c.post("/evaluate", {"building_name": "B", "zone_id": str(zid)}).status_code, 302)   # sécurisée
        m.post(f"/admin/zones/{zid}/edit", {"name": "Zone Test", "country": "Pays", "note": "test"})        # décochée = exposée
        self.assertEqual(c.post("/evaluate", {"building_name": "B", "zone_id": str(zid)}).status_code, 200)   # étape 2
        dup = m.post("/admin/zones/new", {"name": "zone test"})
        self.assertIn("déjà", dup.data.decode())

    def test_zone_with_buildings_cannot_be_deleted(self):
        make_user("z_dm2", "domain_manager"); make_user("z_cl10", "user")
        c = WebClient(); c.login("z_cl10", "secret1")
        c.post("/evaluate/building", form_data(zone_id=zone_id("Alger")))
        m = WebClient(); m.login("z_dm2", "secret1")
        r = m.post(f"/admin/zones/{zone_id('Alger')}/delete", follow_redirects=True)
        self.assertIn("ne peut pas être supprimée", r.data.decode())
        m.post("/admin/zones/new", {"name": "Zone Jetable"})
        self.assertIn("Zone supprimée", m.post(f"/admin/zones/{zone_id('Zone Jetable')}/delete", follow_redirects=True).data.decode())


class ZoneApiTests(unittest.TestCase):
    def setUp(self):
        self.c = app.test_client()
        make_user("z_api_cl", "user"); make_user("z_api_dm", "domain_manager")
        self.cl, self.dm = basic("z_api_cl", "secret1"), basic("z_api_dm", "secret1")

    def test_list_zones(self):
        zones = self.c.get("/api/zones", headers=self.cl).get_json()
        self.assertIn("Chlef", [z["name"] for z in zones])
        self.assertEqual(self.c.get("/api/zones").status_code, 401)

    def test_zone_is_required(self):
        r = self.c.post("/api/evaluations", json=dict(SAFE), headers=self.cl)
        self.assertEqual(r.status_code, 422)
        self.assertIn("zone", r.get_json()["error"])
        r = self.c.post("/api/evaluations", json={**SAFE, "zone": "Atlantide"}, headers=self.cl)
        self.assertEqual(r.status_code, 422)

    def test_secure_zone_needs_no_building_data(self):
        r = self.c.post("/api/evaluations", json={"zone": "Tamanrasset", "building_name": "Maison"}, headers=self.cl)
        self.assertEqual(r.status_code, 201)
        res = r.get_json()
        self.assertEqual((res["level"], res["building_evaluated"], res["data"]), ("faible", False, {}))
        self.assertEqual(res["triggered_rules"][0]["name"], "Zone sécurisée")

    def test_secure_zone_ignores_ruined_building(self):
        res = self.c.post("/api/evaluations", json={**RUINED, "zone": "Adrar"}, headers=self.cl).get_json()
        self.assertEqual((res["level"], res["building_evaluated"]), ("faible", False))

    def test_exposed_zone_requires_and_uses_building_data(self):
        r = self.c.post("/api/evaluations", json={"zone": "Chlef"}, headers=self.cl)
        self.assertEqual(r.status_code, 422)
        res = self.c.post("/api/evaluations", json={**RUINED, "zone": "Chlef"}, headers=self.cl).get_json()
        self.assertEqual((res["level"], res["building_evaluated"], res["zone"]["name"]), ("eleve", True, "Chlef"))
        by_id = self.c.post("/api/evaluations", json={**SAFE, "zone": zone_id("Tokyo")}, headers=self.cl).get_json()
        self.assertEqual(by_id["zone"]["name"], "Tokyo")

    def test_zone_crud_permissions(self):
        self.assertEqual(self.c.post("/api/zones", json={"name": "ZoneApi"}, headers=self.cl).status_code, 403)
        r = self.c.post("/api/zones", json={"name": "ZoneApi", "country": "X", "secure": True}, headers=self.dm)
        self.assertEqual(r.status_code, 201)
        zid = r.get_json()["id"]
        self.assertTrue(r.get_json()["secure"])
        self.assertEqual(self.c.put(f"/api/zones/{zid}", json={"secure": False}, headers=self.dm).get_json()["secure"], False)
        self.assertEqual(self.c.post("/api/zones", json={"name": "ZoneApi"}, headers=self.dm).status_code, 422)
        self.assertEqual(self.c.delete(f"/api/zones/{zid}", headers=self.dm).status_code, 204)

    def test_zone_in_use_returns_409(self):
        self.c.post("/api/evaluations", json={**SAFE, "zone": "Istanbul"}, headers=self.cl)
        self.assertEqual(self.c.delete(f"/api/zones/{zone_id('Istanbul')}", headers=self.dm).status_code, 409)


class ZoneMigrationTest(unittest.TestCase):
    def test_database_without_zones_is_upgraded(self):
        path = os.path.join(tempfile.mkdtemp(), "before_zones.db")
        db = sqlite3.connect(path)
        db.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user', created_at TEXT NOT NULL);
            CREATE TABLE rules (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, event TEXT NOT NULL, conditions TEXT NOT NULL,
                level TEXT NOT NULL, message TEXT NOT NULL, author TEXT NOT NULL DEFAULT 'Admin', active INTEGER NOT NULL DEFAULT 1,
                points INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE buildings (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE evaluations (id INTEGER PRIMARY KEY AUTOINCREMENT, building_id INTEGER NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, level TEXT NOT NULL, score INTEGER NOT NULL DEFAULT 0,
                triggered TEXT NOT NULL, created_at TEXT NOT NULL);
            INSERT INTO users VALUES (1, 'sara', 'x', 'user', '2026-01-01 10:00');
            INSERT INTO buildings VALUES (1, 1, 'Ancien bâtiment', '{}', '2026-01-01 10:00');
            INSERT INTO evaluations VALUES (1, 1, 1, 'eleve', 40, '[]', '2026-01-01 10:00');
        """)
        db.commit(); db.close()
        database.init_db(path)
        db = sqlite3.connect(path); db.row_factory = sqlite3.Row
        self.assertIn("zone_id", database._columns(db, "buildings"))
        self.assertGreaterEqual(db.execute("SELECT COUNT(*) FROM zones").fetchone()[0], 7)
        self.assertIsNone(db.execute("SELECT zone_id FROM buildings WHERE id = 1").fetchone()["zone_id"])   # ancienne évaluation conservée
        self.assertEqual(db.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0], 1)
        db.close()


if __name__ == "__main__":
    unittest.main()
