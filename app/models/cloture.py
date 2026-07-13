"""Modèles Cloture et Reouverture."""
import json
from datetime import datetime, timezone
from app.extensions import db

TYPES_PERIODE = ("jour", "semaine", "mois")


class Cloture(db.Model):
    __tablename__ = "clotures"
    __table_args__ = (
        db.UniqueConstraint("boutique_id", "type_periode",
                            "periode_debut", "periode_fin",
                            name="uq_cloture_btq_periode"),
    )

    id = db.Column(db.Integer, primary_key=True)
    type_periode = db.Column(db.Enum(*TYPES_PERIODE, name="type_periode_enum"),
                             nullable=False)
    periode_debut = db.Column(db.Date, nullable=False, index=True)
    periode_fin = db.Column(db.Date, nullable=False, index=True)
    statut = db.Column(db.Enum("cloture", "rouvert", name="statut_cloture_enum"),
                       nullable=False, default="cloture")
    sans_activite = db.Column(db.Boolean, nullable=False, default=False)
    snapshot_json = db.Column(db.Text, nullable=False, default="{}")
    boutique_id = db.Column(db.Integer, db.ForeignKey("boutiques.id"),
                            nullable=False, default=1)
    entreprise_id = db.Column(db.Integer, db.ForeignKey("entreprises.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User")
    reouvertures = db.relationship("Reouverture", back_populates="cloture",
                                   order_by="Reouverture.created_at.desc()")

    @property
    def snapshot(self) -> dict:
        try:
            return json.loads(self.snapshot_json)
        except (TypeError, ValueError):
            return {}


class Reouverture(db.Model):
    __tablename__ = "reouvertures"

    id = db.Column(db.Integer, primary_key=True)
    cloture_id = db.Column(db.Integer, db.ForeignKey("clotures.id"),
                           nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    motif = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    cloture = db.relationship("Cloture", back_populates="reouvertures")
    user = db.relationship("User")
