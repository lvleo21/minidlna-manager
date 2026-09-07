import urllib.error
from pathlib import Path

import pytest

from core import device_status

FIXTURE = Path(__file__).parent / "fixtures" / "minidlna-status.html"


@pytest.fixture
def parsed_status() -> dict:
    return device_status.parse_status_html(FIXTURE.read_text())


def test_parse_status_html_reads_audio_file_count(parsed_status):
    assert parsed_status["audio_files"] == 12


def test_parse_status_html_reads_video_file_count(parsed_status):
    assert parsed_status["video_files"] == 2


def test_parse_status_html_reads_image_file_count(parsed_status):
    assert parsed_status["image_files"] == 0


def test_parse_status_html_reads_connected_clients(parsed_status):
    assert parsed_status["clients"] == [
        {
            "id": "0",
            "type": "LG",
            "ip_address": "192.168.1.10",
            "hw_address": "F0:86:20:E6:FB:50",
            "connections": 1,
        },
        {
            "id": "1",
            "type": "Unknown",
            "ip_address": "127.0.0.1",
            "hw_address": "FF:FF:FF:FF:FF:FF",
            "connections": 0,
        },
    ]


def test_parse_status_html_reads_open_connections(parsed_status):
    assert parsed_status["open_connections"] == 1


@pytest.fixture
def status_with_no_clients() -> dict:
    html = (
        "<table><tr><td>Audio files</td><td>0</td></tr></table>"
        "<table><tr><td>ID</td><td>Type</td><td>IP Address</td><td>HW Address</td><td>Connections</td></tr></table>"
        "0 connections currently open"
    )
    return device_status.parse_status_html(html)


def test_parse_status_html_with_no_clients_returns_empty_list(status_with_no_clients):
    assert status_with_no_clients["clients"] == []


def test_parse_status_html_with_no_clients_still_reads_library_counts(status_with_no_clients):
    assert status_with_no_clients["audio_files"] == 0


def test_parse_status_html_handles_missing_tables():
    result = device_status.parse_status_html("<html><body>no tables here</body></html>")
    assert result == {"audio_files": 0, "video_files": 0, "image_files": 0, "clients": [], "open_connections": 0}


def test_fetch_status_raises_on_connection_error(monkeypatch):
    def fake_urlopen(url, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(device_status.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(device_status.DeviceStatusError):
        device_status.fetch_status(port=8200)


class _FakeResponse:
    def __init__(self, html: str) -> None:
        self._html = html

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._html.encode("utf-8")


@pytest.fixture
def fetched_status(monkeypatch) -> dict:
    html = FIXTURE.read_text()
    monkeypatch.setattr(device_status.urllib.request, "urlopen", lambda url, timeout: _FakeResponse(html))
    return device_status.fetch_status(port=8200)


def test_fetch_status_parses_video_file_count(fetched_status):
    assert fetched_status["video_files"] == 2


def test_fetch_status_parses_client_list_length(fetched_status):
    assert len(fetched_status["clients"]) == 2
