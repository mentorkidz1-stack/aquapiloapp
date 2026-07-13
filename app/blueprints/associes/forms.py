"""Formulaires du blueprint associes."""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length


class AssocieLoginForm(FlaskForm):
    username = StringField(
        "Identifiant",
        validators=[DataRequired(message="Champ obligatoire"), Length(max=50)],
    )
    password = PasswordField(
        "Mot de passe",
        validators=[DataRequired(message="Champ obligatoire")],
    )
    submit = SubmitField("Se connecter")
