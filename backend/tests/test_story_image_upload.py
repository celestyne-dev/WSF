"""Public story image upload: strict validation, re-encoding, rate limit
(app/services/media.py strict mode, app/api/v1/submissions.py)."""
import io
import os

import pytest
from PIL import Image

URL = "/api/v1/submissions/media"


@pytest.fixture(autouse=True)
def _media_root(app, tmp_path):
    app.config["MEDIA_ROOT"] = str(tmp_path)


def _image_bytes(fmt="PNG", size=(40, 30), exif=None):
    buf = io.BytesIO()
    img = Image.new("RGB", size, (120, 40, 80))
    kwargs = {"exif": exif} if exif is not None else {}
    img.save(buf, fmt, **kwargs)
    return buf.getvalue()


def _post(client, data, filename, mimetype):
    return client.post(URL, data={"file": (io.BytesIO(data), filename, mimetype)}, content_type="multipart/form-data")


def test_url_is_the_public_upload(client, app):
    rules = [r.rule for r in app.url_map.iter_rules() if r.rule == URL]
    assert rules, "public submission media upload route moved"


def test_valid_png_is_accepted_and_stored_reencoded_without_trailing_payload(client, app):
    payload = _image_bytes("PNG") + b"<html><script>alert(1)</script></html>"
    res = _post(client, payload, "photo.png", "image/png")
    assert res.status_code == 201
    with app.app_context():
        from app.models.media import Media

        media = Media.query.get(res.get_json()["data"]["id"])
        stored = open(media.file_path, "rb").read()
    assert b"<script>" not in stored and stored != payload
    assert Image.open(io.BytesIO(stored)).format == "PNG"


def test_jpeg_metadata_including_location_is_removed(client, app):
    exif = Image.Exif()
    exif[0x8825] = {2: (51.0, 30.0, 0.0)}  # GPSInfo
    exif[0x010F] = "Illustrative Camera"   # Make
    res = _post(client, _image_bytes("JPEG", exif=exif.tobytes()), "photo.jpg", "image/jpeg")
    assert res.status_code == 201
    with app.app_context():
        from app.models.media import Media

        path = Media.query.get(res.get_json()["data"]["id"]).file_path
    stored_exif = Image.open(path).getexif()
    assert 0x8825 not in stored_exif and 0x010F not in stored_exif


@pytest.mark.parametrize("data,filename,mimetype,code", [
    (_image_bytes("GIF"), "photo.png", "image/png", 415),                     # contents don't match extension
    (_image_bytes("PNG"), "photo.jpg", "image/jpeg", 415),                    # PNG renamed .jpg
    (_image_bytes("PNG"), "photo.png", "image/jpeg", 415),                    # declared MIME disagrees
    (b"<svg xmlns='http://www.w3.org/2000/svg'><script>x</script></svg>", "pic.svg", "image/svg+xml", 415),
    (b"%PDF-1.4 not an image", "doc.png", "image/png", 415),
    (b"MZ\x90\x00 executable", "run.webp", "image/webp", 415),
    (_image_bytes("PNG")[:60], "cut.png", "image/png", 415),                  # truncated pixel data
])
def test_unsafe_or_mismatched_files_are_rejected(client, data, filename, mimetype, code):
    assert _post(client, data, filename, mimetype).status_code == code


def test_decompression_bomb_sized_images_are_rejected(client):
    big = _image_bytes("PNG", size=(7000, 6000))  # 42 megapixels, tiny file
    res = _post(client, big, "huge.png", "image/png")
    assert res.status_code == 413


def test_oversized_file_is_rejected(client, app):
    app.config["MAX_UPLOAD_SIZE"] = 1000
    assert _post(client, _image_bytes("PNG", size=(400, 400)) + os.urandom(2000), "big.png", "image/png").status_code == 413


def test_upload_is_rate_limited(client):
    codes = [_post(client, _image_bytes("PNG"), f"p{i}.png", "image/png").status_code for i in range(11)]
    assert codes[:10] == [201] * 10 and codes[10] == 429


def test_studio_uploads_keep_their_existing_behaviour(app):
    from app.services.media import MediaService

    with app.app_context():
        # Non-strict validation still only checks extension, size and a decodable image.
        from werkzeug.datastructures import FileStorage

        fs = FileStorage(stream=io.BytesIO(_image_bytes("PNG")), filename="studio.png", content_type="image/png")
        assert MediaService().validate(fs) == "png"
