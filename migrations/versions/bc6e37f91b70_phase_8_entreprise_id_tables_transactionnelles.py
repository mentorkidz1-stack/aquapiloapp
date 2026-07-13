"""Phase 8 : entreprise_id sur les tables transactionnelles

Étend le rattachement entreprise (posé en phase 7 sur boutiques/users/
produits) aux tables ventes, achats, pertes, stocks_journaliers, clotures
et audit_log. Nécessaire pour que le mécanisme d'isolation multi-tenant
(chantier 2) puisse filtrer chaque modèle directement, sans dépendre d'une
jointure indirecte via boutique_id.

Backfill : toutes les lignes existantes sont rattachées à l'entreprise
"DONA" (créée en phase 7), pour que l'application actuelle continue de
fonctionner sans interruption.

Revision ID: bc6e37f91b70
Revises: 1ef0d9c8de3e
Create Date: 2026-07-12
"""
import sqlalchemy as sa
from alembic import op

revision = "bc6e37f91b70"
down_revision = "1ef0d9c8de3e"
branch_labels = None
depends_on = None

TABLES = ("ventes", "achats", "pertes", "stocks_journaliers", "clotures", "audit_log")


def upgrade():
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("entreprise_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                f"fk_{table}_entreprise_id", "entreprises", ["entreprise_id"], ["id"])

        op.execute(
            f"UPDATE {table} SET entreprise_id = "
            "(SELECT id FROM entreprises WHERE nom = 'DONA')"
        )

        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column("entreprise_id", existing_type=sa.Integer(),
                                  nullable=False)


def downgrade():
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_entreprise_id", type_="foreignkey")
            batch_op.drop_column("entreprise_id")
