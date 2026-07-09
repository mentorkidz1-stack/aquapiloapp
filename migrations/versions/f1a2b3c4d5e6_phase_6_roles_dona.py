"""Phase 6 : rôles DONA (promoteur/caissier) + verrou rapport journalier.

Revision ID: f1a2b3c4d5e6
Revises: be7908de3f57
Create Date: 2026-07-02
"""
import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "be7908de3f57"
branch_labels = None
depends_on = None

ANCIEN_ENUM = sa.Enum("admin", "gerant", "employe", name="role_enum")
NOUVEL_ENUM = sa.Enum("admin", "promoteur", "gerant", "caissier",
                      name="role_enum")


def upgrade():
    # 1. Relâcher la contrainte (String) pour pouvoir convertir les valeurs
    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", existing_type=ANCIEN_ENUM,
                           type_=sa.String(20))
    # 2. Conversion : les anciens employés deviennent des caissiers
    op.execute("UPDATE users SET role='caissier' WHERE role='employe'")
    # 3. Nouvelle énumération + colonne de verrou
    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", existing_type=sa.String(20),
                           type_=NOUVEL_ENUM)
        batch.add_column(sa.Column("acces_rapport_journalier", sa.Boolean(),
                                   nullable=False, server_default=sa.true()))


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", existing_type=NOUVEL_ENUM,
                           type_=sa.String(20))
        batch.drop_column("acces_rapport_journalier")
    op.execute("UPDATE users SET role='employe' "
               "WHERE role IN ('caissier', 'promoteur')")
    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", existing_type=sa.String(20),
                           type_=ANCIEN_ENUM)
