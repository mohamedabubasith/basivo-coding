"""add_github_fields_to_projects

Revision ID: b2c3d4e5f6a7
Revises: 709a457f7dbd
Create Date: 2026-02-28 14:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = '709a457f7dbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('github_repo_url', sa.String(length=2048), nullable=True))
    op.add_column('projects', sa.Column('github_token_encrypted', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'github_token_encrypted')
    op.drop_column('projects', 'github_repo_url')
