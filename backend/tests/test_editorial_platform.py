"""Editorial platform: FIRST PLACEMENT WINS on every page, the editorial
homepage modules, Topic hubs, Article provenance, WSF Weekly settings,
community stories and goal-based Handpicked."""
import json
import os
import re
from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
from tests.conftest import auth_headers

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")
NOW = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def _fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


def _token(client, app, email="ed-admin@example.com", role="admin"):
    from app.models.user import Role, User

    payload = {"email": email, "password": "supersecret1", "first_name": "A", "last_name": "B"}
    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if role:
            user.roles.append(Role.query.filter_by(name=role).first())
        db.session.commit()
    return client.post("/api/v1/auth/login", json={"email": email, "password": "supersecret1"}).get_json()["data"]["access_token"]


@pytest.fixture()
def admin(client, app):
    return auth_headers(_token(client, app))


def _seed(app, n=10, topic_slugs=("careers",), series_slug=None):
    """n published Articles, newest first (a-1 is the newest)."""
    from app.models.article import Article
    from app.models.people import Author
    from app.models.taxonomy import Series, Topic

    with app.app_context():
        author = Author.query.filter_by(slug="ed-author").first() or Author(slug="ed-author", name="Ed Author", status="active")
        db.session.add(author)
        topics = []
        for slug in topic_slugs:
            topic = Topic.query.filter_by(slug=slug).first() or Topic(slug=slug, name=slug.title(), status="published")
            db.session.add(topic)
            topics.append(topic)
        series = None
        if series_slug:
            series = Series.query.filter_by(slug=series_slug).first() or Series(slug=series_slug, name="S", status="published")
            db.session.add(series)
        db.session.flush()
        for i in range(1, n + 1):
            db.session.add(Article(slug=f"a-{i}", title=f"Story {i}", status="published", author_id=author.id, excerpt="E.",
                                   content=[], publish_date=NOW - timedelta(hours=i), topics=list(topics),
                                   series_id=series.id if series else None))
        db.session.commit()


def _modules(app, *specs):
    from app.models.cms import HomepageModule

    with app.app_context():
        ids = []
        for order, (type_, config, extra) in enumerate(specs):
            row = HomepageModule(type=type_, enabled=True, sort_order=order, config=config, **extra)
            db.session.add(row)
            db.session.flush()
            ids.append(row.id)
        db.session.commit()
        return ids


def _public(client):
    return client.get("/api/v1/public/homepage").get_json()["data"]


def _slugs(module):
    data = module.get("initial_data") or {}
    out = []
    if data.get("lead"):
        out.append(data["lead"]["slug"])
    for key in ("secondary", "articles"):
        out += [a["slug"] for a in data.get(key) or []]
    out += [a["slug"] for a in (module.get("resolved") or {}).get("items") or [] if module.get("type") == "content_collection"]
    return out


def _all_slugs(modules):
    return [s for m in modules for s in _slugs(m)]


# --- homepage: first placement wins -----------------------------------------------------------------


def test_hero_and_featured_same_article_featured_skips_it(client, app):
    _seed(app, 6)
    _modules(app, ("hero", {"leadArticleSlug": "a-3", "secondaryArticleSlugs": ["a-4"]}, {}),
             ("featured_stories", {"articleSlugs": ["a-3", "a-5", "a-4", "a-6"]}, {"heading": "F"}))
    hero, featured = _public(client)
    assert _slugs(hero) == ["a-3", "a-4"]
    assert _slugs(featured) == ["a-5", "a-6"]  # editor order kept, earlier placements skipped, nothing repeated


