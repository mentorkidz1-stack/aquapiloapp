"""Isolation multi-tenant : filtre automatique de lecture, auto-marquage à
la création, et validation des références croisées entre entreprises.

Le tenant courant est résolu une fois par requête (g.entreprise_id,
alimenté depuis current_user.entreprise_id) et appliqué automatiquement à
TOUTE requête ORM via des events SQLAlchemy — même principe que le journal
d'audit (app/services/audit.py).

Fail-closed : si le tenant n'est pas résolu (pas encore authentifié,
@login_required oublié sur une nouvelle route...), le filtre applique
`entreprise_id IS NULL`, qui ne correspond à AUCUNE ligne (la colonne est
NOT NULL) — donc rien n'est montré. La seule façon de voir plusieurs
entreprises est le bypass explicite `sans_filtre_tenant()`, utilisé
uniquement pour la recherche d'utilisateur à la connexion (avant de
connaître son entreprise) et pour un futur accès opérateur SaaS.

Hors contexte de requête (scripts d'administration, migrations, seed),
aucun filtre ni marquage n'est appliqué : ces scripts tournent sur le
serveur, hors de portée d'un client HTTP, et gèrent entreprise_id
explicitement.

Piège SQLAlchemy évité ici : `with_loader_criteria` met en cache le SQL
compilé par forme de requête. Si la valeur du tenant est capturée via un
argument par défaut du lambda (`lambda cls, eid=entreprise_id: ...`),
SQLAlchemy ne suit PAS cette valeur d'une exécution à l'autre : la
première requête compilée fige sa valeur dans le cache, et TOUTES les
requêtes suivantes de même forme — y compris celles d'un autre tenant —
reçoivent le même filtre figé. Utiliser une vraie variable de fermeture
(closure), résolue à chaque appel du handler, corrige ce problème :
SQLAlchemy la retrace et recalcule le paramètre lié à chaque exécution.
"""
from contextlib import contextmanager

from flask import g, has_request_context
from flask_login import current_user
from sqlalchemy import event, inspect
from sqlalchemy.orm import with_loader_criteria

from app.extensions import db
from app.models import (Achat, AuditLog, Boutique, Cloture, Perte,
                        PrixHistorique, Produit, Reouverture,
                        StockJournalier, User, Vente, VenteLigne)

# Modèles qui portent directement entreprise_id : filtrés en lecture et
# marqués automatiquement à la création.
MODELES_TENANT = (Boutique, User, Produit, Vente, Achat, Perte,
                  StockJournalier, Cloture, AuditLog)

# Clés étrangères à valider comme pointant vers une ligne du tenant courant
# avant tout flush. Couvre aussi les modèles sans colonne entreprise_id
# propre (VenteLigne, PrixHistorique, Reouverture) : leur cohérence tenant
# est garantie via la ligne référencée (déjà filtrée par tenant ci-dessus).
CLES_A_VALIDER = {
    User: {"boutique_id": Boutique},
    Vente: {"boutique_id": Boutique},
    VenteLigne: {"produit_id": Produit},
    Achat: {"produit_id": Produit, "boutique_id": Boutique},
    Perte: {"produit_id": Produit, "boutique_id": Boutique},
    PrixHistorique: {"produit_id": Produit},
    StockJournalier: {"produit_id": Produit, "boutique_id": Boutique},
    Cloture: {"boutique_id": Boutique},
    Reouverture: {"cloture_id": Cloture},
}


def entreprise_courante_id():
    """Entreprise de l'utilisateur connecté, ou None hors contexte de
    requête authentifiée."""
    if not has_request_context():
        return None
    return getattr(g, "entreprise_id", None)


def init_tenant_context(app):
    """Résout le tenant courant une fois par requête, avant toute vue."""
    @app.before_request
    def _charger_tenant():
        g.entreprise_id = (current_user.entreprise_id
                           if current_user.is_authenticated else None)
        g.tenant_bypass = False


@contextmanager
def sans_filtre_tenant():
    """Bypass explicite et audité du filtre tenant.

    Réservé aux besoins légitimes de recherche cross-tenant :
    - la recherche d'utilisateur à la connexion, avant de savoir à quelle
      entreprise il appartient ;
    - un futur accès opérateur SaaS (support, facturation, activation),
      lui-même protégé par sa propre autorisation stricte.

    Ne jamais utiliser ce bypass pour des données montrées à un client :
    c'est la seule porte de sortie du fail-closed, elle doit rester rare,
    nommée et grep-able (`sans_filtre_tenant`) plutôt qu'implicite."""
    if not has_request_context():
        yield
        return
    avant = getattr(g, "tenant_bypass", False)
    g.tenant_bypass = True
    try:
        yield
    finally:
        g.tenant_bypass = avant


_initialise = False


def init_isolation():
    global _initialise
    if _initialise:      # listeners globaux : ne jamais les enregistrer deux fois
        return
    _initialise = True

    @event.listens_for(db.session.__class__, "do_orm_execute")
    def _filtrer_par_tenant(execute_state):
        if not execute_state.is_select:
            return
        if not has_request_context():
            return  # scripts/CLI hors requête : gèrent entreprise_id explicitement
        if getattr(g, "tenant_bypass", False):
            return  # bypass explicite (cf. sans_filtre_tenant)

        # Variable de fermeture résolue à CHAQUE appel du handler (donc à
        # chaque exécution ORM) : SQLAlchemy la retrace correctement d'une
        # requête à l'autre. entreprise_id peut être None (tenant non
        # résolu) : le critère devient alors "IS NULL", qui ne correspond
        # à aucune ligne puisque la colonne est NOT NULL -> fail-closed.
        entreprise_id = entreprise_courante_id()
        for modele in MODELES_TENANT:
            execute_state.statement = execute_state.statement.options(
                with_loader_criteria(
                    modele,
                    lambda cls: cls.entreprise_id == entreprise_id,
                    include_aliases=True,
                )
            )

    @event.listens_for(db.session.__class__, "before_flush")
    def _marquer_et_valider(session, flush_context, instances):
        entreprise_id = entreprise_courante_id()
        if entreprise_id is None:
            return

        for obj in session.new:
            if isinstance(obj, MODELES_TENANT):
                obj.entreprise_id = entreprise_id

        for obj in session.dirty:
            if (isinstance(obj, MODELES_TENANT)
                    and inspect(obj).attrs.entreprise_id.history.has_changes()):
                raise ValueError(
                    f"Modification de entreprise_id interdite sur "
                    f"{type(obj).__name__} {obj.id}.")

        with session.no_autoflush:
            for obj in list(session.new) + list(session.dirty):
                regles = CLES_A_VALIDER.get(type(obj))
                if not regles:
                    continue
                for colonne, modele_cible in regles.items():
                    valeur = getattr(obj, colonne, None)
                    if valeur is None:
                        continue
                    if session.get(modele_cible, valeur) is None:
                        raise ValueError(
                            f"Référence invalide : {modele_cible.__name__} "
                            f"{valeur} n'appartient pas à votre entreprise.")
