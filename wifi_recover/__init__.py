"""Local shim package to allow running from the repo without installation."""

from __future__ import annotations

from pathlib import Path
import pkgutil

__all__ = ["__version__"]
__version__ = "0.1.0"

# Extend the package search path to include the src layout.
__path__ = pkgutil.extend_path(__path__, __name__)  # type: ignore[name-defined]
_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "wifi_recover"
if _SRC_PACKAGE.exists():
    __path__.append(str(_SRC_PACKAGE))  # type: ignore[attr-defined]
