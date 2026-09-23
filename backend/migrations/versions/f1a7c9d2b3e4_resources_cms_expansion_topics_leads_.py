"""resources cms expansion: topics m2m, tags, images, leads, access type,
seo, file metadata, sponsor, controlled enums, description blocks

Revision ID: f1a7c9d2b3e4
Revises: 62b0aebd454c
Create Date: 2026-09-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f1a7c9d2b3e4'
down_revision = '62b0aebd454c'
branch_labels = None
depends_on = None

RESOURCE_TYPES = (
    "Guide", "Workbook", "Template", "Checklist", "Planner", "Toolkit",
    "Ebook", "Worksheet", "Report", "Download", "Video Resource", "External Resource",
)
RESOURCE_STATUSES = ("draft", "review", "scheduled", "published", "archived")
ACCESS_TYPES = ("direct_download", "email_gate", "member_only", "premium", "external_link")
FILE_FORMATS = ("PDF", "DOCX", "XLSX", "PPTX", "ZIP", "Image", "Video", "Other")


def upgrade():
    op.create_table(
        'resource_topics',
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('resource_id', 'topic_id'),
    )
    op.create_table(
        'resource_tags',
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('resource_id', 'tag_id'),
    )
    op.create_table(
        'resource_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('media_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['media_id'], ['media.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'resource_leads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('country_code', sa.String(length=10), nullable=True),
        sa.Column('newsletter_consent', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('acquisition', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['country_code'], ['countries.code']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_resource_leads_resource_id', 'resource_leads', ['resource_id'])
    op.create_index('ix_resource_leads_email', 'resource_leads', ['email'])

    # Preserve the single existing topic_id relationship as an M2M row
    # before the column is dropped.
    op.execute(
        "INSERT INTO resource_topics (resource_id, topic_id) "
        "SELECT id, topic_id FROM resources WHERE topic_id IS NOT NULL"
    )

    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('subtitle', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('short_description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('author_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('access_type', sa.String(length=20), nullable=False, server_default='direct_download'))
        batch_op.add_column(sa.Column('file_format', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('file_size', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('page_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('sponsor_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('sponsored', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('download_count', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('published_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('seo', sa.JSON(), nullable=True))
        batch_op.create_foreign_key('fk_resources_sponsor_id', 'organizations', ['sponsor_id'], ['id'])
        batch_op.drop_constraint('resources_topic_id_fkey', type_='foreignkey')
        batch_op.drop_column('topic_id')

        batch_op.create_check_constraint(
            'ck_resources_type', "type IS NULL OR type IN (" + ", ".join(f"'{t}'" for t in RESOURCE_TYPES) + ")"
        )
        batch_op.create_check_constraint(
            'ck_resources_status', "status IN (" + ", ".join(f"'{s}'" for s in RESOURCE_STATUSES) + ")"
        )
        batch_op.create_check_constraint(
            'ck_resources_access_type', "access_type IN (" + ", ".join(f"'{a}'" for a in ACCESS_TYPES) + ")"
        )
        batch_op.create_check_constraint(
            'ck_resources_file_format',
            "file_format IS NULL OR file_format IN (" + ", ".join(f"'{f}'" for f in FILE_FORMATS) + ")",
        )
        batch_op.create_check_constraint('ck_resources_price_nonnegative', 'price >= 0')
        batch_op.create_check_constraint('ck_resources_download_count_nonnegative', 'download_count >= 0')
        batch_op.create_check_constraint('ck_resources_page_count_nonnegative', 'page_count IS NULL OR page_count >= 0')
        batch_op.create_check_constraint('ck_resources_file_size_nonnegative', 'file_size IS NULL OR file_size >= 0')

    # description moves from plain Text to an ordered content-block list
    # (same shape as Article.content / Job.description / Product.description)
    # — existing plain-text descriptions are preserved as a paragraph block.
    op.execute(
        """
        ALTER TABLE resources ALTER COLUMN description TYPE JSON USING (
            CASE
                WHEN description IS NULL OR description = '' THEN '[]'::json
                ELSE json_build_array(json_build_object('type', 'paragraph', 'text', description))
            END
        )
        """
    )
    op.execute("ALTER TABLE resources ALTER COLUMN description SET DEFAULT '[]'::json")
    op.execute("ALTER TABLE resources ALTER COLUMN description SET NOT NULL")

    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.alter_column('access_type', server_default=None)
        batch_op.alter_column('sponsored', server_default=None)
        batch_op.alter_column('download_count', server_default=None)


def downgrade():
    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.drop_constraint('ck_resources_file_size_nonnegative', type_='check')
        batch_op.drop_constraint('ck_resources_page_count_nonnegative', type_='check')
        batch_op.drop_constraint('ck_resources_download_count_nonnegative', type_='check')
        batch_op.drop_constraint('ck_resources_price_nonnegative', type_='check')
        batch_op.drop_constraint('ck_resources_file_format', type_='check')
        batch_op.drop_constraint('ck_resources_access_type', type_='check')
        batch_op.drop_constraint('ck_resources_status', type_='check')
        batch_op.drop_constraint('ck_resources_type', type_='check')

    op.execute("ALTER TABLE resources ALTER COLUMN description DROP DEFAULT")
    op.execute("ALTER TABLE resources ALTER COLUMN description DROP NOT NULL")
    op.execute(
        """
        ALTER TABLE resources ALTER COLUMN description TYPE TEXT USING (
            CASE
                WHEN jsonb_array_length(description::jsonb) = 0 THEN NULL
                ELSE (description::jsonb -> 0 ->> 'text')
            END
        )
        """
    )

    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('topic_id', sa.Integer(), nullable=True))

    op.execute(
        "UPDATE resources SET topic_id = rt.topic_id FROM ("
        "SELECT DISTINCT ON (resource_id) resource_id, topic_id FROM resource_topics ORDER BY resource_id, topic_id"
        ") rt WHERE resources.id = rt.resource_id"
    )

    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.create_foreign_key('resources_topic_id_fkey', 'topics', ['topic_id'], ['id'])
        batch_op.drop_constraint('fk_resources_sponsor_id', type_='foreignkey')
        batch_op.drop_column('seo')
        batch_op.drop_column('published_date')
        batch_op.drop_column('download_count')
        batch_op.drop_column('sponsored')
        batch_op.drop_column('sponsor_id')
        batch_op.drop_column('page_count')
        batch_op.drop_column('file_size')
        batch_op.drop_column('file_format')
        batch_op.drop_column('access_type')
        batch_op.drop_column('author_name')
        batch_op.drop_column('short_description')
        batch_op.drop_column('subtitle')

    op.drop_index('ix_resource_leads_email', table_name='resource_leads')
    op.drop_index('ix_resource_leads_resource_id', table_name='resource_leads')
    op.drop_table('resource_leads')
    op.drop_table('resource_images')
    op.drop_table('resource_tags')
    op.drop_table('resource_topics')
