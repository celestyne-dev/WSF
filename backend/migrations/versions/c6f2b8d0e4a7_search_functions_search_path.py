"""Pin search_path on the full-text search functions (makes backups restorable).

pg_restore runs with an empty search_path. The index on articles uses
wsf_article_search_vector(), which calls wsf_block_list_text() without a
schema prefix, so restoring any dump of this database failed at that index
("function wsf_block_list_text(jsonb) does not exist"). Pinning each
function's search_path (stored with the function and carried by pg_dump)
fixes this. Function bodies, results and the index are unchanged.

Downgrade removes the setting again.

Revision ID: c6f2b8d0e4a7
Revises: b5e1a7c9d3f6
"""
from alembic import op

revision = "c6f2b8d0e4a7"
down_revision = "b5e1a7c9d3f6"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "public.wsf_block_list_text(jsonb)",
    "public.wsf_article_search_vector(text, text, text, json)",
)


def upgrade():
    for signature in _FUNCTIONS:
        op.execute(f"ALTER FUNCTION {signature} SET search_path = public, pg_catalog")


def downgrade():
    for signature in _FUNCTIONS:
        op.execute(f"ALTER FUNCTION {signature} RESET search_path")
