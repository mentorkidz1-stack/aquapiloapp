"""Tests du verrouillage : aucune écriture après clôture."""
import json
from datetime import date
from decimal import Decimal

from app.extensions import db
from app.models import Achat, Cloture, Perte, Produit, User, Vente
from app.services.cmup import enregistrer_achat
from tests.conftest import contexte_dona


def _preparer(app):
    with contexte_dona(app):
        produit = Produit.query.filter_by(nom="Tilapia").first()
        admin = User.query.filter_by(username="admin").first()
        enregistrer_achat(produit, Decimal("50"), 1500, None,
                          date.today(), admin.id)
        db.session.commit()
        return produit.id


def _vendre(client, produit_id, qte=1, prix=None):
    ligne = {"produit_id": produit_id, "quantite": qte}
    if prix is not None:
        ligne["prix"] = prix
    return client.post("/ventes/caisse", data={
        "lignes": json.dumps([ligne]),
        "mode_paiement": "especes"}, follow_redirects=True)


def _nb(app, modele):
    with app.app_context():
        return modele.query.count()


def test_ecritures_bloquees_apres_cloture(app, client_admin, client_caissier):
    produit_id = _preparer(app)
    _vendre(client_caissier, produit_id, 2)
    assert _nb(app, Vente) == 1

    # L'employé clôture sa journée
    client_caissier.post("/clotures/jour", data={"jour": date.today().isoformat()})

    # Vente refusée, même pour l'admin : rien de créé en base
    r = _vendre(client_admin, produit_id, 1)
    assert "Période clôturée" in r.get_data(as_text=True)
    assert _nb(app, Vente) == 1

    # Achat et perte refusés
    client_admin.post("/achats/nouveau", data={
        "produit_id": produit_id, "quantite": "5", "prix_unitaire": 1400,
        "fournisseur": "", "date_achat": date.today().isoformat()})
    assert _nb(app, Achat) == 1     # seul l'achat de préparation
    client_admin.post("/pertes/nouvelle", data={
        "produit_id": produit_id, "quantite": "1", "motif": "x",
        "date_perte": date.today().isoformat()})
    assert _nb(app, Perte) == 0


def test_reouverture_admin_puis_ecriture(app, client_admin, client_gerant,
                                         client_caissier):
    produit_id = _preparer(app)
    client_caissier.post("/clotures/jour", data={"jour": date.today().isoformat()})
    with app.app_context():
        cloture_id = Cloture.query.first().id

    def statut():
        with app.app_context():
            return db.session.get(Cloture, cloture_id).statut

    # Gérant refusé, admin sans motif refusé
    assert client_gerant.post(f"/clotures/{cloture_id}/rouvrir",
                              data={"motif": "x"}).status_code == 403
    client_admin.post(f"/clotures/{cloture_id}/rouvrir", data={"motif": ""})
    assert statut() == "cloture"

    # Admin avec motif : réouverture effective, la vente repasse
    client_admin.post(f"/clotures/{cloture_id}/rouvrir",
                      data={"motif": "correction"})
    assert statut() == "rouvert"
    _vendre(client_caissier, produit_id, 1)
    assert _nb(app, Vente) == 1


def test_prix_employe_force_au_catalogue(app, client_caissier):
    produit_id = _preparer(app)
    _vendre(client_caissier, produit_id, qte=2, prix=1)   # prix trafiqué
    with app.app_context():
        ligne = Vente.query.first().lignes[0]
        assert ligne.prix_applique == 1900   # prix catalogue imposé
        assert ligne.marge == 800            # (1900-1500) x 2
