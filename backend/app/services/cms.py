from app.extensions import db
from app.models.cms import HomepageModule, Menu, MenuItem, SiteSetting, SocialLink


def replace_homepage_modules(modules_data):
    """The homepage builder saves its whole ordered arrangement at once —
    simpler and safer than tracking per-module diffs client-side.
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
            )
        )


def _create_menu_items(menu_id, items_data, parent_id=None):
    for index, item_data in enumerate(items_data):
        item = MenuItem(
            menu_id=menu_id,
            parent_id=parent_id,
            label=item_data["label"],
            url=item_data["url"],
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
