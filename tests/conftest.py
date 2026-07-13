"""Fixtures pytest.

Règle d'or : les requêtes HTTP des clients de test s'exécutent HORS de tout
app_context persistant (comme en production, chaque requête crée le sien).
Les accès base dans les tests utilisent de courts `with app.app_context():`.

Pour les tests qui appellent des services directement (hors client HTTP),
utiliser `with contexte_dona(app):` plutôt que `with app.app_context():`
dès qu'un objet rattaché à une entreprise (Achat, Vente, Perte,
StockJournalier, Cloture...) est créé : le mécanisme d'isolation
multi-tenant (app/services/tenant.py) a besoin d'un contexte de requête
avec g.entreprise_id positionné pour marquer automatiquement ces objets.
"""
import os
import tempfile
from contextlib import contextmanager

import pytest
from flask import g

from app import create_app
from app.extensions import db as _db
from app.models import Boutique, Entreprise, Produit, User


@contextmanager
def contexte_dona(app):
    """Contexte de requête minimal avec le tenant DONA actif, pour les
    appels directs aux services (hors client HTTP)."""
    with app.test_request_context():
        g.entreprise_id = Entreprise.query.filter_by(nom="DONA").first().id
        yield


@pytest.fixture()
def app():
    fd, chemin = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    application = create_app("dev", config_surcharges={
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{chemin}",
    })
    with application.app_context():
        _db.create_all()
        entreprise = Entreprise(nom="DONA", statut_abonnement="actif")
        _db.session.add(entreprise)
        _db.session.flush()
        _db.session.add_all([Boutique(nom="Boutique 1 Marché", entreprise_id=entreprise.id),
                             Boutique(nom="Boutique 2 Pavé", entreprise_id=entreprise.id),
                             Boutique(nom="Boutique 3 Chambre Froide", entreprise_id=entreprise.id)])
        for username, role, mdp in [("admin", "admin", "Admin@Test1"),
                                    ("promoteur", "promoteur", "Promo@Test1"),
                                    ("gerant", "gerant", "Gerant@Test1"),
                                    ("caissier", "caissier", "Caissier@Test1")]:
            u = User(username=username, nom_complet=username.capitalize(),
                     role=role, boutique_id=1, entreprise_id=entreprise.id)
            u.set_password(mdp)
            _db.session.add(u)
        _db.session.add(Produit(nom="Tilapia", categorie="poisson", unite="kg",
                                prix_achat=1500, prix_vente=1900,
                                cmup_actuel=1500, seuil_alerte=10,
                                entreprise_id=entreprise.id))
        _db.session.commit()
    yield application
    with application.app_context():
        _db.session.remove()
        _db.engine.dispose()
    os.unlink(chemin)


def _client(app, username, mdp):
    c = app.test_client()
    c.post("/auth/login", data={"username": username, "password": mdp})
    return c


@pytest.fixture()
def client_admin(app):
    return _client(app, "admin", "Admin@Test1")


@pytest.fixture()
def client_gerant(app):
    return _client(app, "gerant", "Gerant@Test1")


@pytest.fixture()
def client_caissier(app):
    return _client(app, "caissier", "Caissier@Test1")


@pytest.fixture()
def client_promoteur(app):
    return _client(app, "promoteur", "Promo@Test1")
