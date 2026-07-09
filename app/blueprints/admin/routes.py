"""Blueprint admin : gestion des utilisateurs. Accès admin uniquement."""
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Boutique, User
from app.utils.decorators import role_required
from app.blueprints.admin.forms import UtilisateurForm

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/utilisateurs")
@login_required
@role_required("promoteur")
def utilisateurs():
    users = User.query.order_by(User.role, User.nom_complet).all()
    return render_template("admin/utilisateurs.html", users=users)


@admin_bp.route("/utilisateurs/nouveau", methods=["GET", "POST"])
@login_required
@role_required("promoteur")
def nouveau():
    form = UtilisateurForm()
    form.boutique_id.choices = [
        (b.id, b.nom) for b in
        Boutique.query.filter_by(actif=True).order_by(Boutique.id)]
    if form.validate_on_submit():
        if not form.password.data:
            flash("Le mot de passe est obligatoire à la création.", "danger")
        elif User.query.filter_by(username=form.username.data.strip()).first():
            flash("Ce nom d'utilisateur existe déjà.", "danger")
        else:
            u = User(username=form.username.data.strip(),
                     nom_complet=form.nom_complet.data.strip(),
                     role=form.role.data, actif=form.actif.data,
                     acces_rapport_journalier=form.acces_rapport_journalier.data,
                     boutique_id=form.boutique_id.data)
            u.set_password(form.password.data)
            db.session.add(u)
            db.session.commit()
            flash(f"Utilisateur « {u.username} » créé ({u.role}).", "success")
            return redirect(url_for("admin.utilisateurs"))
    return render_template("admin/form.html", form=form,
                           titre="Nouvel utilisateur", creation=True)


@admin_bp.route("/utilisateurs/<int:user_id>/modifier", methods=["GET", "POST"])
@login_required
@role_required("promoteur")
def modifier(user_id):
    u = db.get_or_404(User, user_id)
    form = UtilisateurForm(obj=u)
    form.boutique_id.choices = [
        (b.id, b.nom) for b in
        Boutique.query.filter_by(actif=True).order_by(Boutique.id)]
    if form.validate_on_submit():
        if u.id == current_user.id and not form.actif.data:
            flash("Impossible de désactiver votre propre compte.", "danger")
        elif (u.role == "admin" and form.role.data != "admin"
              and User.query.filter_by(role="admin", actif=True).count() <= 1):
            flash("Impossible : il doit rester au moins un administrateur actif.",
                  "danger")
        else:
            u.username = form.username.data.strip()
            u.nom_complet = form.nom_complet.data.strip()
            u.role = form.role.data
            u.actif = form.actif.data
            u.acces_rapport_journalier = form.acces_rapport_journalier.data
            u.boutique_id = form.boutique_id.data
            if form.password.data:
                u.set_password(form.password.data)
                flash("Mot de passe réinitialisé.", "info")
            db.session.commit()
            flash(f"Utilisateur « {u.username} » mis à jour.", "success")
            return redirect(url_for("admin.utilisateurs"))
    return render_template("admin/form.html", form=form,
                           titre=f"Modifier — {u.username}", creation=False)
