"""Modèle Entreprise — le tenant SaaS (une poissonnerie cliente)."""
from datetime import datetime, timezone
from app.extensions import db

STATUTS_ABONNEMENT = ("essai", "actif", "suspendu")
TARIF_BASE = 3000     # FCFA/mois, 1 à 2 boutiques
TARIF_PALIER = 5000   # FCFA/mois, à partir de 3 boutiques
SEUIL_PALIER = 3


class Entreprise(db.Model):
    __tablename__ = "entreprises"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(150), unique=True, nullable=False, index=True)
    statut_abonnement = db.Column(
        db.Enum(*STATUTS_ABONNEMENT, name="statut_abonnement_enum"),
        nullable=False, default="essai",
    )
    date_fin_essai = db.Column(db.Date, nullable=True)
    date_echeance = db.Column(db.Date, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    boutiques = db.relationship("Boutique", back_populates="entreprise", lazy="dynamic")
    users = db.relationship("User", back_populates="entreprise", lazy="dynamic")
    produits = db.relationship("Produit", back_populates="entreprise", lazy="dynamic")

    def tarif_mensuel(self) -> int:
        """3000 FCFA/mois pour 1-2 boutiques, 5000 FCFA/mois à partir de 3."""
        return TARIF_PALIER if self.boutiques.count() >= SEUIL_PALIER else TARIF_BASE

    def __repr__(self):
        return f"<Entreprise {self.nom}>"
