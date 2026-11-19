"""Video/recording-ready Learning lessons (safe provider embeds, transcript,
captions, slides Resource, facet-gated filter) and Event post-event content
(recording + links to existing Resource/Article/Learning program)."""
import os
from datetime import date, timedelta

import pytest

from app.extensions import db
from tests.conftest import auth_headers
from tests.test_events_cms import _base_payload
from tests.test_learning_certificates import admin  # noqa: F401  (fixture)
from tests.test_learning_circle_access import _make_program


class TestVideoEmbedService:
    @pytest.mark.parametrize(
        "url,provider,embed",
        [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube", "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "youtube", "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"),
            ("https://vimeo.com/123456789", "vimeo", "https://player.vimeo.com/video/123456789"),
            ("https://acme.wistia.com/medias/abc123xyz", "wistia", "https://fast.wistia.net/embed/iframe/abc123xyz"),
            ("https://www.loom.com/share/0f1e2d3c4b5a", "loom", "https://www.loom.com/embed/0f1e2d3c4b5a"),
            ("https://example.com/talk.mp4", "other", None),
        ],
    )
    def test_detection_and_embed(self, url, provider, embed):
        from app.services.video_embed import detect_video_provider, video_embed_url

        assert detect_video_provider(url) == provider
        assert video_embed_url(url) == embed

    @pytest.mark.parametrize("url", ["javascript:alert(1)", "<iframe src=x>", "ftp://youtube.com/x", "", None,
                                     "https://youtube.com.evil.com/watch?v=abc12345"])
    def test_unsafe_or_lookalike_never_embeds(self, url):
        from app.services.video_embed import video_embed_url

        assert video_embed_url(url) is None

    def test_contradicting_provider_rejected(self):
        from app.services.video_embed import resolve_video_provider

        with pytest.raises(ValueError):
            resolve_video_provider("https://vimeo.com/123456", "youtube")
        assert resolve_video_provider("https://vimeo.com/123456", "other") == "other"
        assert resolve_video_provider("https://vimeo.com/123456") == "vimeo"


def _put_curriculum(client, admin, program_id, lessons):
    return client.put(f"/api/v1/learning/admin/programs/{program_id}/curriculum",
                      json={"modules": [{"title": "Module", "lessons": lessons}]}, headers=admin)


def _resource_slug(app):
    from app.models.resource import Resource

    with app.app_context():
        r = Resource(slug="session-slides", name="Session slides", status="published", description=[],
                     access_type="direct_download", published_date=date.today())
        db.session.add(r)
        db.session.commit()
        return r.slug


