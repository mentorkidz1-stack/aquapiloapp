"""Modèles Produit et PrixHistorique."""
from datetime import datetime, timezone, date
from app.extensions import db

CATEGORIES = ("poisson", "viande")
UNITES = ("kg", "piece")


class Produit(db.Model):
    __tablename__ = "produits"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(80), unique=True, nullable=False, index=True)
    categorie = db.Column(db.Enum(*CATEGORIES, name="categorie_enum"), nullable=False)
    # L'unité gouverne toute la chaîne : achat, stock et vente (décision Phase 0)
    unite = db.Column(db.Enum(*UNITES, name="unite_enum"), nullable=False, default="kg")
    prix_achat = db.Column(db.Integer, nullable=False, default=0)   # FCFA / unité
    prix_vente = db.Column(db.Integer, nullable=False, default=0)   # FCFA / unité
    cmup_actuel = db.Column(db.Integer, nullable=False, default=0)  # FCFA / unité
    seuil_alerte = db.Column(db.Numeric(10, 3), nullable=False, default=10)
    actif = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    achats = db.relationship("Achat", back_populates="produit", lazy="dynamic")
    historique_prix = db.relationship("PrixHistorique", back_populates="produit",
                                      lazy="dynamic",
                                      order_by="PrixHistorique.created_at.desc()")

    @property
    def unite_affichee(self) -> str:
        return "kg" if self.unite == "kg" else "pièce"

    def __repr__(self):
        return f"<Produit {self.nom}>"


class PrixHistorique(db.Model):
    __tablename__ = "prix_historique"

    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey("produits.id"),
                           nullable=False, index=True)
    type_prix = db.Column(db.Enum("achat", "vente", name="type_prix_enum"),
                          nullable=False)
    ancien_prix = db.Column(db.Integer, nullable=False)
    nouveau_prix = db.Column(db.Integer, nullable=False)
    date_effet = db.Column(db.Date, nullable=False, default=date.today)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    produit = db.relationship("Produit", back_populates="historique_prix")
    user = db.relationship("User")
