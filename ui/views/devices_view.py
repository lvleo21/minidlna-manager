from __future__ import annotations

from typing import ClassVar

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GObject, Gtk


class DevicesView(Gtk.ScrolledWindow):
    """Connected-clients list — pure display, no core/* imports."""

    __gsignals__: ClassVar[dict] = {
        "refresh-clicked": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(vexpand=True, **kwargs)
        self._device_rows: list[Adw.ActionRow] = []
        self.set_child(self._build_content())

    def _build_content(self) -> Gtk.Widget:
        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.summary_label = Gtk.Label(label="", xalign=0, hexpand=True, wrap=True)
        self.refresh_button = Gtk.Button(label="Atualizar")
        self.refresh_button.connect("clicked", lambda _b: self.emit("refresh-clicked"))
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

        clamp = Adw.Clamp(margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
        clamp.set_child(content_box)
        return clamp

    # -- display API (controller -> view) --------------------------------------------

    def set_summary(self, text: str) -> None:
        self.summary_label.set_label(text)

    def set_refresh_sensitive(self, sensitive: bool) -> None:
        self.refresh_button.set_sensitive(sensitive)

    def show_empty_state(self, title: str, description: str) -> None:
        self._clear_device_rows()
        self.devices_group.set_visible(False)
        self.empty_status_page.set_title(title)
        self.empty_status_page.set_description(description)
        self.empty_status_page.set_visible(True)

    def show_clients(self, clients: list[dict]) -> None:
        self._clear_device_rows()
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

    # -- internal ----------------------------------------------------------------------

    def _clear_device_rows(self) -> None:
        for row in self._device_rows:
            self.devices_group.remove(row)
        self._device_rows = []
