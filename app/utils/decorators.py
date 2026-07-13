"""Décorateurs de contrôle d'accès.

Le décorateur @periode_non_cloturee sera ajouté ici en Phase 4.
"""
from functools import wraps
from flask import abort, session, redirect, url_for
from flask_login import current_user


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
    activation). Session dédiée, totalement indépendante de Flask-Login
    et de current_user : évite toute interférence avec la résolution du
    tenant courant dans app/services/tenant.py (g.entreprise_id ne dépend
    que de current_user.is_authenticated, jamais de cette session)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("operateur_authentifie"):
            return redirect(url_for("operateur.login"))
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
