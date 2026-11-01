"""GEO security correction — public linked-entity visibility.

A public parent may reference a draft/archived/inactive linked entity;
anonymous payloads (APIs, Saved Items, search, the server bootstrap and
prerender) must not reveal that linked entity, while parent-owned
fallback text stays and staff/CMS responses keep the full relation.
See app/services/public_visibility.py.
"""
import json
import os
import re
from datetime import date, timedelta

import pytest

from app.extensions import db
from tests.conftest import auth_headers

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")


@pytest.fixture(autouse=True)
def _fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


@pytest.fixture()
def staff(client, app):
    from app.models.user import Role, User

    payload = {"email": "visibility-admin@example.com", "password": "supersecret1", "first_name": "Vis",
               "last_name": "Admin", "country_code": "US"}
    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        user.roles.append(Role.query.filter_by(name="super_admin").first())
        db.session.commit()
    token = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"]
    return auth_headers(token)


def _add(app, *objs):
    with app.app_context():
        db.session.add_all(objs)
        db.session.commit()
        return [o.id for o in objs]


def _json(client, path, headers=None):
    resp = client.get(path, headers=headers or {})
    assert resp.status_code == 200, (path, resp.status_code)
    return resp.get_json()["data"], json.dumps(resp.get_json())


def _raw(client, path):
    resp = client.get(path)
    assert resp.status_code == 200, path
    return resp.get_data(as_text=True)


def _entities(app):
    """One public and one non-public instance of every linked type."""
    from app.models.people import Author, Organization, Person
    from app.models.taxonomy import Category, Series, Tag, Topic

    with app.app_context():
        objs = dict(
            pub_person=Person(slug="pub-person", name="Public Person", status="published"),
            draft_person=Person(slug="secret-person-slug", name="Secret Draft Person", title="Secret Draft Title", status="draft"),
            pub_org=Organization(slug="pub-org", name="Public Org", status="published", description=[]),
            draft_org=Organization(slug="secret-org-slug", name="Secret Draft Org", status="draft", description=[]),
            archived_org=Organization(slug="archived-org-slug", name="Secret Archived Org", status="archived", description=[]),
            pub_author=Author(slug="pub-author", name="Public Author", status="active"),
            inactive_author=Author(slug="secret-author-slug", name="Secret Inactive Author", status="archived"),
            pub_topic=Topic(slug="pub-topic", name="Public Topic", status="published"),
            draft_topic=Topic(slug="secret-topic-slug", name="Secret Draft Topic", status="draft"),
            pub_tag=Tag(slug="pub-tag", name="Public Tag", status="published"),
            archived_tag=Tag(slug="secret-tag-slug", name="Secret Archived Tag", status="archived"),
            pub_series=Series(slug="pub-series", name="Public Series", status="published"),
            draft_series=Series(slug="secret-series-slug", name="Secret Draft Series", status="draft"),
            draft_category=Category(slug="secret-category-slug", name="Secret Draft Category", status="archived"),
        )
        db.session.add_all(objs.values())
        db.session.commit()
        return {k: v.id for k, v in objs.items()}


SECRETS = ("Secret Draft Person", "Secret Draft Title", "secret-person-slug", "Secret Draft Org", "secret-org-slug",
           "Secret Archived Org", "archived-org-slug", "Secret Inactive Author", "secret-author-slug",
           "Secret Draft Topic", "secret-topic-slug", "Secret Archived Tag", "secret-tag-slug",
           "Secret Draft Series", "secret-series-slug", "Secret Draft Category", "secret-category-slug")


def _assert_no_secrets(text):
    for secret in SECRETS:
        assert secret not in text, secret


def _get(app, model, entity_id):
    return db.session.get(model, entity_id)


# --- Author --------------------------------------------------------------------------------


def test_author_topics_public_vs_staff(client, app, staff):
    from app.models.people import Author
    from app.models.taxonomy import Topic

    ids = _entities(app)
    with app.app_context():
        author = Author(slug="amara", name="Amara Otieno", status="active", bio=[{"type": "paragraph", "text": "Bio."}])
        author.topics = [db.session.get(Topic, ids["pub_topic"]), db.session.get(Topic, ids["draft_topic"])]
        db.session.add(author)
        db.session.commit()

    data, text = _json(client, "/api/v1/authors/amara")
    assert [t["slug"] for t in data["author"]["topics"]] == ["pub-topic"]
    _assert_no_secrets(text)
    items, list_text = _json(client, "/api/v1/authors")
    assert [t["slug"] for t in items[0]["topics"]] == ["pub-topic"]
    _assert_no_secrets(list_text)
    _assert_no_secrets(_raw(client, "/authors/amara"))
    # Staff keep the draft Topic for editing.
    staff_data, _ = _json(client, "/api/v1/authors/amara", staff)
    assert sorted(t["slug"] for t in staff_data["author"]["topics"]) == ["pub-topic", "secret-topic-slug"]


