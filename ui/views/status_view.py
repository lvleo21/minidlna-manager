from __future__ import annotations

from typing import ClassVar

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GObject, Gtk

from ui.compat import SwitchRow


class StatusView(Gtk.ScrolledWindow):
    """Service status, controls and log — pure display.

    No core/* imports and no calls to run_async/service_client here:
    user actions are exposed as signals for a controller to handle, and
    the controller pushes results back in through the set_*() methods.
    """

    __gsignals__: ClassVar[dict] = {
        "start-clicked": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "stop-clicked": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "restart-clicked": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "refresh-logs-clicked": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "boot-toggled": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(vexpand=True, **kwargs)
        self._updating_boot_switch = False
        self.set_child(self._build_content())

    def _build_content(self) -> Gtk.Widget:
        self.status_row = Adw.ActionRow(title="Serviço", subtitle="Desconhecido")
        self.boot_switch_row = SwitchRow(title="Iniciar no boot")
        self.boot_switch_row.connect("notify::active", self._on_boot_switch_notify)

        status_group = Adw.PreferencesGroup(title="Status")
        status_group.add(self.status_row)
        status_group.add(self.boot_switch_row)

        self.start_button = Gtk.Button(label="Iniciar")
        self.stop_button = Gtk.Button(label="Parar")
        self.restart_button = Gtk.Button(label="Reiniciar")
        self.start_button.connect("clicked", lambda _b: self.emit("start-clicked"))
        self.stop_button.connect("clicked", lambda _b: self.emit("stop-clicked"))
        self.restart_button.connect("clicked", lambda _b: self.emit("restart-clicked"))

        self.control_buttons = [self.start_button, self.stop_button, self.restart_button]
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.add_css_class("linked")
        for button in self.control_buttons:
            button_box.append(button)

        self.log_view = Gtk.TextView(editable=False, monospace=True)
        self.log_view.get_buffer().set_text("")
        log_scroller = Gtk.ScrolledWindow(vexpand=True)
        log_scroller.set_child(self.log_view)
        log_scroller.set_min_content_height(200)

        self.refresh_logs_button = Gtk.Button(label="Atualizar log")
        self.refresh_logs_button.connect("clicked", lambda _b: self.emit("refresh-logs-clicked"))

        log_frame = Gtk.Frame(label="Log do serviço")
        log_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin_top=6,
            margin_bottom=6,
            margin_start=6,
            margin_end=6,
        )
        log_box.append(log_scroller)
        log_box.append(self.refresh_logs_button)
        log_frame.set_child(log_box)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content_box.append(status_group)
        content_box.append(button_box)
        content_box.append(log_frame)

        clamp = Adw.Clamp(margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
        clamp.set_child(content_box)
        return clamp

    # -- display API (controller -> view) --------------------------------------------

    def set_status_subtitle(self, text: str) -> None:
        self.status_row.set_subtitle(text)

    def set_boot_switch(self, active: bool) -> None:
        self._updating_boot_switch = True
        self.boot_switch_row.set_active(active)
        self._updating_boot_switch = False

    def set_log_text(self, text: str) -> None:
        self.log_view.get_buffer().set_text(text)

    def set_status_sensitive(self, sensitive: bool) -> None:
        self.status_row.set_sensitive(sensitive)

    def set_boot_switch_sensitive(self, sensitive: bool) -> None:
        self.boot_switch_row.set_sensitive(sensitive)

    def set_control_buttons_sensitive(self, sensitive: bool) -> None:
        for button in self.control_buttons:
            button.set_sensitive(sensitive)

    # -- internal ----------------------------------------------------------------------

    def _on_boot_switch_notify(self, switch_row: SwitchRow, _pspec) -> None:
        if self._updating_boot_switch:
            return
        self.emit("boot-toggled", switch_row.get_active())
