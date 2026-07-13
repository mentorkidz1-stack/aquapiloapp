"""Blueprint auth — connexion et déconnexion."""
from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from app.blueprints.auth.forms import LoginForm
from app.models import User
from app.services.tenant import sans_filtre_tenant

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        # Avant authentification, l'entreprise de l'utilisateur n'est pas
        # encore connue : recherche volontairement cross-tenant par
        # username, via le bypass explicite (cf. app/services/tenant.py).
        with sans_filtre_tenant():
            user = User.query.filter_by(username=form.username.data.strip()).first()
        if user and user.actif and user.check_password(form.password.data):
            # Efface tout accès opérateur qui traînerait dans cette session
            # (même navigateur) : une connexion locataire ne doit jamais
            # hériter d'un accès cross-tenant précédemment établi.
            session.pop("operateur_authentifie", None)
            login_user(user, remember=form.remember.data)
            flash(f"Bienvenue, {user.nom_complet} !", "success")
            # Sécurité : n'accepter que des redirections internes
            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("main.dashboard"))
        flash("Identifiants incorrects ou compte désactivé.", "danger")

    return render_template("auth/login.html", form=form, annee=date.today().year)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("operateur_authentifie", None)
    flash("Vous êtes déconnecté(e).", "info")
    return redirect(url_for("auth.login"))
