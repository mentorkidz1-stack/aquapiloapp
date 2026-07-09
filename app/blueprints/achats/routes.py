"""Module Achats : saisie des approvisionnements avec recalcul du CMUP."""
from datetime import date, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Achat, Boutique, Produit
from app.services.cmup import enregistrer_achat
from app.utils.decorators import (role_required, periode_non_cloturee,
                                  _date_du_formulaire)
from app.blueprints.achats.forms import AchatForm

achats_bp = Blueprint("achats", __name__, url_prefix="/achats")


@achats_bp.route("/")
@login_required
@role_required("gerant")
def liste():
    # Filtres : période (défaut 30 derniers jours) et produit
    try:
        debut = date.fromisoformat(request.args.get("debut", ""))
    except ValueError:
        debut = date.today() - timedelta(days=30)
    try:
        fin = date.fromisoformat(request.args.get("fin", ""))
    except ValueError:
        fin = date.today()
    produit_id = request.args.get("produit_id", type=int)
    boutique_id = request.args.get("boutique_id", type=int)

    requete = Achat.query.filter(Achat.date_achat.between(debut, fin))
    if produit_id:
        requete = requete.filter_by(produit_id=produit_id)
    if boutique_id:
        requete = requete.filter_by(boutique_id=boutique_id)
    achats = requete.order_by(Achat.date_achat.desc(), Achat.id.desc()).all()
    total = sum(a.montant_total for a in achats)

    produits = Produit.query.filter_by(actif=True).order_by(Produit.nom).all()
    boutiques = Boutique.query.filter_by(actif=True).order_by(Boutique.id).all()
    noms_boutiques = {b.id: b.nom for b in boutiques}
    return render_template("achats/liste.html", achats=achats, total=total,
                           noms_boutiques=noms_boutiques,
                           produits=produits, debut=debut, fin=fin,
                           produit_id=produit_id, boutiques=boutiques,
                           boutique_id=boutique_id)


@achats_bp.route("/nouveau", methods=["GET", "POST"])
@login_required
@role_required("gerant")
@periode_non_cloturee(_date_du_formulaire("date_achat"))
def nouveau():
    form = AchatForm()
    produits_actifs = Produit.query.filter_by(actif=True).order_by(
        Produit.categorie, Produit.nom).all()
    form.produit_id.choices = [
        (p.id, f"{p.nom} ({p.unite_affichee})") for p in produits_actifs
    ]
    form.boutique_id.choices = [
        (b.id, b.nom) for b in
        Boutique.query.filter_by(actif=True).order_by(Boutique.id)
    ]

    if form.validate_on_submit():
        produit = db.session.get(Produit, form.produit_id.data)
        achat = enregistrer_achat(
            produit=produit,
            quantite=form.quantite.data,
            prix_unitaire=form.prix_unitaire.data,
            fournisseur=form.fournisseur.data,
            date_achat=form.date_achat.data,
            user_id=current_user.id,
            boutique_id=form.boutique_id.data,
        )
        db.session.commit()
        flash(
            f"Achat enregistré : {achat.quantite} {produit.unite_affichee} de "
            f"{produit.nom}. Nouveau CMUP : {achat.cmup_apres} FCFA.",
            "success",
        )
        return redirect(url_for("achats.liste"))

    if request.method == "POST":
        if form.errors:
            for champ, erreurs in form.errors.items():
                libelle = getattr(form, champ).label.text if hasattr(form, champ) else champ
                flash(f"{libelle} : {' ; '.join(erreurs)}", "danger")
        else:
            flash("Saisie refusée : la journée sélectionnée est peut-être clôturée.", "warning")
    # Prix d'achat courants pour pré-remplissage côté JS
    prix_courants = {p.id: p.prix_achat for p in produits_actifs}
    return render_template("achats/form.html", form=form,
                           prix_courants=prix_courants)
