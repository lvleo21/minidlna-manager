import subprocess

import pytest

from core import service_client


class FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_helper_path_uses_env_override(monkeypatch):
    monkeypatch.setenv("MINIDLNA_MANAGER_HELPER", "/custom/helper")
    assert service_client._helper_path() == "/custom/helper"


def test_helper_path_uses_installed_path_when_present(monkeypatch, tmp_path):
    monkeypatch.delenv("MINIDLNA_MANAGER_HELPER", raising=False)
    installed = tmp_path / "helper"
    installed.write_text("#!/bin/true\n")
    monkeypatch.setattr(service_client, "INSTALLED_HELPER_PATH", str(installed))
    assert service_client._helper_path() == str(installed)


def test_helper_path_falls_back_to_dev_path(monkeypatch):
    monkeypatch.delenv("MINIDLNA_MANAGER_HELPER", raising=False)
    monkeypatch.setattr(service_client, "INSTALLED_HELPER_PATH", "/does/not/exist")
    assert service_client._helper_path() == service_client.DEV_HELPER_PATH


@pytest.fixture
def is_installed_run(monkeypatch) -> dict:
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompletedProcess(stdout='{"ok": true, "installed": false}')

    monkeypatch.setattr(service_client.subprocess, "run", fake_run)
    result = service_client.is_installed()
    return {"captured": captured, "result": result}


def test_is_installed_runs_helper_without_pkexec(is_installed_run):
    assert is_installed_run["captured"]["command"][0] != "pkexec"


def test_is_installed_returns_the_parsed_result(is_installed_run):
    assert is_installed_run["result"] == {"ok": True, "installed": False}


PRIVILEGED_ACTIONS = [
    ("start", "start"),
    ("stop", "stop"),
    ("restart", "restart"),
    ("enable", "enable"),
    ("disable", "disable"),
    ("install_package", "install-package"),
]


@pytest.fixture(params=PRIVILEGED_ACTIONS, ids=[name for name, _ in PRIVILEGED_ACTIONS])
def privileged_action_run(request, monkeypatch) -> dict:
    func_name, expected_action = request.param
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompletedProcess(stdout='{"ok": true}')

    monkeypatch.setattr(service_client.subprocess, "run", fake_run)
    func = getattr(service_client, func_name)
    result = func()
    return {"captured": captured, "result": result, "expected_action": expected_action}


def test_privileged_actions_go_through_pkexec(privileged_action_run):
    assert privileged_action_run["captured"]["command"][0] == "pkexec"


def test_privileged_actions_pass_the_expected_action_name(privileged_action_run):
    assert privileged_action_run["captured"]["command"][-1] == privileged_action_run["expected_action"]


def test_privileged_actions_return_the_parsed_result(privileged_action_run):
    assert privileged_action_run["result"] == {"ok": True}


@pytest.fixture
def write_config_run(monkeypatch) -> dict:
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["input"] = kwargs.get("input")
        return FakeCompletedProcess(stdout='{"ok": true}')

    monkeypatch.setattr(service_client.subprocess, "run", fake_run)
    service_client.write_config("port=8200\n")
    return captured


def test_write_config_invokes_the_write_config_action(write_config_run):
    assert write_config_run["command"][-1] == "write-config"


def test_write_config_sends_content_via_stdin(write_config_run):
    assert write_config_run["input"] == "port=8200\n"


def test_run_privileged_raises_permission_denied_on_126(monkeypatch):
    monkeypatch.setattr(
        service_client.subprocess, "run", lambda *a, **k: FakeCompletedProcess(returncode=126)
    )
    with pytest.raises(service_client.PermissionDeniedError):
        service_client.start()


def test_run_privileged_raises_not_found_on_127(monkeypatch):
    monkeypatch.setattr(
        service_client.subprocess, "run", lambda *a, **k: FakeCompletedProcess(returncode=127)
    )
    with pytest.raises(service_client.HelperNotFoundError):
        service_client.start()


