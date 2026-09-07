import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "helper"))
import minidlna_manager_helper as helper


class FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _which_only(*allowed):
    def fake_which(binary):
        return f"/usr/bin/{binary}" if binary in allowed else None

    return fake_which


def test_detect_package_manager_prefers_apt(monkeypatch):
    monkeypatch.setattr(helper.shutil, "which", _which_only("apt-get", "dnf"))
    assert helper.detect_package_manager() == "apt"


def test_detect_package_manager_falls_back_to_pacman(monkeypatch):
    monkeypatch.setattr(helper.shutil, "which", _which_only("pacman", "zypper"))
    assert helper.detect_package_manager() == "pacman"


def test_detect_package_manager_returns_none_when_nothing_found(monkeypatch):
    monkeypatch.setattr(helper.shutil, "which", _which_only())
    assert helper.detect_package_manager() is None


def test_is_installed_true_when_binary_present(monkeypatch):
    monkeypatch.setattr(helper.shutil, "which", _which_only("minidlnad"))
    result = helper.is_installed()
    assert result == {
        "ok": True,
        "installed": True,
        "binary_path": "/usr/bin/minidlnad",
        "package_manager": None,
    }


def test_is_installed_true_when_package_db_reports_installed(monkeypatch):
    monkeypatch.setattr(helper.shutil, "which", _which_only("apt-get", "dpkg"))
    monkeypatch.setattr(helper.subprocess, "run", lambda *a, **k: FakeCompletedProcess(returncode=0))
    result = helper.is_installed()
    assert result["installed"] is True
    assert result["package_manager"] == "apt"


def test_is_installed_false_when_nothing_found(monkeypatch):
    monkeypatch.setattr(helper.shutil, "which", _which_only())
    result = helper.is_installed()
    assert result["installed"] is False


def test_install_package_errors_when_no_manager_found(monkeypatch):
    monkeypatch.setattr(helper.shutil, "which", _which_only())
    result = helper.install_package()
    assert result["ok"] is False
    assert result["package_manager"] is None


def test_install_package_runs_expected_command(monkeypatch):
    monkeypatch.setattr(helper.shutil, "which", _which_only("dnf"))
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompletedProcess(returncode=0, stdout="done")

    monkeypatch.setattr(helper.subprocess, "run", fake_run)
    result = helper.install_package()
    assert captured["command"] == ["dnf", "install", "-y", "minidlna"]
    assert result == {
        "ok": True,
        "package_manager": "dnf",
        "exit_code": 0,
        "stdout": "done",
        "stderr": "",
    }


def test_install_package_reports_timeout(monkeypatch):
    monkeypatch.setattr(helper.shutil, "which", _which_only("apt-get"))

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=1)

    monkeypatch.setattr(helper.subprocess, "run", fake_run)
    result = helper.install_package()
    assert result["ok"] is False
    assert "tempo limite" in result["error"]


