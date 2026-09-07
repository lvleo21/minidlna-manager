import urllib.error
from pathlib import Path

import pytest

from core import device_status

FIXTURE = Path(__file__).parent / "fixtures" / "minidlna-status.html"


def test_parse_status_html_reads_library_counts():
    result = device_status.parse_status_html(FIXTURE.read_text())
    assert result["audio_files"] == 12
    assert result["video_files"] == 2
    assert result["image_files"] == 0


def test_parse_status_html_reads_connected_clients():
    result = device_status.parse_status_html(FIXTURE.read_text())
    assert result["clients"] == [
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


def test_parse_status_html_reads_open_connections():
    result = device_status.parse_status_html(FIXTURE.read_text())
    assert result["open_connections"] == 1


def test_parse_status_html_handles_no_clients():
    html = (
        "<table><tr><td>Audio files</td><td>0</td></tr></table>"
        "<table><tr><td>ID</td><td>Type</td><td>IP Address</td><td>HW Address</td><td>Connections</td></tr></table>"
        "0 connections currently open"
    )
    result = device_status.parse_status_html(html)
    assert result["clients"] == []
    assert result["audio_files"] == 0


def test_parse_status_html_handles_missing_tables():
    result = device_status.parse_status_html("<html><body>no tables here</body></html>")
    assert result == {"audio_files": 0, "video_files": 0, "image_files": 0, "clients": [], "open_connections": 0}


def test_fetch_status_raises_on_connection_error(monkeypatch):
    def fake_urlopen(url, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(device_status.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(device_status.DeviceStatusError):
        device_status.fetch_status(port=8200)


def test_fetch_status_parses_successful_response(monkeypatch):
    html = FIXTURE.read_text()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return html.encode("utf-8")

    monkeypatch.setattr(device_status.urllib.request, "urlopen", lambda url, timeout: FakeResponse())

    result = device_status.fetch_status(port=8200)
    assert result["video_files"] == 2
    assert len(result["clients"]) == 2
