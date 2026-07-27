"""Blueprint operateur — espace exploitant SaaS (support, facturation,
activation des comptes), strictement séparé de l'authentification des
locataires : session dédiée (@operateur_required), jamais Flask-Login /
current_user, pour ne jamais interférer avec la résolution du tenant
courant dans app/services/tenant.py.

Toute lecture ou écriture cross-tenant passe explicitement par le
bypass sans_filtre_tenant() déjà prévu à cet effet — ce fichier ne
modifie jamais app/services/tenant.py."""
import hmac
import secrets
import string

from flask import (Blueprint, render_template, redirect, url_for, flash,
                   session, request, current_app)

from app.extensions import db, bcrypt
from app.models import Boutique, DemandeAcces, Entreprise, User
from app.models.entreprise import STATUTS_ABONNEMENT
from app.services.tenant import sans_filtre_tenant
from app.blueprints.operateur.forms import ActivationForm, OperateurLoginForm
from app.utils.decorators import operateur_required

operateur_bp = Blueprint("operateur", __name__, url_prefix="/operateur")


def _generer_mot_de_passe() -> str:
    alphabet = string.ascii_letters + string.digits
    return "-".join("".join(secrets.choice(alphabet) for _ in range(4))
                    for _ in range(3))


@operateur_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("operateur_authentifie"):
        return redirect(url_for("operateur.dashboard"))

    form = OperateurLoginForm()
    if form.validate_on_submit():
        attendu = current_app.config.get("OPERATEUR_USERNAME") or ""
        hash_attendu = current_app.config.get("OPERATEUR_PASSWORD_HASH") or ""
        fourni = form.username.data.strip()
        identifiant_ok = bool(attendu) and hmac.compare_digest(fourni, attendu)
        mdp_ok = bool(hash_attendu) and bcrypt.check_password_hash(
            hash_attendu, form.password.data)
        if identifiant_ok and mdp_ok:
            session.clear()
            session["operateur_authentifie"] = True
            session.permanent = True
            flash("Bienvenue dans l'espace opérateur.", "success")
            return redirect(url_for("operateur.dashboard"))
        flash("Identifiants opérateur incorrects.", "danger")

    return render_template("operateur/login.html", form=form)


@operateur_bp.route("/logout")
@operateur_required
def logout():
    session.pop("operateur_authentifie", None)
    flash("Déconnecté de l'espace opérateur.", "info")
    return redirect(url_for("operateur.login"))


@operateur_bp.route("/")
@operateur_required
def dashboard():
    with sans_filtre_tenant():
        entreprises = Entreprise.query.order_by(Entreprise.created_at.desc()).all()
        stats = {e.id: {"nb_boutiques": e.boutiques.count(),
                        "nb_users": e.users.count(),
                        "tarif": e.tarif_mensuel()}
                for e in entreprises}

    total_mensuel = sum(stats[e.id]["tarif"] for e in entreprises
                        if e.statut_abonnement == "actif")
    demandes_en_attente = (DemandeAcces.query.filter_by(traite=False)
                           .order_by(DemandeAcces.created_at.desc()).all())
    demandes_traitees = (DemandeAcces.query.filter_by(traite=True)
                         .order_by(DemandeAcces.created_at.desc()).limit(20).all())

    return render_template("operateur/dashboard.html",
                           entreprises=entreprises, stats=stats,
                           total_mensuel=total_mensuel,
                           demandes_en_attente=demandes_en_attente,
                           demandes_traitees=demandes_traitees,
                           statuts=STATUTS_ABONNEMENT)


@operateur_bp.route("/demandes/<int:demande_id>/activer", methods=["GET", "POST"])
@operateur_required
def activer(demande_id):
    demande = db.get_or_404(DemandeAcces, demande_id)
    if demande.traite:
        flash("Cette demande a déjà été traitée.", "warning")
        return redirect(url_for("operateur.dashboard"))

    form = ActivationForm()
    if request.method == "GET":
        form.nom_entreprise.data = demande.nom_poissonnerie
        form.responsable.data = demande.responsable
        form.nombre_boutiques.data = demande.nombre_boutiques

    if form.validate_on_submit():
        with sans_filtre_tenant():
            deja = Entreprise.query.filter_by(
                nom=form.nom_entreprise.data.strip()).first()
        if deja:
            flash("Une entreprise porte déjà ce nom.", "danger")
            return render_template("operateur/activer.html", form=form, demande=demande)

        entreprise = Entreprise(nom=form.nom_entreprise.data.strip(),
                                statut_abonnement="actif")
        db.session.add(entreprise)
        db.session.flush()

        premiere_boutique = None
        for i in range(1, form.nombre_boutiques.data + 1):
            b = Boutique(nom=f"Boutique {i}", entreprise_id=entreprise.id)
            db.session.add(b)
            if i == 1:
                premiere_boutique = b
        db.session.flush()

        mot_de_passe = _generer_mot_de_passe()
        admin = User(username=form.username_admin.data.strip(),
                    nom_complet=form.responsable.data.strip(), role="admin",
                    boutique_id=premiere_boutique.id, entreprise_id=entreprise.id)
        admin.set_password(mot_de_passe)
        db.session.add(admin)

        demande.traite = True
        db.session.commit()

        flash(f"Entreprise « {entreprise.nom} » activée avec "
              f"{form.nombre_boutiques.data} boutique(s). Identifiants à "
              f"transmettre au client — affichés une seule fois : "
              f"{admin.username} / {mot_de_passe}", "success")
        return redirect(url_for("operateur.dashboard"))

    return render_template("operateur/activer.html", form=form, demande=demande)


@operateur_bp.route("/demandes/<int:demande_id>")
@operateur_required
def detail_demande(demande_id):
    demande = db.get_or_404(DemandeAcces, demande_id)
    return render_template("operateur/demande_detail.html", demande=demande)


@operateur_bp.route("/entreprises/<int:entreprise_id>/statut", methods=["POST"])
@operateur_required
def changer_statut(entreprise_id):
    nouveau_statut = request.form.get("statut")
    if nouveau_statut not in STATUTS_ABONNEMENT:
        flash("Statut invalide.", "danger")
        return redirect(url_for("operateur.dashboard"))

    with sans_filtre_tenant():
        entreprise = db.get_or_404(Entreprise, entreprise_id)
        entreprise.statut_abonnement = nouveau_statut
        db.session.commit()
        nom = entreprise.nom

    flash(f"Statut de « {nom} » mis à jour : {nouveau_statut}.", "success")
    return redirect(url_for("operateur.dashboard"))
