"""Blueprint ventes : caisse (par boutique), journal, ticket 58 mm, annulation.

Droits : caisse = tous ; journal = gérant+ (gérant : seulement si son accès
au rapport journalier est activé par la direction) ; annulation = gérant+.
Le caissier vend dans SA boutique ; gérant/direction choisissent la boutique.
"""
import json
from datetime import date, datetime

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, abort, jsonify)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Boutique, Vente, Produit, User
from app.models.vente import MODES_PAIEMENT, MODES_LIBELLES
from app.services.ventes import creer_vente, contexte_ticket
from app.services.cmup import matrice_stocks
from app.services.clotures import periode_est_cloturee
from app.utils.decorators import role_required, periode_non_cloturee

ventes_bp = Blueprint("ventes", __name__, url_prefix="/ventes")


def _boutiques():
    return Boutique.query.filter_by(actif=True).order_by(Boutique.id).all()


def _boutique_du_formulaire():
    """Boutique de la vente : le caissier est FORCÉ sur la sienne."""
    if not current_user.is_gerant:
        return current_user.boutique_id
    try:
        return int(request.form.get("boutique_id", current_user.boutique_id))
    except (TypeError, ValueError):
        return current_user.boutique_id


# ---------------- CAISSE ----------------
@ventes_bp.route("/ping")
@login_required
def ping():
    # Endpoint volontairement minimal (aucune requête DB) : la caisse
    # s'en sert pour savoir, juste avant de valider une vente, si le
    # serveur est réellement joignable — navigator.onLine ne reflète
    # que l'état de la carte réseau de l'appareil, pas la joignabilité
    # du serveur (cf. phase 2).
    return "OK"


@ventes_bp.route("/caisse", methods=["GET", "POST"])
@login_required
@periode_non_cloturee(lambda: (date.today(), None))  # boutique lue dans le form
def caisse():
    produits = Produit.query.filter_by(actif=True).order_by(
        Produit.categorie, Produit.nom).all()

    if request.method == "POST":
        try:
            lignes_data = json.loads(request.form.get("lignes", "[]"))
            mode = request.form.get("mode_paiement", "")
            if mode not in MODES_PAIEMENT:
                raise ValueError("Mode de paiement invalide.")
            vente = creer_vente(
                lignes_data, mode, current_user,
                prix_modifiables=current_user.is_direction,
                boutique_id=_boutique_du_formulaire(),
            )
            db.session.commit()
            flash(f"Vente {vente.numero_ticket} enregistrée : "
                  f"{vente.montant_total} FCFA.", "success")
            return redirect(url_for("ventes.ticket", vente_id=vente.id))
        except (ValueError, json.JSONDecodeError) as e:
            db.session.rollback()
            flash(str(e) or "Saisie invalide.", "danger")

    stocks = matrice_stocks()
    produits_json = [{
        "id": p.id, "nom": p.nom, "unite": p.unite,
        "prix_vente": p.prix_vente, "categorie": p.categorie,
        "stocks": {str(b.id): float(stocks.get((p.id, b.id), 0))
                   for b in _boutiques()},
    } for p in produits]
    return render_template("ventes/caisse.html", produits_json=produits_json,
                           modes=MODES_LIBELLES,
                           boutiques=_boutiques(),
                           boutique_fixe=(None if current_user.is_gerant
                                          else current_user.boutique_id),
                           prix_modifiable=current_user.is_direction)


@ventes_bp.route("/sync", methods=["POST"])
@login_required
def sync():
    """Synchronise les ventes créées hors-ligne par la caisse PWA.

    Idempotent par uuid_client : rejouer le même envoi (retry après une
    coupure pendant la requête elle-même) ne crée jamais de doublon.
    Chaque vente du lot est traitée indépendamment ; un conflit sur
    l'une (période clôturée depuis, mode de paiement invalide...) ne
    bloque pas les autres et n'est JAMAIS ignoré silencieusement — le
    client garde la vente en statut "conflit" pour résolution manuelle.
    """
    payload = request.get_json(silent=True) or {}
    resultats = []

    for item in payload.get("ventes", []):
        uuid_client = item.get("uuid")
        if not uuid_client:
            resultats.append({"uuid": None, "statut": "conflit",
                              "erreur": "Identifiant de vente manquant."})
            continue

        existante = Vente.query.filter_by(uuid_client=uuid_client).first()
        if existante is not None:
            # Déjà synchronisée lors d'un envoi précédent (retry réseau) :
            # on renvoie son numéro réel, sans rien recréer.
            resultats.append({"uuid": uuid_client, "statut": "synchronisee",
                              "numero_ticket": existante.numero_ticket,
                              "vente_id": existante.id})
            continue

        try:
            boutique_id = int(item.get("boutiqueId") or current_user.boutique_id)
            if not current_user.is_gerant:
                boutique_id = current_user.boutique_id  # même contrainte que la caisse en ligne

            date_creation = datetime.fromtimestamp(int(item.get("dateCreation", 0)) / 1000)
            if periode_est_cloturee(date_creation.date(), boutique_id):
                raise ValueError(
                    f"La période du {date_creation.strftime('%d/%m/%Y')} "
                    "est déjà clôturée : synchronisation impossible, "
                    "contactez un administrateur.")

            mode = item.get("modePaiement", "")
            if mode not in MODES_PAIEMENT:
                raise ValueError("Mode de paiement invalide.")

            lignes_data = [{"produit_id": l.get("produit_id"),
                            "quantite": l.get("quantite"), "prix": l.get("prix")}
                           for l in item.get("lignes", [])]

            vente = creer_vente(
                lignes_data, mode, current_user,
                prix_modifiables=current_user.is_direction,
                boutique_id=boutique_id, date_heure=date_creation,
            )
            vente.uuid_client = uuid_client
            db.session.commit()
            resultats.append({"uuid": uuid_client, "statut": "synchronisee",
                              "numero_ticket": vente.numero_ticket,
                              "vente_id": vente.id})
        except Exception as e:
            db.session.rollback()
            resultats.append({"uuid": uuid_client, "statut": "conflit",
                              "erreur": str(e) or "Erreur inconnue."})

    return jsonify({"resultats": resultats})


