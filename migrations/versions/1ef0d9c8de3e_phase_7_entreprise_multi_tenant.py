"""Phase 7 : entreprise (tenant SaaS) au-dessus de boutique

Crée la table entreprises, rattache boutiques/users/produits à une
entreprise via entreprise_id, et bascule l'unicité de produits.nom
d'une contrainte globale à une contrainte par entreprise.

Backfill : toutes les données existantes sont rattachées à une entreprise
"DONA" créée automatiquement, pour que l'application actuelle continue de
fonctionner sans interruption.

Revision ID: 1ef0d9c8de3e
Revises: f1a2b3c4d5e6
Create Date: 2026-07-12
"""
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "1ef0d9c8de3e"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Table entreprises (le tenant SaaS)
    op.create_table(
        "entreprises",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nom", sa.String(length=150), nullable=False),
        sa.Column("statut_abonnement",
                  sa.Enum("essai", "actif", "suspendu", name="statut_abonnement_enum"),
                  nullable=False),
        sa.Column("date_fin_essai", sa.Date(), nullable=True),
        sa.Column("date_echeance", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("entreprises", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_entreprises_nom"), ["nom"], unique=True)

    # 2. Backfill : entreprise DONA (statut "actif" — activité déjà réelle,
    # pas un essai ; dates d'échéance à brancher plus tard avec la vraie
    # facturation)
    entreprises_table = sa.table(
        "entreprises",
        sa.column("id", sa.Integer),
        sa.column("nom", sa.String),
        sa.column("statut_abonnement", sa.String),
        sa.column("date_fin_essai", sa.Date),
        sa.column("date_echeance", sa.Date),
        sa.column("created_at", sa.DateTime),
    )
    op.bulk_insert(entreprises_table, [{
        "nom": "DONA",
        "statut_abonnement": "actif",
        "date_fin_essai": None,
        "date_echeance": None,
        "created_at": datetime.now(timezone.utc),
    }])

    # 3. entreprise_id sur boutiques / users / produits : nullable -> backfill -> NOT NULL
    for table in ("boutiques", "users", "produits"):
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

    # 4. produits.nom : unicité globale -> unicité par entreprise
    with op.batch_alter_table("produits", schema=None) as batch_op:
        batch_op.drop_index("ix_produits_nom")
        batch_op.create_index(batch_op.f("ix_produits_nom"), ["nom"], unique=False)
        batch_op.create_unique_constraint(
            "uq_produit_entreprise_nom", ["entreprise_id", "nom"])


def downgrade():
    # NB : échoue s'il existe désormais des produits de même nom dans deux
    # entreprises différentes (non applicable tant qu'un seul tenant existe).
    with op.batch_alter_table("produits", schema=None) as batch_op:
        batch_op.drop_constraint("uq_produit_entreprise_nom", type_="unique")
        batch_op.drop_index(batch_op.f("ix_produits_nom"))
        batch_op.create_index(batch_op.f("ix_produits_nom"), ["nom"], unique=True)

    for table in ("produits", "users", "boutiques"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_entreprise_id", type_="foreignkey")
            batch_op.drop_column("entreprise_id")

    with op.batch_alter_table("entreprises", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_entreprises_nom"))
    op.drop_table("entreprises")
