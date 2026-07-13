"""Journal d'audit automatique : toute création/modification/suppression
sur les tables métier est enregistrée (utilisateur, anciennes/nouvelles
valeurs, horodatage) via les événements de session SQLAlchemy.
"""
import json
from datetime import date, time, datetime, timezone
from decimal import Decimal

from sqlalchemy import event, inspect

from app.extensions import db
from app.models import (Achat, AuditLog, Cloture, Perte, PrixHistorique,
                        Produit, Reouverture, StockJournalier, User,
                        Vente, VenteLigne)

TABLES_AUDITEES = (Achat, Vente, VenteLigne, Perte, Produit, PrixHistorique,
                   StockJournalier, Cloture, Reouverture, User)
COLONNES_EXCLUES = {"password_hash"}  # jamais de secret dans l'audit


def _jsonable(v):
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (date, time, datetime)):
        return v.isoformat()
    return v


def _snapshot(obj) -> dict:
    return {c.key: _jsonable(getattr(obj, c.key))
            for c in inspect(obj).mapper.column_attrs
            if c.key not in COLONNES_EXCLUES}


def _changements(obj) -> tuple[dict, dict]:
    """(anciennes, nouvelles) valeurs des seules colonnes modifiées."""
    anciennes, nouvelles = {}, {}
    etat = inspect(obj)
    for attr in etat.mapper.column_attrs:
        if attr.key in COLONNES_EXCLUES:
            continue
        hist = etat.attrs[attr.key].history
        if hist.has_changes():
            anciennes[attr.key] = _jsonable(hist.deleted[0]) if hist.deleted else None
            nouvelles[attr.key] = _jsonable(hist.added[0]) if hist.added else None
    return anciennes, nouvelles


def _user_id():
    try:
        from flask_login import current_user
        if current_user and current_user.is_authenticated:
            return int(current_user.get_id())
    except Exception:
        pass
    return None


def _entreprise_id_de(obj):
    """Entreprise propriétaire de l'objet audité — directe, ou via son
    parent pour les tables sans colonne entreprise_id propre (VenteLigne,
    PrixHistorique, Reouverture). Recherche le parent par identifiant
    (session.get, prioritairement servi par la carte d'identité déjà en
    mémoire) plutôt que par la relation ORM, pour rester fiable même
    pendant un flush en cours."""
    if hasattr(obj, "entreprise_id"):
        return obj.entreprise_id
    from app.models import Cloture, Produit, Vente
    for colonne_fk, modele_parent in (("vente_id", Vente),
                                      ("produit_id", Produit),
                                      ("cloture_id", Cloture)):
        valeur = getattr(obj, colonne_fk, None)
        if valeur is not None:
            parent = db.session.get(modele_parent, valeur)
            if parent is not None:
                return parent.entreprise_id
    return None


_initialise = False


def init_audit():
    global _initialise
    if _initialise:      # listeners globaux : ne jamais les enregistrer deux fois
        return
    _initialise = True

    @event.listens_for(db.session.__class__, "before_flush")
    def _avant(session, flush_context, instances):
        # Capturer les MODIFICATIONS et SUPPRESSIONS avant que l'état ne change
        session.info.setdefault("_audit", [])
        for obj in session.dirty:
            if isinstance(obj, TABLES_AUDITEES) and session.is_modified(obj):
                anciennes, nouvelles = _changements(obj)
                if nouvelles:
                    session.info["_audit"].append(
                        ("update", obj, anciennes, nouvelles))
        for obj in session.deleted:
            if isinstance(obj, TABLES_AUDITEES):
                session.info["_audit"].append(
                    ("delete", obj, _snapshot(obj), None))

    @event.listens_for(db.session.__class__, "after_flush")
    def _apres(session, flush_context):
        # Les CRÉATIONS sont traitées ici : les IDs sont désormais connus
        lignes = []
        uid = _user_id()
        for obj in session.new:
            if isinstance(obj, TABLES_AUDITEES):
                lignes.append({
                    "user_id": uid, "entreprise_id": _entreprise_id_de(obj),
                    "action": "create",
                    "table_nom": obj.__tablename__,
                    "enregistrement_id": obj.id,
                    "ancienne_valeur": None,
                    "nouvelle_valeur": json.dumps(_snapshot(obj), ensure_ascii=False),
                    "created_at": datetime.now(timezone.utc),
                })
        for action, obj, anciennes, nouvelles in session.info.pop("_audit", []):
            lignes.append({
                "user_id": uid, "entreprise_id": _entreprise_id_de(obj),
                "action": action,
                "table_nom": obj.__tablename__,
                "enregistrement_id": obj.id,
                "ancienne_valeur": json.dumps(anciennes, ensure_ascii=False)
                                   if anciennes else None,
                "nouvelle_valeur": json.dumps(nouvelles, ensure_ascii=False)
                                   if nouvelles else None,
                "created_at": datetime.now(timezone.utc),
            })
        if lignes:
            session.connection().execute(AuditLog.__table__.insert(), lignes)
