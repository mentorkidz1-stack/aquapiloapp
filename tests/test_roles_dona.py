"""Tests des règles DONA : caissier, gérant restreint, verrou direction."""
import json
from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models import Produit, User, Vente
from app.services.cmup import enregistrer_achat
from tests.conftest import contexte_dona


def _preparer(app):
    with contexte_dona(app):
        produit = Produit.query.filter_by(nom="Tilapia").first()
        admin = User.query.filter_by(username="admin").first()
        enregistrer_achat(produit, Decimal("50"), 1500, None,
                          date.today(), admin.id, boutique_id=1)
        enregistrer_achat(produit, Decimal("20"), 1500, None,
                          date.today(), admin.id, boutique_id=2)
        db.session.commit()
        return produit.id


def test_caissier_uniquement_la_caisse(app, client_caissier):
    assert client_caissier.get("/ventes/caisse").status_code == 200
    for url in ("/ventes/", "/produits/", "/achats/", "/pertes/",
                "/stocks/", "/rapports/", "/admin/utilisateurs",
                "/clotures/audit"):
        assert client_caissier.get(url).status_code == 403, url


def test_caissier_vend_dans_sa_boutique(app, client_caissier):
    produit_id = _preparer(app)
    # Le caissier tente de vendre pour la boutique 2 : forcé sur la sienne (1)
    client_caissier.post("/ventes/caisse", data={
        "lignes": json.dumps([{"produit_id": produit_id, "quantite": 1}]),
        "mode_paiement": "especes", "boutique_id": 2})
    with app.app_context():
        assert Vente.query.first().boutique_id == 1


def test_stock_par_boutique(app):
    produit_id = _preparer(app)
    with app.app_context():
        from app.services.cmup import stock_courant
        assert stock_courant(produit_id, 1) == Decimal("50")
        assert stock_courant(produit_id, 2) == Decimal("20")
        assert stock_courant(produit_id) == Decimal("70")      # consolidé
        assert stock_courant(produit_id, 3) == Decimal("0")


def test_gerant_jamais_aucun_rapport(app, client_gerant):
    # Le Gérant n'a plus aucun accès aux rapports (marge/comparaisons/
    # exports), quel que soit le type ou l'état du verrou journalier.
    for type_p, fmt in (("jour", "xlsx"), ("semaine", "xlsx"), ("mois", "pdf")):
        assert client_gerant.get(
            f"/rapports/export/{type_p}/{fmt}").status_code == 403
    r = client_gerant.get("/rapports/", follow_redirects=True)
    assert r.status_code == 200
    assert "pas accessibles au rôle Gérant" in r.get_data(as_text=True)
    # La carte "Marge du jour" et le bouton "Rapports" ont disparu du
    # tableau de bord et du journal des ventes.
    tableau = client_gerant.get("/").get_data(as_text=True)
    assert "Marge du jour" not in tableau
    assert "Rapports</a>" not in tableau
    journal = client_gerant.get("/ventes/").get_data(as_text=True)
    assert "Marge du jour" not in journal


def test_verrou_rapport_journalier(app, client_gerant):
    with app.app_context():
        g = User.query.filter_by(username="gerant").first()
        g.acces_rapport_journalier = False
        db.session.commit()
    # Journal des ventes verrouillé (indépendant du blocage rapports)
    r = client_gerant.get("/ventes/", follow_redirects=True)
    assert "verrouillé" in r.get_data(as_text=True)
    # L'opérationnel reste ouvert
    assert client_gerant.get("/produits/").status_code == 200
    assert client_gerant.get("/stocks/").status_code == 200


def test_promoteur_pilote_tout(app, client_promoteur):
    for url in ("/rapports/", "/admin/utilisateurs", "/clotures/audit"):
        assert client_promoteur.get(url).status_code == 200, url
    h = client_promoteur.get("/rapports/").get_data(as_text=True)
    assert "Comparaison hebdomadaire" in h


def test_cloture_par_boutique_independante(app, client_admin, client_caissier):
    produit_id = _preparer(app)
    # Clôture de la boutique 1 par le caissier (la sienne)
    client_caissier.post("/clotures/jour", data={"jour": date.today().isoformat()})
    # Boutique 1 verrouillée pour la vente
    r = client_caissier.post("/ventes/caisse", data={
        "lignes": json.dumps([{"produit_id": produit_id, "quantite": 1}]),
        "mode_paiement": "especes"}, follow_redirects=True)
    assert "Période clôturée" in r.get_data(as_text=True)
    # ... mais la boutique 2 reste ouverte : l'admin y vend
    client_admin.post("/ventes/caisse", data={
        "lignes": json.dumps([{"produit_id": produit_id, "quantite": 1}]),
        "mode_paiement": "especes", "boutique_id": 2})
    with app.app_context():
        assert Vente.query.count() == 1
        assert Vente.query.first().boutique_id == 2
