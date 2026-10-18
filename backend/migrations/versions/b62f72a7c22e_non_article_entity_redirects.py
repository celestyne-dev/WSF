"""non article entity redirects

Revision ID: b62f72a7c22e
Revises: 4082ec5bec43
Create Date: 2026-10-18 08:57:36.650931

WSF SEO Phase 2B: one new table, entity_redirects, generalizing the
existing Article Redirect pattern (see app/models/article.py's Redirect
and app/models/entity_redirect.py's own docstring for why this is a
separate table rather than a reuse of that one) to the 8 non-Article
public, slug-addressed, nested-route entity types: Topic, Series,
Person, Author, Opportunity, Job, Resource, Event. Additive only — no
other schema changes, no data migration or backfill (no old non-Article
slug history was ever stored, so there is nothing to backfill). Never
touches the existing `redirects` table or its data.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b62f72a7c22e'
down_revision = '4082ec5bec43'
branch_labels = None
depends_on = None

ENTITY_REDIRECT_TYPES = ("topic", "series", "person", "author", "opportunity", "job", "resource", "event")


def upgrade():
    op.create_table(
        'entity_redirects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=20), nullable=False),
        sa.Column('from_slug', sa.String(length=220), nullable=False),
        sa.Column('to_slug', sa.String(length=220), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "entity_type IN (" + ", ".join(f"'{t}'" for t in ENTITY_REDIRECT_TYPES) + ")",
            name='ck_entity_redirects_entity_type',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'from_slug', name='uq_entity_redirects_type_from_slug'),
    )


def downgrade():
    op.drop_table('entity_redirects')