# --- Event -----------------------------------------------------------------------------------


def test_event_linked_person_organizer_sponsor(client, app, staff):
    from app.models.opportunity import Event, EventSpeaker, EventSponsor

    ids = _entities(app)
    with app.app_context():
        event = Event(slug="summit", title="WSF Summit", status="published", date=date.today() + timedelta(days=30),
                      organizer_id=ids["draft_org"], organizer_name="WSF Events Team",
                      description=[{"type": "paragraph", "text": "Summit body."}])
        db.session.add(event)
        db.session.flush()
        db.session.add_all([
            EventSpeaker(event_id=event.id, person_id=ids["draft_person"], name="Fallback Speaker", title="Fallback Title", position=0),
            EventSpeaker(event_id=event.id, person_id=ids["pub_person"], position=1),
            EventSponsor(event_id=event.id, organization_id=ids["archived_org"]),
            EventSponsor(event_id=event.id, organization_id=ids["pub_org"]),
        ])
        db.session.commit()

    data, text = _json(client, "/api/v1/events/summit")
    assert data["organizer"] is None and data["organizer_name"] == "WSF Events Team"
    speakers = sorted(data["speakers"], key=lambda s: s["position"])
    assert speakers[0]["person"] is None and speakers[0]["name"] == "Fallback Speaker"
    assert speakers[1]["person"]["slug"] == "pub-person"
    sponsors = {(s["organization"] or {}).get("slug") for s in data["sponsors"]}
    assert sponsors == {None, "pub-org"}
    _assert_no_secrets(text)
    _, list_text = _json(client, "/api/v1/events")
    _assert_no_secrets(list_text)

    html = _raw(client, "/events/summit")
    _assert_no_secrets(html)
    assert "WSF Events Team" in html and "Fallback Speaker" in html and "Public Person" in html

    # Staff/CMS keep the draft linked entities.
    staff_data, staff_text = _json(client, "/api/v1/events/summit", staff)
    assert staff_data["organizer"]["slug"] == "secret-org-slug"
    assert "Secret Draft Person" in staff_text


def test_event_virtual_link_still_withheld_from_anonymous(client, app):
    from app.models.opportunity import Event

    _add(app, Event(slug="online", title="Online Event", status="published", date=date.today() + timedelta(days=5),
                    format="virtual", virtual_link="https://zoom.example.com/PRIVATE-LINK", virtual_link_public=False))
    data, text = _json(client, "/api/v1/events/online")
    assert data["virtual_link"] is None and "PRIVATE-LINK" not in text


# --- Job / Opportunity --------------------------------------------------------------------------


def test_job_draft_organization_hidden_company_name_kept(client, app, staff):
    from app.models.opportunity import Job

    ids = _entities(app)
    _add(app, Job(slug="draft-org-job", title="Role A", company_name="Kaziwave Fallback", status="published", organization_id=ids["draft_org"]),
         Job(slug="pub-org-job", title="Role B", company_name="Public Co", status="published", organization_id=ids["pub_org"]))
    data, text = _json(client, "/api/v1/jobs/draft-org-job")
    assert data["organization"] is None and data["company_name"] == "Kaziwave Fallback"
    _assert_no_secrets(text)
    assert _json(client, "/api/v1/jobs/pub-org-job")[0]["organization"]["slug"] == "pub-org"
    _, list_text = _json(client, "/api/v1/jobs")
    _assert_no_secrets(list_text)
    html = _raw(client, "/jobs/draft-org-job")
    _assert_no_secrets(html)
    assert "Kaziwave Fallback" in html


