"""Modèle Achat (approvisionnement)."""
from datetime import datetime, timezone, date
from app.extensions import db


class Achat(db.Model):
    __tablename__ = "achats"

    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey("produits.id"),
                           nullable=False, index=True)
    boutique_id = db.Column(db.Integer, db.ForeignKey("boutiques.id"),
                            nullable=False, default=1)
    entreprise_id = db.Column(db.Integer, db.ForeignKey("entreprises.id"), nullable=False)
    quantite = db.Column(db.Numeric(10, 3), nullable=False)      # kg ou pièces
    prix_unitaire = db.Column(db.Integer, nullable=False)        # FCFA / unité
    montant_total = db.Column(db.Integer, nullable=False)
    cmup_apres = db.Column(db.Integer, nullable=False)           # traçabilité du recalcul
    fournisseur = db.Column(db.String(100), nullable=True)
    date_achat = db.Column(db.Date, nullable=False, default=date.today, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    produit = db.relationship("Produit", back_populates="achats")
    user = db.relationship("User")
