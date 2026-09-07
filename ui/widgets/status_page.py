from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from core import service_client
from ui.async_utils import run_async
from ui.toast_utils import show_error_toast, show_toast

ACTIVE_LABELS = {
    "active": "Ativo",
    "inactive": "Inativo",
    "failed": "Falhou",
    "activating": "Iniciando…",
    "deactivating": "Parando…",
    "unknown": "Desconhecido",
}

LOG_LINE_COUNT = 200


class StatusPage(Gtk.ScrolledWindow):
    """Service status, start/stop/restart controls, boot toggle and log."""

    def __init__(self, toast_overlay: Adw.ToastOverlay, **kwargs) -> None:
        super().__init__(vexpand=True, **kwargs)
        self.toast_overlay = toast_overlay
        self._updating_boot_switch = False
        self.set_child(self._build_content())

    def _build_content(self) -> Gtk.Widget:
        self.status_row = Adw.ActionRow(title="Serviço", subtitle="Desconhecido")
        self.boot_switch_row = Adw.SwitchRow(title="Iniciar no boot")
        self.boot_switch_row.connect("notify::active", self._on_boot_switch_toggled)

        status_group = Adw.PreferencesGroup(title="Status")
        status_group.add(self.status_row)
        status_group.add(self.boot_switch_row)

        self.start_button = Gtk.Button(label="Iniciar")
        self.stop_button = Gtk.Button(label="Parar")
        self.restart_button = Gtk.Button(label="Reiniciar")
        self.start_button.connect("clicked", lambda _b: self._run_service_action("start"))
        self.stop_button.connect("clicked", lambda _b: self._run_service_action("stop"))
        self.restart_button.connect("clicked", lambda _b: self._run_service_action("restart"))

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
        self.refresh_logs_button.connect("clicked", lambda _b: self.refresh_logs())

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

    def set_installed(self, installed: bool) -> None:
        for widget in (*self.control_buttons, self.boot_switch_row, self.status_row):
            widget.set_sensitive(installed)
        if installed:
            self.refresh()

    def refresh(self) -> None:
        self.refresh_status()
        self.refresh_logs()

    # -- status/log ---------------------------------------------------------------

    def refresh_status(self) -> None:
        run_async(service_client.get_status, self._on_status_loaded)

    def _on_status_loaded(self, result: dict | None, error: Exception | None) -> bool:
        if error is not None or result is None:
            self.status_row.set_subtitle("Desconhecido")
            return False
        self.status_row.set_subtitle(ACTIVE_LABELS.get(result["active"], result["active"]))
        self._set_boot_switch(result["enabled"] == "enabled")
        return False

    def _set_boot_switch(self, active: bool) -> None:
        self._updating_boot_switch = True
        self.boot_switch_row.set_active(active)
        self._updating_boot_switch = False

    def refresh_logs(self) -> None:
        run_async(lambda: service_client.get_recent_logs(LOG_LINE_COUNT), self._on_logs_loaded)

    def _on_logs_loaded(self, result: str | None, error: Exception | None) -> bool:
        text = result if error is None and result is not None else f"erro ao carregar log: {error}"
        self.log_view.get_buffer().set_text(text)
        return False

    # -- service control ------------------------------------------------------------

    def _set_controls_sensitive(self, sensitive: bool) -> None:
        for widget in (*self.control_buttons, self.boot_switch_row):
            widget.set_sensitive(sensitive)

    def _run_service_action(self, action: str) -> None:
        self._set_controls_sensitive(False)
        func = getattr(service_client, action)
        run_async(func, lambda result, error: self._on_service_action_done(action, result, error))

    def _on_service_action_done(self, action: str, result: dict | None, error: Exception | None) -> bool:
        self._set_controls_sensitive(True)
        if error is not None or not (result or {}).get("ok"):
            show_error_toast(self.toast_overlay, f"Falha ao executar '{action}'", error, result)
        else:
            show_toast(self.toast_overlay, f"'{action}' executado com sucesso.")
        self.refresh()
        return False

    def _on_boot_switch_toggled(self, switch_row: Adw.SwitchRow, _pspec) -> None:
        if self._updating_boot_switch:
            return
        desired = switch_row.get_active()
        switch_row.set_sensitive(False)
        func = service_client.enable if desired else service_client.disable
        run_async(func, lambda result, error: self._on_boot_toggle_done(desired, result, error))

    def _on_boot_toggle_done(self, desired: bool, result: dict | None, error: Exception | None) -> bool:
        self.boot_switch_row.set_sensitive(True)
        if error is not None or not (result or {}).get("ok"):
            show_error_toast(self.toast_overlay, "Não foi possível alterar o início automático", error, result)
            self._set_boot_switch(not desired)
        else:
            show_toast(self.toast_overlay, f"Início no boot {'habilitado' if desired else 'desabilitado'}.")
        return False