def test_latest_series_and_topic_skip_everything_above_and_backfill(client, app):
    _seed(app, 14, series_slug="sx")
    _modules(app, ("hero", {"leadArticleSlug": "a-1", "secondaryArticleSlugs": ["a-2"]}, {}),
             ("featured_stories", {"articleSlugs": ["a-3"]}, {}),
             ("latest_stories", {"itemCount": 4}, {}),
             ("series_feature", {"seriesSlug": "sx", "itemCount": 3}, {}),
             ("topic_collection", {"topicSlug": "careers", "itemCount": 3}, {}))
    modules = _public(client)
    latest, series, topic = modules[2], modules[3], modules[4]
    # Latest needs 4: the 3 newest are already placed, so it backfills with the next 4.
    assert _slugs(latest) == ["a-4", "a-5", "a-6", "a-7"]
    assert _slugs(series) == ["a-8", "a-9", "a-10"]
    assert _slugs(topic) == ["a-11", "a-12", "a-13"]
    everything = _all_slugs(modules)
    assert len(everything) == len(set(everything))


def test_insufficient_unique_content_renders_fewer_and_empty_is_omitted(client, app):
    _seed(app, 3)
    _modules(app, ("latest_stories", {"itemCount": 2}, {}), ("latest_stories", {"itemCount": 4}, {}),
             ("latest_stories", {"itemCount": 4}, {}))
    first, second, third = _public(client)
    assert _slugs(first) == ["a-1", "a-2"] and _slugs(second) == ["a-3"] and _slugs(third) == []
    html = client.get("/").get_data(as_text=True)
    root = html.split('data-wsf-prerender="home"', 1)[1].split("</main>", 1)[0]
    assert root.count("Fresh this week") == 2  # the empty third section is not rendered


def test_module_order_is_priority(client, app):
    from app.models.cms import HomepageModule

    _seed(app, 4)
    ids = _modules(app, ("featured_stories", {"articleSlugs": ["a-1"]}, {}), ("latest_stories", {"itemCount": 1}, {}))
    assert [_slugs(m) for m in _public(client)] == [["a-1"], ["a-2"]]
    with app.app_context():  # editor moves Latest above Featured
        db.session.get(HomepageModule, ids[0]).sort_order = 5
        db.session.commit()
    assert [_slugs(m) for m in _public(client)] == [["a-1"], []]  # Latest now takes a-1; Featured's only pick is skipped


def test_content_collection_articles_take_part(client, app):
    _seed(app, 5)
    _modules(app, ("latest_stories", {"itemCount": 2}, {}),
             ("content_collection", {"entityType": "articles", "layout": "grid", "itemCount": 2, "sort": "latest", "filters": {}},
              {"selection_mode": "automatic"}))
    latest, collection = _public(client)
    assert _slugs(collection) == ["a-3", "a-4"]


def test_server_bootstrap_api_and_prerender_agree(client, app):
    _seed(app, 8)
    _modules(app, ("hero", {"leadArticleSlug": "a-2"}, {}), ("latest_stories", {"itemCount": 4}, {}),
             ("career_moves", {"source": "topic", "topicSlugs": ["careers"], "itemCount": 2}, {"heading": "Career Moves"}))
    api = _public(client)
    html = client.get("/").get_data(as_text=True)
    boot = json.loads(re.search(r'data-wsf-bootstrap="homepage">(.*?)</script>', html, re.S).group(1))
    assert [_slugs(m) for m in boot["modules"]] == [_slugs(m) for m in api]
    root = html.split('data-wsf-prerender="home"', 1)[1].split("</main>", 1)[0]
    for slug in _all_slugs(api):
        # every placed story appears in exactly one card (image link + title link)
        assert root.count(f'href="/{slug}"') == 2, slug
    assert len(set(_all_slugs(api))) == len(_all_slugs(api)) == 7


def test_studio_warns_about_explicit_duplicates_without_blocking(client, app, admin):
    _seed(app, 3)
    resp = client.put("/api/v1/admin/homepage", headers=admin, json={"modules": [
        {"type": "hero", "config": {"leadArticleSlug": "a-1"}},
        {"type": "featured_stories", "heading": "F", "config": {"articleSlugs": ["a-1", "a-2"]}},
        {"type": "career_moves", "heading": "C", "config": {"source": "manual", "articleSlugs": ["a-2"]}},
    ]})
    assert resp.status_code == 200
    rows = client.get("/api/v1/admin/homepage", headers=admin).get_json()["data"]
    featured, moves = rows[1], rows[2]
    assert any('"a-1" is already used earlier in Hero. It will be skipped here' in w for w in featured["warnings"])
    assert any('"a-2" is already used earlier in Featured Stories' in w for w in moves["warnings"])


