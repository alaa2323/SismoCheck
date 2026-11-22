"""Application web SismoCheck : évaluation du risque sismique d'un bâtiment (Rule-Based, ECA)."""
import json
import os
import re
import sqlite3

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import database
import engine
import security
import services
from api import api_bp
from database import get_db, now
from security import login_required, perm_required

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")
app.config["DATABASE"] = os.environ.get("DATABASE", os.path.join(BASE_DIR, "seismic.db"))
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.register_blueprint(api_bp)
app.teardown_appcontext(database.close_db)


@app.before_request
def csrf_protect():
    if request.method == "POST" and request.blueprint != "api":
        security.check_csrf()


@app.context_processor
def inject_globals():
    role = session.get("role")
    return {"LEVEL_LABELS": engine.LEVEL_LABELS, "LEVEL_COLORS": engine.LEVEL_COLORS, "ROLES": security.ROLES,
            "can": lambda perm: security.has_perm(role, perm), "csrf_token": security.csrf_token,
            "role_label": security.ROLES.get(role, "")}


@app.errorhandler(400)
def bad_request(_e):
    return render_template("error.html", code=400, msg="Formulaire expiré ou invalide. Rechargez la page et réessayez."), 400


@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403, msg="Vous n'avez pas les droits pour accéder à cette page."), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, msg="Page introuvable."), 404


# ---------------------------------------------------------------- authentification
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("admin_dashboard" if security.has_perm(session["role"], "stats") else "evaluate"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", username):
            flash("Nom d'utilisateur : 3 à 30 caractères (lettres, chiffres, _ . -).", "danger")
        elif len(password) < 6:
            flash("Le mot de passe doit contenir au moins 6 caractères.", "danger")
        else:
            try:
                get_db().execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?,?,?,?)",
                                 (username, generate_password_hash(password), "user", now()))
                get_db().commit()
                flash("Compte créé. Vous pouvez vous connecter.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Ce nom d'utilisateur existe déjà.", "danger")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        key = username.lower()
        if security.throttled(key):
            flash("Trop de tentatives. Réessayez dans quelques minutes.", "danger")
        else:
            user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
                security.clear_failures(key)
                session.clear()
                session.update(user_id=user["id"], username=user["username"], role=user["role"])
                return redirect(url_for("index"))
            security.record_failure(key)
            flash("Identifiants incorrects.", "danger")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        user = get_db().execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        new, confirm = request.form.get("new_password", ""), request.form.get("confirm_password", "")
        if not check_password_hash(user["password_hash"], request.form.get("current_password", "")):
            flash("Le mot de passe actuel est incorrect.", "danger")
        elif len(new) < 6:
            flash("Le nouveau mot de passe doit contenir au moins 6 caractères.", "danger")
        elif new != confirm:
            flash("La confirmation ne correspond pas au nouveau mot de passe.", "danger")
        else:
            get_db().execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new), user["id"]))
            get_db().commit()
            flash("Mot de passe modifié.", "success")
            return redirect(url_for("account"))
    return render_template("account.html")


# ---------------------------------------------------------------- évaluations
def _zones():
    return database.load_zones(get_db())


@app.route("/evaluate", methods=["GET", "POST"])
@perm_required("evaluate")
def evaluate():
    """Étape 1 : choisir la zone. Zone sécurisée -> résultat direct. Zone exposée -> étape 2 (critères du bâtiment)."""
    if request.method == "POST":
        name = request.form.get("building_name", "").strip()[:120] or "Bâtiment sans nom"
        zone = services.get_zone(get_db(), request.form.get("zone_id", type=int))
        if zone is None:
            flash("Choisissez une zone dans la liste.", "danger")
        elif zone["secure"]:
            eval_id = services.create_evaluation(get_db(), session["user_id"], name, zone["id"])
            return redirect(url_for("result", eval_id=eval_id))
        else:
            return render_template("evaluate_building.html", fields=engine.FORM_FIELDS, values={}, zone=zone, building_name=name)
    return render_template("evaluate.html", zones=_zones(), values=request.form)


