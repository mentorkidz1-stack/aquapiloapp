"""Stocks journaliers : mouvements du jour, report automatique, écart d'inventaire."""
from datetime import date as date_type
from decimal import Decimal

from app.extensions import db
from app.models import Achat, Vente, VenteLigne, Perte, Produit, StockJournalier


def _somme(query) -> Decimal:
    return Decimal(query.scalar() or 0)


def stock_debut_de_journee(produit_id: int, jour: date_type,
                           boutique_id: int = 1) -> Decimal:
    """Stock au début de `jour` = somme de tous les mouvements ANTÉRIEURS au jour.

    Équivaut au report automatique du stock final de la veille, tout en restant
    juste même si des journées n'ont pas été générées (jours fermés, etc.).
    """
    achats = _somme(db.session.query(db.func.coalesce(db.func.sum(Achat.quantite), 0))
                    .filter(Achat.produit_id == produit_id,
                            Achat.boutique_id == boutique_id,
                            Achat.date_achat < jour))
    ventes = _somme(db.session.query(db.func.coalesce(db.func.sum(VenteLigne.quantite), 0))
                    .join(Vente).filter(VenteLigne.produit_id == produit_id,
                                        Vente.boutique_id == boutique_id,
                                        Vente.statut == "valide",
                                        Vente.date_vente < jour))
    pertes = _somme(db.session.query(db.func.coalesce(db.func.sum(Perte.quantite), 0))
                    .filter(Perte.produit_id == produit_id,
                            Perte.boutique_id == boutique_id,
                            Perte.date_perte < jour))
    return achats - ventes - pertes


def mouvements_du_jour(produit_id: int, jour: date_type,
                       boutique_id: int = 1):
    """Retourne (entrées, sorties, pertes) du produit pour le jour donné."""
    entrees = _somme(db.session.query(db.func.coalesce(db.func.sum(Achat.quantite), 0))
                     .filter(Achat.produit_id == produit_id,
                             Achat.boutique_id == boutique_id,
                             Achat.date_achat == jour))
    sorties = _somme(db.session.query(db.func.coalesce(db.func.sum(VenteLigne.quantite), 0))
                     .join(Vente).filter(VenteLigne.produit_id == produit_id,
                                         Vente.boutique_id == boutique_id,
                                         Vente.statut == "valide",
                                         Vente.date_vente == jour))
    pertes = _somme(db.session.query(db.func.coalesce(db.func.sum(Perte.quantite), 0))
                    .filter(Perte.produit_id == produit_id,
                            Perte.boutique_id == boutique_id,
                            Perte.date_perte == jour))
    return entrees, sorties, pertes


def actualiser_stocks_du_jour(jour: date_type,
                              boutique_id: int = 1) -> list[StockJournalier]:
    """Crée ou met à jour la ligne de stock de chaque produit actif pour `jour`.

    Recalcule initial/entrées/sorties/pertes/final à partir des mouvements
    (source de vérité). Conserve le comptage physique déjà saisi et
    recalcule l'écart en conséquence. L'appelant committe.
    """
    lignes = []
    for produit in Produit.query.filter_by(actif=True).order_by(
            Produit.categorie, Produit.nom):
        sj = StockJournalier.query.filter_by(
            produit_id=produit.id, boutique_id=boutique_id,
            date_stock=jour).first()
        if sj is None:
            sj = StockJournalier(produit_id=produit.id,
                                 boutique_id=boutique_id, date_stock=jour)
            db.session.add(sj)

        sj.stock_initial = stock_debut_de_journee(produit.id, jour, boutique_id)
        sj.entrees, sj.sorties, sj.pertes = mouvements_du_jour(
            produit.id, jour, boutique_id)
        sj.stock_final = sj.stock_initial + sj.entrees - sj.sorties - sj.pertes
        if sj.stock_physique is not None:
            sj.ecart = Decimal(sj.stock_physique) - Decimal(sj.stock_final)
        lignes.append(sj)
    return lignes
