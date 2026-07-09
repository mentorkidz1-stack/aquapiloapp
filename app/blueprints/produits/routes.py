"""Module Produits : CRUD + historisation des prix. Accès gérant et admin."""
from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Boutique, Produit, PrixHistorique
from app.services.cmup import stock_courant
from app.utils.decorators import role_required
from app.blueprints.produits.forms import ProduitForm

produits_bp = Blueprint("produits", __name__, url_prefix="/produits")


@produits_bp.route("/")
@login_required
@role_required("gerant")
def liste():
    q = request.args.get("q", "").strip()
    categorie = request.args.get("categorie", "")
    requete = Produit.query
    if q:
        requete = requete.filter(Produit.nom.ilike(f"%{q}%"))
    if categorie in ("poisson", "viande"):
        requete = requete.filter_by(categorie=categorie)
    produits = requete.order_by(Produit.categorie, Produit.nom).all()
    boutique_id = request.args.get("boutique_id", type=int)   # None = consolidé
    stocks = {p.id: stock_courant(p.id, boutique_id) for p in produits}
    boutiques = Boutique.query.filter_by(actif=True).order_by(Boutique.id).all()
    return render_template("produits/liste.html", produits=produits,
                           stocks=stocks, q=q, categorie=categorie,
                           boutiques=boutiques, boutique_id=boutique_id)


@produits_bp.route("/nouveau", methods=["GET", "POST"])
@login_required
@role_required("gerant")
def nouveau():
    form = ProduitForm()
    if form.validate_on_submit():
        if Produit.query.filter(Produit.nom.ilike(form.nom.data.strip())).first():
            flash("Un produit porte déjà ce nom.", "danger")
        else:
            produit = Produit(
                nom=form.nom.data.strip(),
                categorie=form.categorie.data,
                unite=form.unite.data,
                prix_achat=form.prix_achat.data,
                prix_vente=form.prix_vente.data,
                seuil_alerte=form.seuil_alerte.data,
                actif=form.actif.data,
            )
            db.session.add(produit)
            db.session.commit()
            flash(f"Produit « {produit.nom} » créé.", "success")
            return redirect(url_for("produits.liste"))
    return render_template("produits/form.html", form=form, titre="Nouveau produit")


@produits_bp.route("/<int:produit_id>/modifier", methods=["GET", "POST"])
@login_required
@role_required("gerant")
def modifier(produit_id):
    produit = db.get_or_404(Produit, produit_id)
    form = ProduitForm(obj=produit)
    if form.validate_on_submit():
        # Historisation : un enregistrement par prix modifié, jamais d'écrasement muet
        if form.prix_achat.data != produit.prix_achat:
            db.session.add(PrixHistorique(
                produit_id=produit.id, type_prix="achat",
                ancien_prix=produit.prix_achat, nouveau_prix=form.prix_achat.data,
                date_effet=date.today(), user_id=current_user.id))
        if form.prix_vente.data != produit.prix_vente:
            db.session.add(PrixHistorique(
                produit_id=produit.id, type_prix="vente",
                ancien_prix=produit.prix_vente, nouveau_prix=form.prix_vente.data,
                date_effet=date.today(), user_id=current_user.id))
        form.populate_obj(produit)
        produit.nom = produit.nom.strip()
        db.session.commit()
        flash(f"Produit « {produit.nom} » mis à jour.", "success")
        return redirect(url_for("produits.liste"))
    return render_template("produits/form.html", form=form,
                           titre=f"Modifier — {produit.nom}", produit=produit)


@produits_bp.route("/<int:produit_id>/historique-prix")
@login_required
@role_required("gerant")
def historique_prix(produit_id):
    produit = db.get_or_404(Produit, produit_id)
    historique = produit.historique_prix.all()
    return render_template("produits/historique_prix.html",
                           produit=produit, historique=historique)
