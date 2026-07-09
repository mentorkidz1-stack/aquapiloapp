"""Blueprint main — tableau de bord adapté au rôle."""
from datetime import date

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from app.models import Boutique
from app.services.rapports import (alertes_stock, indicateurs_periode,
                                   repartition_paiements, serie_jours)

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def dashboard():
    auj = date.today()

    # Caissier : page minimale orientée caisse
    if not current_user.is_gerant:
        return render_template("main/dashboard_caissier.html",
                               aujourdhui=auj)

    boutique_id = request.args.get("boutique", type=int)  # None = consolidé
    boutiques = Boutique.query.filter_by(actif=True).order_by(Boutique.id).all()
    contexte = {
        "boutiques": boutiques, "boutique_id": boutique_id,
        "alertes": alertes_stock(),
        "montrer_ventes": current_user.peut_voir_rapport_journalier,
        "ind": None, "jours": None, "paiements": None,
        "aujourdhui": auj,
    }
    if contexte["montrer_ventes"]:
        contexte["ind"] = indicateurs_periode(auj, auj, boutique_id)
        contexte["paiements"] = repartition_paiements(auj, auj, boutique_id)
        # Le graphique 7 jours reste réservé à la direction (vision hebdo)
        if current_user.is_direction:
            contexte["jours"] = serie_jours(7, boutique_id)
    return render_template("main/dashboard.html", **contexte)
