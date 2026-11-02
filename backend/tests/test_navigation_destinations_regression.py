"""Navigation CMS destination regression (Community/Shop -> "/"): every
destination type survives admin save -> admin read -> public read, no
navigable item ever silently resolves to "/", stale destination fields are
never stored, a GET -> unchanged PUT round trip is lossless, and default
navigation healing repairs the "/" placeholder rows idempotently without
overwriting legitimate admin configuration.
"""
import pytest

from tests.conftest import auth_headers
from tests.test_navigation_cms import _make_page, _make_series, _make_topic, admin_token  # noqa: F401


def _put(client, token, items, key="primary"):
    return client.put("/api/v1/admin/navigation", json={"menus": [{"key": key, "items": items}]}, headers=auth_headers(token))


def _admin_menu(client, token, key="primary"):
    data = client.get("/api/v1/admin/navigation", headers=auth_headers(token)).get_json()["data"]
    return next(m for m in data if m["key"] == key)


def _public_items(client, key="primary"):
    return client.get("/api/v1/public/navigation").get_json()["data"]["menus"][key]["items"]


def _all_destinations(app):
    page_id = _make_page(app, key="about-wsf")
    topic_id = _make_topic(app, slug="leadership")
    series_id = _make_series(app, slug="founders")
    return [
        {"label": "Community", "itemType": "route", "url": "/community"},
        {"label": "Shop", "itemType": "route", "url": "/shop"},
        {"label": "About", "itemType": "page", "pageId": page_id},
        {"label": "Leadership", "itemType": "topic", "topicId": topic_id},
        {"label": "Founders", "itemType": "series", "seriesId": series_id},
        {"label": "Partner site", "itemType": "external", "url": "https://partner.example.org/wsf", "openNewTab": True},
        {"label": "Explore", "itemType": "group", "children": [
            {"label": "Resources", "itemType": "route", "url": "/resources"},
            {"label": "Series hub", "itemType": "series", "seriesId": series_id},
        ]},
    ]


# 1-10: every destination type through save -> admin read -> public read --------------------------


def test_every_destination_type_survives_save_and_public_serialization(client, app, admin_token):
    resp = _put(client, admin_token, _all_destinations(app))
    assert resp.status_code == 200, resp.get_json()
    admin = {i["label"]: i for i in _admin_menu(client, admin_token)["items"]}
    assert admin["Community"]["url"] == "/community" and admin["Community"]["effectiveUrl"] == "/community"
    assert admin["Shop"]["url"] == "/shop"
    assert admin["About"]["effectiveUrl"] == "/about-wsf" and admin["About"]["linkedLabel"] == "A Page"
    assert admin["Leadership"]["effectiveUrl"] == "/topics/leadership" and admin["Leadership"]["linkedLabel"] == "Leadership"
    assert admin["Founders"]["effectiveUrl"] == "/series/founders"
    assert admin["Explore"]["effectiveUrl"] is None and admin["Explore"]["url"] is None

    public = {i["label"]: i for i in _public_items(client)}
    expected = {
        "Community": ("/community", "internal"), "Shop": ("/shop", "internal"), "About": ("/about-wsf", "internal"),
        "Leadership": ("/topics/leadership", "internal"), "Founders": ("/series/founders", "internal"),
        "Partner site": ("https://partner.example.org/wsf", "external"), "Explore": (None, "group"),
    }
    assert {label: (i["url"], i["linkType"]) for label, i in public.items()} == expected
    assert public["Partner site"]["openNewTab"] is True
    assert [(c["label"], c["url"], c["linkType"]) for c in public["Explore"]["children"]] == [
        ("Resources", "/resources", "internal"), ("Series hub", "/series/founders", "internal")]
    for item in public.values():
        assert item["url"] != "/"