@app.route("/evaluate/building", methods=["GET", "POST"])
@perm_required("evaluate")
def evaluate_building():
    """Étape 2 : critères du bâtiment (seulement pour une zone exposée aux séismes)."""
    if request.method == "GET":
        return redirect(url_for("evaluate"))
    name = request.form.get("building_name", "").strip()[:120] or "Bâtiment sans nom"
    zone = services.get_zone(get_db(), request.form.get("zone_id", type=int))
    if zone is None:
        flash("Choisissez une zone dans la liste.", "danger")
        return redirect(url_for("evaluate"))
    if zone["secure"]:  # la zone a été classée sécurisée entre-temps : le bâtiment n'est pas évalué
        return redirect(url_for("result", eval_id=services.create_evaluation(get_db(), session["user_id"], name, zone["id"])))
    data, errors = engine.parse_form(request.form)
    if errors:
        for e in errors:
            flash(e, "danger")
        return render_template("evaluate_building.html", fields=engine.FORM_FIELDS, values=request.form, zone=zone, building_name=name)
    return redirect(url_for("result", eval_id=services.create_evaluation(get_db(), session["user_id"], name, zone["id"], data)))


@app.route("/result/<int:eval_id>")
@login_required
def result(eval_id):
    ev = services.get_evaluation(get_db(), eval_id)
    if ev is None:
        abort(404)
    if ev["user_id"] != session["user_id"] and not security.has_perm(session["role"], "all_evals"):
        abort(403)
    return render_template("result.html", ev=ev, triggered=json.loads(ev["triggered"]),
                           data=json.loads(ev["building_data"]), fields=engine.FORM_FIELDS)


@app.post("/evaluations/<int:eval_id>/delete")
@login_required
def evaluation_delete(eval_id):
    ev = services.get_evaluation(get_db(), eval_id)
    if ev is None:
        abort(404)
    owner = ev["user_id"] == session["user_id"]
    if not owner and session["role"] != "admin":
        abort(403)
    services.delete_evaluation(get_db(), eval_id)
    flash("Évaluation supprimée.", "info")
    return redirect(url_for("history" if owner else "all_evaluations"))


@app.route("/history")
@perm_required("evaluate")
def history():
    q, level = request.args.get("q", "").strip(), request.args.get("level", "")
    rows = services.search_evaluations(get_db(), session["user_id"], q, level)
    return render_template("history.html", rows=rows, q=q, level=level)


@app.route("/admin/evaluations")
@perm_required("all_evals")
def all_evaluations():
    q, level = request.args.get("q", "").strip(), request.args.get("level", "")
    rows = services.search_evaluations(get_db(), None, q, level)
    return render_template("all_evaluations.html", rows=rows, q=q, level=level)


