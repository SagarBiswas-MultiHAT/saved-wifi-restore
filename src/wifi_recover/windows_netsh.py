"""Windows netsh integration and parsing logic."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set

from .utils import normalize_text


class NetshError(RuntimeError):
    """Raised when netsh returns a non-zero exit code."""


class SensitiveOperationError(RuntimeError):
    """Raised when a sensitive operation is attempted without consent."""


@dataclass(frozen=True)
class WifiProfile:
    """A Wi-Fi profile with an optional cleartext key."""

    name: str
    key: Optional[str] = None


_LINE_WITH_COLON = re.compile(r"^\s*([^:]+?)\s*:\s*(.+?)\s*$")

_PROFILE_LABEL_TOKENS = [
    "profile",
    "profil",
    "perfil",
    "profiel",
    "profilo",
]

_KEY_LABEL_TOKENS = [
    "key",
    "clave",
    "cle",
    "schlussel",
    "senha",
    "chave",
    "password",
    "passphrase",
    "contrasena",
    "motdepasse",
]

_PROFILE_LABEL_PATTERNS = [re.compile(rf"\b{re.escape(token)}\b") for token in _PROFILE_LABEL_TOKENS]
_KEY_LABEL_PATTERNS = [re.compile(rf"\b{re.escape(token)}\b") for token in _KEY_LABEL_TOKENS]

_KEY_SYNONYMS: Set[str] = {
    "key",
    "clave",
    "cle",
    "schlussel",
    "senha",
    "chave",
    "password",
    "passphrase",
    "contrasena",
    "motdepasse",
    "chiave",
    "klucz",
    "sleutel",
    "passwort",
}

_CONTENT_SYNONYMS: Set[str] = {
    "content",
    "contenido",
    "contenu",
    "conteudo",
    "contenuto",
    "inhalt",
    "material",
    "materiel",
    "materiale",
    "indhold",
    "inhoud",
}

_SECURITY_SYNONYMS: Set[str] = {
    "security",
    "seguridad",
    "securite",
    "sicherheit",
    "seguranca",
    "sicurezza",
    "bezpieczenstwo",
}


def _label_matches(label: str, patterns: Iterable[re.Pattern[str]]) -> bool:
    normalized = normalize_text(label)
    return any(pattern.search(normalized) for pattern in patterns)


def _label_has_synonym(normalized_label: str, synonyms: Set[str]) -> bool:
    words = normalized_label.split()
    return any(word in synonyms for word in words)


def _is_key_content_label(normalized_label: str) -> bool:
    return (
        _label_has_synonym(normalized_label, _KEY_SYNONYMS)
        and _label_has_synonym(normalized_label, _CONTENT_SYNONYMS)
    )


def _is_security_key_label(normalized_label: str) -> bool:
    return _label_has_synonym(normalized_label, _SECURITY_SYNONYMS)


def parse_profile_names(output: str) -> List[str]:
    """Parse Wi-Fi profile names from netsh output."""
    profiles: List[str] = []
    for line in output.splitlines():
        match = _LINE_WITH_COLON.match(line)
        if not match:
            continue
        label, value = match.groups()
        value = value.strip()
        if not value:
            continue
        if _label_matches(label, _PROFILE_LABEL_PATTERNS):
            if value not in profiles:
                profiles.append(value)
    if profiles:
        return profiles

    # Fallback: grab all colon-separated values that look like names.
    fallback: List[str] = []
    for line in output.splitlines():
        match = _LINE_WITH_COLON.match(line)
        if not match:
            continue
        _, value = match.groups()
        value = value.strip()
        if value and value not in fallback:
            fallback.append(value)
    return fallback


def parse_key_content(output: str) -> Optional[str]:
    """Parse the cleartext key from netsh profile output."""
    fallback: Optional[str] = None
    for line in output.splitlines():
        match = _LINE_WITH_COLON.match(line)
        if not match:
            continue
        label, value = match.groups()
        value = value.strip()
        if not value:
            continue
        normalized_label = normalize_text(label)
        if _is_key_content_label(normalized_label):
            return value
        if fallback is None and _label_matches(label, _KEY_LABEL_PATTERNS):
            if not _is_security_key_label(normalized_label):
                fallback = value
    return fallback


def run_netsh(args: Sequence[str], dry_run: bool = False) -> str:
    """Run netsh wlan commands and return stdout."""
    cmd = ["netsh", "wlan", *args]
    if dry_run:
        return ""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "netsh failed"
        raise NetshError(detail)
    return result.stdout


def list_profiles(dry_run: bool = False) -> List[str]:
    """List saved Wi-Fi profiles."""
    output = run_netsh(["show", "profiles"], dry_run=dry_run)
    return parse_profile_names(output)


def get_key_for_profile(
    profile: str,
    *,
    dry_run: bool = False,
    allow_secret: bool = False,
) -> Optional[str]:
    """Return the cleartext key for a profile if allowed."""
    if not allow_secret:
        raise SensitiveOperationError("Explicit consent is required to read keys.")
    if dry_run:
        return None
    output = run_netsh(["show", "profile", profile, "key=clear"], dry_run=dry_run)
    return parse_key_content(output)


def get_profiles_with_keys(
    profiles: Iterable[str],
    *,
    dry_run: bool = False,
    allow_secret: bool = False,
) -> List[WifiProfile]:
    """Return a list of profiles with optional keys."""
    results: List[WifiProfile] = []
    for name in profiles:
        key = get_key_for_profile(name, dry_run=dry_run, allow_secret=allow_secret)
        results.append(WifiProfile(name=name, key=key))
    return results
