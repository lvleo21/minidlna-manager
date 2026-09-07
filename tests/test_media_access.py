import subprocess

import pytest

from core import media_access


class FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_run_factory(captured_calls):
    def fake_run(command, **kwargs):
        captured_calls.append(command)
        return FakeCompletedProcess()

    return fake_run


@pytest.fixture
def granted_nested_dir(monkeypatch, tmp_path) -> dict:
    monkeypatch.setenv("HOME", str(tmp_path))
    videos = tmp_path / "Videos" / "Show"
    videos.mkdir(parents=True)

    captured = []
    monkeypatch.setattr(media_access.subprocess, "run", _fake_run_factory(captured))

    return {"result": media_access.grant_directory_access(str(videos)), "captured": captured, "path": videos}


def test_grant_directory_access_reports_success(granted_nested_dir):
    assert granted_nested_dir["result"] == {"ok": True, "path": str(granted_nested_dir["path"])}


def test_grant_directory_access_sets_traverse_and_read_acls(granted_nested_dir):
    tmp_path = granted_nested_dir["path"].parent.parent
    assert granted_nested_dir["captured"] == [
        ["setfacl", "-m", "u:minidlna:x", str(tmp_path)],
        ["setfacl", "-m", "u:minidlna:x", str(tmp_path / "Videos")],
        ["setfacl", "-R", "-m", "u:minidlna:rx", str(granted_nested_dir["path"])],
        ["setfacl", "-R", "-d", "-m", "u:minidlna:rx", str(granted_nested_dir["path"])],
    ]


@pytest.fixture
def rejected_outside_home_result(monkeypatch, tmp_path) -> dict:
    monkeypatch.setenv("HOME", str(tmp_path))
    return media_access.grant_directory_access("/some/other/place")


def test_grant_directory_access_rejects_path_outside_home(rejected_outside_home_result):
    assert rejected_outside_home_result["ok"] is False


def test_grant_directory_access_outside_home_error_mentions_home(rejected_outside_home_result):
    assert "diretório pessoal" in rejected_outside_home_result["error"]


@pytest.fixture
def granted_home_itself(monkeypatch, tmp_path) -> dict:
    monkeypatch.setenv("HOME", str(tmp_path))
    captured = []
    monkeypatch.setattr(media_access.subprocess, "run", _fake_run_factory(captured))

    return {"result": media_access.grant_directory_access(str(tmp_path)), "captured": captured}


def test_grant_directory_access_accepts_home_itself(granted_home_itself):
    assert granted_home_itself["result"]["ok"] is True


def test_grant_directory_access_on_home_itself_skips_ancestor_acls(granted_home_itself, tmp_path):
    assert granted_home_itself["captured"] == [
        ["setfacl", "-R", "-m", "u:minidlna:rx", str(tmp_path)],
        ["setfacl", "-R", "-d", "-m", "u:minidlna:rx", str(tmp_path)],
    ]


@pytest.fixture
def missing_setfacl_result(monkeypatch, tmp_path) -> dict:
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "Videos"
    target.mkdir()

    def fake_run(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(media_access.subprocess, "run", fake_run)

    return media_access.grant_directory_access(str(target))


def test_grant_directory_access_reports_missing_setfacl_as_failure(missing_setfacl_result):
    assert missing_setfacl_result["ok"] is False


def test_grant_directory_access_missing_setfacl_error_names_the_command(missing_setfacl_result):
    assert "setfacl" in missing_setfacl_result["error"]


@pytest.fixture
def command_failure_result(monkeypatch, tmp_path) -> dict:
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "Videos"
    target.mkdir()

    def fake_run(command, **kwargs):
        raise subprocess.CalledProcessError(1, command, stderr="Operation not supported")

    monkeypatch.setattr(media_access.subprocess, "run", fake_run)

    return media_access.grant_directory_access(str(target))


def test_grant_directory_access_reports_command_failure_as_failure(command_failure_result):
    assert command_failure_result["ok"] is False


def test_grant_directory_access_command_failure_includes_stderr(command_failure_result):
    assert "Operation not supported" in command_failure_result["error"]


@pytest.fixture
def timeout_result(monkeypatch, tmp_path) -> dict:
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "Videos"
    target.mkdir()

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=1)

    monkeypatch.setattr(media_access.subprocess, "run", fake_run)

    return media_access.grant_directory_access(str(target))


def test_grant_directory_access_reports_timeout_as_failure(timeout_result):
    assert timeout_result["ok"] is False


def test_grant_directory_access_timeout_error_mentions_time_limit(timeout_result):
    assert "tempo limite" in timeout_result["error"]
