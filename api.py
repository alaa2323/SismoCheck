"""API REST (web services JSON). Authentification : HTTP Basic (nom d'utilisateur + mot de passe)."""
import json
from functools import wraps

from flask import Blueprint, g, jsonify, request, url_for
from werkzeug.security import check_password_hash

import engine
import security
import services
from database import get_db, load_rules, load_zones

api_bp = Blueprint("api", __name__, url_prefix="/api")


def jerr(message, code, **extra):
    resp = jsonify(error=message, **extra)
    resp.status_code = code
    return resp


def _basic_user():
    auth = request.authorization
    if not auth or not auth.username:
        return None
    key = auth.username.lower()
    if security.throttled(key):
        return "throttled"
    user = get_db().execute("SELECT * FROM users WHERE username = ?", (auth.username,)).fetchone()
    if user and check_password_hash(user["password_hash"], auth.password or ""):
        security.clear_failures(key)
        return user
    security.record_failure(key)
    return None


def api_auth(perm=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            user = _basic_user()
            if user == "throttled":
                return jerr("Trop de tentatives. Réessayez dans quelques minutes.", 429)
            if user is None:
                resp = jerr("Authentification requise (HTTP Basic).", 401)
                resp.headers["WWW-Authenticate"] = 'Basic realm="SismoCheck"'
                return resp
            if perm and not security.has_perm(user["role"], perm):
                return jerr("Droits insuffisants pour cette action.", 403)
            g.api_user = user
            return fn(*a, **kw)
        return wrapper
    return decorator


def _json_body():
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else None


# ---------------------------------------------------------------- service public
@api_bp.get("/health")
def health():
    return jsonify(status="ok", service="SismoCheck")


@api_bp.get("/fields")
def fields():
    """Champs attendus pour créer une évaluation."""
    return jsonify([{k: v for k, v in f.items() if k in ("name", "label", "type", "choices", "min", "max")}
                    for f in engine.FORM_FIELDS])


# ---------------------------------------------------------------- service RuleService
@api_bp.get("/rules")
@api_auth()
def list_rules():
    rows = get_db().execute("SELECT * FROM rules ORDER BY id").fetchall()
    return jsonify([services.rule_to_dict(r) for r in rows])


@api_bp.get("/rules/<int:rule_id>")
@api_auth()
def get_rule(rule_id):
    row = get_db().execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
    return jsonify(services.rule_to_dict(row)) if row else jerr("Règle introuvable.", 404)


@api_bp.post("/rules")
@api_auth("rules")
def create_rule():
    body = _json_body()
    if body is None:
        return jerr("Corps JSON attendu.", 400)
    rule, err = services.validate_rule(body, default_author=security.ROLES[g.api_user["role"]])
    if err:
        return jerr(err, 422)
    db = get_db()
    cur = db.execute("INSERT INTO rules (name, event, conditions, level, message, author, points) VALUES (?,?,?,?,?,?,?)",
                     (rule["name"], engine.EVENT_SUBMIT, json.dumps(rule["conditions"]), rule["level"],
                      rule["message"], rule["author"], rule["points"]))
    db.commit()
    row = db.execute("SELECT * FROM rules WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(services.rule_to_dict(row)), 201


@api_bp.put("/rules/<int:rule_id>")
@api_auth("rules")
def update_rule(rule_id):
    db = get_db()
    row = db.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
    if row is None:
        return jerr("Règle introuvable.", 404)
    body = _json_body()
    if body is None:
        return jerr("Corps JSON attendu.", 400)
    merged = {**services.rule_to_dict(row), **body}
    rule, err = services.validate_rule(merged)
    if err:
        return jerr(err, 422)
    active = 1 if merged.get("active", True) else 0
    db.execute("UPDATE rules SET name=?, conditions=?, level=?, message=?, author=?, points=?, active=? WHERE id=?",
               (rule["name"], json.dumps(rule["conditions"]), rule["level"], rule["message"],
                rule["author"], rule["points"], active, rule_id))
    db.commit()
    return jsonify(services.rule_to_dict(db.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()))


@api_bp.delete("/rules/<int:rule_id>")
@api_auth("rules")
def delete_rule(rule_id):
    db = get_db()
    if db.execute("SELECT 1 FROM rules WHERE id = ?", (rule_id,)).fetchone() is None:
        return jerr("Règle introuvable.", 404)
    db.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
    db.commit()
    return "", 204


# ---------------------------------------------------------------- service ZoneService
@api_bp.get("/zones")
@api_auth()
def list_zones():
    return jsonify([{**services.zone_to_dict(z), "buildings": z["buildings"]} for z in load_zones(get_db())])


@api_bp.get("/zones/<int:zone_id>")
@api_auth()
def get_zone(zone_id):
    zone = services.get_zone(get_db(), zone_id)
    return jsonify(services.zone_to_dict(zone)) if zone else jerr("Zone introuvable.", 404)


@api_bp.post("/zones")
@api_auth("rules")
def create_zone():
    body = _json_body()
    if body is None:
        return jerr("Corps JSON attendu.", 400)
    db = get_db()
    zone, err = services.validate_zone(db, body)
    if err:
        return jerr(err, 422)
    zid = services.save_zone(db, zone)
    return jsonify(services.zone_to_dict(services.get_zone(db, zid))), 201


@api_bp.put("/zones/<int:zone_id>")
@api_auth("rules")
def update_zone(zone_id):
    db = get_db()
    existing = services.get_zone(db, zone_id)
    if existing is None:
        return jerr("Zone introuvable.", 404)
    body = _json_body()
    if body is None:
        return jerr("Corps JSON attendu.", 400)
    zone, err = services.validate_zone(db, {**services.zone_to_dict(existing), **body}, zone_id)
    if err:
        return jerr(err, 422)
    services.save_zone(db, zone, zone_id)
    return jsonify(services.zone_to_dict(services.get_zone(db, zone_id)))


@api_bp.delete("/zones/<int:zone_id>")
@api_auth("rules")
def delete_zone(zone_id):
    if services.get_zone(get_db(), zone_id) is None:
        return jerr("Zone introuvable.", 404)
    err = services.delete_zone(get_db(), zone_id)
    return jerr(err, 409) if err else ("", 204)


# ---------------------------------------------------------------- service EvaluationService
@api_bp.post("/evaluations")
@api_auth("evaluate")
def create_evaluation():
    """Étape 1 : la zone (champ `zone`, nom ou id). Zone sécurisée -> les critères du bâtiment sont ignorés.
    Zone exposée -> les critères du bâtiment sont obligatoires (champ `data`, ou à plat)."""
    body = _json_body()
    if body is None:
        return jerr("Corps JSON attendu.", 400)
    db = get_db()
    ref = body.get("zone", body.get("zone_id"))
    if ref in (None, ""):
        return jerr("Le champ `zone` est obligatoire (nom ou id d'une zone).", 422)
    zone = services.get_zone(db, int(ref)) if str(ref).isdigit() else services.get_zone(db, name=ref)
    if zone is None:
        return jerr("Zone inconnue. Consultez GET /api/zones.", 422)
    name = str(body.get("building_name") or "Bâtiment sans nom").strip()[:120]
    data = None
    if not zone["secure"]:
        raw = body["data"] if isinstance(body.get("data"), dict) else {k: v for k, v in body.items() if k not in ("building_name", "zone", "zone_id")}
        data, errors = engine.parse_form({k: str(v) for k, v in raw.items()})
        if errors:
            return jerr("Données invalides.", 422, details=errors)
    eval_id = services.create_evaluation(db, g.api_user["id"], name, zone["id"], data)
    resp = jsonify(services.evaluation_to_dict(services.get_evaluation(db, eval_id)))
    resp.status_code = 201
    resp.headers["Location"] = url_for("api.get_evaluation", eval_id=eval_id)
    return resp


@api_bp.get("/evaluations")
@api_auth("evaluate")
def list_evaluations():
    owner = None if security.has_perm(g.api_user["role"], "all_evals") else g.api_user["id"]
    rows = services.search_evaluations(get_db(), owner, request.args.get("q", "").strip(), request.args.get("level", ""))
    return jsonify([services.evaluation_to_dict(r) for r in rows])


def _visible_evaluation(eval_id):
    row = services.get_evaluation(get_db(), eval_id)
    if row is None:
        return None, jerr("Évaluation introuvable.", 404)
    if row["user_id"] != g.api_user["id"] and not security.has_perm(g.api_user["role"], "all_evals"):
        return None, jerr("Droits insuffisants pour cette évaluation.", 403)
    return row, None


@api_bp.get("/evaluations/<int:eval_id>")
@api_auth()
def get_evaluation(eval_id):
    row, err = _visible_evaluation(eval_id)
    return err or jsonify(services.evaluation_to_dict(row))


@api_bp.delete("/evaluations/<int:eval_id>")
@api_auth()
def delete_evaluation(eval_id):
    row, err = _visible_evaluation(eval_id)
    if err:
        return err
    if row["user_id"] != g.api_user["id"] and g.api_user["role"] != "admin":
        return jerr("Seul le propriétaire ou un administrateur peut supprimer.", 403)
    services.delete_evaluation(get_db(), eval_id)
    return "", 204


# ---------------------------------------------------------------- service UserService
def _user_dict(u):
    return {"id": u["id"], "username": u["username"], "role": u["role"], "role_label": security.ROLES.get(u["role"], u["role"]),
            "created_at": u["created_at"]}


@api_bp.get("/users")
@api_auth("users")
def list_users():
    return jsonify([_user_dict(u) for u in get_db().execute("SELECT * FROM users ORDER BY id")])


@api_bp.patch("/users/<int:user_id>")
@api_auth("users")
def change_role(user_id):
    body, db = _json_body(), get_db()
    target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if target is None:
        return jerr("Utilisateur introuvable.", 404)
    role = (body or {}).get("role")
    if role not in security.ROLES:
        return jerr("Rôle invalide.", 422, allowed=list(security.ROLES))
    if target["id"] == g.api_user["id"]:
        return jerr("Vous ne pouvez pas modifier votre propre rôle.", 403)
    if "admin" in (role, target["role"]) and g.api_user["role"] != "admin":
        return jerr("Seul un administrateur peut attribuer ou retirer ce rôle.", 403)
    db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    db.commit()
    return jsonify(_user_dict(db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()))


@api_bp.delete("/users/<int:user_id>")
@api_auth("users")
def delete_user(user_id):
    db = get_db()
    target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if target is None:
        return jerr("Utilisateur introuvable.", 404)
    if target["id"] == g.api_user["id"]:
        return jerr("Vous ne pouvez pas supprimer votre propre compte.", 403)
    if target["role"] == "admin" and g.api_user["role"] != "admin":
        return jerr("Seul un administrateur peut supprimer un administrateur.", 403)
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return "", 204


# ---------------------------------------------------------------- service StatsService
@api_bp.get("/stats")
@api_auth("stats")
def stats():
    s, chart = services.compute_stats(get_db())
    return jsonify(stats=s, chart=chart)
