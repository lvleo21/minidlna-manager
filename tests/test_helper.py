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


@pytest.fixture
def installed_via_package_db(monkeypatch) -> dict:
    monkeypatch.setattr(helper.shutil, "which", _which_only("apt-get", "dpkg"))
    monkeypatch.setattr(helper.subprocess, "run", lambda *a, **k: FakeCompletedProcess(returncode=0))
    return helper.is_installed()


def test_is_installed_true_when_package_db_reports_installed(installed_via_package_db):
    assert installed_via_package_db["installed"] is True


def test_is_installed_reports_the_detected_package_manager(installed_via_package_db):
    assert installed_via_package_db["package_manager"] == "apt"


def test_is_installed_false_when_nothing_found(monkeypatch):
    monkeypatch.setattr(helper.shutil, "which", _which_only())
    result = helper.is_installed()
    assert result["installed"] is False


@pytest.fixture
def install_result_without_manager(monkeypatch) -> dict:
    monkeypatch.setattr(helper.shutil, "which", _which_only())
    return helper.install_package()


def test_install_package_fails_when_no_manager_found(install_result_without_manager):
    assert install_result_without_manager["ok"] is False


def test_install_package_reports_no_manager_detected(install_result_without_manager):
    assert install_result_without_manager["package_manager"] is None


@pytest.fixture
def install_run(monkeypatch) -> dict:
    monkeypatch.setattr(helper.shutil, "which", _which_only("dnf"))
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompletedProcess(returncode=0, stdout="done")

    monkeypatch.setattr(helper.subprocess, "run", fake_run)
    result = helper.install_package()
    return {"captured": captured, "result": result}


def test_install_package_runs_expected_command(install_run):
    assert install_run["captured"]["command"] == ["dnf", "install", "-y", "minidlna"]


def test_install_package_returns_the_command_result(install_run):
    assert install_run["result"] == {
        "ok": True,
        "package_manager": "dnf",
        "exit_code": 0,
        "stdout": "done",
        "stderr": "",
    }


@pytest.fixture
def install_timeout_result(monkeypatch) -> dict:
    monkeypatch.setattr(helper.shutil, "which", _which_only("apt-get"))

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=1)

    monkeypatch.setattr(helper.subprocess, "run", fake_run)
    return helper.install_package()


def test_install_package_reports_timeout_as_failure(install_timeout_result):
    assert install_timeout_result["ok"] is False


def test_install_package_reports_timeout_message(install_timeout_result):
    assert "tempo limite" in install_timeout_result["error"]


@pytest.fixture
def systemctl_restart_run(monkeypatch) -> dict:
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompletedProcess(returncode=0, stdout="ok")

    monkeypatch.setattr(helper.subprocess, "run", fake_run)
    result = helper.systemctl_action("restart")
    return {"captured": captured, "result": result}


def test_systemctl_action_runs_expected_command(systemctl_restart_run):
    assert systemctl_restart_run["captured"]["command"] == ["systemctl", "restart", "minidlna.service"]


def test_systemctl_action_reports_success(systemctl_restart_run):
    assert systemctl_restart_run["result"]["ok"] is True


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


@pytest.fixture
def systemctl_timeout_result(monkeypatch) -> dict:
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=1)

    monkeypatch.setattr(helper.subprocess, "run", fake_run)
    return helper.systemctl_action("start")


def test_systemctl_action_reports_timeout_as_failure(systemctl_timeout_result):
    assert systemctl_timeout_result["ok"] is False


def test_systemctl_action_reports_timeout_message(systemctl_timeout_result):
    assert "tempo limite" in systemctl_timeout_result["error"]


@pytest.fixture
def written_config_target(tmp_path) -> Path:
    target = tmp_path / "minidlna.conf"
    helper.write_config("port=8200\n", path=str(target))
    return target


def test_write_config_writes_the_expected_content(written_config_target):
    assert written_config_target.read_text() == "port=8200\n"


