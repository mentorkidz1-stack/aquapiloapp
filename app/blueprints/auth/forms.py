"""Formulaires du blueprint auth."""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length


class LoginForm(FlaskForm):
    username = StringField(
        "Nom d'utilisateur",
        validators=[DataRequired(message="Champ obligatoire"), Length(max=50)],
    )
    password = PasswordField(
        "Mot de passe",
        validators=[DataRequired(message="Champ obligatoire")],
    )
    remember = BooleanField("Se souvenir de moi")
    submit = SubmitField("Se connecter")
