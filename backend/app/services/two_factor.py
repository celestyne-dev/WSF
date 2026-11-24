"""TOTP two-factor authentication (RFC 6238: SHA-1, 6 digits, 30-second steps).

Who must use it: accounts holding a role in TWO_FACTOR_REQUIRED_ROLES
(config.py; default "super_admin" and "editor", the role names defined in
app/services/rbac.py ROLE_PERMISSIONS). Everyone else may opt in.

Sign-in with 2FA (app/api/v1/auth.py):
  password OK + 2FA enabled         -> a 10-minute challenge token, no session
  password OK + required, not set up -> a 10-minute set-up token, no session
  challenge passed / set-up confirmed -> the normal session (HttpOnly refresh
                                       cookie + in-memory access token), marked
                                       two_factor_verified
A refresh session that was not 2FA-verified cannot be refreshed for an
account whose role requires 2FA (app/api/v1/auth.py RefreshResource).

Storage: the TOTP secret is encrypted with Fernet (TWO_FACTOR_ENCRYPTION_KEY;
required in production; development/testing derive one from SECRET_KEY).
Recovery codes (10, shown once) are stored as HMAC-SHA256 hashes and are
single-use. A code's time-step is remembered so the same code can't be used
twice.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import datetime, timezone
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.extensions import db
from app.models.two_factor import TwoFactorRecoveryCode, UserTwoFactor

ISSUER = "Women Shaping Futures"
STEP_SECONDS = 30
DIGITS = 6
WINDOW = 1  # accept the previous and next step (clock drift)
RECOVERY_CODE_COUNT = 10
TOKEN_MAX_AGE = 600  # challenge / set-up tokens: 10 minutes
_SALTS = {"challenge": "wsf-2fa-challenge", "setup": "wsf-2fa-setup"}


class TwoFactorError(Exception):
    def __init__(self, message, code="invalid_two_factor_code"):
        super().__init__(message)
        self.code = code


# --- policy ----------------------------------------------------------------------------------


def required_roles():
    return tuple(current_app.config.get("TWO_FACTOR_REQUIRED_ROLES") or ())


def is_required(user):
    return bool(user.role_names() & set(required_roles()))


def record_for(user, create=False):
    row = db.session.get(UserTwoFactor, user.id)
    if row is None and create:
        row = UserTwoFactor(user_id=user.id)
        db.session.add(row)
    return row


def is_enabled(user):
    row = record_for(user)
    return bool(row and row.enabled_at and row.secret_encrypted)


# --- secret encryption -------------------------------------------------------------------------


def _fernet():
    key = current_app.config.get("TWO_FACTOR_ENCRYPTION_KEY")
    if not key:
        if current_app.config.get("ENV") == "production":
            raise RuntimeError("TWO_FACTOR_ENCRYPTION_KEY is not set.")
        key = base64.urlsafe_b64encode(hashlib.sha256(f"2fa:{current_app.config['SECRET_KEY']}".encode()).digest())
    return Fernet(key)


def _encrypt(secret):
    return _fernet().encrypt(secret.encode()).decode()


def _decrypt(token):
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise TwoFactorError("Two-factor data can't be read; ask an administrator to reset it.",
                             code="two_factor_unreadable") from exc


# --- TOTP ------------------------------------------------------------------------------------------


def generate_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code_at(secret, step):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** DIGITS).zfill(DIGITS)


def current_step(now=None):
    return int((now if now is not None else time.time()) // STEP_SECONDS)


def code_for(secret, now=None):
    """The code an authenticator app shows right now (tests, set-up)."""
    return _code_at(secret, current_step(now))


def match_step(secret, code, last_used_step=None, now=None):
    """The matching time-step for `code`, or None. Steps at or before
    `last_used_step` never match (a code works once)."""
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != DIGITS:
        return None
    base = current_step(now)
    for step in range(base - WINDOW, base + WINDOW + 1):
        if last_used_step is not None and step <= last_used_step:
            continue
        if hmac.compare_digest(_code_at(secret, step), code):
            return step
    return None


def provisioning_uri(user, secret):
    label = quote(f"{ISSUER}:{user.email}", safe=":")
    return (f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER)}"
            f"&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}")


def qr_svg_data_uri(uri):
    import qrcode
    import qrcode.image.svg

    image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    svg = image.to_string()
    return "data:image/svg+xml;base64," + base64.b64encode(svg).decode()


# --- set-up / disable --------------------------------------------------------------------------


def start_setup(user):
    """A fresh pending secret (replaces any unfinished set-up). Returns
    {secret, otpauthUri, qrSvg} for the authenticator app."""
    row = record_for(user, create=True)
    secret = generate_secret()
    row.pending_secret_encrypted = _encrypt(secret)
    db.session.flush()
    uri = provisioning_uri(user, secret)
    return {"secret": secret, "otpauthUri": uri, "qrSvg": qr_svg_data_uri(uri)}


def confirm_setup(user, code, now=None):
    """Enables 2FA when `code` matches the pending secret. Returns the new
    recovery codes (plain text, shown once)."""
    row = record_for(user)
    if row is None or not row.pending_secret_encrypted:
        raise TwoFactorError("Start two-factor set-up first.", code="two_factor_setup_missing")
    secret = _decrypt(row.pending_secret_encrypted)
    step = match_step(secret, code, now=now)
    if step is None:
        raise TwoFactorError("That code isn't right. Check the time on your device and try the newest code.")
    row.secret_encrypted = row.pending_secret_encrypted
    row.pending_secret_encrypted = None
    row.enabled_at = datetime.now(timezone.utc)
    row.last_used_step = step
    return regenerate_recovery_codes(user)


def disable(user):
    row = record_for(user)
    if row is not None:
        db.session.delete(row)
    TwoFactorRecoveryCode.query.filter_by(user_id=user.id).delete()


# --- verification -------------------------------------------------------------------------------


def verify_code(user, code, now=None):
    """True (and the step is consumed) when `code` is a current, unused TOTP."""
    row = record_for(user)
    if row is None or not row.secret_encrypted:
        return False
    step = match_step(_decrypt(row.secret_encrypted), code, last_used_step=row.last_used_step, now=now)
    if step is None:
        return False
    row.last_used_step = step
    return True


def _hash_recovery(code):
    normalized = "".join(ch for ch in (code or "").lower() if ch.isalnum())
    key = hashlib.sha256(f"recovery:{current_app.config['SECRET_KEY']}".encode()).digest()
    return hmac.new(key, normalized.encode(), hashlib.sha256).hexdigest()


def regenerate_recovery_codes(user):
    TwoFactorRecoveryCode.query.filter_by(user_id=user.id).delete()
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = base64.b32encode(secrets.token_bytes(8)).decode().rstrip("=").lower()[:10]
        code = f"{raw[:5]}-{raw[5:]}"
        codes.append(code)
        db.session.add(TwoFactorRecoveryCode(user_id=user.id, code_hash=_hash_recovery(code)))
    db.session.flush()
    return codes


def use_recovery_code(user, code):
    """True (and the code is spent) for an unused recovery code."""
    row = TwoFactorRecoveryCode.query.filter_by(user_id=user.id, code_hash=_hash_recovery(code),
                                                used_at=None).first()
    if row is None:
        return False
    row.used_at = datetime.now(timezone.utc)
    return True


def recovery_codes_remaining(user):
    return TwoFactorRecoveryCode.query.filter_by(user_id=user.id, used_at=None).count()


# --- short-lived sign-in tokens ----------------------------------------------------------------


def _serializer(purpose):
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_SALTS[purpose])


def issue_token(user, purpose):
    return _serializer(purpose).dumps({"uid": user.id, "av": user.auth_version})


def read_token(token, purpose):
    """The active user a challenge/set-up token belongs to, or raise."""
    from app.models.user import User

    try:
        data = _serializer(purpose).loads(token or "", max_age=TOKEN_MAX_AGE)
    except SignatureExpired as exc:
        raise TwoFactorError("This sign-in step has expired. Please sign in again.", code="two_factor_expired") from exc
    except BadSignature as exc:
        raise TwoFactorError("Please sign in again.", code="two_factor_token_invalid") from exc
    user = db.session.get(User, data.get("uid"))
    if user is None or not user.is_active or user.auth_version != data.get("av"):
        raise TwoFactorError("Please sign in again.", code="two_factor_token_invalid")
    return user
