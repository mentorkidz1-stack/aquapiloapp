"""Formulaires du blueprint main."""
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length, Email, NumberRange


class DemandeAccesForm(FlaskForm):
    nom_poissonnerie = StringField(
        "Nom de la poissonnerie",
        validators=[DataRequired(message="Champ obligatoire"), Length(max=150)],
    )
    responsable = StringField(
        "Nom du responsable",
        validators=[DataRequired(message="Champ obligatoire"), Length(max=100)],
    )
    telephone = StringField(
        "Téléphone",
        validators=[DataRequired(message="Champ obligatoire"), Length(max=30)],
    )
    email = StringField(
        "Email",
        validators=[DataRequired(message="Champ obligatoire"),
                    Email(message="Adresse email invalide"), Length(max=120)],
    )
    nombre_boutiques = IntegerField(
        "Nombre de boutiques",
        validators=[DataRequired(message="Champ obligatoire"),
                    NumberRange(min=1, max=99, message="Entre 1 et 99")],
    )
    submit = SubmitField("Demander l'accès")