# --- editorial module validation --------------------------------------------------------------------


@pytest.mark.parametrize("module,error", [
    ({"type": "career_moves", "config": {"source": "series", "seriesSlug": "x"}}, "source can be"),
    ({"type": "career_moves", "config": {"source": "manual", "articleSlugs": []}}, "Pick at least one"),
    ({"type": "career_moves", "config": {"source": "topic", "topicSlugs": ["nope"]}}, "don't exist"),
    ({"type": "handpicked", "config": {"itemCount": 20}}, "between 1 and 8"),
    ({"type": "jobs", "config": {"sort": "random"}}, "Jobs can be ordered by"),
    ({"type": "opportunities", "config": {"sort": "random"}}, "Opportunities can show"),
    ({"type": "mission", "heading": "M", "config": {"body": "<script>x</script>"}}, "plain text"),
])
def test_editorial_module_config_is_validated(client, app, admin, module, error):
    resp = client.put("/api/v1/admin/homepage", headers=admin, json={"modules": [module]})
    assert resp.status_code == 422 and error in json.dumps(resp.get_json())


def test_editorial_modules_round_trip_and_public_config_hides_picks(client, app, admin):
    _seed(app, 3)
    resp = client.put("/api/v1/admin/homepage", headers=admin, json={"modules": [
        {"type": "right_now", "heading": "Right now", "config": {"source": "manual", "articleSlugs": ["a-1"], "junk": 1}},
        {"type": "mission", "heading": "We believe…", "ctaLabel": "About WSF", "ctaUrl": "/about",
         "config": {"eyebrow": "Our mission", "body": "Para one.\n\nPara two."}},
    ]})
    assert resp.status_code == 200, resp.get_json()
    rows = client.get("/api/v1/admin/homepage", headers=admin).get_json()["data"]
    assert rows[0]["config"] == {"source": "manual", "eyebrow": None, "itemCount": 3, "articleSlugs": ["a-1"]}
    public = _public(client)
    assert "articleSlugs" not in public[0]["config"] and _slugs(public[0]) == ["a-1"]
    html = client.get("/").get_data(as_text=True)
    assert "We believe…" in html and "Para two." in html and 'href="/about"' in html


# --- non-article modules ------------------------------------------------------------------------------


def test_people_learning_and_closing_soon_modules(client, app):
    from app.models.learning import LearningProgram
    from app.models.opportunity import Job
    from app.models.people import Person

    with app.app_context():
        db.session.add_all([
            Person(slug="p-pub", name="Public Woman", status="published", featured=True, title="CEO"),
            Person(slug="p-draft", name="Draft Woman", status="draft", featured=True),
            LearningProgram(slug="lp-1", title="Course One", status="published", featured=True),
            Job(slug="j-soon", title="Soon Role", company_name="Co", status="published", deadline=(NOW + timedelta(days=3)).date(),
                published_date=(NOW - timedelta(days=2)).date()),
            Job(slug="j-later", title="Later Role", company_name="Co", status="published", deadline=(NOW + timedelta(days=30)).date(),
                published_date=(NOW - timedelta(days=2)).date()),
            Job(slug="j-closed", title="Closed Role", company_name="Co", status="published", deadline=(NOW - timedelta(days=3)).date(),
                published_date=(NOW - timedelta(days=20)).date()),
        ])
        db.session.commit()
    _modules(app, ("people_spotlight", {"source": "featured", "itemCount": 4}, {"heading": "Women Moving Industries"}),
             ("learning", {"source": "featured", "itemCount": 3}, {"heading": "From WSF Learning"}),
             ("jobs", {"sort": "closing_soon", "itemCount": 4}, {"heading": "Jobs Closing Soon"}))
    people, learning, jobs = _public(client)
    assert [p["slug"] for p in people["initial_data"]["items"]] == ["p-pub"]
    assert [p["slug"] for p in learning["initial_data"]["items"]] == ["lp-1"]
    assert [j["slug"] for j in jobs["initial_data"]["items"]] == ["j-soon", "j-later"]
    html = client.get("/").get_data(as_text=True)
    assert "Draft Woman" not in html and "Closed Role" not in html


