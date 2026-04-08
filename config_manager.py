import json
import os
from cryptography.fernet import Fernet

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".tiger_release_helper.json")
KEY_FILE    = os.path.join(os.path.expanduser("~"), ".tiger_release_helper.key")


def _get_or_create_key() -> bytes:
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, 'rb') as f:
            return f.read()
    key = Fernet.generate_key()
    with open(KEY_FILE, 'wb') as f:
        f.write(key)
    return key


def _cipher() -> Fernet:
    return Fernet(_get_or_create_key())


def encrypt_token(token: str) -> str:
    if not token:
        return ""
    return _cipher().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    if not encrypted:
        return ""
    try:
        return _cipher().decrypt(encrypted.encode()).decode()
    except Exception:
        return ""


def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config: dict):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
