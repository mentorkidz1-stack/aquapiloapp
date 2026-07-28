"""Blueprint associes — chaque associé consulte sa part du chiffre
d'affaires mensuel des abonnements actifs. Lecture seule, aucune
capacité de gestion (contrairement à l'espace opérateur). Session
dédiée (@associe_required), indépendante de Flask-Login et de l'accès
opérateur — cf. app/services/tenant.py, non modifié ici."""
import hmac

from flask import (Blueprint, render_template, redirect, url_for, flash,
                   session, current_app)
from flask_login import current_user, logout_user

from app.extensions import bcrypt
from app.services.facturation import detail_entreprises, total_mensuel_actif
from app.blueprints.associes.forms import AssocieLoginForm
from app.utils.decorators import associe_required

associes_bp = Blueprint("associes", __name__, url_prefix="/associes")


def _associes_configures():
    return [a for a in current_app.config.get("ASSOCIES", []) if a.get("username")]


@associes_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("associe_username"):
        return redirect(url_for("associes.dashboard"))

    form = AssocieLoginForm()
    if form.validate_on_submit():
        fourni = form.username.data.strip()
        trouve = next((a for a in _associes_configures()
                       if hmac.compare_digest(fourni, a["username"])), None)
        if (trouve and trouve.get("password_hash")
                and bcrypt.check_password_hash(trouve["password_hash"], form.password.data)):
            if current_user.is_authenticated:
                logout_user()
            session.clear()
            session["associe_username"] = trouve["username"]
            session.permanent = True
            flash(f"Bienvenue, {trouve['nom']} !", "success")
            return redirect(url_for("associes.dashboard"))
        flash("Identifiants incorrects.", "danger")

    return render_template("associes/login.html", form=form)


@associes_bp.route("/logout")
@associe_required
def logout():
    session.pop("associe_username", None)
    flash("Déconnecté.", "info")
    return redirect(url_for("associes.login"))


@associes_bp.route("/")
@associe_required
def dashboard():
    moi = next((a for a in _associes_configures()
               if a["username"] == session.get("associe_username")), None)
    if moi is None:
        # Config modifiée après la connexion (compte retiré du .env)
        session.pop("associe_username", None)
        return redirect(url_for("associes.login"))

    total = total_mensuel_actif()
    parts = [{"nom": a["nom"], "pourcentage": a["pourcentage"],
             "montant": round(total * a["pourcentage"] / 100),
             "toi": a["username"] == moi["username"]}
            for a in _associes_configures()]
    part_moi = next(p for p in parts if p["toi"])

    return render_template("associes/dashboard.html", moi=moi, total=total,
                           parts=parts, part_moi=part_moi,
                           entreprises=detail_entreprises())