def test_expert_guidance_only_with_recorded_relationship(client, app):
    from app.models.article import Article, ArticleExpert
    from app.models.people import Person

    _seed(app, 3)
    with app.app_context():
        person = Person(slug="hr-expert", name="Jane Doe", status="published", title="HR Director",
                        credentials=[{"name": "SPHR", "issuer": "HRCI"}])
        db.session.add(person)
        db.session.flush()
        article = Article.query.filter_by(slug="a-2").first()
        db.session.add(ArticleExpert(article_id=article.id, role="reviewed_by", person_id=person.id, position=0))
        db.session.commit()
    _modules(app, ("expert_guidance", {"source": "expert", "itemCount": 3}, {"heading": "Expert-Backed Guidance"}))
    (module,) = _public(client)
    assert _slugs(module) == ["a-2"]
    card = module["initial_data"]["articles"][0]
    assert card["experts"][0]["label"] == "Reviewed by" and card["experts"][0]["line"] == "HR Director"
    html = client.get("/").get_data(as_text=True)
    assert "Reviewed by</span>" in html and "Jane Doe" in html


# --- community stories --------------------------------------------------------------------------------


def test_community_stories_are_published_articles_from_submissions(client, app):
    from app.models.article import Article
    from app.models.submissions import StorySubmission

    _seed(app, 3)
    with app.app_context():
        submission = StorySubmission.query.first()
        if submission is None:
            columns = {c.name for c in StorySubmission.__table__.columns}
            values = {k: v for k, v in {"first_name": "Reader", "last_name": "R", "email": "r@example.com", "title": "My return",
                                        "body": "Raw text", "summary": "Raw text", "status": "submitted",
                                        "consent_review_given": True}.items() if k in columns}
            submission = StorySubmission(**values)
            db.session.add(submission)
            db.session.flush()
        published = Article.query.filter_by(slug="a-3").first()
        published.source_submission_id = submission.id
        draft = Article(slug="story-draft", title="Draft Story", status="draft", author_id=published.author_id,
                        content=[], source_submission_id=submission.id)
        db.session.add(draft)
        db.session.commit()
    _modules(app, ("latest_stories", {"itemCount": 1}, {}),
             ("community_stories", {"source": "community", "itemCount": 3}, {"heading": "Her Career Story"}))
    latest, community = _public(client)
    assert _slugs(community) == ["a-3"]  # only the editor-published Article; never the draft or the raw submission
    assert "Raw text" not in client.get("/").get_data(as_text=True)


# --- personalized Handpicked --------------------------------------------------------------------------


