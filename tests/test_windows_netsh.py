import subprocess

import pytest

from wifi_recover import windows_netsh


def test_parse_profiles_english() -> None:
    output = """
Profiles on interface Wi-Fi:
Group policy profiles (read only)
---------------------------------
    <None>

User profiles
-------------
    All User Profile     : HomeWifi
    All User Profile     : CafeNet
"""
    assert windows_netsh.parse_profile_names(output) == ["HomeWifi", "CafeNet"]


def test_parse_profiles_spanish() -> None:
    output = """
Perfiles en interfaz Wi-Fi:
    Perfil de todos los usuarios : Casa
    Perfil de todos los usuarios : Oficina
"""
    assert windows_netsh.parse_profile_names(output) == ["Casa", "Oficina"]


def test_parse_key_content_spanish() -> None:
    output = """
Configuracion del perfil
    Contenido de la clave : clave-secreta
"""
    assert windows_netsh.parse_key_content(output) == "clave-secreta"


def test_parse_key_content_prefers_key_content_over_security_key() -> None:
    output = """
Profile Example on interface Wi-Fi:
    Security key            : Present
    Key Content            : p@ssw0rd
"""
    assert windows_netsh.parse_key_content(output) == "p@ssw0rd"


def test_run_netsh_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stdout="", stderr="Access is denied.")

    monkeypatch.setattr(windows_netsh.subprocess, "run", fake_run)
    with pytest.raises(windows_netsh.NetshError):
        windows_netsh.run_netsh(["show", "profiles"])


def test_list_and_get_key_with_mocked_netsh(monkeypatch: pytest.MonkeyPatch) -> None:
    profiles_output = """
User profiles
-------------
    All User Profile     : HomeWifi
    All User Profile     : CafeNet
"""
    profile_output = """
Profile HomeWifi on interface Wi-Fi:
    Key Content            : p@ssw0rd
"""

    def fake_run(cmd, capture_output, text):
        if cmd[:3] == ["netsh", "wlan", "show"] and cmd[3] == "profiles":
            return subprocess.CompletedProcess(cmd, 0, stdout=profiles_output, stderr="")
        if "key=clear" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=profile_output, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(windows_netsh.subprocess, "run", fake_run)

    profiles = windows_netsh.list_profiles()
    assert profiles == ["HomeWifi", "CafeNet"]

    # Simulate consent by explicitly allowing secret access.
    key = windows_netsh.get_key_for_profile("HomeWifi", allow_secret=True)
    assert key == "p@ssw0rd"