def test_opportunity_draft_org_and_topic_hidden(client, app):
    from app.models.opportunity import Opportunity
    from app.models.taxonomy import Topic

    ids = _entities(app)
    with app.app_context():
        opp = Opportunity(slug="grant", title="Grant", status="published", organization_id=ids["draft_org"], organization_name="Fallback Fund")
        opp.topics = [db.session.get(Topic, ids["pub_topic"]), db.session.get(Topic, ids["draft_topic"])]
        db.session.add(opp)
        db.session.commit()
    data, text = _json(client, "/api/v1/opportunities/grant")
    assert data["organization"] is None and data["organization_name"] == "Fallback Fund"
    assert [t["slug"] for t in data["topics"]] == ["pub-topic"]
    _assert_no_secrets(text)
    _assert_no_secrets(_json(client, "/api/v1/opportunities")[1])
    html = _raw(client, "/opportunities/grant")
    _assert_no_secrets(html)
    assert "Fallback Fund" in html


# --- Resource ------------------------------------------------------------------------------------


def test_resource_author_sponsor_taxonomy_hidden(client, app, staff):
    from app.models.resource import Resource
    from app.models.taxonomy import Tag, Topic

    ids = _entities(app)
    with app.app_context():
        resource = Resource(slug="kit", name="Kit", status="published", access_type="direct_download",
                            author_id=ids["inactive_author"], author_name="Fallback Author Name", sponsor_id=ids["draft_org"],
                            file_url="https://files.example.com/PROTECTED-FILE.pdf")
        resource.topics = [db.session.get(Topic, ids["pub_topic"]), db.session.get(Topic, ids["draft_topic"])]
        resource.tags = [db.session.get(Tag, ids["pub_tag"]), db.session.get(Tag, ids["archived_tag"])]
        db.session.add(resource)
        db.session.commit()
    data, text = _json(client, "/api/v1/resources/kit")
    assert data["author"] is None and data["authorName"] == "Fallback Author Name"
    assert data["sponsor"] is None
    assert [t["slug"] for t in data["topics"]] == ["pub-topic"]
    assert [t["slug"] for t in data["tags"]] == ["pub-tag"]
    _assert_no_secrets(text)
    _assert_no_secrets(_json(client, "/api/v1/resources")[1])
    html = _raw(client, "/resources/kit")
    _assert_no_secrets(html)
    assert "Fallback Author Name" in html and 'href="/authors/' not in html
    assert "PROTECTED-FILE" not in html and "PROTECTED-FILE" not in text


# --- Article (audit confirmed the leak) ----------------------------------------------------------------


def test_article_public_payload_and_bootstrap_drop_nonpublic_relations(client, app, staff):
    from app.models.article import Article
    from app.models.people import Author, Organization, Person
    from app.models.taxonomy import Series, Tag, Topic

    ids = _entities(app)
    with app.app_context():
        draft_related = Article(slug="secret-related-article", title="Secret Draft Related Article", status="draft",
                                author_id=ids["pub_author"], content=[])
        article = Article(slug="story", title="Story", status="published", author_id=ids["pub_author"],
                          content=[{"type": "paragraph", "text": "Body."}], category_id=ids["draft_category"], series_id=ids["draft_series"])
        db.session.add_all([draft_related, article])
        db.session.flush()
        article.topics = [db.session.get(Topic, ids["pub_topic"]), db.session.get(Topic, ids["draft_topic"])]
        article.tags = [db.session.get(Tag, ids["pub_tag"]), db.session.get(Tag, ids["archived_tag"])]
        article.related_people = [db.session.get(Person, ids["pub_person"]), db.session.get(Person, ids["draft_person"])]
        article.related_organizations = [db.session.get(Organization, ids["pub_org"]), db.session.get(Organization, ids["archived_org"])]
        article.related_articles = [draft_related]
        public_person = db.session.get(Person, ids["pub_person"])
        public_person.series = [db.session.get(Series, ids["pub_series"]), db.session.get(Series, ids["draft_series"])]
        db.session.get(Author, ids["pub_author"]).topics = [db.session.get(Topic, ids["draft_topic"])]
        db.session.commit()

    data, text = _json(client, "/api/v1/articles/story")
    assert data["category"] is None and data["series"] is None
    assert [t["slug"] for t in data["topics"]] == ["pub-topic"]
    assert [t["slug"] for t in data["tags"]] == ["pub-tag"]
    assert [p["slug"] for p in data["related_people"]] == ["pub-person"]
    assert [s["slug"] for s in data["related_people"][0]["series"]] == ["pub-series"]
    assert [o["slug"] for o in data["related_organizations"]] == ["pub-org"]
    assert data["related_articles"] == []
    assert data["author"]["slug"] == "pub-author" and data["author"]["topics"] == []
    _assert_no_secrets(text)
    assert "Secret Draft Related Article" not in text
    _assert_no_secrets(_json(client, "/api/v1/articles")[1])

    html = _raw(client, "/story")  # bootstrap + prerender + JSON-LD
    _assert_no_secrets(html)
    assert "Secret Draft Related Article" not in html

    # The staff editor keeps every draft relationship.
    staff_data, staff_text = _json(client, "/api/v1/articles/story", staff)
    assert sorted(p["slug"] for p in staff_data["related_people"]) == ["pub-person", "secret-person-slug"]
    assert staff_data["series"]["slug"] == "secret-series-slug"


