"""Modèle Perte (avaries, invendus périmés, casse)."""
from datetime import datetime, timezone, date
from app.extensions import db


class Perte(db.Model):
    __tablename__ = "pertes"

    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey("produits.id"),
                           nullable=False, index=True)
    boutique_id = db.Column(db.Integer, db.ForeignKey("boutiques.id"),
                            nullable=False, default=1)
    quantite = db.Column(db.Numeric(10, 3), nullable=False)
    motif = db.Column(db.String(200), nullable=False)
    valeur_perte = db.Column(db.Integer, nullable=False)  # quantité x CMUP au moment
    date_perte = db.Column(db.Date, nullable=False, default=date.today, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    produit = db.relationship("Produit")
    user = db.relationship("User")
