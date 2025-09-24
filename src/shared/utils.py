import hashlib, uuid

def idempotency_key() -> str:
    """Ключ идемпотентности для платежей ЯКассы."""
    return uuid.uuid4().hex

def hash_file(path: str) -> str:
    """SHA-256 файла."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
