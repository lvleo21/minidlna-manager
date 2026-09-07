from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from core.config_parser import MiniDLNAConfig
from core.device_status import DEFAULT_PORT, fetch_status
from ui.async_utils import run_async

REFRESH_INTERVAL_SECONDS = 15


def _load_status() -> dict:
    try:
        port = int(MiniDLNAConfig.load().get("port") or DEFAULT_PORT)
    except (OSError, ValueError):
        port = DEFAULT_PORT
    return fetch_status(port)


class DevicesPage(Gtk.ScrolledWindow):
    """Clients currently known to minidlnad, read from its own /status page."""

    def __init__(self, toast_overlay: Adw.ToastOverlay, **kwargs) -> None:
        super().__init__(vexpand=True, **kwargs)
        self.toast_overlay = toast_overlay
        self._device_rows: list[Adw.ActionRow] = []
        self._refresh_timeout_id: int | None = None
        self.set_child(self._build_content())
        self.connect("destroy", self._on_destroy)

    def _build_content(self) -> Gtk.Widget:
        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.summary_label = Gtk.Label(label="", xalign=0, hexpand=True, wrap=True)
        self.refresh_button = Gtk.Button(label="Atualizar")
        self.refresh_button.connect("clicked", lambda _b: self.refresh())
        header_row.append(self.summary_label)
        header_row.append(self.refresh_button)

        self.devices_group = Adw.PreferencesGroup(title="Dispositivos conectados")

        self.empty_status_page = Adw.StatusPage(
            icon_name="network-wired-disconnected-symbolic",
            title="Nenhum dispositivo conectado",
            description="Dispositivos que acessarem o MiniDLNA aparecerão aqui.",
            vexpand=False,
        )

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content_box.append(header_row)
        content_box.append(self.devices_group)
        content_box.append(self.empty_status_page)
        self.content_box = content_box

        clamp = Adw.Clamp(margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
        clamp.set_child(content_box)
        return clamp

    def set_installed(self, installed: bool) -> None:
        self.set_sensitive(installed)
        if installed:
            self.refresh()
            if self._refresh_timeout_id is None:
                self._refresh_timeout_id = GLib.timeout_add_seconds(
                    REFRESH_INTERVAL_SECONDS, self._on_periodic_refresh
                )
        elif self._refresh_timeout_id is not None:
            GLib.source_remove(self._refresh_timeout_id)
            self._refresh_timeout_id = None

    def _on_periodic_refresh(self) -> bool:
        self.refresh()
        return True

    def _on_destroy(self, _widget: Gtk.Widget) -> None:
        if self._refresh_timeout_id is not None:
            GLib.source_remove(self._refresh_timeout_id)
            self._refresh_timeout_id = None

    def refresh(self) -> None:
        self.refresh_button.set_sensitive(False)
        run_async(_load_status, self._on_status_loaded)

    def _clear_device_rows(self) -> None:
        for row in self._device_rows:
            self.devices_group.remove(row)
        self._device_rows = []

    def _on_status_loaded(self, result: dict | None, error: Exception | None) -> bool:
        self.refresh_button.set_sensitive(True)
        self._clear_device_rows()

        if error is not None or result is None:
            self.summary_label.set_label("Não foi possível consultar o status do MiniDLNA.")
            self.devices_group.set_visible(False)
            self.empty_status_page.set_visible(True)
            self.empty_status_page.set_title("MiniDLNA não está respondendo")
            self.empty_status_page.set_description("O serviço precisa estar em execução para listar dispositivos.")
            return False

        self.summary_label.set_label(
            f"{result['audio_files']} áudios · {result['video_files']} vídeos · "
            f"{result['image_files']} imagens · {result['open_connections']} conexão(ões) aberta(s)"
        )

        clients = result.get("clients", [])
        if not clients:
            self.devices_group.set_visible(False)
            self.empty_status_page.set_visible(True)
            self.empty_status_page.set_title("Nenhum dispositivo conectado")
            self.empty_status_page.set_description("Dispositivos que acessarem o MiniDLNA aparecerão aqui.")
            return False

        self.empty_status_page.set_visible(False)
        self.devices_group.set_visible(True)
        for client in clients:
            row = Adw.ActionRow(
                title=client["type"] or "Desconhecido",
                subtitle=f"{client['ip_address']} · {client['hw_address']}",
            )
            connections_label = Gtk.Label(label=str(client["connections"]))
            connections_label.add_css_class("dim-label")
            row.add_suffix(connections_label)
            self.devices_group.add(row)
            self._device_rows.append(row)
        return False
