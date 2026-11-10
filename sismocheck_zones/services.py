"""Logique métier partagée par l'interface web et l'API REST."""
import json
from datetime import date, timedelta

import engine
from database import load_rules, now

EVAL_SELECT = """
    SELECT e.id, e.user_id, e.level, e.score, e.triggered, e.created_at,
           b.name AS building_name, b.data AS building_data, b.zone_id, u.username,
           z.name AS zone_name, z.country AS zone_country, z.secure AS zone_secure
    FROM evaluations e
    JOIN buildings b ON b.id = e.building_id
    JOIN users u ON u.id = e.user_id
    LEFT JOIN zones z ON z.id = b.zone_id
"""


# ---------------------------------------------------------------- évaluations
def get_zone(db, zone_id=None, name=None):
    """Retourne la zone (par id ou par nom) ou None."""
    if zone_id is not None:
        return db.execute("SELECT * FROM zones WHERE id = ?", (zone_id,)).fetchone()
    return db.execute("SELECT * FROM zones WHERE name = ? COLLATE NOCASE", (str(name or "").strip(),)).fetchone()


def create_evaluation(db, user_id, building_name, zone_id, data=None):
    """Évalue un bâtiment en deux temps, puis enregistre le bâtiment et l'évaluation. Retourne l'id.

    1) La zone est contrôlée en premier. Si elle est sécurisée (non exposée aux séismes), les critères
       du bâtiment ne sont pas regardés : le niveau est « faible ».
    2) Sinon, les règles actives sont appliquées aux critères du bâtiment (`data`).
    """
    zone = get_zone(db, zone_id)
    if zone is None:
        raise ValueError("Zone inconnue.")
    if zone["secure"]:
        data = {}
        level, triggered = engine.zone_result(dict(zone))
    else:
        if not data:
            raise ValueError("Les critères du bâtiment sont obligatoires pour une zone exposée.")
        level, triggered = engine.evaluate(data, load_rules(db))
    score = engine.score(triggered)
    cur = db.execute("INSERT INTO buildings (user_id, zone_id, name, data, created_at) VALUES (?,?,?,?,?)",
                     (user_id, zone["id"], building_name, json.dumps(data), now()))
    cur = db.execute(
        "INSERT INTO evaluations (building_id, user_id, level, score, triggered, created_at) VALUES (?,?,?,?,?,?)",
        (cur.lastrowid, user_id, level, score, json.dumps(triggered), now()))
    db.commit()
    return cur.lastrowid


def get_evaluation(db, eval_id):
    return db.execute(EVAL_SELECT + " WHERE e.id = ?", (eval_id,)).fetchone()


def evaluation_to_dict(row):
    return {
        "id": row["id"], "building_name": row["building_name"], "user": row["username"],
        "level": row["level"], "level_label": engine.LEVEL_LABELS[row["level"]], "score": row["score"],
        "triggered_rules": json.loads(row["triggered"]), "data": json.loads(row["building_data"]),
        "created_at": row["created_at"],
        "zone": {"id": row["zone_id"], "name": row["zone_name"], "country": row["zone_country"],
                 "secure": None if row["zone_secure"] is None else bool(row["zone_secure"])},
        "building_evaluated": not row["zone_secure"],
    }


def search_evaluations(db, user_id=None, q="", level=""):
    """Liste filtrée (utilisateur, texte, niveau), de la plus récente à la plus ancienne."""
    sql, params, where = EVAL_SELECT, [], []
    if user_id is not None:
        where.append("e.user_id = ?"); params.append(user_id)
    if q:
        where.append("(b.name LIKE ? OR u.username LIKE ?)"); params += [f"%{q}%", f"%{q}%"]
    if level in engine.LEVELS:
        where.append("e.level = ?"); params.append(level)
    if where:
        sql += " WHERE " + " AND ".join(where)
    return db.execute(sql + " ORDER BY e.id DESC", params).fetchall()


def delete_evaluation(db, eval_id):
    row = db.execute("SELECT building_id FROM evaluations WHERE id = ?", (eval_id,)).fetchone()
    if row:
        db.execute("DELETE FROM buildings WHERE id = ?", (row["building_id"],))  # supprime l'évaluation en cascade
        db.commit()


# ---------------------------------------------------------------- zones
def zone_to_dict(z):
    return {"id": z["id"], "name": z["name"], "country": z["country"], "secure": bool(z["secure"]), "note": z["note"]}


