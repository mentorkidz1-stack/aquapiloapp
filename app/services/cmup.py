"""Calcul du Coût Moyen Unitaire Pondéré (CMUP).

Formule à chaque achat :
    CMUP = (stock_avant x CMUP_avant + quantite_achetee x prix_achat)
           / (stock_avant + quantite_achetee)

Le résultat est arrondi au FCFA entier.
"""
from decimal import Decimal, ROUND_HALF_UP

from app.extensions import db
from app.models import Achat, Produit


def stock_courant(produit_id: int, boutique_id: int | None = None) -> Decimal:
    """Stock théorique courant = achats - ventes (valides) - pertes.

    boutique_id None = consolidé (toutes les boutiques).
    """
    from app.models import Vente, VenteLigne, Perte

    q_achats = db.session.query(
        db.func.coalesce(db.func.sum(Achat.quantite), 0)
    ).filter(Achat.produit_id == produit_id)
    q_ventes = db.session.query(
        db.func.coalesce(db.func.sum(VenteLigne.quantite), 0)
    ).join(Vente).filter(VenteLigne.produit_id == produit_id,
                         Vente.statut == "valide")
    q_pertes = db.session.query(
        db.func.coalesce(db.func.sum(Perte.quantite), 0)
    ).filter(Perte.produit_id == produit_id)
    if boutique_id:
        q_achats = q_achats.filter(Achat.boutique_id == boutique_id)
        q_ventes = q_ventes.filter(Vente.boutique_id == boutique_id)
        q_pertes = q_pertes.filter(Perte.boutique_id == boutique_id)

    return (Decimal(q_achats.scalar()) - Decimal(q_ventes.scalar())
            - Decimal(q_pertes.scalar()))


def matrice_stocks() -> dict:
    """{(produit_id, boutique_id): stock} en 3 requêtes agrégées (pour la caisse)."""
    from app.models import Vente, VenteLigne, Perte
    matrice = {}

    for pid, bid, total in db.session.query(
            Achat.produit_id, Achat.boutique_id,
            db.func.sum(Achat.quantite)).group_by(
            Achat.produit_id, Achat.boutique_id):
        matrice[(pid, bid)] = matrice.get((pid, bid), Decimal(0)) + Decimal(total)

    for pid, bid, total in db.session.query(
            VenteLigne.produit_id, Vente.boutique_id,
            db.func.sum(VenteLigne.quantite)).join(Vente).filter(
            Vente.statut == "valide").group_by(
            VenteLigne.produit_id, Vente.boutique_id):
        matrice[(pid, bid)] = matrice.get((pid, bid), Decimal(0)) - Decimal(total)

    for pid, bid, total in db.session.query(
            Perte.produit_id, Perte.boutique_id,
            db.func.sum(Perte.quantite)).group_by(
            Perte.produit_id, Perte.boutique_id):
        matrice[(pid, bid)] = matrice.get((pid, bid), Decimal(0)) - Decimal(total)

    return matrice


def nouveau_cmup(produit: Produit, quantite: Decimal, prix_unitaire: int) -> int:
    """Recalcule le CMUP après un achat de `quantite` à `prix_unitaire`."""
    stock_avant = stock_courant(produit.id)
    if stock_avant <= 0:
        # Premier achat ou stock épuisé : le CMUP repart du prix d'achat
        return int(prix_unitaire)

    valeur_avant = stock_avant * Decimal(produit.cmup_actuel)
    valeur_achat = Decimal(quantite) * Decimal(prix_unitaire)
    cmup = (valeur_avant + valeur_achat) / (stock_avant + Decimal(quantite))
    return int(cmup.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def enregistrer_achat(produit: Produit, quantite: Decimal, prix_unitaire: int,
                      fournisseur, date_achat, user_id: int,
                      boutique_id: int = 1) -> Achat:
    """Cree l'achat, met a jour le CMUP du produit, retourne l'achat.

    IMPORTANT : le CMUP est calcule AVANT l'insertion de l'achat
    (stock_courant ne doit pas inclure la quantite en cours d'ajout).
    L'appelant est responsable du db.session.commit().
    """
    cmup = nouveau_cmup(produit, quantite, prix_unitaire)
    achat = Achat(
        produit_id=produit.id,
        boutique_id=boutique_id,
        quantite=quantite,
        prix_unitaire=prix_unitaire,
        montant_total=int(Decimal(quantite) * Decimal(prix_unitaire)),
        cmup_apres=cmup,
        fournisseur=fournisseur or None,
        date_achat=date_achat,
        user_id=user_id,
    )
    produit.cmup_actuel = cmup
    db.session.add(achat)
    return achat
