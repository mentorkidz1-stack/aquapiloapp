"""Formulaires du blueprint operateur."""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange


class OperateurLoginForm(FlaskForm):
    username = StringField(
        "Identifiant opérateur",
        validators=[DataRequired(message="Champ obligatoire"), Length(max=50)],
    )
    password = PasswordField(
        "Mot de passe",
        validators=[DataRequired(message="Champ obligatoire")],
    )
    submit = SubmitField("Se connecter")


class ActivationForm(FlaskForm):
    nom_entreprise = StringField(
        "Nom de l'entreprise",
        validators=[DataRequired(message="Champ obligatoire"), Length(max=150)],
    )
    responsable = StringField(
        "Nom complet du premier compte (admin)",
        validators=[DataRequired(message="Champ obligatoire"), Length(max=100)],
    )
    username_admin = StringField(
        "Identifiant de connexion du premier compte",
        validators=[DataRequired(message="Champ obligatoire"), Length(max=50)],
    )
    nombre_boutiques = IntegerField(
        "Nombre de boutiques à créer",
        validators=[DataRequired(message="Champ obligatoire"),
                    NumberRange(min=1, max=99, message="Entre 1 et 99")],
    )
    submit = SubmitField("Activer l'entreprise")
