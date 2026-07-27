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
('numero_ticket') sans nom). Sur SQLite, l'inspecteur ne l'expose pas
avec un nom exploitable : on recrée la table par lot (batch) en
pointant sur la définition actuelle du modèle Vente, seule méthode
fiable sur ce moteur. Sur MySQL, la table est référencée par une clé
étrangère (vente_lignes.vente_id) : un DROP/CREATE de la table entière
(recreate='always') échoue avec l'erreur 3730 ("Cannot drop table
'ventes' referenced by a foreign key constraint"). MySQL nomme
correctement les index/contraintes et sait les modifier par un simple
ALTER TABLE ciblé, sans jamais recréer la table : on découvre le nom
réel via l'inspecteur puis on le supprime avant de créer la nouvelle
contrainte composite.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d9ac8ee72dd'
down_revision = 'a9a5f9e45d5d'
branch_labels = None
depends_on = None


def _noms_contrainte_numero_ticket(insp):
    noms = set()
    for uc in insp.get_unique_constraints('ventes'):
        if uc['column_names'] == ['numero_ticket']:
            noms.add(uc['name'])
    for idx in insp.get_indexes('ventes'):
        if idx.get('unique') and idx['column_names'] == ['numero_ticket']:
            noms.add(idx['name'])
    return noms


def upgrade():
    bind = op.get_bind()

    if bind.dialect.name == 'sqlite':
        from app.models import Vente  # définition actuelle : source de vérité du recreate

        with op.batch_alter_table('ventes', schema=None,
                                  copy_from=Vente.__table__,
                                  recreate='always') as batch_op:
            pass
        return

    # MySQL (et tout moteur avec ALTER TABLE natif) : pas de recréation de
    # table, juste un remplacement de contrainte en place.
    insp = sa.inspect(bind)
    for nom in _noms_contrainte_numero_ticket(insp):
        try:
            op.drop_constraint(nom, 'ventes', type_='unique')
        except Exception:
            op.drop_index(nom, table_name='ventes')
    op.create_unique_constraint(
        'uq_ventes_entreprise_numero_ticket', 'ventes',
        ['entreprise_id', 'numero_ticket'])


def downgrade():
    bind = op.get_bind()

    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('ventes', schema=None) as batch_op:
            batch_op.drop_constraint('uq_ventes_entreprise_numero_ticket', type_='unique')
            batch_op.create_unique_constraint('numero_ticket', ['numero_ticket'])
        return

    op.drop_constraint('uq_ventes_entreprise_numero_ticket', 'ventes', type_='unique')
    op.create_unique_constraint('numero_ticket', 'ventes', ['numero_ticket'])
