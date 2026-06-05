"""Secret storage via the OS keychain (Windows Credential Manager, macOS
Keychain, Secret Service on Linux). Nothing sensitive is written to disk in
plaintext or committed to the repo.

We deliberately store only the *refresh token* and client credentials — never
the account password (it's used once during login and discarded).
"""

from __future__ import annotations

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

SERVICE = "mandom"


def set_secret(key: str, value: str) -> None:
    keyring.set_password(SERVICE, key, value)


def get_secret(key: str) -> str | None:
    try:
        return keyring.get_password(SERVICE, key)
    except KeyringError:
        return None


def delete_secret(key: str) -> None:
    try:
        keyring.delete_password(SERVICE, key)
    except (PasswordDeleteError, KeyringError):
        pass