def test_handpicked_anonymous_is_editorial_and_signed_in_is_goal_based(client, app):
    from app.models.article import Article
    from app.models.taxonomy import Topic
    from app.models.user import User

    _seed(app, 6, topic_slugs=("general",))
    with app.app_context():
        promo = Topic(slug="promotion", name="Promotion", status="published", career_goal="get_promoted")
        db.session.add(promo)
        for slug in ("a-5", "a-6"):
            article = Article.query.filter_by(slug=slug).first()
            article.topics.append(promo)
        db.session.commit()
    _modules(app, ("latest_stories", {"itemCount": 1}, {}),
             ("handpicked", {"source": "editorial", "articleSlugs": ["a-1", "a-3"], "itemCount": 2}, {"heading": "Handpicked"}),
             ("latest_stories", {"itemCount": 1}, {}))
    latest, handpicked, below = _public(client)
    assert _slugs(latest) == ["a-1"] and _slugs(handpicked) == ["a-3", "a-2"] and _slugs(below) == ["a-4"]

    assert client.get("/api/v1/public/homepage/handpicked").get_json()["data"] == {"personalized": False}
    token = _token(client, app, email="reader@example.com", role=None)
    with app.app_context():
        User.query.filter_by(email="reader@example.com").first().career_goals = ["get_promoted"]
        db.session.commit()
    resp = client.get("/api/v1/public/homepage/handpicked", headers=auth_headers(token))
    body = resp.get_json()["data"]
    assert resp.headers["Cache-Control"] == "private, no-store"
    assert body["personalized"] is True and [a["slug"] for a in body["articles"]] == ["a-5", "a-6"]
    again = client.get("/api/v1/public/homepage/handpicked", headers=auth_headers(token)).get_json()["data"]
    assert again == body  # deterministic
    others = set(_slugs(latest) + _slugs(below))
    assert not others & {a["slug"] for a in body["articles"]}
    assert "email" not in json.dumps(body)


# --- article page ---------------------------------------------------------------------------------------


def test_article_page_recommendations_never_repeat(client, app):
    from app.models.article import Article

    _seed(app, 12, series_slug="sx")
    with app.app_context():
        current = Article.query.filter_by(slug="a-6").first()
        current.related_articles = [Article.query.filter_by(slug=s).first() for s in ("a-5", "a-7")]
        current.content = [{"type": "relatedBlock", "heading": "Read", "articleSlugs": ["a-7"]}]
        db.session.commit()
    recs = client.get("/api/v1/articles/a-6/recommendations").get_json()["data"]
    up_next = recs["upNext"]["slug"]
    assert up_next == "a-5"  # next in the series by publish order
    body = [a["slug"] for a in recs["bodyArticles"]]
    related = [a["slug"] for a in recs["related"]]
    by_author = [a["slug"] for a in recs["moreFromAuthor"]]
    sidebar = [a["slug"] for a in recs["sidebar"]]
    everything = body + [up_next] + related + by_author + sidebar
    assert "a-6" not in everything
    assert len(everything) == len(set(everything))
    assert body == ["a-7"] and related[0] != "a-5"  # manual related a-5 / a-7 already placed above
    assert len(related) == 3 and len(by_author) == 3 and len(sidebar) == 3  # 12 - current - body - up next - 6 placed


def test_article_recommendations_with_little_content_show_fewer(client, app):
    _seed(app, 2)
    recs = client.get("/api/v1/articles/a-1/recommendations").get_json()["data"]
    assert recs["upNext"]["slug"] == "a-2"
    assert recs["related"] == [] and recs["moreFromAuthor"] == [] and recs["sidebar"] == []


def test_article_hard_load_embeds_the_same_recommendations(client, app):
    _seed(app, 14)
    html = client.get("/a-3").get_data(as_text=True)
    boot = json.loads(re.search(r'data-wsf-bootstrap="article">(.*?)</script>', html, re.S).group(1))
    api = client.get("/api/v1/articles/a-3/recommendations").get_json()["data"]
    assert boot["recommendations"] == api
    assert "More on WSF" in html and "Up next" in html


# --- article provenance -------------------------------------------------------------------------------