def test_write_config_reports_success(tmp_path):
    target = tmp_path / "minidlna.conf"
    result = helper.write_config("port=8200\n", path=str(target))
    assert result == {"ok": True, "path": str(target)}


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


@pytest.fixture
def empty_content_write_result(tmp_path) -> dict:
    target = tmp_path / "minidlna.conf"
    return {"result": helper.write_config("   \n", path=str(target)), "target": target}


def test_write_config_rejects_empty_content(empty_content_write_result):
    assert empty_content_write_result["result"]["ok"] is False


def test_write_config_leaves_no_file_behind_for_empty_content(empty_content_write_result):
    assert not empty_content_write_result["target"].exists()


@pytest.fixture
def write_config_os_error_result(tmp_path) -> dict:
    target = tmp_path / "no-such-dir" / "minidlna.conf"
    return helper.write_config("port=8200\n", path=str(target))


def test_write_config_reports_os_errors_as_failure(write_config_os_error_result):
    assert write_config_os_error_result["ok"] is False


def test_write_config_os_error_result_includes_the_path(write_config_os_error_result):
    assert "path" in write_config_os_error_result


def test_main_rejects_unknown_action():
    with pytest.raises(SystemExit):
        helper.main(["bogus-action"])


@pytest.fixture
def is_installed_dispatch(monkeypatch, capsys) -> dict:
    monkeypatch.setattr(helper, "is_installed", lambda: {"ok": True, "installed": True})
    exit_code = helper.main(["is-installed"])
    return {"exit_code": exit_code, "stdout": capsys.readouterr().out}


def test_main_dispatches_is_installed_with_success_exit_code(is_installed_dispatch):
    assert is_installed_dispatch["exit_code"] == 0


def test_main_dispatches_is_installed_prints_the_result(is_installed_dispatch):
    assert '"installed": true' in is_installed_dispatch["stdout"]


@pytest.fixture
def home_readable_run(monkeypatch, tmp_path) -> dict:
    override_dir = tmp_path / "minidlna.service.d"
    monkeypatch.setattr(helper, "SANDBOX_OVERRIDE_DIR", str(override_dir))
    monkeypatch.setattr(helper, "SANDBOX_OVERRIDE_PATH", str(override_dir / "override.conf"))

    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(helper.subprocess, "run", fake_run)

    return {
        "result": helper.ensure_home_readable(),
        "captured": captured,
        "override_path": override_dir / "override.conf",
    }


def test_ensure_home_readable_reports_success(home_readable_run):
    assert home_readable_run["result"] == {"ok": True}


def test_ensure_home_readable_reloads_systemd(home_readable_run):
    assert home_readable_run["captured"]["command"] == ["systemctl", "daemon-reload"]


def test_ensure_home_readable_writes_the_dropin_content(home_readable_run):
    assert home_readable_run["override_path"].read_text() == "[Service]\nProtectHome=read-only\n"


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

    # the config write itself succeeded; the sandbox tweak is best-effort
    assert exit_code == 0


@pytest.fixture
def failed_write_dispatch(monkeypatch) -> dict:
    monkeypatch.setattr(helper, "write_config", lambda content: {"ok": False, "error": "disk full"})
    calls = []
    monkeypatch.setattr(helper, "ensure_home_readable", lambda: calls.append(1))
    monkeypatch.setattr(helper.sys, "stdin", type("_S", (), {"read": staticmethod(lambda: "port=8200\n")})())

    exit_code = helper.main(["write-config"])
    return {"exit_code": exit_code, "ensure_home_readable_calls": calls}


def test_write_config_dispatch_fails_when_write_fails(failed_write_dispatch):
    assert failed_write_dispatch["exit_code"] == 1


def test_write_config_dispatch_skips_home_access_when_write_fails(failed_write_dispatch):
    assert failed_write_dispatch["ensure_home_readable_calls"] == []
