from __future__ import annotations

from cryptography.fernet import Fernet

from oj.config import get_settings


def _fernet() -> Fernet:
    path = get_settings().data_dir / "secret.key"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Fernet.generate_key())
    return Fernet(path.read_bytes())


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()