# --- Person / Learning (audit found the API leak) ----------------------------------------------------------


def test_person_public_series_filtered_staff_keeps(client, app, staff):
    from app.models.people import Person
    from app.models.taxonomy import Series

    ids = _entities(app)
    with app.app_context():
        person = db.session.get(Person, ids["pub_person"])
        person.series = [db.session.get(Series, ids["pub_series"]), db.session.get(Series, ids["draft_series"])]
        db.session.commit()
    data, text = _json(client, "/api/v1/people/pub-person")
    assert [s["slug"] for s in data["series"]] == ["pub-series"]
    _assert_no_secrets(text)
    _assert_no_secrets(_json(client, "/api/v1/people")[1])
    staff_data, _ = _json(client, "/api/v1/people/pub-person", staff)
    assert sorted(s["slug"] for s in staff_data["series"]) == ["pub-series", "secret-series-slug"]


def test_learning_public_instructor_provider_topics_filtered(client, app):
    from app.models.learning import LearningProgram
    from app.models.people import Author
    from app.models.taxonomy import Topic

    ids = _entities(app)
    with app.app_context():
        program = LearningProgram(slug="course", title="Course", status="published", access_type="free", overview=[],
                                  primary_instructor_id=ids["inactive_author"], provider_organization_id=ids["draft_org"])
        program.co_instructors = [db.session.get(Author, ids["pub_author"])]
        program.topics = [db.session.get(Topic, ids["pub_topic"]), db.session.get(Topic, ids["draft_topic"])]
        db.session.add(program)
        db.session.commit()
    data, text = _json(client, "/api/v1/learning/course")
    assert data["primary_instructor"] is None and data["provider_organization"] is None
    assert [a["slug"] for a in data["co_instructors"]] == ["pub-author"]
    assert [t["slug"] for t in data["topics"]] == ["pub-topic"]
    _assert_no_secrets(text)
    _assert_no_secrets(_json(client, "/api/v1/learning")[1])
    _assert_no_secrets(_raw(client, "/learning/course"))


# --- Saved Items / Search -----------------------------------------------------------------------------


def test_saved_item_fetchers_use_public_filtering(app):
    from app.models.opportunity import Event, Job
    from app.services.saved_items import fetch_public_content

    ids = _entities(app)
    job_id, event_id = _add(
        app,
        Job(slug="saved-job", title="Saved Job", company_name="Fallback Co", status="published", organization_id=ids["draft_org"]),
        Event(slug="saved-event", title="Saved Event", status="published", date=date.today() + timedelta(days=3), organizer_id=ids["draft_org"]),
    )
    with app.app_context():
        for content_type, content_id in (("job", job_id), ("event", event_id)):
            _assert_no_secrets(json.dumps(fetch_public_content(content_type, content_id), default=str))


def test_search_does_not_surface_unpublished_linked_names(client, app):
    from app.models.opportunity import Event
    from app.models.people import Person

    ids = _entities(app)
    _add(app, Event(slug="searchable-event", title="Searchable Summit", status="published",
                    date=date.today() + timedelta(days=3), organizer_id=ids["draft_org"], organizer_name="Fallback Organizer"))
    with app.app_context():
        db.session.get(Person, ids["pub_person"]).organization_id = ids["draft_org"]
        db.session.commit()
    for term in ("Searchable", "Public Person", "Secret Draft Org"):
        resp = client.get("/api/v1/search", query_string={"q": term})
        assert resp.status_code == 200
        # The response echoes `query`; only the results must stay clean.
        results = resp.get_json()["data"]["results"]
        _assert_no_secrets(json.dumps(results))
        if term == "Secret Draft Org":
            assert results == []  # a draft linked name is not a search hit