def validate_zone(db, payload, zone_id=None):
    """Valide une zone (web ou API). Retourne (zone_nettoyée, None) ou (None, message_d_erreur)."""
    name = str(payload.get("name") or "").strip()
    if not 2 <= len(name) <= 60:
        return None, "Le nom de la zone doit contenir de 2 à 60 caractères."
    other = db.execute("SELECT id FROM zones WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    if other and other["id"] != zone_id:
        return None, "Une zone porte déjà ce nom."
    secure = payload.get("secure")
    secure = str(secure).lower() in ("1", "true", "on", "yes") if not isinstance(secure, bool) else secure
    return {"name": name, "country": str(payload.get("country") or "").strip()[:60],
            "secure": secure, "note": str(payload.get("note") or "").strip()[:200]}, None


def save_zone(db, zone, zone_id=None):
    if zone_id is None:
        cur = db.execute("INSERT INTO zones (name, country, secure, note) VALUES (?,?,?,?)",
                         (zone["name"], zone["country"], 1 if zone["secure"] else 0, zone["note"]))
        zone_id = cur.lastrowid
    else:
        db.execute("UPDATE zones SET name=?, country=?, secure=?, note=? WHERE id=?",
                   (zone["name"], zone["country"], 1 if zone["secure"] else 0, zone["note"], zone_id))
    db.commit()
    return zone_id


def delete_zone(db, zone_id):
    """Supprime une zone sans bâtiment. Retourne un message d'erreur ou None."""
    n = db.execute("SELECT COUNT(*) FROM buildings WHERE zone_id = ?", (zone_id,)).fetchone()[0]
    if n:
        return f"Cette zone est utilisée par {n} bâtiment(s) évalué(s) : elle ne peut pas être supprimée."
    db.execute("DELETE FROM zones WHERE id = ?", (zone_id,))
    db.commit()
    return None


# ---------------------------------------------------------------- règles
def rule_to_dict(row):
    return {"id": row["id"], "name": row["name"], "event": row["event"], "conditions": json.loads(row["conditions"]),
            "level": row["level"], "message": row["message"], "author": row["author"],
            "points": row["points"], "active": bool(row["active"])}


def validate_rule(payload, default_author="Admin"):
    """Valide une règle (web ou API). Retourne (règle_nettoyée, None) ou (None, message_d_erreur)."""
    name, message = str(payload.get("name") or "").strip(), str(payload.get("message") or "").strip()
    level, conditions = payload.get("level"), payload.get("conditions")
    if not name or not message:
        return None, "Le nom et le message sont obligatoires."
    if level not in engine.LEVELS:
        return None, "Niveau invalide (faible, moyen ou eleve)."
    if not isinstance(conditions, list) or not conditions:
        return None, "Au moins une condition est obligatoire."
    clean = []
    for c in conditions:
        if not isinstance(c, dict):
            return None, "Condition invalide."
        field, op, value = c.get("field"), c.get("op"), str(c.get("value", "")).strip().replace(",", ".")
        if field not in engine.RULE_FIELDS or op not in engine.OPERATORS or not value:
            return None, "Condition invalide : champ, opérateur et valeur sont obligatoires."
        spec = engine.RULE_FIELDS[field]
        if spec["type"] == "choice":
            if value not in [v for v, _ in spec["choices"]]:
                return None, f"Valeur « {value} » invalide pour le champ {field}."
            if op not in ("==", "!="):
                return None, f"Le champ {field} accepte seulement == ou !=."
        else:
            try:
                float(value)
            except ValueError:
                return None, f"Le champ {field} attend un nombre."
        clean.append({"field": field, "op": op, "value": value})
    try:
        points = int(payload.get("points") if payload.get("points") not in (None, "") else engine.DEFAULT_POINTS[level])
    except (TypeError, ValueError):
        return None, "Les points doivent être un nombre entier."
    if not 0 <= points <= 100:
        return None, "Les points doivent être compris entre 0 et 100."
    author = str(payload.get("author") or "").strip() or default_author
    return {"name": name, "message": message, "level": level, "conditions": clean,
            "points": points, "author": author[:60]}, None


# ---------------------------------------------------------------- statistiques
def compute_stats(db):
    total = db.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
    by_level = {r["level"]: r["n"] for r in db.execute("SELECT level, COUNT(*) AS n FROM evaluations GROUP BY level")}
    days = [date.today() - timedelta(days=i) for i in range(29, -1, -1)]
    keys = [d.isoformat() for d in days]
    per_day = {k: {"faible": 0, "moyen": 0, "eleve": 0} for k in keys}
    for r in db.execute("SELECT substr(created_at, 1, 10) AS d, level, COUNT(*) AS n FROM evaluations GROUP BY d, level"):
        if r["d"] in per_day and r["level"] in per_day[r["d"]]:
            per_day[r["d"]][r["level"]] = r["n"]
    signups = {k: 0 for k in keys}
    for r in db.execute("SELECT substr(created_at, 1, 10) AS d, COUNT(*) AS n FROM users GROUP BY d"):
        if r["d"] in signups:
            signups[r["d"]] = r["n"]
    chart = {
        "labels": [d.strftime("%d/%m") for d in days],
        "faible": [per_day[k]["faible"] for k in keys], "moyen": [per_day[k]["moyen"] for k in keys],
        "eleve": [per_day[k]["eleve"] for k in keys], "total": [sum(per_day[k].values()) for k in keys],
        "users": [signups[k] for k in keys],
        "levels": [by_level.get("faible", 0), by_level.get("moyen", 0), by_level.get("eleve", 0)],
    }
    counts = {}
    for r in db.execute("SELECT triggered FROM evaluations"):
        for t in json.loads(r["triggered"]):
            if t["name"] == "Aucune anomalie détectée":
                continue
            item = counts.setdefault(t["name"], {"name": t["name"], "level": t["level"], "message": t["message"], "n": 0})
            item["n"] += 1
    rules_total = db.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
    rules_active = db.execute("SELECT COUNT(*) FROM rules WHERE active = 1").fetchone()[0]
    avg = db.execute("SELECT AVG(score) FROM evaluations").fetchone()[0]
    stats = {
        "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "rules": rules_total, "rules_active": rules_active,
        "evaluations": total, "by_level": by_level,
        "top_rules": sorted(counts.values(), key=lambda x: -x["n"])[:4],
        "high_pct": round(by_level.get("eleve", 0) * 100 / total) if total else 0,
        "avg_score": round(avg) if avg is not None else 0,
        "week_eval": sum(chart["total"][-7:]), "week_high": sum(chart["eleve"][-7:]),
        "week_users": sum(chart["users"][-7:]),
    }
    return stats, chart