def test_reviewer_and_fact_checker_shown_only_when_recorded(client, app, admin):
    from app.models.people import Author, Person

    _seed(app, 2)
    with app.app_context():
        db.session.add_all([
            Person(slug="rev", name="Rita Reviewer", status="published", title="Talent Director",
                   credentials=[{"name": "CIPD Fellow", "issuer": "CIPD"}]),
            Person(slug="secret", name="Secret Draft Person", status="draft"),
            Author(slug="fc", name="Fiona Checker", status="active", role="Research Editor"),
        ])
        db.session.commit()
    article = client.get("/api/v1/articles/a-1", headers=admin).get_json()["data"]
    assert article["experts"] == []
    html = client.get("/a-1").get_data(as_text=True)
    assert "Reviewed by" not in html and "Fact checked by" not in html

    payload = {"title": article["title"], "authorSlug": "ed-author", "status": "published",
               "content": [{"type": "paragraph", "text": "Body."}],
               "topicSlugs": ["careers"], "experts": [{"role": "reviewed_by", "personSlug": "rev"},
                                                      {"role": "fact_checked_by", "authorSlug": "fc"},
                                                      {"role": "expert_contributor", "personSlug": "secret"}],
               "editorialUpdatedAt": (NOW + timedelta(days=1)).isoformat()}
    assert client.put("/api/v1/articles/a-1", json=payload, headers=admin).status_code == 200
    public = client.get("/api/v1/articles/a-1").get_json()["data"]
    assert [(e["label"], e["name"]) for e in public["experts"]] == [("Reviewed by", "Rita Reviewer"), ("Fact checked by", "Fiona Checker")]
    assert public["experts"][0]["credentials"] == [{"name": "CIPD Fellow", "issuer": "CIPD"}]
    html = client.get("/a-1").get_data(as_text=True)
    assert "Reviewed by</p>" in html and "Talent Director" in html and "Fact checked by</p>" in html
    assert "Secret Draft Person" not in html and "Updated " in html

    bad = dict(payload, experts=[{"role": "reviewed_by", "personSlug": "rev", "authorSlug": "fc"}])
    assert client.put("/api/v1/articles/a-1", json=bad, headers=admin).status_code == 422
    nobody = dict(payload, experts=[{"role": "reviewed_by", "personSlug": "missing"}])
    assert client.put("/api/v1/articles/a-1", json=nobody, headers=admin).status_code == 422


# --- topic hubs -------------------------------------------------------------------------------------------


def test_topic_hub_sections_dedupe_and_related_topics(client, app, admin):
    from app.models.learning import LearningProgram
    from app.models.taxonomy import Topic

    _seed(app, 9, topic_slugs=("career-growth",))
    with app.app_context():
        db.session.add_all([Topic(slug="job-search", name="Job Search", status="published"),
                            Topic(slug="hidden", name="Hidden", status="draft")])
        topic = Topic.query.filter_by(slug="career-growth").first()
        db.session.add(LearningProgram(slug="lp-cg", title="Grow Course", status="published", topics=[topic]))
        db.session.commit()
        topic_id = topic.id
    resp = client.put(f"/api/v1/admin/taxonomy/topics/{topic_id}/hub", headers=admin, json={
        "startHereSlugs": ["a-5", "a-1"], "editorsPicksSlugs": ["a-1", "a-9"], "relatedTopicSlugs": ["job-search", "hidden"]})
    assert resp.status_code == 200, resp.get_json()
    hub = client.get("/api/v1/topics/career-growth/hub").get_json()["data"]
    start = [a["slug"] for a in hub["startHere"]]
    latest = [a["slug"] for a in hub["latest"]]
    picks = [a["slug"] for a in hub["editorsPicks"]]
    assert start == ["a-5", "a-1"]
    assert latest == ["a-2", "a-3", "a-4", "a-6", "a-7", "a-8"]
    assert picks == ["a-9"]  # a-1 already placed in Start here
    assert [t["slug"] for t in hub["relatedTopics"]] == ["job-search"]  # draft related topic never shown
    assert [p["slug"] for p in hub["learning"]] == ["lp-cg"] and hub["resources"] == [] and hub["opportunities"] == []
    html = client.get("/topics/career-growth").get_data(as_text=True)
    assert len(re.findall(r"<h1\b", html.split('id="root"', 1)[1])) == 1
    assert "Browse related topics" in html and 'href="/topics/job-search"' in html and "Grow Course" in html
    assert "Resources" not in html.split('data-wsf-prerender="topic"', 1)[1].split("</main>", 1)[0].replace("Resources\"", "")
    boot = json.loads(re.search(r'data-wsf-bootstrap="topic">(.*?)</script>', html, re.S).group(1))
    assert [a["slug"] for a in boot["data"]["hub"]["editorsPicks"]] == ["a-9"]
    assert client.put(f"/api/v1/admin/taxonomy/topics/{topic_id}/hub", headers=admin,
                      json={"relatedTopicSlugs": ["career-growth"]}).status_code == 422


