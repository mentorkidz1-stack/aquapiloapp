"""Modèle Boutique — prévu pour l'extension multi-boutique future."""
from datetime import datetime, timezone
from app.extensions import db


class Boutique(db.Model):
    __tablename__ = "boutiques"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    adresse = db.Column(db.String(200), nullable=True)
    actif = db.Column(db.Boolean, nullable=False, default=True)
    entreprise_id = db.Column(db.Integer, db.ForeignKey("entreprises.id"), nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    entreprise = db.relationship("Entreprise", back_populates="boutiques")
    users = db.relationship("User", back_populates="boutique", lazy="dynamic")

    def __repr__(self):
        return f"<Boutique {self.nom}>"
