from app.utils.passwords import (
    create_token,
    hash_password,
    verify_password,
    verify_token,
)


def test_password_hash_roundtrip():
    encoded = hash_password("s3cret")
    assert encoded.startswith("pbkdf2_sha256$")
    assert verify_password("s3cret", encoded)
    assert not verify_password("wrong", encoded)


def test_password_hash_is_salted():
    assert hash_password("same") != hash_password("same")


def test_token_roundtrip():
    token = create_token("analyst", "secret", ttl_seconds=60)
    assert verify_token(token, "secret") == "analyst"


def test_token_rejects_wrong_secret():
    token = create_token("analyst", "secret", ttl_seconds=60)
    assert verify_token(token, "another-secret") is None


def test_token_rejects_expired():
    token = create_token("analyst", "secret", ttl_seconds=-1)
    assert verify_token(token, "secret") is None


def test_token_rejects_tampering():
    token = create_token("analyst", "secret", ttl_seconds=60)
    payload, signature = token.split(".", 1)
    tampered = f"{payload[:-1]}A.{signature}"
    assert verify_token(tampered, "secret") is None
