"""Blueprint pertes : saisie et journal des avaries. Accès gérant/admin."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Boutique, Perte, Produit
from app.utils.decorators import (role_required, periode_non_cloturee,
                                  _date_du_formulaire)
from app.blueprints.pertes.forms import PerteForm

pertes_bp = Blueprint("pertes", __name__, url_prefix="/pertes")


@pertes_bp.route("/")
@login_required
@role_required("gerant")
def liste():
    try:
        debut = date.fromisoformat(request.args.get("debut", ""))
    except ValueError:
        debut = date.today() - timedelta(days=30)
    try:
        fin = date.fromisoformat(request.args.get("fin", ""))
    except ValueError:
        fin = date.today()
    boutique_id = request.args.get("boutique_id", type=int)
    requete = Perte.query.filter(Perte.date_perte.between(debut, fin))
    if boutique_id:
        requete = requete.filter_by(boutique_id=boutique_id)
    pertes = requete.order_by(Perte.date_perte.desc(), Perte.id.desc()).all()
    total = sum(p.valeur_perte for p in pertes)
    boutiques = Boutique.query.filter_by(actif=True).order_by(Boutique.id).all()
    return render_template("pertes/liste.html", pertes=pertes,
                           boutiques=boutiques, boutique_id=boutique_id,
                           noms_boutiques={b.id: b.nom for b in boutiques},
                           debut=debut, fin=fin, total=total)


@pertes_bp.route("/nouvelle", methods=["GET", "POST"])
@login_required
@role_required("gerant")
@periode_non_cloturee(_date_du_formulaire("date_perte"))
def nouvelle():
    form = PerteForm()
    produits = Produit.query.filter_by(actif=True).order_by(
        Produit.categorie, Produit.nom).all()
    form.produit_id.choices = [(p.id, f"{p.nom} ({p.unite_affichee})")
                               for p in produits]
    form.boutique_id.choices = [
        (b.id, b.nom) for b in
        Boutique.query.filter_by(actif=True).order_by(Boutique.id)]
    if form.validate_on_submit():
        produit = db.session.get(Produit, form.produit_id.data)
        valeur = int((Decimal(form.quantite.data) * Decimal(produit.cmup_actuel))
                     .quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        db.session.add(Perte(
            produit_id=produit.id,
            boutique_id=form.boutique_id.data,
            quantite=form.quantite.data,
            motif=form.motif.data.strip(),
            valeur_perte=valeur,
            date_perte=form.date_perte.data,
            user_id=current_user.id,
        ))
        db.session.commit()
        flash(f"Perte enregistrée : {form.quantite.data} "
              f"{produit.unite_affichee} de {produit.nom} "
              f"({valeur} FCFA au CMUP).", "success")
        return redirect(url_for("pertes.liste"))
    return render_template("pertes/form.html", form=form)
