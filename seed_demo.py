"""Remplit la base avec des comptes et des évaluations de démonstration (utile pour la soutenance).

Usage :  python seed_demo.py
Comptes créés (mot de passe : demo123) : manager (Domain-Manager), itadmin (IT_ADMIN), client1, client2 (Clients).
"""
import random
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

import database
import engine
import services
from app import app

PASSWORD = "demo123"
ACCOUNTS = [("manager", "domain_manager"), ("itadmin", "it_admin"), ("client1", "user"), ("client2", "user")]
NAMES = ["Villa Rose", "Immeuble A", "Résidence El Amal", "Tour Nord", "Maison Familiale", "Bloc B3", "Cité 200 logements", "École Primaire"]


def random_data(rng):
    data = {}
    for f in engine.FORM_FIELDS:
        if f["type"] == "choice":
            values = [v for v, _ in f["choices"]]
            weights = [0.85] + [0.15 / (len(values) - 1)] * (len(values) - 1)  # le plus souvent l'état le plus sain
            data[f["name"]] = rng.choices(values, weights)[0]
        elif f["name"] == "annee_construction":
            data[f["name"]] = rng.choice([rng.randint(1960, 2000), rng.randint(2001, 2024), rng.randint(2005, 2024)])
        elif f["name"] == "nb_etages":
            data[f["name"]] = rng.choice([2, 3, 4, 5, 6, 8, 10])
        elif f["name"] == "espace_voisins_cm":
            data[f["name"]] = rng.choice([12, 20, 30, 40, 80, 8])
        elif f["name"] == "magnitude":
            data[f["name"]] = round(rng.choice([rng.uniform(3.0, 5.0), rng.uniform(3.0, 5.4), rng.uniform(5.0, 7.0)]), 1)
        else:
            data[f["name"]] = round(rng.choice([rng.uniform(30, 150), rng.uniform(40, 200), rng.uniform(5, 40)]), 1)
    return data


def main():
    rng = random.Random(7)
    with app.app_context():
        db = database.get_db()
        ids = {}
        for username, role in ACCOUNTS:
            if not db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
                db.execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?,?,?,?)",
                           (username, generate_password_hash(PASSWORD), role, database.now()))
            ids[username] = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]
        db.commit()
        zones = database.load_zones(db)
        for _ in range(40):
            owner = rng.choice(["client1", "client2"])
            zone = rng.choice(zones)
            data = None if zone["secure"] else random_data(rng)  # zone sécurisée : le bâtiment n'est pas évalué
            eval_id = services.create_evaluation(db, ids[owner], rng.choice(NAMES), zone["id"], data)
            when = (datetime.now() - timedelta(days=rng.randint(0, 29), hours=rng.randint(0, 10))).strftime("%Y-%m-%d %H:%M")
            db.execute("UPDATE evaluations SET created_at = ? WHERE id = ?", (when, eval_id))
        db.commit()
    print("Démonstration prête : 4 comptes (mot de passe demo123) et 40 évaluations.")


if __name__ == "__main__":
    main()
