"""Secret storage.

Primary backend is the OS keychain (Windows Credential Manager, macOS Keychain,
Secret Service on Linux) via ``keyring`` — nothing sensitive on disk.

Fallback: in headless environments (e.g. a Docker container) there's no keychain,
so we fall back to a JSON file under ``data/`` (gitignored, chmod 600 where
supported). Set ``MANDOM_SECRET_BACKEND=file`` to force the file store, or
``MANDOM_SECRETS_FILE=/path`` to choose its location.

We deliberately store only the refresh token + client credentials — never the
account password.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import keyring
from keyring.errors import KeyringError

from app.config import ROOT

SERVICE = "mandom"
_DEFAULT_FILE = ROOT / "data" / "secrets.json"


def _force_file() -> bool:
    return bool(os.environ.get("MANDOM_SECRETS_FILE")) or \
        os.environ.get("MANDOM_SECRET_BACKEND") == "file"


def _file_path() -> Path:
    custom = os.environ.get("MANDOM_SECRETS_FILE")
    return Path(custom) if custom else _DEFAULT_FILE


def _read_file() -> dict:
    p = _file_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _write_file(data: dict) -> None:
    p = _file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def set_secret(key: str, value: str) -> None:
    if not _force_file():
        try:
            keyring.set_password(SERVICE, key, value)
            return
        except (KeyringError, RuntimeError):
            pass  # no keychain backend -> fall through to file
    data = _read_file()
    data[key] = value
    _write_file(data)


def get_secret(key: str) -> str | None:
    if not _force_file():
        try:
            value = keyring.get_password(SERVICE, key)
            if value is not None:
                return value
        except (KeyringError, RuntimeError):
            pass
    return _read_file().get(key)


def delete_secret(key: str) -> None:
    if not _force_file():
        try:
            keyring.delete_password(SERVICE, key)
        except (KeyringError, RuntimeError):
            pass
    data = _read_file()
    if key in data:
        del data[key]
        _write_file(data)
