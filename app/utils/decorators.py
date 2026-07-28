"""Décorateurs de contrôle d'accès.

Le décorateur @periode_non_cloturee sera ajouté ici en Phase 4.
"""
from functools import wraps
from flask import abort, session, redirect, url_for
from flask_login import current_user, logout_user


# Hiérarchie : un rôle donne accès à tout ce qui est en dessous de lui
_HIERARCHIE = {"admin": 4, "promoteur": 3, "gerant": 2, "caissier": 1}


def role_required(role_minimum):
    """Restreint une vue au rôle minimum (hiérarchie admin > promoteur >
    gérant > caissier).

    Usage :
        @role_required("gerant")      # gérant, promoteur ou admin
        @role_required("promoteur")   # promoteur ou admin ("direction")
        @role_required("admin")       # admin uniquement
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if (_HIERARCHIE.get(current_user.role, 0)
                    < _HIERARCHIE.get(role_minimum, 99)):
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def operateur_required(view):
    """Protège les vues de l'espace opérateur SaaS (support/facturation/
    activation).

    CRITIQUE : le cookie "se souvenir de moi" de Flask-Login survit à
    session.clear() (c'est un cookie séparé, prévu pour survivre à un
    nettoyage de session). Si un opérateur avait une session locataire
    "mémorisée" active (testée avec "se souvenir de moi" coché), Flask-
    Login la restaure silencieusement sur la requête suivante — même
    après être passé par /operateur/login. g.entreprise_id (résolu
    depuis current_user.entreprise_id) redevenait alors celui de CE
    tenant fantôme, et le marquage automatique de tenant.py rattachait
    chaque nouvelle entreprise/boutique/compte créés pendant l'activation
    à ce tenant au lieu du nouveau client — bug réel constaté en
    production (plusieurs comptes clients rattachés à la mauvaise
    entreprise). On force donc explicitement la déconnexion Flask-Login
    (session ET cookie mémorisé) à chaque accès à l'espace opérateur,
    plutôt que de supposer qu'elle est déjà absente."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("operateur_authentifie"):
            return redirect(url_for("operateur.login"))
        if current_user.is_authenticated:
            logout_user()
        return view(*args, **kwargs)
    return wrapped


def associe_required(view):
    """Protège les vues de l'espace associé (part de chiffre d'affaires).
    Session dédiée (clé 'associe_username'), indépendante de Flask-Login
    et de l'accès opérateur : lecture seule, aucune capacité de gestion.
    Même précaution que operateur_required : un cookie "se souvenir de
    moi" locataire peut survivre à session.clear() et restaurer
    silencieusement current_user — on force donc la déconnexion."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("associe_username"):
            return redirect(url_for("associes.login"))
        if current_user.is_authenticated:
            logout_user()
        return view(*args, **kwargs)
    return wrapped


def periode_non_cloturee(extraire_date):
    """Bloque toute écriture (POST/PUT/DELETE) sur une période clôturée.

    `extraire_date` : fonction sans argument retournant la date concernée
    (lue dans request.form, request.args ou date du jour). Appliqué côté
    serveur : contourner l'interface ne sert à rien.

    Usage :
        @periode_non_cloturee(lambda: date.today())
        @periode_non_cloturee(_date_du_formulaire("date_achat"))
    """
    from flask import request, flash, redirect
    from app.services.clotures import periode_est_cloturee

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                resultat = extraire_date()
                jour, boutique_id = (resultat if isinstance(resultat, tuple)
                                     else (resultat, None))
                try:
                    boutique_id = int(boutique_id or
                                      request.form.get("boutique_id", 1))
                except (TypeError, ValueError):
                    boutique_id = 1
                if jour is not None and periode_est_cloturee(jour, boutique_id):
                    flash(
                        f"Période clôturée : aucune écriture possible sur le "
                        f"{jour.strftime('%d/%m/%Y')}. Demandez à un "
                        "administrateur de rouvrir la période.", "danger")
                    return redirect(request.referrer or "/")
            return view(*args, **kwargs)
        return wrapped
    return decorator


def _date_du_formulaire(champ):
    """Extracteur : lit une date ISO dans request.form[champ] (None si invalide)."""
    from datetime import date
    from flask import request

    def extraire():
        try:
            return date.fromisoformat(request.form.get(champ, ""))
        except ValueError:
            return None
    return extraire
