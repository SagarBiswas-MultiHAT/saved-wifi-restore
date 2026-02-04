# wifi_recover

**Recover your saved Windows Wi-Fi profiles with clear, auditable consent before any secret is shown.**

`wifi_recover` is a Windows-only utility that wraps `netsh wlan` commands in a consent-first workflow so that you can enumerate saved profiles and (optionally) reveal their cleartext keys. It is built for administrators and desktop support engineers who need to recover credentials they already own, not for abuse.

## Table of contents

1. [Why this project exists](#why-this-project-exists)
2. [Safety-first rules](#safety-first-rules)
3. [Quick start](#quick-start)
4. [CLI reference](#cli-reference)
5. [Typical workflows & examples](#typical-workflows--examples)
6. [Consent and export flows](#consent-and-export-flows)
7. [Output formats](#output-formats)
8. [Security guidance](#security-guidance)
9. [Development notes](#development-notes)
10. [Troubleshooting](#troubleshooting)
11. [Project layout](#project-layout)

## Why this project exists

Windows already has the plumbing (`netsh wlan show profiles`, `netsh wlan show profile ... key=clear`) to list profiles and reveal passwords, but the native workflow is noisy, localized, and lacks guardrails. `wifi_recover`:

- enforces a Windows-only, elevated context before touching secrets,
- demands typed, explicit consent before showing or exporting keys,
- parses `netsh` output in many languages by normalizing tokens,
- masks secrets by default and enables optional encrypted exports,
- keeps everything local with no telemetry, uploads, or remote interactions.

The tool is meant to be safe by default, auditable, and easy enough that anyone with admin rights can recover credentials they are entitled to.

## Safety-first rules

1. **Windows only.** The CLI refuses to run on macOS or Linux.
2. **Administrator required.** Clear messaging tells you to relaunch PowerShell with elevation.
3. **Typed consent.** Secrets are never shown unless you type `I confirm I own this machine and have permission to access these credentials`.
4. **Local-only exports.** Any JSON export requires another typed confirmation (`LOCAL ONLY`) and blocks UNC paths.
5. **Encrypted-by-default exports.** Plain-text export requires an explicit `--export-plain` flag with additional confirmation.
6. **Masking.** Output secrets can be masked via `--mask` so you don’t accidentally expose them on-screen.
7. **Dry-run.** `--dry-run` lets you prove the command flow works without invoking `netsh`.

## Quick start

1. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install the package in editable mode for iterative work:
   ```powershell
   pip install -e .
   ```
3. Run the default (list-only) command:
   ```powershell
   python -m wifi_recover --list
   ```

If you are not in the repository root you can either install the package first or set `PYTHONPATH=src` before running. For quick demos you can omit installation and run `python -m wifi_recover --list` from the repo root directly.

## CLI reference

Launch the command with:

```powershell
python -m wifi_recover [OPTIONS]
```

| Flag                    | What it does                                                       | Notes                                                                                                       |
| ----------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| `--list`                | Lists saved Wi-Fi profile names without requesting consent.        | This is the default action when you don’t request secrets. No typed consent is needed.                      |
| `--show PROFILE`        | Shows the cleartext password for one profile.                      | Triggers the consent prompt; secrets are only shown if you type the exact consent string.                   |
| `--all`                 | Shows every stored password.                                       | Same consent guard as `--show`, but works across all profiles.                                              |
| `--export FILE`         | Writes profiles (and keys, if allowed) to `FILE` in plain JSON.    | Additional confirmation is required unless you also pass `--export-plain`.                                  |
| `--encrypt-export FILE` | Writes an encrypted JSON blob to `FILE` using a passphrase prompt. | Recommended for any export that includes secrets.                                                           |
| `--export-plain`        | Allows plain-text export even when secrets are being shown.        | Requires two confirmations: local-only and `EXPORT PLAIN`.                                                  |
| `--mask` / `--no-mask`  | Mask (or unmask) passwords in the terminal output.                 | When `--mask` is enabled, only the last two characters are visible. Default is unmasked but can be toggled. |
| `--dry-run`             | Simulates every action without calling `netsh`.                    | Useful in documentation, demos, or automation pipelines. No consent prompt appears.                         |
| `--log-level LEVEL`     | Set log verbosity (`INFO`, `DEBUG`, `WARNING`).                    | Helpful when debugging parsing or export issues.                                                            |

Combining flags is permitted; e.g., `--all --mask --encrypt-export secrets.enc` enumerates all keys, masks them on-screen, and writes an encrypted dump.

## Typical workflows & examples

### Most common (list profiles only)

```powershell
python -m wifi_recover --list
```

Output:

```
Wi-Fi Profile                            | Password
----------------------------------------+---------
Black Hat v3.0                           |
Hidden                                   |
```

### Reveal a single secret (consent required)

```powershell
python -m wifi_recover --show "HomeWifi"
```

After you type the consent string, the window prints the cleartext key for `HomeWifi`.

### Reveal every password (consent required)

```powershell
python -m wifi_recover --all
```

Consent is requested once, and all stored keys are shown (masking optional with `--mask`).

### Encrypted export of secrets (recommended)

```powershell
python -m wifi_recover --all --encrypt-export secrets.enc
```

You will be prompted for:

1. The consent string.
2. Local-only export confirmation.
3. A passphrase (typed twice) to encrypt the JSON payload using Fernet.

This flow never writes plain text credentials to disk.

### Plain-text export (only if you truly need it)

```powershell
python -m wifi_recover --all --export secrets.json --export-plain
```

This triggers all three confirmations: consent, local-only, and the `EXPORT PLAIN` warning. Avoid this unless you plan to securely delete the file immediately.

### Dry-run for documentation/CI

```powershell
python -m wifi_recover --all --dry-run
```

The CLI logs what it would do, including the consent check and export path, but never calls `netsh`.

## Consent and export flows

1. Running `--show` or `--all` with secrets forces the **consent prompt**:
   > `I confirm I own this machine and have permission to access these credentials`
2. Any export (`--export` or `--encrypt-export`) additionally requires the **local-only confirmation**:
   > `Type "LOCAL ONLY" to confirm:`
3. If you also request plain JSON, you must then type:
   > `Type "EXPORT PLAIN" to confirm:`
4. Exports respect local-only rules:
   - UNC paths (`\\server\\share`) are rejected.
   - Encrypted exports are default; no secrets are written unless you explicitly allow them.
   - Passphrases are never accepted via CLI flags and are entered interactively.

## Output formats

- **Terminal table:** shows `Wi-Fi Profile` and `Password`. Password cells are empty unless consent is granted and `--show`/`--all` is used, in which case the key is either shown or masked (`--mask`).
- **Plain export JSON:** contains `generated_at` (ISO 8601 UTC) and a list of `{ name, key? }` pairs. Keys are emitted only when the CLI was allowed to read secrets.
- **Encrypted export JSON:** stores Fernet metadata (`salt`, iterations, cipher text). The CLI later decrypts the file only when you provide the same passphrase.

## Security guidance

1. Keep exports on encrypted disks and delete them once recovery is complete.
2. If you choose plain export, delete the file using secure deletion tools or move it into a secure password manager immediately.
3. Never share the encryption passphrase; losing it makes the secrets unrecoverable.
4. Run `wifi_recover` only on machines you control or administer.
5. The tool never calls home, uploads data, or modifies networking state.

## Development notes

- Install for local iteration: `pip install -e .`
- Run tests with:
  ```powershell
  $env:PYTHONPATH='src'; pytest tests/test_windows_netsh.py
  ```
- Type checking:
  ```powershell
  mypy src
  ```
- Logging configuration lives in `src/wifi_recover/logger.py`, paring the same log level as the CLI.
- The CLI entry point is `src/wifi_recover/cli.py` and the Windows logic is in `src/wifi_recover/windows_netsh.py`.

Pre-commit hooks are configured via `.pre-commit-config.yaml` and fire automatically in CI.

## Troubleshooting

| Symptom                                                   | Fix                                                                                                                          |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `ModuleNotFoundError: wifi_recover`                       | Run from the repo root, set `PYTHONPATH=src`, or install with `pip install -e .`.                                            |
| `PermissionError: Administrator privileges are required.` | Re-run the command in an elevated PowerShell prompt (right-click > Run as Administrator).                                    |
| Consent prompt refused                                    | Type the consent string exactly. Extra spaces or wrong casing will reject the input.                                         |
| `netsh failed: ...`                                       | Ensure the WLAN service is running, you have the correct profile name, and the command works manually outside of the script. |
| Export path rejected                                      | Use a local path (no UNC). Verify the directory exists or the tool has permission to write there.                            |

## Project layout

```
src/wifi_recover/
  cli.py          # Typer CLI, logging, consent flow, exports
  windows_netsh.py # netsh invocation and locale-aware parsing
  utils.py         # Consent string, masking, encryption helpers
  logger.py        # Structured logging configuration
wifi_recover/       # Local shim for `python -m wifi_recover` without installation
tests/              # Pytest verification, includes parsing coverage and subprocess mocks
```

CI runs on every PR via `.github/workflows/ci.yml`, including linting, formatting, and type checks.
