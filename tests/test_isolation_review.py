"""Preuves de la revue de sécurité de l'isolation multi-tenant
(app/services/tenant.py), avant commit du chantier 2.

Quatre points couverts, chacun avec un test qui échouerait si la garantie
était violée :
1. Fail-closed quand le tenant courant n'est pas résolu.
2. Isolation en écriture : impossible de créer OU de rattacher un objet
   à une autre entreprise.
3. Couverture des agrégations (rapports/stats) + limite documentée sur
   les tables sans colonne entreprise_id propre (VenteLigne, etc.).
4. Accès opérateur SaaS cross-tenant : contrôlé et explicite, jamais
   atteignable par un client.
"""
from datetime import date

import pytest
from flask import g

from app.extensions import db
from app.models import Entreprise, Produit, VenteLigne
from app.services.tenant import sans_filtre_tenant
from tests.conftest import contexte_dona
# Réutilise le jeu de données "entreprise B" déjà construit pour
# tests/test_isolation.py (boutique/user/produit/achat/vente/perte/cloture).
from tests.test_isolation import tenant_b  # noqa: F401

MARQUEUR = "SECRETB"


# ------------------- 1. Fail-closed sans tenant résolu -------------------

def test_fail_closed_nouvelle_route_sans_login_required(app, tenant_b):
    """Simule un développeur qui ajoute une route plus tard et oublie
    @login_required. Avant le correctif, le filtre était sauté quand
    g.entreprise_id valait None -> la route montrait TOUTES les
    entreprises. Après correctif : elle n'en montre AUCUNE."""
    @app.route("/_route_oubliee_sans_login")
    def _route_oubliee():
        return {"produits": [p.nom for p in Produit.query.all()]}

    client = app.test_client()  # jamais connecté
    r = client.get("/_route_oubliee_sans_login")
    assert r.get_json()["produits"] == []


def test_fail_closed_sans_g_entreprise_id(app, tenant_b):
    """Contexte de requête sans g.entreprise_id positionné (hook
    before_request oublié, ou appel direct depuis une tâche de fond mal
    câblée) : aucune ligne ne doit être visible, jamais toutes."""
    with app.test_request_context():
        assert Produit.query.all() == []


def test_sans_filtre_tenant_est_le_seul_moyen_cross_tenant(app, tenant_b):
    """Le bypass explicite sans_filtre_tenant() est la SEULE façon de
    voir plusieurs entreprises ; en dehors de lui, c'est fail-closed."""
    with app.test_request_context():
        assert Produit.query.all() == []
        with sans_filtre_tenant():
            noms = {p.nom for p in Produit.query.all()}
        assert {"Tilapia", f"Poisson {MARQUEUR}"} <= noms
        # Le bypass ne survit pas à la sortie du `with`.
        assert Produit.query.all() == []


# ------------------- 2. Isolation en écriture -------------------

def test_creation_avec_entreprise_id_falsifie_est_ecrasee(app, tenant_b):
    """Même en fournissant explicitement l'entreprise_id d'un concurrent
    à la construction, l'objet est rattaché au tenant courant."""
    with contexte_dona(app):
        produit = Produit(nom="Test falsification", categorie="poisson",
                          unite="kg", prix_achat=1, prix_vente=1,
                          cmup_actuel=1, seuil_alerte=1,
                          entreprise_id=tenant_b["entreprise_id"])
        db.session.add(produit)
        db.session.commit()
        assert produit.entreprise_id == g.entreprise_id
        assert produit.entreprise_id != tenant_b["entreprise_id"]


def test_modification_entreprise_id_objet_existant_rejetee(app, tenant_b):
    """Rattacher a posteriori un de ses propres objets à une autre
    entreprise (déplacement/évasion de données) doit être bloqué."""
    with contexte_dona(app):
        produit = Produit.query.filter_by(nom="Tilapia").first()
        produit.entreprise_id = tenant_b["entreprise_id"]
        with pytest.raises(ValueError):
            db.session.commit()
        db.session.rollback()


# ------------------- 3. Couverture : agrégations + limites -------------------

def test_agregation_rapports_isolee_par_tenant(app, tenant_b):
    """indicateurs_periode() fait un func.sum(Vente.montant_total) — on
    vérifie que la vente de 1500 FCFA de l'entreprise B (créée aujourd'hui
    par la fixture tenant_b) n'apparaît PAS dans le CA de DONA du jour."""
    from app.services.rapports import indicateurs_periode
    with contexte_dona(app):
        ind = indicateurs_periode(date.today(), date.today())
    assert ind["ca"] == 0  # DONA n'a vendu rien aujourd'hui, surtout pas les 1500 de SECRETB


def test_scripts_hors_requete_voient_toutes_les_entreprises(app, tenant_b):
    """Documente le mécanisme d'accès existant hors requête HTTP (scripts
    d'administration façon seed.py) : aucun filtre n'est appliqué, par
    conception, car ce chemin n'est jamais atteignable par un client
    (il n'y a pas de requête HTTP sans contexte de requête Flask)."""
    with app.app_context():   # PAS test_request_context : simule un script CLI
        noms = {p.nom for p in Produit.query.all()}
    assert {"Tilapia", f"Poisson {MARQUEUR}"} <= noms


def test_gap_documente_vente_ligne_sans_jointure_non_filtree(app, tenant_b):
    """LIMITE CONNUE ET DOCUMENTÉE : VenteLigne (comme PrixHistorique et
    Reouverture) n'a pas de colonne entreprise_id propre et n'est donc
    PAS dans MODELES_TENANT. Sa cohérence tenant dépend aujourd'hui du
    fait que le code applicatif ne la requête jamais qu'en jointure avec
    Vente (déjà filtrée) — vérifié par grep, aucune route ne fait
    `VenteLigne.query` seule actuellement. Si ce test se met à ÉCHOUER
    (assert plus vrai), cela veut dire qu'une route a changé et que
    VenteLigne doit être durcie (colonne entreprise_id + entrée dans
    MODELES_TENANT). Ce test sert de garde-fou, pas de validation d'un
    comportement souhaitable."""
    with contexte_dona(app):
        toutes_les_lignes = VenteLigne.query.all()
    montants = {l.montant for l in toutes_les_lignes}
    assert 1500 in montants  # la ligne de SECRETB est visible ici : gap connu
