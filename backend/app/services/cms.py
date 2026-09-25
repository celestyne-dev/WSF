from app.extensions import db
from app.models.cms import HomepageModule, Menu, MenuItem, SiteSetting, SocialLink


def replace_homepage_modules(modules_data):
    """The homepage builder saves its whole ordered arrangement at once —
    simpler and safer than tracking per-module diffs client-side. This is
    also the app's "publish" action for the homepage: there is no separate
    draft copy, so a save takes effect immediately (see final report for
    why a full staged-version system was judged out of scope).
    """
    HomepageModule.query.delete()
    for index, data in enumerate(modules_data):
        db.session.add(
            HomepageModule(
                type=data["type"],
                enabled=data.get("enabled", True),
                sort_order=index,
                heading=data.get("heading"),
                subheading=data.get("subheading"),
                selection_mode=data.get("selection_mode"),
                config=data.get("config") or {},
                media_id=data.get("media_id"),
                cta_label=data.get("cta_label"),
                cta_url=data.get("cta_url"),
                secondary_cta_label=data.get("secondary_cta_label"),
                secondary_cta_url=data.get("secondary_cta_url"),
            )
        )


def _create_menu_items(menu_id, items_data, parent_id=None):
    for index, item_data in enumerate(items_data):
        item = MenuItem(
            menu_id=menu_id,
            parent_id=parent_id,
            label=item_data["label"],
            item_type=item_data.get("item_type", "route"),
            url=item_data.get("url"),
            topic_id=item_data.get("topic_id"),
            series_id=item_data.get("series_id"),
            page_id=item_data.get("page_id"),
            open_new_tab=item_data.get("open_new_tab", False),
            style=item_data.get("style", "standard"),
            sort_order=index,
            visible=item_data.get("visible", True),
        )
        db.session.add(item)
        db.session.flush()  # assign item.id before recursing into children
        _create_menu_items(menu_id, item_data.get("children") or [], parent_id=item.id)


def replace_menu(key, heading, items_data):
    menu = Menu.query.filter_by(key=key).first()
    if menu is None:
        menu = Menu(key=key)
        db.session.add(menu)
        db.session.flush()

    menu.heading = heading
    # A single bulk delete removes every row for this menu (parents and
    # children alike), so this never depends on ORM cascade behavior.
    MenuItem.query.filter_by(menu_id=menu.id).delete()
    _create_menu_items(menu.id, items_data)
    return menu


def replace_social_links(links_data):
    SocialLink.query.delete()
    for index, data in enumerate(links_data):
        db.session.add(
            SocialLink(platform=data["platform"], url=data["url"], handle=data.get("handle"), sort_order=index)
        )


def upsert_site_settings(settings_dict):
    for key, value in settings_dict.items():
        setting = db.session.get(SiteSetting, key)
        if setting is None:
            setting = SiteSetting(key=key)
            db.session.add(setting)
        setting.value = value
