"""Command-line interface for wifi_recover."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import typer

from . import windows_netsh
from .logger import configure_logging, get_logger
from .utils import (
    CONSENT_STRING,
    confirm_local_only_export,
    confirm_plain_export,
    ensure_local_path,
    mask_secret,
    prompt_consent,
    prompt_passphrase,
    require_admin,
    require_windows,
    write_json,
    encrypt_json_to_file,
)

app = typer.Typer(add_completion=False, help="Recover saved Wi-Fi profiles with explicit consent.")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_export_data(entries: List[windows_netsh.WifiProfile]) -> Dict[str, object]:
    return {
        "generated_at": _now_iso(),
        "profiles": [
            {"name": entry.name, **({"key": entry.key} if entry.key is not None else {})}
            for entry in entries
        ],
    }


@app.command()
def main(
    list_flag: bool = typer.Option(
        False,
        "--list",
        help="List saved profiles (default when no other action is selected).",
    ),
    show: Optional[str] = typer.Option(
        None, "--show", help="Show password for a specific profile."
    ),
    all_profiles: bool = typer.Option(
        False, "--all", help="Show passwords for all profiles."
    ),
    export: Optional[Path] = typer.Option(
        None, "--export", help="Export results as local JSON."
    ),
    encrypt_export: Optional[Path] = typer.Option(
        None,
        "--encrypt-export",
        help="Export encrypted JSON using a passphrase prompt.",
    ),
    export_plain: bool = typer.Option(
        False,
        "--export-plain",
        help="Allow plain-text export of secrets (not recommended).",
    ),
    mask: bool = typer.Option(
        False,
        "--mask/--no-mask",
        help="Mask passwords in console output.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simulate actions without running netsh."
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging level (INFO, DEBUG, WARNING)."
    ),
) -> None:
    """Recover Wi-Fi profiles and optionally cleartext keys on Windows."""
    configure_logging(log_level)
    logger = get_logger(__name__)

    if show and all_profiles:
        typer.echo("Choose only one of --show or --all.")
        raise typer.Exit(code=2)

    if export and encrypt_export:
        typer.echo("Choose only one of --export or --encrypt-export.")
        raise typer.Exit(code=2)

    list_only = list_flag or (not show and not all_profiles)
    include_secrets = bool(show or all_profiles)

    try:
        require_windows()
        require_admin()
    except (RuntimeError, PermissionError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    if dry_run:
        logger.info("dry run enabled", extra={"event": "dry_run"})

    if include_secrets and not dry_run:
        if not prompt_consent():
            typer.echo("Consent not granted. Aborting.")
            raise typer.Exit(code=1)

    export_path = encrypt_export or export
    if export_path is not None:
        try:
            ensure_local_path(export_path)
        except ValueError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1)
        if not confirm_local_only_export():
            typer.echo("Local-only confirmation not granted. Aborting.")
            raise typer.Exit(code=1)

    if include_secrets and export and not encrypt_export and not export_plain:
        typer.echo(
            "Plain export of secrets is disabled by default. "
            "Use --encrypt-export (recommended) or add --export-plain."
        )
        raise typer.Exit(code=2)

    if include_secrets and export_plain and not dry_run:
        if not confirm_plain_export():
            typer.echo("Plain export not confirmed. Aborting.")
            raise typer.Exit(code=1)

    try:
        if list_only:
            profiles = windows_netsh.list_profiles(dry_run=dry_run)
            entries = [windows_netsh.WifiProfile(name=name) for name in profiles]
        else:
            if show:
                profiles = [show]
            else:
                profiles = windows_netsh.list_profiles(dry_run=dry_run)
            entries = windows_netsh.get_profiles_with_keys(
                profiles, dry_run=dry_run, allow_secret=True
            )
    except windows_netsh.NetshError as exc:
        typer.echo(f"netsh failed: {exc}")
        raise typer.Exit(code=1)
    except windows_netsh.SensitiveOperationError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    header = f"{'Wi-Fi Profile':<40} | Password"
    typer.echo(header)
    typer.echo("-" * len(header))
    for entry in entries:
        password = ""
        if include_secrets and entry.key is not None:
            password = mask_secret(entry.key) if mask else entry.key
        typer.echo(f"{entry.name:<40} | {password}")

    logger.info(
        "profiles processed",
        extra={"event": "profiles", "count": len(entries), "secrets": include_secrets},
    )

    if export_path is None or dry_run:
        if dry_run:
            typer.echo("Dry run: no files written.")
        return

    data = _build_export_data(entries)

    try:
        if encrypt_export is not None:
            passphrase = prompt_passphrase()
            encrypt_json_to_file(export_path, data, passphrase)
        else:
            write_json(export_path, data)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo(f"Exported results to {export_path}")


if __name__ == "__main__":
    app()