# ---------------- JOURNAL ----------------
@ventes_bp.route("/")
@login_required
@role_required("gerant")
def journal():
    if not current_user.peut_voir_rapport_journalier:
        flash("L'accès au rapport des ventes journalier a été verrouillé "
              "par la direction.", "warning")
        return redirect(url_for("main.dashboard"))
    try:
        jour = date.fromisoformat(request.args.get("jour", ""))
    except ValueError:
        jour = date.today()
    produit_id = request.args.get("produit_id", type=int)
    vendeur_id = request.args.get("vendeur_id", type=int)
    mode = request.args.get("mode", "")
    boutique_id = request.args.get("boutique_id", type=int)

    requete = Vente.query.filter_by(date_vente=jour)
    if boutique_id:
        requete = requete.filter_by(boutique_id=boutique_id)
    if vendeur_id:
        requete = requete.filter_by(user_id=vendeur_id)
    if mode in MODES_PAIEMENT:
        requete = requete.filter_by(mode_paiement=mode)
    ventes = requete.order_by(Vente.id.desc()).all()
    if produit_id:
        ventes = [v for v in ventes
                  if any(l.produit_id == produit_id for l in v.lignes)]

    valides = [v for v in ventes if v.statut == "valide"]
    ca = sum(v.montant_total for v in valides)
    marge = sum(v.marge_totale for v in valides)

    produits = Produit.query.filter_by(actif=True).order_by(Produit.nom).all()
    vendeurs = User.query.filter_by(actif=True).order_by(User.nom_complet).all()
    noms_boutiques = {b.id: b.nom for b in _boutiques()}
    return render_template("ventes/journal.html", ventes=ventes, jour=jour,
                           ca=ca, marge=marge, produits=produits,
                           vendeurs=vendeurs, modes=MODES_LIBELLES,
                           noms_boutiques=noms_boutiques,
                           masquer_marge=(current_user.role == "gerant"),
                           boutiques=_boutiques(), boutique_id=boutique_id,
                           produit_id=produit_id, vendeur_id=vendeur_id,
                           mode=mode)


# ---------------- TICKET (impression / réimpression) ----------------
@ventes_bp.route("/<int:vente_id>/ticket")
@login_required
def ticket(vente_id):
    vente = db.get_or_404(Vente, vente_id)
    # Un caissier ne consulte que les tickets de sa boutique
    if not current_user.is_gerant and vente.boutique_id != current_user.boutique_id:
        abort(403)
    return render_template("ventes/ticket.html",
                           vente=contexte_ticket(vente),
                           demo=False, annulee=(vente.statut == "annule"))


# ---------------- ANNULATION (gérant / direction) ----------------
@ventes_bp.route("/<int:vente_id>/annuler", methods=["POST"])
@login_required
@role_required("gerant")
def annuler(vente_id):
    vente = db.get_or_404(Vente, vente_id)
    if periode_est_cloturee(vente.date_vente, vente.boutique_id):
        flash("Période clôturée : impossible d'annuler cette vente. "
              "Demandez à un administrateur de rouvrir la période.", "danger")
    elif vente.statut == "annule":
        flash("Cette vente est déjà annulée.", "warning")
    else:
        vente.statut = "annule"
        db.session.commit()
        flash(f"Vente {vente.numero_ticket} annulée. "
              "Le stock a été automatiquement restitué.", "success")
    return redirect(url_for("ventes.journal", jour=vente.date_vente.isoformat()))


# ---------------- DÉMO ticket (test d'impression) ----------------
@ventes_bp.route("/ticket-demo")
@login_required
def ticket_demo():
    vente_demo = {
        "numero_ticket": "V-20260702-0042",
        "date_heure": datetime.now(),
        "vendeur": current_user.nom_complet,
        "boutique": "Boutique 1 Marché",
        "mode_paiement": "Espèces",
        "lignes": [
            {"produit": "Tilapia", "quantite": "1,250 kg", "prix": 2500, "montant": 3125},
            {"produit": "Poulet complet", "quantite": "1 pièce", "prix": 4500, "montant": 4500},
        ],
        "montant_total": 7625,
    }
    return render_template("ventes/ticket.html", vente=vente_demo,
                           demo=True, annulee=False)
