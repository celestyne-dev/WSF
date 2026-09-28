from app.extensions import ma
from app.models.notification import Notification


class NotificationSchema(ma.SQLAlchemyAutoSchema):
    """Never exposes recipient_user_id (implicit — every list/detail call
    is already scoped to request.user, see api/v1/notifications.py) or
    dedupe_key (an internal idempotency detail, not a client concern) —
    see task spec's SERIALIZATION section.
    """

    class Meta:
        model = Notification
        load_instance = False
        exclude = ("recipient_user_id", "dedupe_key")
