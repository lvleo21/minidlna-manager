from __future__ import annotations

import gi

gi.require_version("Adw", "1")

from gi.repository import Adw, GLib

from core.config_parser import MiniDLNAConfig
from core.device_status import DEFAULT_PORT, fetch_status
from ui.async_utils import run_async
from ui.views.devices_view import DevicesView

REFRESH_INTERVAL_SECONDS = 15


def _load_status() -> dict:
    try:
        port = int(MiniDLNAConfig.load().get("port") or DEFAULT_PORT)
    except (OSError, ValueError):
        port = DEFAULT_PORT
    return fetch_status(port)


class DevicesController:
    """Mediates between DevicesView and core.device_status/config_parser."""

    def __init__(self, view: DevicesView, toast_overlay: Adw.ToastOverlay) -> None:
        self.view = view
        self.toast_overlay = toast_overlay
        self._refresh_timeout_id: int | None = None
        view.connect("refresh-clicked", lambda _v: self.refresh())
        view.connect("destroy", self._on_view_destroyed)

    def set_installed(self, installed: bool) -> None:
        self.view.set_sensitive(installed)
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

    def _on_view_destroyed(self, _view: DevicesView) -> None:
        if self._refresh_timeout_id is not None:
            GLib.source_remove(self._refresh_timeout_id)
            self._refresh_timeout_id = None

    def refresh(self) -> None:
        self.view.set_refresh_sensitive(False)
        run_async(_load_status, self._on_status_loaded)

    def _on_status_loaded(self, result: dict | None, error: Exception | None) -> bool:
        self.view.set_refresh_sensitive(True)

        if error is not None or result is None:
            self.view.set_summary("Não foi possível consultar o status do MiniDLNA.")
            self.view.show_empty_state(
                "MiniDLNA não está respondendo",
                "O serviço precisa estar em execução para listar dispositivos.",
            )
            return False

        self.view.set_summary(
            f"{result['audio_files']} áudios · {result['video_files']} vídeos · "
            f"{result['image_files']} imagens · {result['open_connections']} conexão(ões) aberta(s)"
        )

        clients = result.get("clients", [])
        if not clients:
            self.view.show_empty_state(
                "Nenhum dispositivo conectado", "Dispositivos que acessarem o MiniDLNA aparecerão aqui."
            )
        else:
            self.view.show_clients(clients)
        return False
