"""Blueprint stocks : situation journalière, comptage physique, écart."""
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from app.extensions import db
from app.models import Boutique
from app.services.stocks import actualiser_stocks_du_jour
from app.utils.decorators import (role_required, periode_non_cloturee,
                                  _date_du_formulaire)

stocks_bp = Blueprint("stocks", __name__, url_prefix="/stocks")


@stocks_bp.route("/")
@login_required
@role_required("gerant")
def journee():
    try:
        jour = date.fromisoformat(request.args.get("jour", ""))
    except ValueError:
        jour = date.today()
    boutique_id = request.args.get("boutique_id", type=int) or 1
    lignes = actualiser_stocks_du_jour(jour, boutique_id)
    db.session.commit()
    boutiques = Boutique.query.filter_by(actif=True).order_by(Boutique.id).all()
    return render_template("stocks/journee.html", lignes=lignes, jour=jour,
                           boutiques=boutiques, boutique_id=boutique_id,
                           aujourdhui=date.today())


@stocks_bp.route("/comptage", methods=["POST"])
@login_required
@role_required("gerant")
@periode_non_cloturee(_date_du_formulaire("jour"))
def comptage():
    try:
        jour = date.fromisoformat(request.form.get("jour", ""))
    except ValueError:
        flash("Date invalide.", "danger")
        return redirect(url_for("stocks.journee"))

    try:
        boutique_id = int(request.form.get("boutique_id", 1))
    except (TypeError, ValueError):
        boutique_id = 1
    lignes = actualiser_stocks_du_jour(jour, boutique_id)
    saisis = 0
    for sj in lignes:
        brut = request.form.get(f"physique_{sj.produit_id}", "").strip()
        if brut == "":
            continue
        try:
            physique = Decimal(brut.replace(",", "."))
        except InvalidOperation:
            flash(f"Valeur invalide pour {sj.produit.nom} : « {brut} »", "danger")
            continue
        sj.stock_physique = physique
        sj.ecart = physique - Decimal(sj.stock_final)
        saisis += 1
    db.session.commit()
    flash(f"Comptage enregistré pour {saisis} produit(s).", "success")
    return redirect(url_for("stocks.journee", jour=jour.isoformat(),
                            boutique_id=boutique_id))
