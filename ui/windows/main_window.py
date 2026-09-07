from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from core import service_client
from ui.async_utils import run_async
from ui.toast_utils import show_error_toast, show_toast
from ui.widgets.config_page import ConfigPage
from ui.widgets.devices_page import DevicesPage
from ui.widgets.status_page import StatusPage


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("MiniDLNA Manager")
        self.set_default_size(560, 720)

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self._build_content())

        self._refresh_installed_state()

    # -- layout -----------------------------------------------------------------

    def _build_content(self) -> Gtk.Widget:
        self.view_stack = Adw.ViewStack()
        self.status_page = StatusPage(self.toast_overlay)
        self.config_page = ConfigPage(self.toast_overlay)
        self.devices_page = DevicesPage(self.toast_overlay)

        self.view_stack.add_titled_with_icon(self.status_page, "status", "Status", "utilities-system-monitor-symbolic")
        self.view_stack.add_titled_with_icon(self.config_page, "config", "Configuração", "preferences-system-symbolic")
        self.view_stack.add_titled_with_icon(self.devices_page, "devices", "Dispositivos", "network-workgroup-symbolic")

        view_switcher = Adw.ViewSwitcher(stack=self.view_stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        header = Adw.HeaderBar(title_widget=view_switcher)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)

        self.install_banner = Adw.Banner(title="MiniDLNA não está instalado")
        self.install_banner.set_button_label("Instalar MiniDLNA")
        self.install_banner.connect("button-clicked", self._on_install_clicked)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(self.install_banner)
        content_box.append(self.view_stack)
        self.view_stack.set_vexpand(True)

        toolbar_view.set_content(content_box)
        self.toast_overlay.set_child(toolbar_view)
        return self.toast_overlay

    # -- install flow ---------------------------------------------------------------

    def _refresh_installed_state(self) -> None:
        run_async(service_client.is_installed, self._on_installed_checked)

    def _on_installed_checked(self, result: dict | None, error: Exception | None) -> bool:
        installed = bool(result) and result.get("installed", False)
        self.install_banner.set_revealed(not installed)
        self.status_page.set_installed(installed)
        self.config_page.set_installed(installed)
        self.devices_page.set_installed(installed)
        if not installed and error is not None:
            show_error_toast(
                self.toast_overlay, "Não foi possível checar se o MiniDLNA está instalado", error, result
            )
        return False

    def _on_install_clicked(self, _banner: Adw.Banner) -> None:
        self.install_banner.set_sensitive(False)
        self.install_banner.set_button_label("Instalando…")
        run_async(service_client.install_package, self._on_install_done)

    def _on_install_done(self, result: dict | None, error: Exception | None) -> bool:
        self.install_banner.set_sensitive(True)
        self.install_banner.set_button_label("Instalar MiniDLNA")
        if error is not None or not (result or {}).get("ok"):
            show_error_toast(self.toast_overlay, "Falha ao instalar o MiniDLNA", error, result)
            return False
        show_toast(self.toast_overlay, "MiniDLNA instalado com sucesso.")
        self._refresh_installed_state()
        return False
