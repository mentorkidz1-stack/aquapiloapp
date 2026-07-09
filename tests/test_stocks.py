"""Tests du stock final journalier et du report automatique."""
from datetime import date, timedelta
from decimal import Decimal

from app.extensions import db
from app.models import Perte, Produit, User
from app.services.cmup import enregistrer_achat
from app.services.stocks import (actualiser_stocks_du_jour,
                                 stock_debut_de_journee)


def test_stock_final_et_report(app):
    hier = date.today() - timedelta(days=1)
    with app.app_context():
        produit = Produit.query.filter_by(nom="Tilapia").first()
        admin = User.query.filter_by(username="admin").first()
        enregistrer_achat(produit, Decimal("30"), 1500, None, hier, admin.id)
        db.session.add(Perte(produit_id=produit.id, quantite=Decimal("2"),
                             motif="test", valeur_perte=3000, date_perte=hier,
                             user_id=admin.id))
        db.session.commit()

        lignes = actualiser_stocks_du_jour(hier)
        db.session.commit()
        sj = next(l for l in lignes if l.produit_id == produit.id)
        assert sj.stock_initial == Decimal("0")
        assert sj.entrees == Decimal("30")
        assert sj.pertes == Decimal("2")
        assert sj.stock_final == Decimal("28")
        # Report automatique : initial d'aujourd'hui = final d'hier
        assert stock_debut_de_journee(produit.id, date.today()) == Decimal("28")


def test_ecart_inventaire(app, client_gerant):
    with app.app_context():
        produit = Produit.query.filter_by(nom="Tilapia").first()
        admin = User.query.filter_by(username="admin").first()
        enregistrer_achat(produit, Decimal("10"), 1500, None,
                          date.today(), admin.id)
        db.session.commit()
        produit_id = produit.id

    client_gerant.post("/stocks/comptage", data={
        "jour": date.today().isoformat(),
        f"physique_{produit_id}": "9,5",
    })

    with app.app_context():
        lignes = actualiser_stocks_du_jour(date.today())
        sj = next(l for l in lignes if l.produit_id == produit_id)
        assert sj.stock_physique == Decimal("9.5")
        assert sj.ecart == Decimal("-0.5")