# ---------------------------------------------------------------- tableau de bord
@app.route("/admin")
@perm_required("stats")
def admin_dashboard():
    stats, chart = services.compute_stats(get_db())
    me = get_db().execute("SELECT password_hash FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    weak = bool(me) and check_password_hash(me["password_hash"], "admin123")
    return render_template("admin_dashboard.html", stats=stats, chart=chart, weak_password=weak)


# ---------------------------------------------------------------- règles (Domain-Manager)
@app.route("/admin/rules")
@perm_required("rules")
def rules_list():
    return render_template("rules_list.html", rules=database.load_rules(get_db()))


def _rule_payload(form):
    conditions = []
    for i in range(5):
        field, op, value = form.get(f"c_field_{i}", ""), form.get(f"c_op_{i}", ""), form.get(f"c_value_{i}", "").strip()
        if field or value:
            conditions.append({"field": field, "op": op, "value": value})
    return {"name": form.get("name"), "message": form.get("message"), "level": form.get("level"),
            "conditions": conditions, "author": form.get("author"), "points": form.get("points")}


@app.route("/admin/rules/new", methods=["GET", "POST"])
@app.route("/admin/rules/<int:rule_id>/edit", methods=["GET", "POST"])
@perm_required("rules")
def rule_form(rule_id=None):
    db, rule = get_db(), None
    if rule_id:
        row = db.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
        if row is None:
            abort(404)
        rule = services.rule_to_dict(row)
    if request.method == "POST":
        new, err = services.validate_rule(_rule_payload(request.form), default_author=security.ROLES[session["role"]])
        if err:
            flash(err, "danger")
        else:
            if rule_id:
                db.execute("UPDATE rules SET name=?, conditions=?, level=?, message=?, author=?, points=? WHERE id=?",
                           (new["name"], json.dumps(new["conditions"]), new["level"], new["message"], new["author"], new["points"], rule_id))
            else:
                db.execute("INSERT INTO rules (name, event, conditions, level, message, author, points) VALUES (?,?,?,?,?,?,?)",
                           (new["name"], engine.EVENT_SUBMIT, json.dumps(new["conditions"]), new["level"], new["message"], new["author"], new["points"]))
            db.commit()
            flash("Règle enregistrée.", "success")
            return redirect(url_for("rules_list"))
    return render_template("rule_form.html", rule=rule, fields=engine.RULE_FIELDS, ops=engine.OPERATORS)


@app.post("/admin/rules/<int:rule_id>/toggle")
@perm_required("rules")
def rule_toggle(rule_id):
    get_db().execute("UPDATE rules SET active = 1 - active WHERE id = ?", (rule_id,))
    get_db().commit()
    return redirect(url_for("rules_list"))


@app.post("/admin/rules/<int:rule_id>/delete")
@perm_required("rules")
def rule_delete(rule_id):
    get_db().execute("DELETE FROM rules WHERE id = ?", (rule_id,))
    get_db().commit()
    flash("Règle supprimée.", "info")
    return redirect(url_for("rules_list"))


# ---------------------------------------------------------------- zones (Domain-Manager)
@app.route("/admin/zones")
@perm_required("rules")
def zones_list():
    return render_template("zones_list.html", zones=_zones())


@app.route("/admin/zones/new", methods=["GET", "POST"])
@app.route("/admin/zones/<int:zone_id>/edit", methods=["GET", "POST"])
@perm_required("rules")
def zone_form(zone_id=None):
    db, zone = get_db(), None
    if zone_id:
        zone = services.get_zone(db, zone_id)
        if zone is None:
            abort(404)
    values = request.form if request.method == "POST" else (services.zone_to_dict(zone) if zone else {})
    if request.method == "POST":
        new, err = services.validate_zone(db, request.form, zone_id)
        if err:
            flash(err, "danger")
        else:
            services.save_zone(db, new, zone_id)
            flash("Zone enregistrée.", "success")
            return redirect(url_for("zones_list"))
    return render_template("zone_form.html", zone=zone, values=values)


@app.post("/admin/zones/<int:zone_id>/delete")
@perm_required("rules")
def zone_delete(zone_id):
    if services.get_zone(get_db(), zone_id) is None:
        abort(404)
    err = services.delete_zone(get_db(), zone_id)
    flash(err or "Zone supprimée.", "danger" if err else "info")
    return redirect(url_for("zones_list"))


# ---------------------------------------------------------------- utilisateurs (IT_ADMIN)
@app.route("/admin/users")
@perm_required("users")
def users_list():
    return render_template("users_list.html", users=get_db().execute("SELECT * FROM users ORDER BY id").fetchall())


@app.post("/admin/users/<int:user_id>/role")
@perm_required("users")
def user_role(user_id):
    db = get_db()
    target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    role = request.form.get("role", "")
    if target is None:
        abort(404)
    if role not in security.ROLES:
        flash("Rôle invalide.", "danger")
    elif user_id == session["user_id"]:
        flash("Vous ne pouvez pas modifier votre propre rôle.", "warning")
    elif "admin" in (role, target["role"]) and session["role"] != "admin":
        flash("Seul un administrateur peut attribuer ou retirer le rôle Administrateur.", "danger")
    else:
        db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        db.commit()
        flash(f"Rôle de {target['username']} : {security.ROLES[role]}.", "success")
    return redirect(url_for("users_list"))


@app.post("/admin/users/<int:user_id>/delete")
@perm_required("users")
def user_delete(user_id):
    db = get_db()
    target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if target is None:
        abort(404)
    if user_id == session["user_id"]:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "warning")
    elif target["role"] == "admin" and session["role"] != "admin":
        flash("Seul un administrateur peut supprimer un administrateur.", "danger")
    else:
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
        flash("Utilisateur supprimé.", "info")
    return redirect(url_for("users_list"))


database.init_db(app.config["DATABASE"])

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