@pytest.mark.parametrize("bad", [
    {"label": "Community", "itemType": "route"},
    {"label": "Community", "itemType": "route", "url": ""},
    {"label": "Community", "itemType": "route", "url": "community"},
    {"label": "Community", "itemType": "route", "url": "//evil.example"},
    {"label": "Studio", "itemType": "route", "url": "/admin/navigation"},
    {"label": "Bad", "itemType": "external", "url": "javascript:alert(1)"},
    {"label": "Bad", "itemType": "external", "url": "/relative"},
    {"label": "Bad", "itemType": "external"},
    {"label": "P", "itemType": "page"},
    {"label": "T", "itemType": "topic"},
    {"label": "S", "itemType": "series"},
    {"label": "P", "itemType": "page", "pageId": 999999},
])
def test_missing_or_invalid_destination_is_rejected_not_defaulted_to_home(client, admin_token, bad):
    resp = _put(client, admin_token, [bad])
    assert resp.status_code in (400, 422), bad


def test_stale_fields_from_a_previous_type_are_never_stored(client, app, admin_token):
    topic_id = _make_topic(app, slug="careers")
    page_id = _make_page(app, key="press")
    items = [
        {"label": "Group with stale url", "itemType": "group", "url": "/community", "pageId": page_id,
         "children": [{"label": "Kid", "itemType": "route", "url": "/kid"}]},
        {"label": "Topic with stale url", "itemType": "topic", "topicId": topic_id, "url": "/", "pageId": page_id},
        {"label": "Route with stale ids", "itemType": "route", "url": "/events", "topicId": topic_id, "openNewTab": True},
    ]
    assert _put(client, admin_token, items).status_code == 200
    admin = {i["label"]: i for i in _admin_menu(client, admin_token)["items"]}
    assert (admin["Group with stale url"]["url"], admin["Group with stale url"]["pageId"]) == (None, None)
    assert (admin["Topic with stale url"]["url"], admin["Topic with stale url"]["pageId"]) == (None, None)
    assert admin["Route with stale ids"]["topicId"] is None and admin["Route with stale ids"]["openNewTab"] is False
    public = {i["label"]: i for i in _public_items(client)}
    assert public["Group with stale url"]["url"] is None and public["Group with stale url"]["linkType"] == "group"


def test_legacy_field_names_and_type_spellings_are_normalized(client, app, admin_token):
    page_id = _make_page(app, key="legacy-page")
    items = [
        {"label": "Legacy route", "item_type": "internal", "route": "/community"},
        {"label": "Legacy page", "type": "page", "page_id": page_id},
        {"label": "Legacy external", "destinationType": "external_url", "externalUrl": "https://ex.org"},
        {"label": "Legacy group", "itemType": "dropdown", "children": [{"label": "Shop", "item_type": "link", "href": "/shop"}]},
    ]
    resp = _put(client, admin_token, items)
    assert resp.status_code == 200, resp.get_json()
    admin = {i["label"]: i for i in _admin_menu(client, admin_token)["items"]}
    assert (admin["Legacy route"]["itemType"], admin["Legacy route"]["url"]) == ("route", "/community")
    assert (admin["Legacy page"]["itemType"], admin["Legacy page"]["pageId"]) == ("page", page_id)
    assert (admin["Legacy external"]["itemType"], admin["Legacy external"]["url"]) == ("external", "https://ex.org")
    assert admin["Legacy group"]["itemType"] == "group" and admin["Legacy group"]["children"][0]["url"] == "/shop"


# 12: unpublished linked entities -----------------------------------------------------------------------------


def test_unpublished_entity_hidden_publicly_but_warned_in_admin(client, app, admin_token):
    draft_topic = _make_topic(app, slug="draft-topic", status="draft")
    items = [
        {"label": "Draft topic", "itemType": "topic", "topicId": draft_topic},
        {"label": "Group of drafts", "itemType": "group", "children": [{"label": "Draft kid", "itemType": "topic", "topicId": draft_topic}]},
    ]
    assert _put(client, admin_token, items).status_code == 200
    admin = {i["label"]: i for i in _admin_menu(client, admin_token)["items"]}
    assert any("not currently public" in w for w in admin["Draft topic"]["warnings"])
    labels = [i["label"] for i in _public_items(client)]
    assert "Draft topic" not in labels and "Group of drafts" not in labels  # empty group dropped


def test_entity_link_follows_renamed_slug_and_removal_keeps_entity(client, app, admin_token):
    from app.extensions import db
    from app.models.page import Page

    page_id = _make_page(app, key="mission")
    _put(client, admin_token, [{"label": "Mission", "itemType": "page", "pageId": page_id}])
    with app.app_context():
        page = db.session.get(Page, page_id)
        page.slug, page.title = "our-mission", "Our Mission (renamed)"
        db.session.commit()
    assert _public_items(client)[0]["url"] == "/our-mission"
    _put(client, admin_token, [])
    with app.app_context():
        assert db.session.get(Page, page_id) is not None


