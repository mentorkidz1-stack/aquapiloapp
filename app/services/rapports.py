"""Indicateurs, séries hebdo/mensuelles, top/flop, alertes stock."""
import calendar
from datetime import date as date_type, timedelta
from decimal import Decimal

from app.extensions import db
from app.models import Perte, Produit, Vente, VenteLigne
from app.services.cmup import stock_courant


def indicateurs_periode(debut: date_type, fin: date_type,
                        boutique_id: int | None = None) -> dict:
    q_ventes = Vente.query.filter(Vente.date_vente.between(debut, fin),
                                  Vente.statut == "valide")
    q_volume = db.session.query(
        db.func.coalesce(db.func.sum(VenteLigne.quantite), 0)
    ).join(Vente).filter(Vente.date_vente.between(debut, fin),
                         Vente.statut == "valide")
    q_pertes = db.session.query(
        db.func.coalesce(db.func.sum(Perte.valeur_perte), 0)
    ).filter(Perte.date_perte.between(debut, fin))
    if boutique_id:
        q_ventes = q_ventes.filter(Vente.boutique_id == boutique_id)
        q_volume = q_volume.filter(Vente.boutique_id == boutique_id)
        q_pertes = q_pertes.filter(Perte.boutique_id == boutique_id)
    ventes = q_ventes.all()
    volume = q_volume.scalar()
    pertes = q_pertes.scalar()
    return {
        "debut": debut, "fin": fin,
        "debut_iso": debut.isoformat(), "fin_iso": fin.isoformat(),
        "ca": sum(v.montant_total for v in ventes),
        "marge": sum(v.marge_totale for v in ventes),
        "nb_ventes": len(ventes),
        "volume": float(volume),
        "pertes": int(pertes),
    }


def _variation(serie: list[dict], cle: str) -> None:
    """Ajoute serie[i][cle+'_var'] = variation % vs période précédente."""
    for i, p in enumerate(serie):
        if i == 0 or serie[i - 1][cle] == 0:
            p[cle + "_var"] = None
        else:
            p[cle + "_var"] = round(
                (p[cle] - serie[i - 1][cle]) / serie[i - 1][cle] * 100, 1)


def serie_semaines(nb: int = 8, boutique_id: int | None = None) -> list[dict]:
    """Les `nb` dernières semaines (lundi->dimanche), la plus ancienne d'abord."""
    lundi_courant = date_type.today() - timedelta(days=date_type.today().weekday())
    serie = []
    for i in range(nb - 1, -1, -1):
        lundi = lundi_courant - timedelta(weeks=i)
        p = indicateurs_periode(lundi, lundi + timedelta(days=6), boutique_id)
        p["libelle"] = "Sem. " + lundi.strftime("%d/%m")
        p["en_cours"] = (lundi == lundi_courant)
        serie.append(p)
    for cle in ("ca", "marge", "volume"):
        _variation(serie, cle)
    return serie


def serie_mois(nb: int = 6, boutique_id: int | None = None) -> list[dict]:
    """Les `nb` derniers mois, le plus ancien d'abord."""
    auj = date_type.today()
    serie = []
    annee, mois = auj.year, auj.month
    piles = []
    for _ in range(nb):
        piles.append((annee, mois))
        mois -= 1
        if mois == 0:
            annee, mois = annee - 1, 12
    for annee, mois in reversed(piles):
        debut = date_type(annee, mois, 1)
        fin = date_type(annee, mois, calendar.monthrange(annee, mois)[1])
        p = indicateurs_periode(debut, fin, boutique_id)
        p["libelle"] = debut.strftime("%m/%Y")
        p["en_cours"] = (annee, mois) == (auj.year, auj.month)
        serie.append(p)
    for cle in ("ca", "marge", "volume"):
        _variation(serie, cle)
    return serie


def serie_jours(nb: int = 7, boutique_id: int | None = None) -> list[dict]:
    serie = []
    for i in range(nb - 1, -1, -1):
        j = date_type.today() - timedelta(days=i)
        p = indicateurs_periode(j, j, boutique_id)
        p["libelle"] = j.strftime("%d/%m")
        serie.append(p)
    return serie


def detail_produits(debut: date_type, fin: date_type,
                    boutique_id: int | None = None) -> list[dict]:
    """Par produit : quantité vendue, CA, marge sur la période (ventes valides)."""
    q = db.session.query(
        Produit.nom, Produit.unite,
        db.func.sum(VenteLigne.quantite),
        db.func.sum(VenteLigne.montant),
        db.func.sum(VenteLigne.marge),
    ).join(VenteLigne.produit).join(VenteLigne.vente).filter(
        Vente.date_vente.between(debut, fin), Vente.statut == "valide")
    if boutique_id:
        q = q.filter(Vente.boutique_id == boutique_id)
    lignes = q.group_by(Produit.id).order_by(
        db.func.sum(VenteLigne.marge).desc()).all()
    return [{"nom": n, "unite": u, "quantite": float(q),
             "ca": int(ca), "marge": int(m)}
            for n, u, q, ca, m in lignes]


def top_flop(debut: date_type, fin: date_type, n: int = 5,
             boutique_id: int | None = None):
    d = detail_produits(debut, fin, boutique_id)
    return d[:n], list(reversed(d[-n:])) if len(d) > n else list(reversed(d))


def alertes_stock() -> list[dict]:
    alertes = []
    for p in Produit.query.filter_by(actif=True).all():
        stock = stock_courant(p.id)
        if stock <= p.seuil_alerte:
            alertes.append({"produit": p, "stock": stock})
    return sorted(alertes, key=lambda a: float(a["stock"]))


def repartition_paiements(debut: date_type, fin: date_type,
                          boutique_id: int | None = None) -> list[tuple]:
    from app.models.vente import MODES_LIBELLES
    q = db.session.query(
        Vente.mode_paiement, db.func.count(Vente.id),
        db.func.sum(Vente.montant_total),
    ).filter(Vente.date_vente.between(debut, fin), Vente.statut == "valide")
    if boutique_id:
        q = q.filter(Vente.boutique_id == boutique_id)
    lignes = q.group_by(Vente.mode_paiement).all()
    return [(MODES_LIBELLES.get(m, m), int(nb), int(total or 0))
            for m, nb, total in lignes]
