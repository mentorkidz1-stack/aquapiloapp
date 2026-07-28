"""Formulaires du blueprint auth."""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo


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


class ChangerMotDePasseForm(FlaskForm):
    mot_de_passe_actuel = PasswordField(
        "Mot de passe actuel",
        validators=[DataRequired(message="Champ obligatoire")],
    )
    nouveau_mot_de_passe = PasswordField(
        "Nouveau mot de passe",
        validators=[DataRequired(message="Champ obligatoire"),
                   Length(min=8, message="8 caractères minimum")],
    )
    confirmation = PasswordField(
        "Confirmer le nouveau mot de passe",
        validators=[DataRequired(message="Champ obligatoire"),
                   EqualTo("nouveau_mot_de_passe",
                          message="Les deux mots de passe ne correspondent pas")],
    )
    submit = SubmitField("Changer le mot de passe")
