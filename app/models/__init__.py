"""Import centralisé des modèles (nécessaire pour Alembic autogenerate)."""
from app.models.boutique import Boutique
from app.models.user import User
from app.models.produit import Produit, PrixHistorique
from app.models.achat import Achat
from app.models.vente import Vente, VenteLigne
from app.models.perte import Perte
from app.models.stock_journalier import StockJournalier
from app.models.cloture import Cloture, Reouverture
from app.models.audit import AuditLog

__all__ = ["Boutique", "User", "Produit", "PrixHistorique", "Achat",
           "Vente", "VenteLigne", "Perte", "StockJournalier",
           "Cloture", "Reouverture", "AuditLog"]
