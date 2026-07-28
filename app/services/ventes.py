"""Création des ventes : numérotation des tickets, lignes, marges figées."""
from datetime import date as date_type, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Vente, VenteLigne, Produit

NB_TENTATIVES_NUMERO_TICKET = 5


def prochain_numero_ticket(jour: date_type) -> str:
    """V-AAAAMMJJ-0001, séquence par jour."""
    n = Vente.query.filter_by(date_vente=jour).count() + 1
    return f"V-{jour.strftime('%Y%m%d')}-{n:04d}"


def creer_vente(lignes_data: list[dict], mode_paiement: str, user,
                prix_modifiables: bool, boutique_id: int | None = None,
                date_heure: datetime | None = None) -> Vente:
    """Crée une vente multi-lignes.

    lignes_data : [{"produit_id": int, "quantite": Decimal, "prix": int|None}, ...]
    prix_modifiables : True uniquement pour l'admin ; sinon le prix soumis est
    IGNORÉ et remplacé par le prix catalogue (application stricte côté serveur).
    date_heure : moment réel de la vente si différent de maintenant — utilisé
    par /ventes/sync pour qu'une vente créée hors-ligne hier reste attribuée
    à hier, pas au jour où elle est synchronisée.
    L'appelant committe.
    """
    maintenant = date_heure or datetime.now()
    jour = maintenant.date()

    specs = []
    total = 0
    for item in lignes_data:
        produit = db.session.get(Produit, int(item["produit_id"]))
        if produit is None or not produit.actif:
            raise ValueError("Produit invalide ou inactif.")
        quantite = Decimal(str(item["quantite"]))
        if quantite <= 0:
            raise ValueError("Quantité invalide.")

        prix_catalogue = produit.prix_vente
        if prix_modifiables and item.get("prix") not in (None, ""):
            prix_applique = int(item["prix"])
            if prix_applique < 0:
                raise ValueError("Prix invalide.")
        else:
            prix_applique = prix_catalogue

        montant = int((quantite * Decimal(prix_applique))
                      .quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        # Marge = prix de vente - prix d'achat (pas le CMUP, qui reste
        # utilisé séparément pour la valorisation du stock/des pertes).
        cout = produit.prix_achat
        marge = int(((Decimal(prix_applique) - Decimal(cout)) * quantite)
                    .quantize(Decimal("1"), rounding=ROUND_HALF_UP))

        specs.append(dict(
            produit_id=produit.id, quantite=quantite, prix_catalogue=prix_catalogue,
            prix_applique=prix_applique, montant=montant, cmup_au_moment=cout,
            marge=marge,
        ))
        total += montant

    if not specs:
        raise ValueError("Une vente doit contenir au moins une ligne.")

    # Concurrence : prochain_numero_ticket() compte les ventes du jour pour
    # deviner le prochain numéro — deux ventes soumises au même instant
    # (double-clic, deux caissiers en même temps) peuvent calculer le même
    # numéro. On retente avec un numéro frais plutôt que de laisser planter
    # la requête sur la contrainte d'unicité.
    derniere_erreur = None
    for _ in range(NB_TENTATIVES_NUMERO_TICKET):
        vente = Vente(
            numero_ticket=prochain_numero_ticket(jour),
            date_vente=jour,
            heure_vente=maintenant.time().replace(microsecond=0),
            mode_paiement=mode_paiement,
            user_id=user.id,
            boutique_id=boutique_id or user.boutique_id,
        )
        vente.lignes = [VenteLigne(**s) for s in specs]
        vente.montant_total = total
        db.session.add(vente)
        try:
            db.session.flush()
            return vente
        except IntegrityError as e:
            derniere_erreur = e
            db.session.rollback()
    raise ValueError(
        "Impossible d'enregistrer le ticket (numéro déjà utilisé), réessayez."
    ) from derniere_erreur


def contexte_ticket(vente: Vente) -> dict:
    """Prépare le dictionnaire attendu par le template ticket.html."""
    lignes = []
    for l in vente.lignes:
        qte = f"{l.quantite:.3f}".rstrip("0").rstrip(".").replace(".", ",")
        unite = "kg" if l.produit.unite == "kg" else ("pièce" if l.quantite == 1 else "pièces")
        lignes.append({
            "produit": l.produit.nom,
            "quantite": f"{qte} {unite}",
            "prix": l.prix_applique,
            "montant": l.montant,
        })
    from app.models import Boutique, Entreprise
    boutique = db.session.get(Boutique, vente.boutique_id)
    entreprise = db.session.get(Entreprise, vente.entreprise_id)
    return {
        "numero_ticket": vente.numero_ticket,
        "entreprise": entreprise.nom if entreprise else "",
        "boutique": boutique.nom if boutique else "",
        "date_heure": datetime.combine(vente.date_vente, vente.heure_vente),
        "vendeur": vente.user.nom_complet,
        "mode_paiement": vente.mode_paiement_libelle,
        "lignes": lignes,
        "montant_total": vente.montant_total,
    }
