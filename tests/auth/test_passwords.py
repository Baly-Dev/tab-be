import hashlib

from auth.utils.passwords import hash_password, verify_password


def test_bcrypt_round_trip():
    stored = hash_password("correct-horse")
    assert stored.startswith("$2b$12$")
    assert verify_password("correct-horse", stored) is True
    assert verify_password("wrong", stored) is False


def test_md5_hex_hashes_are_rejected():
    digest = hashlib.md5(b"secret").hexdigest()
    assert len(digest) == 32
    assert verify_password("secret", digest) is False
    assert verify_password("secret", digest[:16]) is False
    assert verify_password("secret", "not-a-hash") is False