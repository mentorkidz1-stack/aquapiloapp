"""Tests d'isolation multi-tenant.

Une 2e entreprise cliente ("Entreprise SECRETB") est créée avec ses propres
boutique/utilisateur/produit/achat/vente/perte/clôture. Chaque test prouve
qu'un utilisateur de l'entreprise DONA (fixture `app` standard) ne peut ni
voir ni modifier ces données, malgré leur présence dans la même base.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from flask import g

from app.extensions import db
from app.models import (Achat, Boutique, Cloture, Entreprise, Perte, Produit,
                        User, Vente, VenteLigne)
from app.services.clotures import cloturer_jour
from app.services.cmup import enregistrer_achat
from tests.conftest import contexte_dona

MARQUEUR = "SECRETB"


@pytest.fixture()
def tenant_b(app):
    """Crée une 2e entreprise cliente avec un jeu de données complet."""
    with app.app_context():
        entreprise = Entreprise(nom=f"Entreprise {MARQUEUR}", statut_abonnement="actif")
        db.session.add(entreprise)
        db.session.flush()

        boutique = Boutique(nom=f"Boutique {MARQUEUR}", entreprise_id=entreprise.id)
        db.session.add(boutique)
        db.session.flush()

        utilisateur = User(username=f"admin{MARQUEUR.lower()}", nom_complet=f"Admin {MARQUEUR}",
                           role="admin", boutique_id=boutique.id, entreprise_id=entreprise.id)
        utilisateur.set_password("Admin@Test1")
        db.session.add(utilisateur)

        produit = Produit(nom=f"Poisson {MARQUEUR}", categorie="poisson", unite="kg",
                          prix_achat=1000, prix_vente=1500, cmup_actuel=1000,
                          seuil_alerte=5, entreprise_id=entreprise.id)
        db.session.add(produit)
        db.session.commit()

        ids = {"entreprise_id": entreprise.id, "boutique_id": boutique.id,
               "user_id": utilisateur.id, "produit_id": produit.id}

    # Objets transactionnels créés via un vrai contexte de requête pour que
    # l'auto-marquage entreprise_id (app/services/tenant.py) s'applique,
    # exactement comme lors d'un vrai appel HTTP.
    with app.test_request_context():
        g.entreprise_id = ids["entreprise_id"]
        produit = db.session.get(Produit, ids["produit_id"])

        achat = enregistrer_achat(produit, Decimal("20"), 1000, f"Fournisseur {MARQUEUR}",
                                  date.today(), ids["user_id"], boutique_id=ids["boutique_id"])
        db.session.commit()
        ids["achat_id"] = achat.id

        vente = Vente(numero_ticket=f"{MARQUEUR}-0001", date_vente=date.today(),
                      heure_vente=datetime.now().time(), mode_paiement="especes",
                      user_id=ids["user_id"], boutique_id=ids["boutique_id"],
                      montant_total=1500)
        vente.lignes.append(VenteLigne(produit_id=produit.id, quantite=Decimal("1"),
                                       prix_catalogue=1500, prix_applique=1500,
                                       montant=1500, cmup_au_moment=1000, marge=500))
        db.session.add(vente)
        db.session.commit()
        ids["vente_id"] = vente.id

        perte = Perte(produit_id=produit.id, quantite=Decimal("1"), motif=f"Motif {MARQUEUR}",
                      valeur_perte=1000, date_perte=date.today(), user_id=ids["user_id"])
        db.session.add(perte)
        db.session.commit()
        ids["perte_id"] = perte.id

        utilisateur = db.session.get(User, ids["user_id"])
        cloture = cloturer_jour(date.today() - timedelta(days=1), utilisateur,
                                ids["boutique_id"])
        db.session.commit()
        ids["cloture_id"] = cloture.id

    return ids


# ---------------- Routes de liste : aucune fuite du marqueur B ----------------

def test_produits_liste_isolee(app, client_gerant, tenant_b):
    html = client_gerant.get("/produits/").get_data(as_text=True)
    assert MARQUEUR not in html


def test_ventes_journal_isole(app, client_gerant, tenant_b):
    html = client_gerant.get("/ventes/").get_data(as_text=True)
    assert MARQUEUR not in html


def test_ventes_caisse_isolee(app, client_caissier, tenant_b):
    html = client_caissier.get("/ventes/caisse").get_data(as_text=True)
    assert MARQUEUR not in html


def test_achats_liste_isolee(app, client_gerant, tenant_b):
    html = client_gerant.get("/achats/").get_data(as_text=True)
    assert MARQUEUR not in html


def test_pertes_liste_isolee(app, client_gerant, tenant_b):
    html = client_gerant.get("/pertes/").get_data(as_text=True)
    assert MARQUEUR not in html


def test_clotures_index_isole(app, client_admin, tenant_b):
    html = client_admin.get("/clotures/").get_data(as_text=True)
    assert MARQUEUR not in html


def test_admin_utilisateurs_isole(app, client_promoteur, tenant_b):
    html = client_promoteur.get("/admin/utilisateurs").get_data(as_text=True)
    assert MARQUEUR not in html


def test_clotures_audit_isole(app, client_promoteur, tenant_b):
    html = client_promoteur.get("/clotures/audit").get_data(as_text=True)
    assert MARQUEUR not in html


def test_rapports_index_isole(app, client_promoteur, tenant_b):
    html = client_promoteur.get("/rapports/").get_data(as_text=True)
    assert MARQUEUR not in html


def test_dashboard_isole(app, client_gerant, tenant_b):
    html = client_gerant.get("/").get_data(as_text=True)
    assert MARQUEUR not in html


# ---------------- Accès direct par ID (IDOR) : 404, pas de fuite ----------------

def test_produits_modifier_idor(app, client_gerant, tenant_b):
    r = client_gerant.get(f"/produits/{tenant_b['produit_id']}/modifier")
    assert r.status_code == 404


def test_produits_historique_prix_idor(app, client_gerant, tenant_b):
    r = client_gerant.get(f"/produits/{tenant_b['produit_id']}/historique-prix")
    assert r.status_code == 404


def test_ventes_ticket_idor(app, client_admin, tenant_b):
    r = client_admin.get(f"/ventes/{tenant_b['vente_id']}/ticket")
    assert r.status_code == 404


def test_ventes_annuler_idor(app, client_admin, tenant_b):
    r = client_admin.post(f"/ventes/{tenant_b['vente_id']}/annuler")
    assert r.status_code == 404


def test_clotures_reouvrir_idor(app, client_admin, tenant_b):
    r = client_admin.post(f"/clotures/{tenant_b['cloture_id']}/rouvrir",
                          data={"motif": "test"})
    assert r.status_code == 404


def test_admin_modifier_idor(app, client_promoteur, tenant_b):
    r = client_promoteur.get(f"/admin/utilisateurs/{tenant_b['user_id']}/modifier")
    assert r.status_code == 404


# ---------------- Écriture cross-tenant : rejetée avant tout commit ----------------

def test_creation_achat_avec_produit_dune_autre_entreprise_rejetee(app, tenant_b):
    with app.test_request_context():
        entreprise_a = Entreprise.query.filter_by(nom="DONA").first()
        g.entreprise_id = entreprise_a.id
        db.session.add(Achat(
            produit_id=tenant_b["produit_id"],  # produit de l'entreprise B
            boutique_id=1, quantite=Decimal("1"), prix_unitaire=100,
            montant_total=100, cmup_apres=100, date_achat=date.today(),
            user_id=1,
        ))
        with pytest.raises(ValueError):
            db.session.commit()
        db.session.rollback()


def test_formulaire_achat_ne_propose_pas_les_produits_dune_autre_entreprise(
        app, client_gerant, tenant_b):
    """Défense en profondeur : même la liste déroulante du formulaire ne
    contient pas les produits d'une autre entreprise."""
    html = client_gerant.get("/achats/nouveau").get_data(as_text=True)
    assert MARQUEUR not in html


def test_annuler_boutique_dune_autre_entreprise_rejetee(app, tenant_b):
    """Créer une vente pour SA propre entreprise mais avec le boutique_id
    d'une autre entreprise doit être rejeté par le garde-fou FK."""
    with app.test_request_context():
        entreprise_a = Entreprise.query.filter_by(nom="DONA").first()
        g.entreprise_id = entreprise_a.id
        produit_a = Produit.query.first()
        vente = Vente(numero_ticket="X-0001", date_vente=date.today(),
                      heure_vente=datetime.now().time(), mode_paiement="especes",
                      user_id=1, boutique_id=tenant_b["boutique_id"],  # boutique B
                      montant_total=100)
        vente.lignes.append(VenteLigne(produit_id=produit_a.id, quantite=Decimal("1"),
                                       prix_catalogue=100, prix_applique=100,
                                       montant=100, cmup_au_moment=100, marge=0))
        db.session.add(vente)
        with pytest.raises(ValueError):
            db.session.commit()
        db.session.rollback()
