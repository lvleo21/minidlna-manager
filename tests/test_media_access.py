import subprocess

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


def test_grant_directory_access_sets_traverse_and_read_acls(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    videos = tmp_path / "Videos" / "Show"
    videos.mkdir(parents=True)

    captured = []
    monkeypatch.setattr(media_access.subprocess, "run", _fake_run_factory(captured))

    result = media_access.grant_directory_access(str(videos))

    assert result == {"ok": True, "path": str(videos)}
    assert captured == [
        ["setfacl", "-m", "u:minidlna:x", str(tmp_path)],
        ["setfacl", "-m", "u:minidlna:x", str(tmp_path / "Videos")],
        ["setfacl", "-R", "-m", "u:minidlna:rx", str(videos)],
        ["setfacl", "-R", "-d", "-m", "u:minidlna:rx", str(videos)],
    ]


def test_grant_directory_access_rejects_path_outside_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = media_access.grant_directory_access("/some/other/place")
    assert result["ok"] is False
    assert "diretório pessoal" in result["error"]


def test_grant_directory_access_accepts_home_itself(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    captured = []
    monkeypatch.setattr(media_access.subprocess, "run", _fake_run_factory(captured))

    result = media_access.grant_directory_access(str(tmp_path))

    assert result["ok"] is True
    assert captured == [
        ["setfacl", "-R", "-m", "u:minidlna:rx", str(tmp_path)],
        ["setfacl", "-R", "-d", "-m", "u:minidlna:rx", str(tmp_path)],
    ]


def test_grant_directory_access_reports_missing_setfacl(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "Videos"
    target.mkdir()

    def fake_run(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(media_access.subprocess, "run", fake_run)

    result = media_access.grant_directory_access(str(target))
    assert result["ok"] is False
    assert "setfacl" in result["error"]


def test_grant_directory_access_reports_command_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "Videos"
    target.mkdir()

    def fake_run(command, **kwargs):
        raise subprocess.CalledProcessError(1, command, stderr="Operation not supported")

    monkeypatch.setattr(media_access.subprocess, "run", fake_run)

    result = media_access.grant_directory_access(str(target))
    assert result["ok"] is False
    assert "Operation not supported" in result["error"]


def test_grant_directory_access_reports_timeout(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "Videos"
    target.mkdir()

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=1)

    monkeypatch.setattr(media_access.subprocess, "run", fake_run)

    result = media_access.grant_directory_access(str(target))
    assert result["ok"] is False
    assert "tempo limite" in result["error"]
