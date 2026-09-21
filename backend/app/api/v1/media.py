from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.media import Media
from app.schemas.media import MediaSchema
from app.services.media import MediaService
from app.utils.responses import ApiError, success_response

media_bp = Blueprint("media", __name__)
api = Api(media_bp)

media_schema = MediaSchema()


class MediaUploadResource(Resource):
    @permission_required("media.upload", "media.manage")
    def post(self):
        service = MediaService()
        media = service.save(
            request.files.get("file"),
            uploaded_by=current_user,
            alt_text=request.form.get("alt_text"),
            caption=request.form.get("caption"),
            credit=request.form.get("credit"),
        )
        return success_response(media_schema.dump(media), status=201)


class MediaDetailResource(Resource):
    @jwt_required()
    def get(self, media_id):
        media = db.session.get(Media, media_id)
        if media is None:
            raise ApiError("Media not found.", 404, code="not_found")
        return success_response(media_schema.dump(media))

    @permission_required("media.manage")
    def delete(self, media_id):
        media = db.session.get(Media, media_id)
        if media is None:
            raise ApiError("Media not found.", 404, code="not_found")
        MediaService().delete(media)
        return success_response(None, message="Media deleted.")


api.add_resource(MediaUploadResource, "/upload")
api.add_resource(MediaDetailResource, "/<int:media_id>")
