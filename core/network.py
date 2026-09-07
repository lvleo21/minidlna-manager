"""System network introspection — no privilege needed."""
from __future__ import annotations

import socket


def list_network_interfaces() -> list[str]:
    try:
        return sorted(name for _, name in socket.if_nameindex())
    except OSError:
        return []
