"""Tests critiques du calcul CMUP (Coût Moyen Unitaire Pondéré)."""
from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models import Produit, User
from app.services.cmup import enregistrer_achat, stock_courant
from tests.conftest import contexte_dona


def _acheter(qte, prix):
    produit = Produit.query.filter_by(nom="Tilapia").first()
    admin = User.query.filter_by(username="admin").first()
    achat = enregistrer_achat(produit, Decimal(qte), prix, None,
                              date.today(), admin.id)
    db.session.commit()
    return produit, achat


def test_premier_achat_initialise_le_cmup(app):
    with contexte_dona(app):
        produit, achat = _acheter("10", 1000)
        assert achat.cmup_apres == 1000
        assert produit.cmup_actuel == 1000


def test_moyenne_ponderee(app):
    with contexte_dona(app):
        _acheter("10", 1000)
        _, achat2 = _acheter("10", 2000)
        # (10x1000 + 10x2000) / 20 = 1500
        assert achat2.cmup_apres == 1500


def test_quantite_decimale_et_arrondi(app):
    with contexte_dona(app):
        _acheter("20", 1500)
        produit, achat = _acheter("5.5", 1200)
        # (20x1500 + 5,5x1200) / 25,5 = 1435,29... -> 1435
        assert achat.cmup_apres == 1435
        assert stock_courant(produit.id) == Decimal("25.5")


def test_montant_total_calcule(app):
    with contexte_dona(app):
        _, achat = _acheter("2.5", 1400)
        assert achat.montant_total == 3500
