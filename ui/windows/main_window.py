from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from core import service_client
from ui.async_utils import run_async

ACTIVE_LABELS = {
    "active": "Ativo",
    "inactive": "Inativo",
    "failed": "Falhou",
    "activating": "Iniciando…",
    "deactivating": "Parando…",
    "unknown": "Desconhecido",
}

LOG_LINE_COUNT = 200


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("MiniDLNA Manager")
        self.set_default_size(560, 640)

        self._updating_boot_switch = False

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self._build_content())

        self._refresh_installed_state()

    # -- layout -----------------------------------------------------------------

    def _build_content(self) -> Gtk.Widget:
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        self.install_banner = Adw.Banner(title="MiniDLNA não está instalado")
        self.install_banner.set_button_label("Instalar MiniDLNA")
        self.install_banner.connect("button-clicked", self._on_install_clicked)

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
        self.refresh_logs_button.connect("clicked", lambda _b: self._refresh_logs())

        log_frame = Gtk.Frame(label="Log do serviço")
        log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6,
                           margin_bottom=6, margin_start=6, margin_end=6)
        log_box.append(log_scroller)
        log_box.append(self.refresh_logs_button)
        log_frame.set_child(log_box)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content_box.append(self.install_banner)
        content_box.append(status_group)
        content_box.append(button_box)
        content_box.append(log_frame)

        clamp = Adw.Clamp(margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
        clamp.set_child(content_box)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_child(clamp)

        toolbar_view.set_content(scroller)
        self.toast_overlay.set_child(toolbar_view)
        return self.toast_overlay

    # -- toasts -------------------------------------------------------------------

    def _toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message))

    def _toast_error(self, message: str, error: Exception | None, result: dict | None) -> None:
        detail = str(error) if error is not None else (result or {}).get("error", "")
        text = f"{message}: {detail}" if detail else message
        self.toast_overlay.add_toast(Adw.Toast(title=text, timeout=0))

    # -- install flow ---------------------------------------------------------------

    def _refresh_installed_state(self) -> None:
        run_async(service_client.is_installed, self._on_installed_checked)

    def _on_installed_checked(self, result: dict | None, error: Exception | None) -> bool:
        installed = bool(result) and result.get("installed", False)
        self.install_banner.set_revealed(not installed)
        for widget in (*self.control_buttons, self.boot_switch_row, self.status_row):
            widget.set_sensitive(installed)
        if installed:
            self._refresh_status()
            self._refresh_logs()
        elif error is not None:
            self._toast_error("Não foi possível checar se o MiniDLNA está instalado", error, result)
        return False

    def _on_install_clicked(self, _banner: Adw.Banner) -> None:
        self.install_banner.set_sensitive(False)
        self.install_banner.set_button_label("Instalando…")
        run_async(service_client.install_package, self._on_install_done)

    def _on_install_done(self, result: dict | None, error: Exception | None) -> bool:
        self.install_banner.set_sensitive(True)
        self.install_banner.set_button_label("Instalar MiniDLNA")
        if error is not None or not (result or {}).get("ok"):
            self._toast_error("Falha ao instalar o MiniDLNA", error, result)
            return False
        self._toast("MiniDLNA instalado com sucesso.")
        self._refresh_installed_state()
        return False

    # -- status/log ---------------------------------------------------------------

    def _refresh_status(self) -> None:
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

    def _refresh_logs(self) -> None:
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
            self._toast_error(f"Falha ao executar '{action}'", error, result)
        else:
            self._toast(f"'{action}' executado com sucesso.")
        self._refresh_status()
        self._refresh_logs()
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
            self._toast_error("Não foi possível alterar o início automático", error, result)
            self._set_boot_switch(not desired)
        else:
            self._toast(f"Início no boot {'habilitado' if desired else 'desabilitado'}.")
        return False
