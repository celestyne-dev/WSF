import bcrypt


def hash_password(raw_password):
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw_password, password_hash):
    if not password_hash:
        return False
    return bcrypt.checkpw(raw_password.encode("utf-8"), password_hash.encode("utf-8"))
