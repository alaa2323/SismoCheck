"""Initialisation commune des tests : base temporaire + client avec protection CSRF."""
import base64
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["ADMIN_PASSWORD"] = "admin123"

import app as app_module  # noqa: E402

app = app_module.app
app.config["TESTING"] = True

SAFE = dict(annee_construction=2022, nb_etages=3, type_sol="stable", fondation="normale", etat_murs="bon",
            deformation="non", etat_toiture="bon", etat_dalles="bon", espace_voisins_cm=50,
            normes="respecte", magnitude=4.0, distance_km=100)


class WebClient:
    """Client de test qui ajoute automatiquement le jeton CSRF aux POST."""

    def __init__(self):
        self.c = app.test_client()

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, data=None, csrf=True, **kw):
        with self.c.session_transaction() as s:
            token = s.setdefault("csrf_token", "test-token")
        data = dict(data or {})
        if csrf:
            data["csrf_token"] = token
        return self.c.post(url, data=data, **kw)

    def login(self, username, password):
        return self.post("/login", {"username": username, "password": password}, follow_redirects=True)

    def logout(self):
        return self.post("/logout")


def make_user(username, role="user", password="secret1"):
    """Crée un compte avec le rôle voulu (passage direct par la base)."""
    from werkzeug.security import generate_password_hash
    import database
    with app.app_context():
        db = database.get_db()
        db.execute("INSERT OR REPLACE INTO users (username, password_hash, role, created_at) VALUES (?,?,?,?)",
                   (username, generate_password_hash(password), role, database.now()))
        db.commit()


def basic(username, password):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def zone_id(name="Chlef"):
    """Identifiant d'une zone par défaut (Chlef : exposée ; Tamanrasset : sécurisée)."""
    import database
    with app.app_context():
        return database.get_db().execute("SELECT id FROM zones WHERE name = ?", (name,)).fetchone()["id"]


def form_data(**override):
    """Données de l'étape 2 (critères du bâtiment) pour une zone exposée aux séismes (Chlef)."""
    return {**{k: str(v) for k, v in SAFE.items()}, "building_name": "Immeuble test", "zone_id": str(zone_id()),
            **{k: str(v) for k, v in override.items()}}
