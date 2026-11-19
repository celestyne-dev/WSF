"""Author authority profiles: headline, derived counts, bounded authored
Resources and taught/co-taught Learning programs, publication filtering,
linked-Person privacy, prerender depth and constant query counts."""
import os
import re
from datetime import date, datetime, timedelta, timezone

import pytest

from app.extensions import db
from tests.conftest import auth_headers

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")


def _add(app, row):
    with app.app_context():
        db.session.add(row)
        db.session.commit()
        return row.id


def _author(app, slug="celestine", status="active", **extra):
    from app.models.people import Author

    return _add(app, Author(slug=slug, name="Celestine Nyamoita", role="Founder & Editor", status=status, **extra))


def _article(app, author_id, slug, status="published", days_ago=0):
    from app.models.article import Article

    return _add(app, Article(slug=slug, title=f"Article {slug}", status=status, content=[], author_id=author_id,
                             publish_date=datetime.now(timezone.utc) - timedelta(days=days_ago)))


def _resource(app, author_id, slug, status="published", access="direct_download", published=None):
    from app.models.resource import Resource

    return _add(app, Resource(slug=slug, name=f"Resource {slug}", status=status, description=[], author_id=author_id,
                              access_type=access, published_date=published or date.today(),
                              protected_file_path="vault/secret.pdf"))


def _program(app, slug, primary=None, co=(), status="published"):
    from app.models.learning import LearningProgram
    from app.models.people import Author

    with app.app_context():
        program = LearningProgram(slug=slug, title=f"Program {slug}", status=status, primary_instructor_id=primary,
                                  published_at=datetime.now(timezone.utc))
        for author_id in co:
            program.co_instructors.append(db.session.get(Author, author_id))
        db.session.add(program)
        db.session.commit()
        return program.id


def _detail(client, slug="celestine", **kw):
    return client.get(f"/api/v1/authors/{slug}", **kw)