def test_empty_topic_hub_omits_sections(client, app):
    from app.models.taxonomy import Topic

    with app.app_context():
        db.session.add(Topic(slug="empty-topic", name="Empty Topic", status="published", description="Nothing yet."))
        db.session.commit()
    html = client.get("/topics/empty-topic").get_data(as_text=True)
    root = html.split('data-wsf-prerender="topic"', 1)[1].split("</main>", 1)[0]
    assert "Start here" not in root and "Editor&#x27;s picks" not in root and "No stories yet" in root


# --- WSF Weekly ---------------------------------------------------------------------------------------------


def test_newsletter_page_settings_defaults_and_validation(client, app, admin):
    settings = client.get("/api/v1/public/settings").get_json()["data"]["newsletterPage"]
    assert settings["title"] == "WSF Weekly" and settings["cadence"] == ""  # no frequency promised by default
    assert "Thursday" not in json.dumps(settings)
    ok = client.put("/api/v1/admin/settings", headers=admin, json={"settings": {"newsletter_page": {
        "tagline": "Career moves, weekly.", "benefits": ["Jobs worth applying for", "  "], "cadence": ""}}})
    assert ok.status_code == 200, ok.get_json()
    saved = client.get("/api/v1/public/settings").get_json()["data"]["newsletterPage"]
    assert saved["tagline"] == "Career moves, weekly." and saved["benefits"] == ["Jobs worth applying for"]
    bad = client.put("/api/v1/admin/settings", headers=admin, json={"settings": {"newsletter_page": {"tagline": "<b>x</b>"}}})
    assert bad.status_code == 422


def test_newsletter_archive_lists_only_sent_issues(client, app):
    from app.models.newsletter import NewsletterIssue

    with app.app_context():
        columns = {c.name for c in NewsletterIssue.__table__.columns}
        for slug, status in (("sent-one", "sent"), ("draft-one", "draft")):
            values = {"slug": slug, "title": f"Issue {slug}", "subject": f"Subject {slug}", "status": status,
                      "sent_at": NOW if status == "sent" else None, "content": []}
            db.session.add(NewsletterIssue(**{k: v for k, v in values.items() if k in columns}))
        db.session.commit()
    items = client.get("/api/v1/newsletter/issues").get_json()["data"]
    assert [i["slug"] for i in items] == ["sent-one"]


# --- query cost -------------------------------------------------------------------------------------------


def test_homepage_query_count_is_bounded(client, app):
    from sqlalchemy import event

    _seed(app, 20, series_slug="sx")
    _modules(app, ("hero", {"leadArticleSlug": "a-1", "secondaryArticleSlugs": ["a-2", "a-3"]}, {}),
             ("featured_stories", {"articleSlugs": ["a-4", "a-5"]}, {}),
             ("latest_stories", {"itemCount": 8}, {}),
             ("series_feature", {"seriesSlug": "sx", "itemCount": 3}, {}),
             ("career_moves", {"source": "topic", "topicSlugs": ["careers"], "itemCount": 4}, {}),
             ("handpicked", {"source": "editorial", "itemCount": 4}, {}))
    counter = {"n": 0}
    with app.app_context():
        engine = db.engine

        def count(*_args, **_kwargs):
            counter["n"] += 1

        event.listen(engine, "before_cursor_execute", count)
        try:
            assert client.get("/").status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", count)
    # One bounded query per selection plus batched card relations; the number
    # does not grow with the number of cards (no N+1).
    assert counter["n"] < 150, counter["n"]
