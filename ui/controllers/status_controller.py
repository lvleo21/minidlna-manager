from __future__ import annotations

import gi

gi.require_version("Adw", "1")

from gi.repository import Adw

from core import service_client
from ui.async_utils import run_async
from ui.toast_utils import show_error_toast, show_toast
from ui.views.status_view import StatusView

ACTIVE_LABELS = {
    "active": "Ativo",
    "inactive": "Inativo",
    "failed": "Falhou",
    "activating": "Iniciando…",
    "deactivating": "Parando…",
    "unknown": "Desconhecido",
}

LOG_LINE_COUNT = 200


class StatusController:
    """Mediates between StatusView and core.service_client."""

    def __init__(self, view: StatusView, toast_overlay: Adw.ToastOverlay) -> None:
        self.view = view
        self.toast_overlay = toast_overlay
        view.connect("start-clicked", lambda _v: self._run_service_action("start"))
        view.connect("stop-clicked", lambda _v: self._run_service_action("stop"))
        view.connect("restart-clicked", lambda _v: self._run_service_action("restart"))
        view.connect("refresh-logs-clicked", lambda _v: self.refresh_logs())
        view.connect("boot-toggled", self._on_boot_toggled)

    def set_installed(self, installed: bool) -> None:
        self.view.set_status_sensitive(installed)
        self.view.set_boot_switch_sensitive(installed)
        self.view.set_control_buttons_sensitive(installed)
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
            self.view.set_status_subtitle("Desconhecido")
            return False
        self.view.set_status_subtitle(ACTIVE_LABELS.get(result["active"], result["active"]))
        self.view.set_boot_switch(result["enabled"] == "enabled")
        return False

    def refresh_logs(self) -> None:
        run_async(lambda: service_client.get_recent_logs(LOG_LINE_COUNT), self._on_logs_loaded)

    def _on_logs_loaded(self, result: str | None, error: Exception | None) -> bool:
        text = result if error is None and result is not None else f"erro ao carregar log: {error}"
        self.view.set_log_text(text)
        return False

    # -- service control ------------------------------------------------------------

    def _run_service_action(self, action: str) -> None:
        self.view.set_control_buttons_sensitive(False)
        self.view.set_boot_switch_sensitive(False)
        func = getattr(service_client, action)
        run_async(func, lambda result, error: self._on_service_action_done(action, result, error))

    def _on_service_action_done(self, action: str, result: dict | None, error: Exception | None) -> bool:
        self.view.set_control_buttons_sensitive(True)
        self.view.set_boot_switch_sensitive(True)
        if error is not None or not (result or {}).get("ok"):
            show_error_toast(self.toast_overlay, f"Falha ao executar '{action}'", error, result)
        else:
            show_toast(self.toast_overlay, f"'{action}' executado com sucesso.")
        self.refresh()
        return False

    def _on_boot_toggled(self, _view: StatusView, desired: bool) -> None:
        self.view.set_boot_switch_sensitive(False)
        func = service_client.enable if desired else service_client.disable
        run_async(func, lambda result, error: self._on_boot_toggle_done(desired, result, error))

    def _on_boot_toggle_done(self, desired: bool, result: dict | None, error: Exception | None) -> bool:
        self.view.set_boot_switch_sensitive(True)
        if error is not None or not (result or {}).get("ok"):
            show_error_toast(self.toast_overlay, "Não foi possível alterar o início automático", error, result)
            self.view.set_boot_switch(not desired)
        else:
            show_toast(self.toast_overlay, f"Início no boot {'habilitado' if desired else 'desabilitado'}.")
        return False
