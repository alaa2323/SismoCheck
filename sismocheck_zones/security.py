"""Rôles, permissions (RBAC), protection CSRF et limitation des tentatives de connexion."""
import secrets
import time
from functools import wraps

from flask import abort, flash, redirect, session, url_for, request

ROLES = {
    "admin": "Administrateur",
    "domain_manager": "Domain-Manager",
    "it_admin": "IT_ADMIN",
    "user": "Client",
}

# Permissions par rôle
#   evaluate  : remplir le formulaire et voir ses propres évaluations
#   rules     : créer / modifier / supprimer les règles métier
#   users     : gérer les comptes et les rôles
#   stats     : voir le tableau de bord et les statistiques
#   all_evals : voir les évaluations de tous les utilisateurs
PERMS = {
    "admin": {"evaluate", "rules", "users", "stats", "all_evals"},
    "domain_manager": {"evaluate", "rules", "stats", "all_evals"},
    "it_admin": {"users", "stats", "all_evals"},
    "user": {"evaluate"},
}


def has_perm(role, perm):
    return perm in PERMS.get(role, set())


# ---------------------------------------------------------------- décorateurs web
def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if "user_id" not in session:
            flash("Veuillez vous connecter.", "warning")
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


def perm_required(perm):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*a, **kw):
            if not has_perm(session.get("role"), perm):
                abort(403)
            return view(*a, **kw)
        return wrapped
    return decorator


# ---------------------------------------------------------------- CSRF
def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


def check_csrf():
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    expected = session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(sent.encode(), expected.encode()):
        abort(400)


# ---------------------------------------------------------------- limitation des tentatives
MAX_FAILS, WINDOW_SECONDS = 5, 300
_FAILS = {}


def throttled(key):
    recent = [t for t in _FAILS.get(key, []) if time.time() - t < WINDOW_SECONDS]
    _FAILS[key] = recent
    return len(recent) >= MAX_FAILS


def record_failure(key):
    _FAILS.setdefault(key, []).append(time.time())


def clear_failures(key):
    _FAILS.pop(key, None)
