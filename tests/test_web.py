import json
import os
import sqlite3
import tempfile
import unittest

from helpers import WebClient, app, form_data, make_user
import database
import services


class WebTests(unittest.TestCase):
    def test_csrf_required_on_post(self):
        c = WebClient()
        self.assertEqual(c.post("/login", {"username": "admin", "password": "admin123"}, csrf=False).status_code, 400)

    def test_protected_pages_need_login(self):
        c = WebClient()
        self.assertEqual(c.get("/admin").status_code, 302)
        self.assertEqual(c.get("/evaluate").status_code, 302)

    def test_register_login_and_evaluate(self):
        c = WebClient()
        c.post("/register", {"username": "sara", "password": "secret1"})
        self.assertIn(b"Nouvelle", c.login("sara", "secret1").data)
        r = c.post("/evaluate/building", form_data(etat_murs="fissures_diagonales"), follow_redirects=True)
        self.assertIn("Risque élevé".encode(), r.data)
        self.assertIn(b"/100", r.data)
        self.assertIn(b"Imprimer", r.data)
        self.assertIn(b"Immeuble test", c.get("/history").data)

    def test_register_validation(self):
        c = WebClient()
        self.assertIn("3 à 30".encode(), c.post("/register", {"username": "a b", "password": "secret1"}).data)
        self.assertIn("6 caractères".encode(), c.post("/register", {"username": "bob_ok", "password": "123"}).data)

    def test_client_cannot_access_admin_pages(self):
        make_user("client1", "user")
        c = WebClient(); c.login("client1", "secret1")
        for url in ["/admin", "/admin/rules", "/admin/users", "/admin/evaluations"]:
            self.assertEqual(c.get(url).status_code, 403, url)

    def test_domain_manager_permissions(self):
        make_user("dm1", "domain_manager")
        c = WebClient(); c.login("dm1", "secret1")
        self.assertEqual(c.get("/admin/rules").status_code, 200)
        self.assertEqual(c.get("/admin").status_code, 200)
        self.assertEqual(c.get("/admin/users").status_code, 403)

    def test_it_admin_permissions(self):
        make_user("it1", "it_admin")
        c = WebClient(); c.login("it1", "secret1")
        self.assertEqual(c.get("/admin/users").status_code, 200)
        self.assertEqual(c.get("/admin/rules").status_code, 403)
        self.assertEqual(c.get("/evaluate").status_code, 403)

    def test_it_admin_cannot_grant_admin_role(self):
        make_user("it2", "it_admin"); make_user("victim", "user")
        with app.app_context():
            vid = database.get_db().execute("SELECT id FROM users WHERE username='victim'").fetchone()["id"]
        c = WebClient(); c.login("it2", "secret1")
        c.post(f"/admin/users/{vid}/role", {"role": "admin"})
        with app.app_context():
            self.assertEqual(database.get_db().execute("SELECT role FROM users WHERE id=?", (vid,)).fetchone()["role"], "user")
        c.post(f"/admin/users/{vid}/role", {"role": "domain_manager"})
        with app.app_context():
            self.assertEqual(database.get_db().execute("SELECT role FROM users WHERE id=?", (vid,)).fetchone()["role"], "domain_manager")

    def test_user_cannot_see_other_users_evaluation(self):
        make_user("owner", "user"); make_user("intruder", "user")
        a = WebClient(); a.login("owner", "secret1")
        resp = a.post("/evaluate/building", form_data(), follow_redirects=False)
        url = resp.headers["Location"]
        b = WebClient(); b.login("intruder", "secret1")
        self.assertEqual(b.get(url).status_code, 403)
        self.assertEqual(a.get(url).status_code, 200)

    def test_domain_manager_adds_rule_applied_immediately(self):
        make_user("dm2", "domain_manager"); make_user("cl2", "user")
        m = WebClient(); m.login("dm2", "secret1")
        r = m.post("/admin/rules/new", {"name": "R99 test", "message": "Test", "level": "eleve", "points": "55",
                                        "c_field_0": "nb_etages", "c_op_0": ">=", "c_value_0": "10"}, follow_redirects=True)
        self.assertIn(b"R99 test", r.data)
        c = WebClient(); c.login("cl2", "secret1")
        res = c.post("/evaluate/building", form_data(nb_etages=12), follow_redirects=True)
        self.assertIn(b"R99 test", res.data)
        self.assertIn(b"55/100", res.data)

    def test_invalid_rule_rejected(self):
        make_user("dm3", "domain_manager")
        m = WebClient(); m.login("dm3", "secret1")
        r = m.post("/admin/rules/new", {"name": "Mauvaise", "message": "x", "level": "eleve",
                                        "c_field_0": "type_sol", "c_op_0": "==", "c_value_0": "volcan"})
        self.assertIn("invalide".encode(), r.data)

    def test_history_filters_and_delete(self):
        make_user("hist", "user")
        c = WebClient(); c.login("hist", "secret1")
        c.post("/evaluate/building", form_data(building_name="Villa Rose"))
        c.post("/evaluate/building", form_data(building_name="Tour Nord", deformation="oui"))
        self.assertIn(b"Villa Rose", c.get("/history?q=Villa").data)
        self.assertNotIn(b"Tour Nord", c.get("/history?q=Villa").data)
        self.assertNotIn(b"Villa Rose", c.get("/history?level=eleve").data)
        with app.app_context():
            ev = database.get_db().execute("SELECT e.id FROM evaluations e JOIN buildings b ON b.id=e.building_id WHERE b.name='Villa Rose'").fetchone()["id"]
        c.post(f"/evaluations/{ev}/delete")
        self.assertNotIn(b"Villa Rose", c.get("/history").data)

    def test_login_throttling(self):
        c = WebClient()
        for _ in range(5):
            c.post("/login", {"username": "ghost", "password": "bad"})
        self.assertIn("Trop de tentatives".encode(), c.post("/login", {"username": "ghost", "password": "bad"}).data)

    def test_change_password(self):
        make_user("pw1", "user")
        c = WebClient(); c.login("pw1", "secret1")
        self.assertIn("incorrect".encode(), c.post("/account", {"current_password": "zzz", "new_password": "newpass1", "confirm_password": "newpass1"}).data)
        c.post("/account", {"current_password": "secret1", "new_password": "newpass1", "confirm_password": "newpass1"})
        c.logout()
        self.assertIn(b"Nouvelle", c.login("pw1", "newpass1").data)

    def test_dashboard_renders_with_data(self):
        make_user("dash", "user")
        c = WebClient(); c.login("dash", "secret1"); c.post("/evaluate/building", form_data(deformation="oui")); c.logout()
        c.login("admin", "admin123")
        page = c.get("/admin").data
        self.assertIn(b"Bienvenue", page)
        self.assertIn(b"main-chart", page)
        self.assertIn("mot de passe par défaut".encode(), page)

    def test_services_validate_rule(self):
        ok, err = services.validate_rule({"name": "a", "message": "b", "level": "moyen",
                                          "conditions": [{"field": "age", "op": ">=", "value": "30"}]})
        self.assertIsNone(err); self.assertEqual(ok["points"], 15)
        _, err = services.validate_rule({"name": "a", "message": "b", "level": "moyen",
                                         "conditions": [{"field": "type_sol", "op": ">", "value": "stable"}]})
        self.assertTrue(err)
        _, err = services.validate_rule({"name": "a", "message": "b", "level": "moyen", "points": 500,
                                         "conditions": [{"field": "age", "op": ">=", "value": "30"}]})
        self.assertTrue(err)


