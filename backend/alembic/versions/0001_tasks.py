"""initial task history

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
revision="0001"; down_revision=None; branch_labels=None; depends_on=None
def upgrade():
    op.create_table("tasks", sa.Column("id",sa.String(36),primary_key=True),sa.Column("repository_url",sa.String(2048),nullable=False),sa.Column("request",sa.Text,nullable=False),sa.Column("branch",sa.String(255),nullable=False),sa.Column("status",sa.String(32),nullable=False),sa.Column("plan",sa.JSON),sa.Column("result",sa.JSON),sa.Column("error",sa.Text),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)))
    op.create_index("ix_tasks_status_created","tasks",["status","created_at"])
def downgrade(): op.drop_table("tasks")