def test_homepage_destination_is_flagged_for_admin(client, admin_token):
    _put(client, admin_token, [{"label": "Community", "itemType": "route", "url": "/"}])
    item = _admin_menu(client, admin_token)["items"][0]
    assert any("homepage" in w for w in item["warnings"])


# 13: admin GET -> unchanged save -> GET round trip --------------------------------------------------------------


def _strip_ids(items):
    return [{k: (_strip_ids(v) if k == "children" else v) for k, v in i.items() if k not in ("id",)} for i in items]


def test_admin_round_trip_is_lossless(client, app, admin_token):
    _put(client, admin_token, _all_destinations(app))
    first = _admin_menu(client, admin_token)["items"]
    payload_keys = ("label", "itemType", "url", "pageId", "topicId", "seriesId", "openNewTab", "style", "visible")

    def to_input(item):
        out = {k: item[k] for k in payload_keys}
        out["children"] = [to_input(c) for c in item["children"]]
        return out

    assert _put(client, admin_token, [to_input(i) for i in first]).status_code == 200
    second = _admin_menu(client, admin_token)["items"]
    assert _strip_ids(second) == _strip_ids(first)


# 14-15: default navigation seeding / healing --------------------------------------------------------------------


def _primary_destinations(app):
    from app.models.cms import Menu, MenuItem

    with app.app_context():
        menu = Menu.query.filter_by(key="primary").first()
        items = MenuItem.query.filter_by(menu_id=menu.id, parent_id=None).order_by(MenuItem.sort_order).all()
        return [(i.label, i.item_type, i.effective_url()) for i in items]


def _seed(app):
    from app.services.navigation import seed_default_navigation

    with app.app_context():
        seed_default_navigation()


def test_fresh_seed_has_canonical_destinations_and_is_idempotent(app):
    _seed(app)
    first = _primary_destinations(app)
    assert ("Community", "route", "/community") in first and ("Shop", "route", "/shop") in first
    assert all(dest != "/" for _, _, dest in first)
    _seed(app)
    _seed(app)
    assert _primary_destinations(app) == first


def test_healing_repairs_community_and_shop_homepage_placeholders(client, app, admin_token):
    # The exact production regression: Community/Shop saved as "/".
    _put(client, admin_token, [
        {"label": "Stories", "itemType": "route", "url": "/topics"},
        {"label": "Topics", "itemType": "group", "children": [{"label": "Leadership", "itemType": "route", "url": "/topics/leadership"}]},
        {"label": "Community", "itemType": "route", "url": "/"},
        {"label": "Shop", "itemType": "route", "url": "/"},
    ])
    _seed(app)
    dests = _primary_destinations(app)
    assert ("Community", "route", "/community") in dests and ("Shop", "route", "/shop") in dests
    assert [label for label, _, _ in dests].count("Community") == 1  # repaired in place, no duplicate
    assert [label for label, _, _ in dests].count("Shop") == 1
    assert ("Topics", "group", None) in dests  # admin's own group untouched
    _seed(app)
    assert _primary_destinations(app) == dests


def test_healing_never_overwrites_legitimate_admin_changes(client, app, admin_token):
    _put(client, admin_token, [
        {"label": "Home", "itemType": "route", "url": "/"},  # a real homepage link stays
        {"label": "Our Community", "itemType": "route", "url": "/community"},  # admin relabel stays
        {"label": "Store", "itemType": "external", "url": "https://store.example.org"},  # admin's own shop link
        {"label": "Custom", "itemType": "route", "url": "/custom-page"},
    ])
    _seed(app)
    dests = _primary_destinations(app)
    assert ("Home", "route", "/") in dests
    assert ("Our Community", "route", "/community") in dests
    assert [d for _, _, d in dests].count("/community") == 1
    assert ("Store", "external", "https://store.example.org") in dests
    assert ("Custom", "route", "/custom-page") in dests
    assert ("Shop", "route", "/shop") in dests  # missing canonical destination added