class TestAuthorAuthority:
    def test_draft_author_404_and_active_visible(self, client, app):
        _author(app, slug="draft-author", status="draft")
        assert _detail(client, "draft-author").status_code == 404
        _author(app)
        assert _detail(client).status_code == 200

    def test_counts_and_bounded_sections(self, client, app):
        aid = _author(app, headline="Career, Leadership & Future of Work")
        other = _author(app, slug="other")
        for i in range(8):
            _article(app, aid, f"a{i}", days_ago=i)
        _article(app, aid, "draft-art", status="draft")
        for i in range(5):
            _resource(app, aid, f"r{i}")
        _resource(app, aid, "r-draft", status="draft")
        _resource(app, aid, "r-future", status="scheduled", published=date.today() + timedelta(days=9))
        _resource(app, other, "r-other")
        _program(app, "p-primary", primary=aid)
        _program(app, "p-co", primary=other, co=(aid,))
        _program(app, "p-draft", primary=aid, status="draft")
        _program(app, "p-unrelated", primary=other)
        data = _detail(client).get_json()["data"]
        assert data["author"]["headline"] == "Career, Leadership & Future of Work"
        authority = data["authority"]
        assert authority["counts"] == {"articles": 8, "resources": 5, "courses": 2}
        assert len(authority["resources"]) == 3
        assert {r["slug"] for r in authority["resources"]} <= {f"r{i}" for i in range(5)}
        assert {p["slug"] for p in authority["learningPrograms"]} == {"p-primary", "p-co"}
        body = _detail(client).get_data(as_text=True)
        assert "vault/secret.pdf" not in body and "user_id" not in body

    def test_empty_author_has_zero_counts_and_empty_lists(self, client, app):
        _author(app)
        authority = _detail(client).get_json()["data"]["authority"]
        assert authority == {"counts": {"articles": 0, "resources": 0, "courses": 0}, "resources": [], "learningPrograms": []}

    def test_article_pagination_preserved(self, client, app):
        aid = _author(app)
        for i in range(12):
            _article(app, aid, f"p{i}", days_ago=i)
        page2 = _detail(client, query_string={"page": 2, "per_page": 5}).get_json()
        assert len(page2["data"]["articles"]) == 5 and page2["meta"]["page"] == 2

    def test_linked_person_only_when_published(self, client, app):
        from app.models.people import Person

        pid = _add(app, Person(slug="celestine-person", name="Celestine", status="draft"))
        _author(app, person_id=pid)
        assert _detail(client).get_json()["data"]["author"]["person"] is None
        with app.app_context():
            db.session.get(Person, pid).status = "published"
            db.session.commit()
        assert _detail(client).get_json()["data"]["author"]["person"]["slug"] == "celestine-person"

    def test_headline_editable_and_omission_keeps_it(self, client, app):
        from app.models.user import Role, User

        payload = {"email": "auth-admin@example.com", "password": "supersecret1", "first_name": "A", "last_name": "D"}
        client.post("/api/v1/auth/register", json=payload)
        with app.app_context():
            user = User.query.filter_by(email=payload["email"]).first()
            user.roles.append(Role.query.filter_by(name="admin").first())
            db.session.commit()
        token = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"]
        created = client.post("/api/v1/authors", json={"name": "Wanjiru Kamau", "headline": "Pay & Negotiation", "shortBio": "Writes about pay.", "status": "active"}, headers=auth_headers(token))
        assert created.status_code == 201, created.get_json()
        slug = created.get_json()["data"]["slug"]
        client.put(f"/api/v1/authors/{slug}", json={"name": "Wanjiru Kamau", "shortBio": "Writes about pay.", "status": "active"}, headers=auth_headers(token))
        assert _detail(client, slug).get_json()["data"]["author"]["headline"] == "Pay & Negotiation"
        assert client.post("/api/v1/authors", json={"name": "X", "headline": "x" * 161}, headers=auth_headers(token)).status_code == 422

    def test_constant_query_count(self, client, app):
        from sqlalchemy import event

        aid = _author(app)
        other = _author(app, slug="other")

        def measure():
            statements = []
            listener = lambda *args: statements.append(args[2])  # noqa: E731
            with app.app_context():
                event.listen(db.engine, "before_cursor_execute", listener)
            try:
                assert _detail(client).status_code == 200
            finally:
                with app.app_context():
                    event.remove(db.engine, "before_cursor_execute", listener)
            return len(statements)

        measure()
        empty = measure()
        for i in range(2):
            _article(app, aid, f"s{i}")
            _resource(app, aid, f"s{i}")
            _program(app, f"s{i}", primary=aid)
        small = measure()
        for i in range(2, 9):
            _article(app, aid, f"s{i}")
            _resource(app, aid, f"s{i}")
            _program(app, f"s{i}", primary=other, co=(aid,))
        large = measure()
        assert small == large, (empty, small, large)
        assert large <= 40, (empty, small, large)


class TestAuthorPrerender:
    def test_prerender_has_bounded_authority_content(self, client, app):
        app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
        aid = _author(app, headline="Career, Leadership & Future of Work")
        for i in range(9):
            _article(app, aid, f"pre{i}", days_ago=i)
        _resource(app, aid, "pre-tool")
        _program(app, "pre-course", primary=aid)
        html = client.get("/authors/celestine").get_data(as_text=True)
        root = html.split('data-wsf-prerender="author"', 1)[1]
        assert "Career, Leadership &amp; Future of Work" in root
        assert "9 Articles" in root and "1 Career Tool" in root and "1 Course" in root
        assert "Learn with Celestine" in root and "/learning/pre-course" in root
        assert "Career tools by Celestine" in root and "/resources/pre-tool" in root
        assert "Latest articles" in root
        assert len(re.findall(r'href="/pre\d"', root)) == 6  # bounded, not the archive
        assert "vault/secret.pdf" not in html
