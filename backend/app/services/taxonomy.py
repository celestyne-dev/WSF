from sqlalchemy import func

from app.extensions import db
from app.utils.responses import ApiError

# Every association table (and FK column) that points at a Topic, so usage
# counts and safe-delete checks stay accurate as new content types add a
# Topic relationship. Extend this tuple, not ad-hoc queries elsewhere.
_TOPIC_LINK_TABLES = (
    ("article_topics", "topic_id"),
    ("resource_topics", "topic_id"),
    ("opportunity_topics", "topic_id"),
    ("author_topics", "topic_id"),
    ("member_topics", "topic_id"),
    ("submission_topics", "topic_id"),
    ("newsletter_subscriber_topics", "topic_id"),
    ("nomination_topics", "topic_id"),
    ("mentorship_program_topics", "topic_id"),
    ("mentorship_application_topics", "topic_id"),
)

_TAG_LINK_TABLES = (
    ("article_tags", "tag_id"),
    ("resource_tags", "tag_id"),
)

# Series is referenced both by a direct FK (Article/StorySubmission/
# Nomination) and one M2M (Person.series via person_series).
_SERIES_FK_TABLES = (
    ("articles", "series_id"),
    ("story_submissions", "series_id"),
    ("nominations", "series_id"),
)
_SERIES_LINK_TABLES = (("person_series", "series_id"),)

# Category has exactly one referrer today: Article.category_id.
_CATEGORY_FK_TABLES = (("articles", "category_id"),)


def _counts_from_link_tables(link_tables, ids=None):
    """One grouped COUNT query per association table — never one query per
    row — then summed in Python. Returns {id: count} with every requested
    id present (0 if unused).
    """
    totals = {i: 0 for i in ids} if ids is not None else {}
    for table_name, fk_column in link_tables:
        table = db.metadata.tables[table_name]
        column = table.c[fk_column]
        query = db.session.query(column, func.count().label("n")).group_by(column)
        if ids is not None:
            query = query.filter(column.in_(ids))
        for row_id, count in query.all():
            totals[row_id] = totals.get(row_id, 0) + count
    return totals


def _counts_from_fk_tables(fk_tables, ids=None):
    totals = {i: 0 for i in ids} if ids is not None else {}
    for table_name, fk_column in fk_tables:
        table = db.metadata.tables[table_name]
        column = table.c[fk_column]
        query = db.session.query(column, func.count().label("n")).filter(column.isnot(None)).group_by(column)
        if ids is not None:
            query = query.filter(column.in_(ids))
        for row_id, count in query.all():
            totals[row_id] = totals.get(row_id, 0) + count
    return totals


def topic_usage_counts(topic_ids=None):
    return _counts_from_link_tables(_TOPIC_LINK_TABLES, topic_ids)


def tag_usage_counts(tag_ids=None):
    return _counts_from_link_tables(_TAG_LINK_TABLES, tag_ids)


def series_usage_counts(series_ids=None):
    fk_totals = _counts_from_fk_tables(_SERIES_FK_TABLES, series_ids)
    link_totals = _counts_from_link_tables(_SERIES_LINK_TABLES, series_ids)
    merged = dict(fk_totals)
    for k, v in link_totals.items():
        merged[k] = merged.get(k, 0) + v
    return merged


def category_usage_counts(category_ids=None):
    return _counts_from_fk_tables(_CATEGORY_FK_TABLES, category_ids)


def find_duplicate_name(model, name, exclude_id=None):
    """Case-insensitive exact-name match — catches "Leadership" vs.
    "leadership", which generate_unique_slug's suffix behavior does not
    prevent (it would just mint a new "leadership-2" row). Whitespace-
    normalized so "Leadership " isn't a way around it either.
    """
    normalized = " ".join(name.strip().split())
    if not normalized:
        return None
    query = model.query.filter(func.lower(model.name) == normalized.lower())
    if exclude_id is not None:
        query = query.filter(model.id != exclude_id)
    return query.first()


def merge_tags(from_tag, to_tag):
    """Move every Article/Resource relationship from `from_tag` onto
    `to_tag`, skipping rows that would duplicate an existing association,
    then delete `from_tag`. Transactional — caller commits.
    """
    from app.models.article import Article
    from app.models.resource import Resource

    if from_tag.id == to_tag.id:
        raise ApiError("Cannot merge a tag into itself.", 400, code="invalid_merge")

    for article in Article.query.filter(Article.tags.any(id=from_tag.id)).all():
        article.tags.remove(from_tag)
        if to_tag not in article.tags:
            article.tags.append(to_tag)

    for resource in Resource.query.filter(Resource.tags.any(id=from_tag.id)).all():
        resource.tags.remove(from_tag)
        if to_tag not in resource.tags:
            resource.tags.append(to_tag)

    db.session.delete(from_tag)
