"""Formulaires d'administration des utilisateurs."""
from flask_wtf import FlaskForm
from wtforms import (BooleanField, PasswordField, SelectField, StringField,
                     SubmitField)
# boutique_id : affectation (obligatoire pour les caissiers)
from wtforms.validators import DataRequired, EqualTo, Length, Optional


class UtilisateurForm(FlaskForm):
    username = StringField("Nom d'utilisateur",
                           validators=[DataRequired(message="Champ obligatoire"),
                                       Length(min=3, max=50)])
    nom_complet = StringField("Nom complet",
                              validators=[DataRequired(message="Champ obligatoire"),
                                          Length(max=100)])
    role = SelectField("Rôle", choices=[
        ("caissier", "Caissier (caisse uniquement)"),
        ("gerant", "Gérant (opérationnel 3 boutiques, sans points hebdo/mensuels)"),
        ("promoteur", "Promoteur (vue et contrôle complets)"),
        ("admin", "Administrateur (tout)")])
    boutique_id = SelectField("Boutique d'affectation", coerce=int)
    actif = BooleanField("Compte actif", default=True)
    acces_rapport_journalier = BooleanField(
        "Accès au rapport des ventes journalier (concerne le gérant)",
        default=True)
    # Vide en modification = mot de passe inchangé
    password = PasswordField("Mot de passe",
                             validators=[Optional(), Length(min=8,
                                message="8 caractères minimum")])
    password2 = PasswordField("Confirmer le mot de passe",
                              validators=[EqualTo("password",
                                message="Les mots de passe ne correspondent pas")])
    submit = SubmitField("Enregistrer")