class MigrationTest(unittest.TestCase):
    def test_old_database_is_upgraded(self):
        path = os.path.join(tempfile.mkdtemp(), "old.db")
        db = sqlite3.connect(path)
        db.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin','user')), created_at TEXT NOT NULL);
            CREATE TABLE rules (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, event TEXT NOT NULL, conditions TEXT NOT NULL,
                level TEXT NOT NULL, message TEXT NOT NULL, author TEXT NOT NULL DEFAULT 'Admin', active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE buildings (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE evaluations (id INTEGER PRIMARY KEY AUTOINCREMENT, building_id INTEGER NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, level TEXT NOT NULL, triggered TEXT NOT NULL, created_at TEXT NOT NULL);
            INSERT INTO users VALUES (1, 'sara', 'x', 'user', '2026-01-01 10:00');
            INSERT INTO rules (name, event, conditions, level, message) VALUES ('R', 'e', '[]', 'eleve', 'm');
            INSERT INTO buildings VALUES (1, 1, 'B', '{}', '2026-01-01 10:00');
            INSERT INTO evaluations VALUES (1, 1, 1, 'eleve', '[]', '2026-01-01 10:00');
        """)
        db.commit(); db.close()
        database.init_db(path)
        db = sqlite3.connect(path)
        db.execute("UPDATE users SET role = 'domain_manager' WHERE id = 1")  # impossible avant la migration
        self.assertEqual(db.execute("SELECT points FROM rules").fetchone()[0], 40)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT score FROM evaluations").fetchone()[0], 0)
        db.close()


if __name__ == "__main__":
    unittest.main()
