from core.network import list_network_interfaces


def test_list_network_interfaces_returns_a_sorted_list(monkeypatch):
    monkeypatch.setattr(
        "core.network.socket.if_nameindex", lambda: [(1, "lo"), (2, "eth0"), (3, "wlan0")]
    )
    assert list_network_interfaces() == ["eth0", "lo", "wlan0"]


def test_list_network_interfaces_returns_empty_list_on_os_error(monkeypatch):
    def raise_os_error():
        raise OSError

    monkeypatch.setattr("core.network.socket.if_nameindex", raise_os_error)
    assert list_network_interfaces() == []
