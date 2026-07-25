"""Blueprint main — landing publique + tableau de bord adapté au rôle."""
from datetime import date

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user

from app.extensions import db
from app.models import Boutique, DemandeAcces
from app.models.entreprise import TARIF_BASE, TARIF_PALIER, SEUIL_PALIER
from app.blueprints.main.forms import DemandeAccesForm
from app.services.rapports import (alertes_stock, indicateurs_periode,
                                   repartition_paiements, serie_jours)

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def dashboard():
    if not current_user.is_authenticated:
        return render_template("main/landing.html", form=DemandeAccesForm(),
                               tarif_base=TARIF_BASE, tarif_palier=TARIF_PALIER,
                               seuil_palier=SEUIL_PALIER, annee=date.today().year)

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
        # Le rôle Gérant (strictement) ne voit jamais la marge ni les
        # rapports, indépendamment du verrou acces_rapport_journalier
        # (qui reste réservé au promoteur/admin).
        "masquer_marge": current_user.role == "gerant",
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


@main_bp.route("/confidentialite")
def confidentialite():
    return render_template("legal/confidentialite.html", annee=date.today().year)


@main_bp.route("/cgu")
def cgu():
    return render_template("legal/cgu.html", annee=date.today().year,
                           tarif_base=TARIF_BASE, tarif_palier=TARIF_PALIER,
                           seuil_palier=SEUIL_PALIER)


@main_bp.route("/mentions-legales")
def mentions_legales():
    return render_template("legal/mentions_legales.html", annee=date.today().year)


@main_bp.route("/demande-acces", methods=["POST"])
def demande_acces():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = DemandeAccesForm()
    if form.validate_on_submit():
        db.session.add(DemandeAcces(
            nom_poissonnerie=form.nom_poissonnerie.data.strip(),
            responsable=form.responsable.data.strip(),
            telephone=form.telephone.data.strip(),
            email=form.email.data.strip(),
            nombre_boutiques=form.nombre_boutiques.data,
        ))
        db.session.commit()
        flash("Votre demande a bien été envoyée ! Nous vous recontactons "
              "très vite pour activer votre compte.", "success")
        return redirect(url_for("main.dashboard", _anchor="demande-acces"))

    for champ in form:
        for err in champ.errors:
            flash(f"{champ.label.text} : {err}", "danger")
    return render_template("main/landing.html", form=form,
                           tarif_base=TARIF_BASE, tarif_palier=TARIF_PALIER,
                           seuil_palier=SEUIL_PALIER, annee=date.today().year), 400