def test_systemctl_action_success(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompletedProcess(returncode=0, stdout="ok")

    monkeypatch.setattr(helper.subprocess, "run", fake_run)
    result = helper.systemctl_action("restart")
    assert captured["command"] == ["systemctl", "restart", "minidlna.service"]
    assert result["ok"] is True


def test_systemctl_action_reports_failure(monkeypatch):
    monkeypatch.setattr(
        helper.subprocess, "run", lambda *a, **k: FakeCompletedProcess(returncode=1, stderr="nope")
    )
    result = helper.systemctl_action("stop")
    assert result == {
        "ok": False,
        "action": "stop",
        "exit_code": 1,
        "stdout": "",
        "stderr": "nope",
    }


def test_systemctl_action_reports_timeout(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=1)

    monkeypatch.setattr(helper.subprocess, "run", fake_run)
    result = helper.systemctl_action("start")
    assert result["ok"] is False
    assert "tempo limite" in result["error"]


def test_write_config_writes_content_atomically(tmp_path):
    target = tmp_path / "minidlna.conf"
    result = helper.write_config("port=8200\n", path=str(target))
    assert result == {"ok": True, "path": str(target)}
    assert target.read_text() == "port=8200\n"


def test_write_config_preserves_existing_file_mode(tmp_path):
    target = tmp_path / "minidlna.conf"
    target.write_text("port=8000\n")
    target.chmod(0o644)

    helper.write_config("port=8200\n", path=str(target))

    assert target.stat().st_mode & 0o777 == 0o644


def test_write_config_defaults_to_world_readable_for_new_file(tmp_path):
    target = tmp_path / "minidlna.conf"

    helper.write_config("port=8200\n", path=str(target))

    assert target.stat().st_mode & 0o777 == 0o644


def test_write_config_rejects_empty_content(tmp_path):
    target = tmp_path / "minidlna.conf"
    result = helper.write_config("   \n", path=str(target))
    assert result["ok"] is False
    assert not target.exists()


def test_write_config_reports_os_errors(tmp_path):
    target = tmp_path / "no-such-dir" / "minidlna.conf"
    result = helper.write_config("port=8200\n", path=str(target))
    assert result["ok"] is False
    assert "path" in result


def test_main_rejects_unknown_action():
    with pytest.raises(SystemExit):
        helper.main(["bogus-action"])


def test_main_dispatches_is_installed(monkeypatch, capsys):
    monkeypatch.setattr(helper, "is_installed", lambda: {"ok": True, "installed": True})
    exit_code = helper.main(["is-installed"])
    assert exit_code == 0
    assert '"installed": true' in capsys.readouterr().out


def test_ensure_home_readable_writes_dropin_and_reloads(monkeypatch, tmp_path):
    override_dir = tmp_path / "minidlna.service.d"
    monkeypatch.setattr(helper, "SANDBOX_OVERRIDE_DIR", str(override_dir))
    monkeypatch.setattr(helper, "SANDBOX_OVERRIDE_PATH", str(override_dir / "override.conf"))

    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(helper.subprocess, "run", fake_run)

    result = helper.ensure_home_readable()

    assert result == {"ok": True}
    assert captured["command"] == ["systemctl", "daemon-reload"]
    assert (override_dir / "override.conf").read_text() == "[Service]\nProtectHome=read-only\n"


def test_ensure_home_readable_reports_daemon_reload_failure(monkeypatch, tmp_path):
    override_dir = tmp_path / "minidlna.service.d"
    monkeypatch.setattr(helper, "SANDBOX_OVERRIDE_DIR", str(override_dir))
    monkeypatch.setattr(helper, "SANDBOX_OVERRIDE_PATH", str(override_dir / "override.conf"))

    def fake_run(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(helper.subprocess, "run", fake_run)

    result = helper.ensure_home_readable()
    assert result["ok"] is False


def test_write_config_dispatch_also_ensures_home_access(monkeypatch):
    monkeypatch.setattr(helper, "write_config", lambda content: {"ok": True, "path": "/etc/minidlna.conf"})
    monkeypatch.setattr(helper, "ensure_home_readable", lambda: {"ok": False, "error": "boom"})
    monkeypatch.setattr(helper.sys, "stdin", type("_S", (), {"read": staticmethod(lambda: "port=8200\n")})())

    exit_code = helper.main(["write-config"])

    assert exit_code == 0  # the config write itself succeeded; the sandbox tweak is best-effort


def test_write_config_dispatch_skips_home_access_when_write_fails(monkeypatch):
    monkeypatch.setattr(helper, "write_config", lambda content: {"ok": False, "error": "disk full"})
    calls = []
    monkeypatch.setattr(helper, "ensure_home_readable", lambda: calls.append(1))
    monkeypatch.setattr(helper.sys, "stdin", type("_S", (), {"read": staticmethod(lambda: "port=8200\n")})())

    exit_code = helper.main(["write-config"])

    assert exit_code == 1
    assert calls == []
