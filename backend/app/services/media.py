import os
import uuid as uuid_lib

from flask import current_app
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.media import Media, MediaVariant
from app.utils.responses import ApiError


class MediaService:
    """Validates, stores, and processes uploaded images on the Hostinger
    VPS filesystem. Flask only ever handles upload -> validate -> process
    -> persist metadata -> permissions; Nginx serves the resulting files
    directly from MEDIA_ROOT at MEDIA_URL in production (see
    app/__init__.py for the development-only Flask fallback route).
    """

    def __init__(self, app=None):
        self.app = app or current_app

    def _config(self, key):
        return self.app.config[key]

    def _variant_dir(self, subdir):
        path = os.path.join(self._config("MEDIA_ROOT"), subdir)
        os.makedirs(path, exist_ok=True)
        return path

    def validate(self, file_storage):
        if not file_storage or not file_storage.filename:
            raise ApiError("No file provided.", 400, code="no_file")

        filename = file_storage.filename
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in self._config("ALLOWED_IMAGE_EXTENSIONS"):
            raise ApiError(f"File type .{ext} is not allowed.", 415, code="unsupported_media_type")

        file_storage.stream.seek(0, os.SEEK_END)
        size = file_storage.stream.tell()
        file_storage.stream.seek(0)
        if size > self._config("MAX_UPLOAD_SIZE"):
            raise ApiError("File exceeds the maximum upload size.", 413, code="file_too_large")

        try:
            image = Image.open(file_storage.stream)
            image.verify()
        except Exception as exc:
            raise ApiError("File is not a valid image.", 415, code="invalid_image") from exc
        file_storage.stream.seek(0)

        return ext

    def save(self, file_storage, uploaded_by=None, alt_text=None, caption=None, credit=None):
        ext = self.validate(file_storage)
        original_filename = secure_filename(file_storage.filename)
        file_uuid = str(uuid_lib.uuid4())
        stored_filename = f"{file_uuid}.{ext}"

        original_path = os.path.join(self._variant_dir("originals"), stored_filename)
        file_storage.save(original_path)

        base_image = ImageOps.exif_transpose(Image.open(original_path))
        width, height = base_image.size
        media_url = self._config("MEDIA_URL").rstrip("/")

        media = Media(
            uuid=file_uuid,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=original_path,
            public_url=f"{media_url}/originals/{stored_filename}",
            mime_type=file_storage.mimetype or f"image/{ext}",
            original_format=ext,
            delivered_format="webp",
            width=width,
            height=height,
            file_size=os.path.getsize(original_path),
            alt_text=alt_text,
            caption=caption,
            credit=credit,
            uploaded_by_id=uploaded_by.id if uploaded_by else None,
        )
        db.session.add(media)
        db.session.flush()  # assign media.id for the variant rows below

        for variant_name, (max_w, max_h) in self._config("MEDIA_VARIANTS").items():
            variant_image = ImageOps.exif_transpose(Image.open(original_path))
            if variant_image.mode not in ("RGB", "L"):
                variant_image = variant_image.convert("RGB")
            variant_image.thumbnail((max_w, max_h), Image.LANCZOS)

            variant_filename = f"{file_uuid}_{variant_name}.webp"
            variant_path = os.path.join(self._variant_dir(variant_name), variant_filename)
            variant_image.save(variant_path, "WEBP", quality=82)

            db.session.add(
                MediaVariant(
                    media_id=media.id,
                    variant=variant_name,
                    file_path=variant_path,
                    public_url=f"{media_url}/{variant_name}/{variant_filename}",
                    width=variant_image.width,
                    height=variant_image.height,
                    file_size=os.path.getsize(variant_path),
                )
            )

        db.session.commit()
        return media

    def delete(self, media):
        if media.is_referenced():
            raise ApiError("This file is still in use and cannot be deleted.", 409, code="media_in_use")

        paths = [media.file_path] + [variant.file_path for variant in media.variants]
        for path in paths:
            if os.path.exists(path):
                os.remove(path)

        db.session.delete(media)
        db.session.commit()
