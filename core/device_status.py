"""Fetches and parses minidlnad's own /status page.

It's the only place minidlnad exposes currently connected DLNA clients —
there's no separate protocol or CLI for it. A plain HTTP GET to
localhost, no privilege needed.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.request
from html.parser import HTMLParser

DEFAULT_PORT = 8200
REQUEST_TIMEOUT = 5


class DeviceStatusError(Exception):
    """Raised when the status page can't be fetched or parsed."""


class _StatusTableParser(HTMLParser):
    """Collects every <table> on the page as a list of rows of cell text,
    in document order — minidlnad's /status page has no ids/classes to
    target more precisely.
    """

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._in_table = False
        self._current_table: list[list[str]] = []
        self._current_row: list[str] = []
        self._in_cell = False
        self._cell_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "table":
            self._in_table = True
            self._current_table = []
        elif tag == "tr" and self._in_table:
            self._current_row = []
        elif tag == "td" and self._in_table:
            self._in_cell = True
            self._cell_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._in_table:
            self.tables.append(self._current_table)
            self._in_table = False
        elif tag == "tr" and self._in_table:
            self._current_table.append(self._current_row)
        elif tag == "td" and self._in_table:
            self._current_row.append("".join(self._cell_text).strip())
            self._in_cell = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_text.append(data)


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def parse_status_html(html: str) -> dict:
    parser = _StatusTableParser()
    parser.feed(html)

    library = {"audio_files": 0, "video_files": 0, "image_files": 0}
    if parser.tables:
        for row in parser.tables[0]:
            if len(row) != 2:
                continue
            label, value = row
            if "Audio" in label:
                library["audio_files"] = _safe_int(value)
            elif "Video" in label:
                library["video_files"] = _safe_int(value)
            elif "Image" in label:
                library["image_files"] = _safe_int(value)

    clients = []
    if len(parser.tables) > 1:
        for row in parser.tables[1][1:]:  # skip the header row
            if len(row) != 5:
                continue
            client_id, client_type, ip_address, hw_address, connections = row
            clients.append(
                {
                    "id": client_id,
                    "type": client_type,
                    "ip_address": ip_address,
                    "hw_address": hw_address,
                    "connections": _safe_int(connections),
                }
            )

    open_match = re.search(r"(\d+) connections? currently open", html)
    open_connections = int(open_match.group(1)) if open_match else 0

    return {**library, "clients": clients, "open_connections": open_connections}


def fetch_status(port: int = DEFAULT_PORT, timeout: float = REQUEST_TIMEOUT) -> dict:
    url = f"http://127.0.0.1:{port}/status"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise DeviceStatusError(str(exc)) from exc
    return parse_status_html(html)
