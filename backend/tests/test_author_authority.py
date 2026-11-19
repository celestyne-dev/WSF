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
        for label, value in (("Articles", 9), ("Career Tool", 1), ("Course", 1)):
            assert re.search(rf"<dt[^>]*>{label}</dt><dd[^>]*>{value}</dd>", root), label
        assert "Learn with Celestine" in root and "/learning/pre-course" in root
        assert "Career tools by Celestine" in root and "/resources/pre-tool" in root
        assert "Latest articles" in root
        assert len(re.findall(r'href="/pre\d"', root)) == 6  # bounded, not the archive
        assert "vault/secret.pdf" not in html

    def test_prerender_order_and_single_expertise_list(self, client, app):
        from app.models.taxonomy import Topic

        app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
        topic_id = _add(app, Topic(slug="leadership", name="Leadership", status="published"))
        aid = _author(app, headline="Career, Leadership & Future of Work", location="Nairobi")
        with app.app_context():
            from app.models.people import Author

            author = db.session.get(Author, aid)
            author.topics.append(db.session.get(Topic, topic_id))
            db.session.commit()
        _article(app, aid, "order-1")
        html = client.get("/authors/celestine").get_data(as_text=True)
        root = html.split('data-wsf-prerender="author"', 1)[1]
        positions = [root.index(s) for s in ("Celestine Nyamoita", "Future of Work", "Founder &amp; Editor", "Nairobi",
                                              'href="/topics/leadership"', ">Article</dt>")]
        assert positions == sorted(positions), positions
        assert root.count('href="/topics/leadership"') == 1


def _bootstrap(html):
    import json

    match = re.search(r'<script type="application/json" data-wsf-bootstrap="author">(.*?)</script>', html, re.S)
    return json.loads(match.group(1)) if match else None


def _portrait_media(app):
    from app.models.media import Media, MediaVariant

    with app.app_context():
        media = Media(original_filename="p.jpg", stored_filename="secret-stored-name.jpg", file_path="uploads/secret/p.jpg",
                      public_url="/media/p.jpg", mime_type="image/jpeg", width=1200, height=1500, alt_text="Celestine portrait")
        db.session.add(media)
        db.session.flush()
        for name, width in (("thumbnail", 240), ("card", 640), ("large", 1200)):
            db.session.add(MediaVariant(media_id=media.id, variant=name, file_path=f"uploads/secret/{name}.webp",
                                        public_url=f"/media/p-{name}.webp", width=width, height=int(width * 1.25)))
        db.session.commit()
        return media.id


class TestAuthorBootstrap:
    def test_bootstrap_matches_public_api_and_first_article_page(self, client, app):
        app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
        aid = _author(app, headline="Career, Leadership & Future of Work")
        for i in range(12):
            _article(app, aid, f"boot{i}", days_ago=i)
        _article(app, aid, "boot-draft", status="draft")
        _resource(app, aid, "boot-tool")
        html = client.get("/authors/celestine").get_data(as_text=True)
        boot = _bootstrap(html)
        assert boot["key"] == "celestine"
        data = boot["data"]
        api = _detail(client).get_json()["data"]
        assert data["author"] == api["author"]
        assert data["authority"]["counts"] == api["authority"]["counts"]
        assert [r["slug"] for r in data["authority"]["resources"]] == [r["slug"] for r in api["authority"]["resources"]]
        # Nested bylines are slimmed to what the cards read; nothing else differs.
        assert set(data["articles"][0]["author"]) <= {"id", "slug", "name", "role", "photo"}
        assert data["articles"][0]["author"]["name"] == "Celestine Nyamoita"
        assert set(data["authority"]["resources"][0]["author"]) <= {"id", "slug", "name", "role", "photo"}
        page1 = client.get("/api/v1/articles", query_string={"author": "celestine", "page": 1, "per_page": 9}).get_json()
        assert [a["slug"] for a in data["articles"]] == [a["slug"] for a in page1["data"]]
        assert data["meta"]["total"] == 12 and data["meta"]["total_pages"] == 2 and data["meta"]["per_page"] == 9
        assert "boot-draft" not in html

    def test_bootstrap_is_public_only(self, client, app):
        from app.models.people import Person
        from app.models.taxonomy import Topic

        app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
        pid = _add(app, Person(slug="hidden-person", name="Hidden Person Name", status="draft"))
        tid = _add(app, Topic(slug="secret-topic", name="Secret Topic Name", status="archived"))
        media_id = _portrait_media(app)
        aid = _author(app, person_id=pid, photo_media_id=media_id)
        with app.app_context():
            from app.models.people import Author

            author = db.session.get(Author, aid)
            author.topics.append(db.session.get(Topic, tid))
            db.session.commit()
        _resource(app, aid, "pub-tool")
        html = client.get("/authors/celestine").get_data(as_text=True)
        data = _bootstrap(html)["data"]
        assert data["author"]["person"] is None and data["author"]["topics"] == []
        for secret in ("Hidden Person Name", "hidden-person", "Secret Topic Name", "secret-stored-name", "uploads/secret",
                       "vault/secret.pdf", '"user_id"', '"uploaded_by_id"'):
            assert secret not in html, secret

    def test_inactive_or_unknown_author_has_no_bootstrap_and_404s(self, client, app):
        app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
        _author(app, slug="draft-only", status="draft")
        for path in ("/authors/draft-only", "/authors/nobody"):
            resp = client.get(path)
            assert resp.status_code == 404
            assert 'data-wsf-bootstrap="author"' not in resp.get_data(as_text=True)


class TestAuthorPrerenderParity:
    def test_portrait_uses_public_card_variant_and_is_preloaded(self, client, app):
        app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
        media_id = _portrait_media(app)
        _author(app, photo_media_id=media_id, headline="Career, Leadership & Future of Work")
        html = client.get("/authors/celestine").get_data(as_text=True)
        root = html.split('data-wsf-prerender="author"', 1)[1]
        img = re.search(r"<img [^>]*>", root).group(0)
        assert 'src="/media/p-card.webp"' in img and "640w" in img and "1200w" in img
        assert 'alt="Celestine portrait"' in img and "aspect-[4/5]" in img
        assert 'rel="preload"' in html and "p-card.webp" in html.split("</head>")[0]
        assert "uploads/secret" not in html

    def test_hero_parity_and_no_empty_headings(self, client, app):
        app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
        _author(app, slug="sparse", status="active")  # no photo, headline, topics, links, bio, content
        html = client.get("/authors/sparse").get_data(as_text=True)
        root = html.split('data-wsf-prerender="author"', 1)[1].split("</main>")[0]
        assert 'role="img"' in root and ">CN<" in root  # initials placeholder, not an <img>
        assert "<img" not in root
        assert 'class="border-b border-taupe-200 bg-cream"' in root
        assert 'aria-label="Breadcrumb"' in root and 'href="/authors"' in root
        for heading in ("About ", "Credentials", "Learn with", "Career tools", "Latest articles", "Sources", "Areas of expertise"):
            assert heading not in root, heading
        assert "<dl" not in root
