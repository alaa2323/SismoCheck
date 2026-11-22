import unittest

from helpers import SAFE, app, basic, make_user

ADMIN = basic("admin", "admin123")


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.c = app.test_client()

    def test_health_and_fields_are_public(self):
        self.assertEqual(self.c.get("/api/health").get_json()["status"], "ok")
        self.assertEqual(len(self.c.get("/api/fields").get_json()), 12)

    def test_authentication_required(self):
        r = self.c.get("/api/rules")
        self.assertEqual(r.status_code, 401)
        self.assertIn("Basic", r.headers["WWW-Authenticate"])
        self.assertEqual(self.c.get("/api/rules", headers=basic("admin", "mauvais")).status_code, 401)

    def test_list_rules(self):
        rules = self.c.get("/api/rules", headers=ADMIN).get_json()
        self.assertGreaterEqual(len(rules), 12)
        self.assertIn("conditions", rules[0])

    def test_rule_crud_for_domain_manager(self):
        make_user("api_dm", "domain_manager"); h = basic("api_dm", "secret1")
        body = {"name": "R50 api", "message": "m", "level": "moyen",
                "conditions": [{"field": "nb_etages", "op": ">=", "value": "8"}]}
        r = self.c.post("/api/rules", json=body, headers=h)
        self.assertEqual(r.status_code, 201)
        rid = r.get_json()["id"]
        self.assertEqual(r.get_json()["points"], 15)
        r = self.c.put(f"/api/rules/{rid}", json={"points": 25, "active": False}, headers=h)
        self.assertEqual((r.get_json()["points"], r.get_json()["active"]), (25, False))
        self.assertEqual(self.c.delete(f"/api/rules/{rid}", headers=h).status_code, 204)
        self.assertEqual(self.c.get(f"/api/rules/{rid}", headers=h).status_code, 404)

    def test_invalid_rule_returns_422(self):
        r = self.c.post("/api/rules", json={"name": "x", "message": "y", "level": "moyen", "conditions": []}, headers=ADMIN)
        self.assertEqual(r.status_code, 422)

    def test_client_cannot_write_rules(self):
        make_user("api_cl", "user")
        r = self.c.post("/api/rules", json={}, headers=basic("api_cl", "secret1"))
        self.assertEqual(r.status_code, 403)

    def test_create_and_get_evaluation(self):
        make_user("api_cl2", "user"); h = basic("api_cl2", "secret1")
        payload = {"building_name": "Immeuble API", "zone": "Chlef", "data": {**SAFE, "etat_murs": "fissures_diagonales"}}
        r = self.c.post("/api/evaluations", json=payload, headers=h)
        self.assertEqual(r.status_code, 201)
        res = r.get_json()
        self.assertEqual((res["level"], res["building_name"]), ("eleve", "Immeuble API"))
        self.assertEqual(res["score"], 40)
        self.assertIn("Location", r.headers)
        self.assertEqual(self.c.get(f"/api/evaluations/{res['id']}", headers=h).get_json()["id"], res["id"])
        self.assertIn(res["id"], [e["id"] for e in self.c.get("/api/evaluations?level=eleve", headers=h).get_json()])

    def test_flat_payload_and_validation_errors(self):
        make_user("api_cl3", "user"); h = basic("api_cl3", "secret1")
        self.assertEqual(self.c.post("/api/evaluations", json={**SAFE, "zone": "Chlef"}, headers=h).status_code, 201)
        r = self.c.post("/api/evaluations", json={**SAFE, "zone": "Chlef", "nb_etages": 0}, headers=h)
        self.assertEqual(r.status_code, 422)
        self.assertTrue(r.get_json()["details"])
        self.assertEqual(self.c.post("/api/evaluations", data="pas du json", headers=h).status_code, 400)

    def test_evaluations_are_private(self):
        make_user("api_a", "user"); make_user("api_b", "user")
        ev = self.c.post("/api/evaluations", json={**SAFE, "zone": "Chlef"}, headers=basic("api_a", "secret1")).get_json()
        hb = basic("api_b", "secret1")
        self.assertEqual(self.c.get(f"/api/evaluations/{ev['id']}", headers=hb).status_code, 403)
        self.assertNotIn(ev["id"], [e["id"] for e in self.c.get("/api/evaluations", headers=hb).get_json()])
        self.assertIn(ev["id"], [e["id"] for e in self.c.get("/api/evaluations", headers=ADMIN).get_json()])
        self.assertEqual(self.c.delete(f"/api/evaluations/{ev['id']}", headers=hb).status_code, 403)
        self.assertEqual(self.c.delete(f"/api/evaluations/{ev['id']}", headers=basic("api_a", "secret1")).status_code, 204)

    def test_users_endpoints_permissions(self):
        make_user("api_it", "it_admin"); make_user("api_target", "user")
        it = basic("api_it", "secret1")
        users = self.c.get("/api/users", headers=it).get_json()
        self.assertNotIn("password_hash", users[0])
        tid = next(u["id"] for u in users if u["username"] == "api_target")
        self.assertEqual(self.c.patch(f"/api/users/{tid}", json={"role": "admin"}, headers=it).status_code, 403)
        self.assertEqual(self.c.patch(f"/api/users/{tid}", json={"role": "domain_manager"}, headers=it).get_json()["role"], "domain_manager")
        self.assertEqual(self.c.patch(f"/api/users/{tid}", json={"role": "roi"}, headers=it).status_code, 422)
        self.assertEqual(self.c.get("/api/users", headers=basic("api_target", "secret1")).status_code, 403)

    def test_stats(self):
        s = self.c.get("/api/stats", headers=ADMIN).get_json()
        self.assertIn("evaluations", s["stats"])
        self.assertEqual(len(s["chart"]["labels"]), 30)


if __name__ == "__main__":
    unittest.main()
