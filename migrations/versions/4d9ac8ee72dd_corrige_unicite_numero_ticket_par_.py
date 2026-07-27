"""corrige unicite numero_ticket : par entreprise, pas globale

Revision ID: 4d9ac8ee72dd
Revises: a9a5f9e45d5d
Create Date: 2026-07-27 00:05:01.921592

Bug corrigé : numero_ticket était unique GLOBALEMENT, alors que
prochain_numero_ticket() ne compte que les ventes DE L'ENTREPRISE
COURANTE (filtre tenant automatique). Deux entreprises clientes
différentes calculent donc légitimement le même numéro pour leur 1re
vente du jour (ex. V-20260727-0001 chacune) — la contrainte globale
bloquait alors systématiquement toutes les entreprises sauf la
première à avoir pris ce numéro ce jour-là.

L'ancienne contrainte unique sur numero_ticket seul n'a jamais été
nommée explicitement dans la migration d'origine (sa.UniqueConstraint
('numero_ticket') sans nom) : impossible à cibler par nom de façon
fiable sur SQLite (contrainte anonyme, non exposée nommée par
l'inspecteur) ni en toute confiance sur MySQL (nom par défaut variable
selon la version). On recrée donc la table par lot (batch) en pointant
explicitement sur la définition actuelle du modèle Vente, qui ne
contient plus que la nouvelle contrainte composite — la façon la plus
sûre de garantir que l'ancienne contrainte disparaît, quel que soit le
moteur.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d9ac8ee72dd'
down_revision = 'a9a5f9e45d5d'
branch_labels = None
depends_on = None


def upgrade():
    from app.models import Vente  # définition actuelle : source de vérité du recreate

    with op.batch_alter_table('ventes', schema=None,
                              copy_from=Vente.__table__,
                              recreate='always') as batch_op:
        pass


def downgrade():
    with op.batch_alter_table('ventes', schema=None) as batch_op:
        batch_op.drop_constraint('uq_ventes_entreprise_numero_ticket', type_='unique')
        batch_op.create_unique_constraint('numero_ticket', ['numero_ticket'])