def test_run_privileged_raises_not_found_when_pkexec_missing(monkeypatch):
    def fake_run(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(service_client.subprocess, "run", fake_run)
    with pytest.raises(service_client.HelperNotFoundError):
        service_client.start()


def test_run_privileged_raises_timeout(monkeypatch):
    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(cmd=["pkexec"], timeout=1)

    monkeypatch.setattr(service_client.subprocess, "run", fake_run)
    with pytest.raises(service_client.HelperTimeoutError):
        service_client.start()


def test_run_unprivileged_raises_not_found_when_helper_missing(monkeypatch):
    def fake_run(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(service_client.subprocess, "run", fake_run)
    with pytest.raises(service_client.HelperNotFoundError):
        service_client.is_installed()


def test_run_unprivileged_raises_timeout(monkeypatch):
    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(cmd=["helper"], timeout=1)

    monkeypatch.setattr(service_client.subprocess, "run", fake_run)
    with pytest.raises(service_client.HelperTimeoutError):
        service_client.is_installed()


def test_parse_result_falls_back_to_raw_output_when_not_json():
    proc = FakeCompletedProcess(returncode=1, stdout="not json", stderr="boom")
    result = service_client._parse_result(proc)
    assert result == {"ok": False, "exit_code": 1, "stdout": "not json", "stderr": "boom"}


@pytest.fixture
def main_error_run(monkeypatch, capsys) -> dict:
    def fake_start():
        raise service_client.PermissionDeniedError("negado")

    monkeypatch.setattr(service_client, "start", fake_start)
    exit_code = service_client._main(["start"])
    return {"exit_code": exit_code, "stdout": capsys.readouterr().out}


def test_main_reports_error_exit_code(main_error_run):
    assert main_error_run["exit_code"] == 1


def test_main_reports_error_message_from_service_client_error(main_error_run):
    assert "negado" in main_error_run["stdout"]


def test_main_rejects_unknown_action(capsys):
    exit_code = service_client._main(["bogus"])
    assert exit_code == 2


def test_main_requires_an_argument(capsys):
    exit_code = service_client._main([])
    assert exit_code == 2


@pytest.fixture
def active_state_run(monkeypatch) -> dict:
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompletedProcess(stdout="active\n")

    monkeypatch.setattr(service_client.subprocess, "run", fake_run)
    return {"captured": captured, "state": service_client.get_active_state()}


def test_get_active_state_returns_the_reported_state(active_state_run):
    assert active_state_run["state"] == "active"


def test_get_active_state_runs_the_expected_command(active_state_run):
    assert active_state_run["captured"]["command"] == ["systemctl", "is-active", "minidlna.service"]


def test_get_active_state_runs_without_pkexec(active_state_run):
    assert active_state_run["captured"]["command"][0] != "pkexec"


def test_get_enabled_state_returns_unknown_on_empty_output(monkeypatch):
    monkeypatch.setattr(
        service_client.subprocess, "run", lambda *a, **k: FakeCompletedProcess(returncode=1, stdout="")
    )
    assert service_client.get_enabled_state() == "unknown"


def test_get_status_combines_active_and_enabled(monkeypatch):
    outputs = iter(["active\n", "enabled\n"])
    monkeypatch.setattr(
        service_client.subprocess,
        "run",
        lambda *a, **k: FakeCompletedProcess(stdout=next(outputs)),
    )
    assert service_client.get_status() == {"active": "active", "enabled": "enabled"}


@pytest.fixture
def recent_logs_run(monkeypatch) -> dict:
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompletedProcess(stdout="log line 1\nlog line 2\n")

    monkeypatch.setattr(service_client.subprocess, "run", fake_run)
    return {"captured": captured, "logs": service_client.get_recent_logs(50)}


def test_get_recent_logs_returns_stdout_on_success(recent_logs_run):
    assert recent_logs_run["logs"] == "log line 1\nlog line 2\n"


def test_get_recent_logs_runs_the_expected_command(recent_logs_run):
    assert recent_logs_run["captured"]["command"] == [
        "journalctl",
        "-u",
        "minidlna.service",
        "-n",
        "50",
        "--no-pager",
    ]


def test_get_recent_logs_returns_stderr_on_failure(monkeypatch):
    monkeypatch.setattr(
        service_client.subprocess,
        "run",
        lambda *a, **k: FakeCompletedProcess(returncode=1, stderr="no journal access"),
    )
    assert service_client.get_recent_logs() == "no journal access"
