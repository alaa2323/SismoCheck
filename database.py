"""Couche persistance : schéma SQLite, connexion, migrations et données initiales."""
import json
import os
import sqlite3
from datetime import datetime

from flask import current_app, g
from werkzeug.security import generate_password_hash

import default_rules
import default_zones
import engine

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    event TEXT NOT NULL,
    conditions TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('faible','moyen','eleve')),
    message TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT 'Admin',
    active INTEGER NOT NULL DEFAULT 1,
    points INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS zones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    country TEXT NOT NULL DEFAULT '',
    secure INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS buildings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    zone_id INTEGER REFERENCES zones(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    building_id INTEGER NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    level TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    triggered TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evaluations_user ON evaluations(user_id);
"""


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _columns(db, table):
    return {r[1] for r in db.execute(f"PRAGMA table_info({table})")}


def _migrate(db):
    """Met à niveau une base créée par une version précédente (rôles, points, score)."""
    row = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    if row and "CHECK (role IN" in row[0]:  # ancienne contrainte : seulement admin / user
        db.execute("PRAGMA foreign_keys = OFF")
        db.executescript("""
            CREATE TABLE users_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', created_at TEXT NOT NULL);
            INSERT INTO users_new SELECT id, username, password_hash, role, created_at FROM users;
            DROP TABLE users;
            ALTER TABLE users_new RENAME TO users;
        """)
        db.execute("PRAGMA foreign_keys = ON")
    if "points" not in _columns(db, "rules"):
        db.execute("ALTER TABLE rules ADD COLUMN points INTEGER NOT NULL DEFAULT 0")
        for level, pts in engine.DEFAULT_POINTS.items():
            db.execute("UPDATE rules SET points = ? WHERE level = ?", (pts, level))
    if "score" not in _columns(db, "evaluations"):
        db.execute("ALTER TABLE evaluations ADD COLUMN score INTEGER NOT NULL DEFAULT 0")
    if "zone_id" not in _columns(db, "buildings"):
        db.execute("ALTER TABLE buildings ADD COLUMN zone_id INTEGER REFERENCES zones(id) ON DELETE RESTRICT")
    db.commit()


def init_db(path):
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    _migrate(db)
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        password = os.environ.get("ADMIN_PASSWORD", "admin123")
        db.execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?,?,?,?)",
                   ("admin", generate_password_hash(password), "admin", now()))
    if db.execute("SELECT COUNT(*) FROM zones").fetchone()[0] == 0:
        db.executemany("INSERT INTO zones (name, country, secure, note) VALUES (?,?,?,?)",
                       [(z["name"], z["country"], z["secure"], z["note"]) for z in default_zones.DEFAULT_ZONES])
    if db.execute("SELECT COUNT(*) FROM rules").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO rules (name, event, conditions, level, message, author, points) VALUES (?,?,?,?,?,?,?)",
            list(default_rules.as_db_rows()))
    db.commit()
    db.close()


def load_rules(db):
    """Retourne toutes les règles avec leurs conditions décodées."""
    rows = db.execute("SELECT * FROM rules ORDER BY id").fetchall()
    return [{**dict(r), "conditions": json.loads(r["conditions"]), "active": bool(r["active"])} for r in rows]


def load_zones(db):
    """Toutes les zones, avec le nombre de bâtiments évalués dans chacune."""
    rows = db.execute("""SELECT z.*, (SELECT COUNT(*) FROM buildings b WHERE b.zone_id = z.id) AS buildings
                         FROM zones z ORDER BY z.name COLLATE NOCASE""").fetchall()
    return [{**dict(r), "secure": bool(r["secure"])} for r in rows]