class TestVideoLessons:
    def test_recording_lesson_saves_metadata_and_public_embed(self, client, app, admin):  # noqa: F811
        program_id, _ = _make_program(app, lesson_count=1, slug="video-course")
        slides = _resource_slug(app)
        resp = _put_curriculum(client, admin, program_id, [
            {"title": "Kickoff text", "lessonType": "text", "content": [{"type": "paragraph", "text": "Hi"}]},
            {"title": "Webinar replay", "lessonType": "recording", "externalUrl": "https://youtu.be/dQw4w9WgXcQ",
             "durationMinutes": 45, "transcript": "Welcome everyone.", "captionsUrl": "https://example.com/c.vtt",
             "resourceSlug": slides},
        ])
        assert resp.status_code == 200, resp.get_json()
        lessons = client.get("/api/v1/learning/video-course").get_json()["data"]["modules"][0]["lessons"]
        rec = lessons[1]
        assert rec["lesson_type"] == "recording" and rec["video_provider"] == "youtube"
        assert rec["embed_url"] == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
        assert rec["transcript"] == "Welcome everyone." and rec["captions_url"] == "https://example.com/c.vtt"
        assert rec["resource"]["slug"] == slides and rec["duration_minutes"] == 45
        assert lessons[0]["embed_url"] is None and lessons[0]["video_provider"] is None

    def test_unsafe_and_contradicting_urls_rejected(self, client, app, admin):  # noqa: F811
        program_id, _ = _make_program(app, lesson_count=1, status="draft")
        bad = _put_curriculum(client, admin, program_id, [
            {"title": "V", "lessonType": "video", "externalUrl": "javascript:alert(1)"}])
        assert bad.status_code == 422
        wrong = _put_curriculum(client, admin, program_id, [
            {"title": "V", "lessonType": "video", "externalUrl": "https://vimeo.com/1234567", "videoProvider": "youtube"}])
        assert wrong.status_code == 422
        captions = _put_curriculum(client, admin, program_id, [
            {"title": "V", "lessonType": "video", "externalUrl": "https://vimeo.com/1234567", "captionsUrl": "data:text/vtt,x"}])
        assert captions.status_code == 422
        missing = _put_curriculum(client, admin, program_id, [{"title": "V", "lessonType": "recording"}])
        assert missing.status_code == 422

    def test_switching_type_clears_video_metadata(self, client, app, admin):  # noqa: F811
        from app.models.learning import LearningLesson

        program_id, _ = _make_program(app, lesson_count=1, status="draft")
        resp = _put_curriculum(client, admin, program_id, [
            {"title": "V", "lessonType": "video", "externalUrl": "https://vimeo.com/1234567", "transcript": "T"}])
        module = resp.get_json()["data"]["modules"][0]
        lesson_id = module["lessons"][0]["id"]
        switched = client.put(f"/api/v1/learning/admin/programs/{program_id}/curriculum", headers=admin, json={
            "modules": [{"id": module["id"], "title": "Module", "lessons": [
                {"id": lesson_id, "title": "V", "lessonType": "external_link", "externalUrl": "https://example.com"}]}]})
        assert switched.status_code == 200, switched.get_json()
        with app.app_context():
            lesson = db.session.get(LearningLesson, lesson_id)
            assert lesson.video_provider is None and lesson.transcript is None

    def test_changed_link_redetects_provider_without_stale_value(self, client, app, admin):  # noqa: F811
        # The Studio editor no longer sends videoProvider: the server must
        # re-detect from the new link instead of keeping the old provider.
        program_id, _ = _make_program(app, lesson_count=1, status="draft")
        first = _put_curriculum(client, admin, program_id, [
            {"title": "V", "lessonType": "video", "externalUrl": "https://vimeo.com/1234567"}])
        module = first.get_json()["data"]["modules"][0]
        lesson = module["lessons"][0]
        assert lesson["video_provider"] == "vimeo"
        second = client.put(f"/api/v1/learning/admin/programs/{program_id}/curriculum", headers=admin, json={
            "modules": [{"id": module["id"], "title": "Module", "lessons": [
                {"id": lesson["id"], "title": "V", "lessonType": "video", "externalUrl": "https://youtu.be/dQw4w9WgXcQ"}]}]})
        assert second.status_code == 200, second.get_json()
        updated = second.get_json()["data"]["modules"][0]["lessons"][0]
        assert updated["video_provider"] == "youtube"
        assert updated["embed_url"] == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
        iframe = _put_curriculum(client, admin, program_id, [
            {"title": "V", "lessonType": "video", "externalUrl": '<iframe src="https://player.vimeo.com/video/1"></iframe>'}])
        assert iframe.status_code == 422

    def test_outline_never_leaks_url_or_transcript(self, client, app, admin):  # noqa: F811
        program_id, _ = _make_program(app, lesson_count=1, slug="circle-video", access_type="circle_only")
        _put_curriculum(client, admin, program_id, [
            {"title": "Text", "lessonType": "text", "content": [{"type": "paragraph", "text": "Hi"}]},
            {"title": "V", "lessonType": "video", "externalUrl": "https://vimeo.com/1234567", "transcript": "Secret"}])
        body = client.get("/api/v1/learning/circle-video").get_data(as_text=True)
        assert "vimeo.com" not in body and "Secret" not in body
        lesson = client.get("/api/v1/learning/circle-video").get_json()["data"]["modules"][0]["lessons"][1]
        assert lesson["videoProvider"] == "vimeo" and lesson["hasTranscript"] is True

    def test_facets_and_filter_only_when_real_content(self, client, app, admin):  # noqa: F811
        assert client.get("/api/v1/learning/meta/facets").get_json()["data"] == {"lessonFormats": []}
        draft_id, _ = _make_program(app, lesson_count=1, status="draft")
        _put_curriculum(client, admin, draft_id, [{"title": "V", "lessonType": "video", "externalUrl": "https://vimeo.com/1234567"}])
        assert client.get("/api/v1/learning/meta/facets").get_json()["data"] == {"lessonFormats": []}
        pub_id, _ = _make_program(app, lesson_count=1, slug="has-recording")
        _make_program(app, lesson_count=1, slug="plain")
        _put_curriculum(client, admin, pub_id, [
            {"title": "T", "lessonType": "text", "content": [{"type": "paragraph", "text": "Hi"}]},
            {"title": "R", "lessonType": "recording", "externalUrl": "https://vimeo.com/1234567"}])
        assert client.get("/api/v1/learning/meta/facets").get_json()["data"] == {"lessonFormats": ["recording"]}
        listed = client.get("/api/v1/learning?lesson_format=recording").get_json()["data"]
        assert [p["slug"] for p in listed] == ["has-recording"]

    def test_migration_chain(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config()
        config.set_main_option("script_location", os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations"))
        script = ScriptDirectory.from_config(config)
        assert len(script.get_heads()) == 1
        assert script.get_revision("b2e4c7f9a1d6").down_revision == "a1d3b6e8f0c5"
        assert script.get_revision("c3f5d8a0b2e7").down_revision == "b2e4c7f9a1d6"


class TestPostEventContent:
    def _setup_targets(self, app):
        from app.models.article import Article
        from app.models.people import Author

        slides = _resource_slug(app)
        with app.app_context():
            author = Author(slug="recap-writer", name="Recap Writer", status="active")
            db.session.add(author)
            db.session.flush()
            db.session.add(Article(slug="summit-recap", title="Summit recap", status="published", content=[], author_id=author.id))
            db.session.add(Article(slug="draft-recap", title="Draft recap", status="draft", content=[], author_id=author.id))
            db.session.commit()
        _make_program(app, lesson_count=1, slug="go-deeper")
        return slides

    def test_editor_links_and_public_payload(self, client, app, admin):  # noqa: F811
        slides = self._setup_targets(app)
        past = (date.today() - timedelta(days=7)).isoformat()
        created = client.post("/api/v1/events", json=_base_payload(
            date=past, status="published", recordingUrl="https://vimeo.com/7654321",
            postEventResourceSlug=slides, postEventArticleSlug="summit-recap",
            postEventLearningProgramSlug="go-deeper"), headers=admin)
        assert created.status_code == 201, created.get_json()
        slug = created.get_json()["data"]["slug"]
        assert created.get_json()["data"]["postEvent"]["editor"]["articleSlug"] == "summit-recap"
        post = client.get(f"/api/v1/events/{slug}").get_json()["data"]["postEvent"]
        assert post["recording"]["provider"] == "vimeo"
        assert post["recording"]["embedUrl"] == "https://player.vimeo.com/video/7654321"
        assert post["resource"]["slug"] == slides and post["article"]["slug"] == "summit-recap"
        assert post["learningProgram"]["slug"] == "go-deeper" and "editor" not in post

        # Omitted keys keep the saved links (older clients never wipe them).
        body = _base_payload(date=past, status="published")
        client.put(f"/api/v1/events/{slug}", json=body, headers=admin)
        assert client.get(f"/api/v1/events/{slug}").get_json()["data"]["postEvent"]["article"]["slug"] == "summit-recap"

        # Unpublished targets are never exposed; clearing removes the link.
        client.put(f"/api/v1/events/{slug}", json={**body, "postEventArticleSlug": "draft-recap", "recordingUrl": ""},
                   headers=admin)
        post = client.get(f"/api/v1/events/{slug}").get_json()["data"]["postEvent"]
        assert post["article"] is None and post["recording"] is None and post["resource"] is not None

    def test_circle_only_recording_locked_and_never_in_lists(self, client, app, admin):  # noqa: F811
        past = (date.today() - timedelta(days=7)).isoformat()
        created = client.post("/api/v1/events", json=_base_payload(
            date=past, status="published", accessType="circle_only", registrationMode="wsf",
            registrationUrl=None, recordingUrl="https://vimeo.com/7654321"), headers=admin)
        assert created.status_code == 201, created.get_json()
        slug = created.get_json()["data"]["slug"]
        post = client.get(f"/api/v1/events/{slug}").get_json()["data"]["postEvent"]
        assert post["recording"] is None and post["recordingLocked"] is True
        assert "vimeo.com" not in client.get(f"/api/v1/events/{slug}").get_data(as_text=True)
        assert "vimeo.com" not in client.get("/api/v1/events").get_data(as_text=True)
        staff = client.get(f"/api/v1/events/{slug}", headers=admin).get_json()["data"]["postEvent"]
        assert staff["recording"]["url"] == "https://vimeo.com/7654321"

    def test_changed_recording_link_redetects_provider(self, client, app, admin):  # noqa: F811
        past = (date.today() - timedelta(days=7)).isoformat()
        created = client.post("/api/v1/events", json=_base_payload(
            date=past, status="published", recordingUrl="https://vimeo.com/7654321"), headers=admin)
        slug = created.get_json()["data"]["slug"]
        resp = client.put(f"/api/v1/events/{slug}", json=_base_payload(
            date=past, status="published", recordingUrl="https://www.loom.com/share/0f1e2d3c4b5a", recordingProvider=None),
            headers=admin)
        assert resp.status_code == 200, resp.get_json()
        rec = client.get(f"/api/v1/events/{slug}").get_json()["data"]["postEvent"]["recording"]
        assert rec["provider"] == "loom" and rec["embedUrl"] == "https://www.loom.com/embed/0f1e2d3c4b5a"

    def test_event_without_post_content_has_none(self, client, app, admin):  # noqa: F811
        created = client.post("/api/v1/events", json=_base_payload(status="published"), headers=admin)
        slug = created.get_json()["data"]["slug"]
        assert client.get(f"/api/v1/events/{slug}").get_json()["data"]["postEvent"] is None

    def test_validation(self, client, app, admin):  # noqa: F811
        assert client.post("/api/v1/events", json=_base_payload(recordingUrl="javascript:alert(1)"), headers=admin).status_code == 422
        assert client.post("/api/v1/events", json=_base_payload(postEventArticleSlug="nope"), headers=admin).status_code == 404
