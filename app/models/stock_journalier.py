"""Modèle StockJournalier : la photo quotidienne du stock par produit."""
from app.extensions import db


class StockJournalier(db.Model):
    __tablename__ = "stocks_journaliers"
    __table_args__ = (
        db.UniqueConstraint("boutique_id", "produit_id", "date_stock",
                            name="uq_stock_btq_produit_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey("produits.id"),
                           nullable=False, index=True)
    boutique_id = db.Column(db.Integer, db.ForeignKey("boutiques.id"),
                            nullable=False, default=1)
    date_stock = db.Column(db.Date, nullable=False, index=True)
    stock_initial = db.Column(db.Numeric(10, 3), nullable=False, default=0)
    entrees = db.Column(db.Numeric(10, 3), nullable=False, default=0)
    sorties = db.Column(db.Numeric(10, 3), nullable=False, default=0)
    pertes = db.Column(db.Numeric(10, 3), nullable=False, default=0)
    stock_final = db.Column(db.Numeric(10, 3), nullable=False, default=0)
    stock_physique = db.Column(db.Numeric(10, 3), nullable=True)  # comptage réel
    ecart = db.Column(db.Numeric(10, 3), nullable=True)           # physique - théorique

    produit = db.relationship("Produit")
