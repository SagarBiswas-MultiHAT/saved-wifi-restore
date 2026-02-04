"""Utility helpers for wifi_recover."""

from __future__ import annotations

import base64
import getpass
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Callable, Dict

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

CONSENT_STRING = "I confirm I own this machine and have permission to access these credentials"
LOCAL_ONLY_STRING = "LOCAL ONLY"
PLAIN_EXPORT_STRING = "EXPORT PLAIN"

ETHICAL_STATEMENT = (
    "This tool is intended only for credential recovery on systems you own "
    "or where you have explicit administrative permission. Unauthorized access "
    "to credentials is illegal and unethical."
)


def normalize_text(text: str) -> str:
    """Normalize text for locale-agnostic comparisons."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def is_windows() -> bool:
    """Return True if the current platform is Windows."""
    return sys.platform == "win32"


def require_windows() -> None:
    """Raise an error if not running on Windows."""
    if not is_windows():
        raise RuntimeError("wifi_recover runs only on Windows.")


def is_admin() -> bool:
    """Return True if the current process has elevated privileges."""
    if not is_windows():
        return False
    try:
        import ctypes  # Local import to keep module importable on non-Windows.

        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return False
        return bool(windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def require_admin() -> None:
    """Raise an error if the process is not running as administrator."""
    if not is_admin():
        raise PermissionError(
            "Administrator privileges are required. "
            "Open PowerShell as Administrator and re-run the command."
        )


def prompt_consent(
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> bool:
    """Prompt for the exact consent string before sensitive actions."""
    print_func(ETHICAL_STATEMENT)
    print_func("\nTo continue, type the exact confirmation string:")
    print_func(CONSENT_STRING)
    response = input_func("Confirmation: ")
    return response.strip() == CONSENT_STRING


def confirm_local_only_export(
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> bool:
    """Confirm that export stays local (no remote upload or network share)."""
    print_func("Export must remain local. This tool does not upload data.")
    response = input_func(f'Type "{LOCAL_ONLY_STRING}" to confirm: ')
    return response.strip() == LOCAL_ONLY_STRING


def confirm_plain_export(
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> bool:
    """Confirm explicit intent to export secrets in plain text."""
    print_func("Plain-text export is not recommended.")
    response = input_func(f'Type "{PLAIN_EXPORT_STRING}" to confirm: ')
    return response.strip() == PLAIN_EXPORT_STRING


def mask_secret(secret: str | None, show_last: int = 2) -> str:
    """Return a masked representation of a secret."""
    if not secret:
        return ""
    if show_last <= 0 or len(secret) <= show_last:
        return "*" * len(secret)
    return "*" * (len(secret) - show_last) + secret[-show_last:]


def ensure_local_path(path: Path) -> None:
    """Reject UNC or obviously remote paths."""
    path_str = str(path)
    if path_str.startswith("\\\\"):
        raise ValueError("UNC paths are not allowed for exports. Use a local path.")


def _derive_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt_json_payload(data: Dict[str, object], passphrase: str) -> Dict[str, object]:
    """Encrypt a JSON-serializable dict with a passphrase using Fernet."""
    iterations = 390000
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt, iterations)
    fernet = Fernet(key)
    plaintext = json.dumps(data, separators=(",", ":")).encode("utf-8")
    token = fernet.encrypt(plaintext)
    return {
        "version": 1,
        "kdf": {
            "name": "PBKDF2HMAC",
            "hash": "SHA256",
            "iterations": iterations,
            "salt": base64.b64encode(salt).decode("ascii"),
        },
        "fernet": {
            "ciphertext": base64.b64encode(token).decode("ascii"),
        },
    }


def write_json(path: Path, data: Dict[str, object]) -> None:
    """Write JSON to disk, creating parent directories when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def encrypt_json_to_file(path: Path, data: Dict[str, object], passphrase: str) -> None:
    """Encrypt a JSON payload and write it to disk."""
    payload = encrypt_json_payload(data, passphrase)
    write_json(path, payload)


def prompt_passphrase() -> str:
    """Prompt for an encryption passphrase twice and return it."""
    first = getpass.getpass("Passphrase: ")
    if not first:
        raise ValueError("Passphrase cannot be empty.")
    second = getpass.getpass("Confirm passphrase: ")
    if first != second:
        raise ValueError("Passphrases do not match.")
    return first
