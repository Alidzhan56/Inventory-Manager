from alembic import op
import sqlalchemy as sa


revision = "45b0e7c7a8d5"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("email_verified_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("verification_sent_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("verification_sent_at")
        batch_op.drop_column("email_verified_at")
        batch_op.drop_column("email_verified")