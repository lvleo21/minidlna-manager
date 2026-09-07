from __future__ import annotations

import gi

gi.require_version("Adw", "1")

from gi.repository import Adw

from core import service_client
from core.config_parser import MiniDLNAConfig
from core.media_access import grant_directory_access
from core.network import list_network_interfaces
from core.validator import (
    ValidationError,
    format_log_level,
    format_media_dir,
    parse_log_level,
    parse_media_dir,
    validate_log_level,
    validate_media_dir,
    validate_port,
)
from ui.async_utils import run_async
from ui.toast_utils import show_error_toast, show_toast
from ui.views.config_view import ConfigView


class ConfigController:
    """Mediates between ConfigView and core.config_parser/validator/service_client."""

    def __init__(self, view: ConfigView, toast_overlay: Adw.ToastOverlay) -> None:
        self.view = view
        self.toast_overlay = toast_overlay
        self.config: MiniDLNAConfig | None = None
        view.set_interface_options(list_network_interfaces())
        view.connect("save-clicked", lambda _v: self._on_save_clicked())
        view.connect("media-dir-selected", lambda _v, path: self._on_media_dir_selected(path))

    def set_installed(self, installed: bool) -> None:
        self.view.set_save_sensitive(installed)
        if installed:
            self._load_config()

    # -- load ---------------------------------------------------------------------

    def _load_config(self) -> None:
        run_async(MiniDLNAConfig.load, self._on_config_loaded)

    def _on_config_loaded(self, config: MiniDLNAConfig | None, error: Exception | None) -> bool:
        if error is not None or config is None:
            show_error_toast(self.toast_overlay, "Não foi possível carregar o config atual", error, None)
            self.view.set_save_sensitive(False)
            return False
        self.config = config
        log_categories, log_level = parse_log_level(config.get("log_level") or "")
        self.view.set_form_data(
            {
                "friendly_name": config.get("friendly_name") or "",
                "port": config.get("port") or "",
                "network_interface": config.get("network_interface") or "",
                "log_categories": log_categories,
                "log_level": log_level,
                "media_dirs": [parse_media_dir(value) for value in config.get_all("media_dir")],
            }
        )
        return False

    # -- media dir access -----------------------------------------------------------

    def _on_media_dir_selected(self, path: str) -> None:
        run_async(lambda: grant_directory_access(path), self._on_directory_access_granted)

    def _on_directory_access_granted(self, result: dict | None, error: Exception | None) -> bool:
        if error is not None or not (result or {}).get("ok"):
            show_error_toast(
                self.toast_overlay,
                "Não foi possível garantir acesso do MiniDLNA à pasta selecionada",
                error,
                result,
            )
        return False

    # -- save ---------------------------------------------------------------------

    def _on_save_clicked(self) -> None:
        if self.config is None:
            return
        self.view.clear_errors()
        data = self.view.get_form_data()
        errors = []

        try:
            port_value = str(validate_port(data["port"], check_in_use=False))
        except ValidationError as exc:
            self.view.set_port_error(True)
            errors.append(str(exc))
            port_value = None

        log_level_value = format_log_level(data["log_categories"], data["log_level"])
        if log_level_value:
            try:
                validate_log_level(log_level_value)
            except ValidationError as exc:
                errors.append(str(exc))
                log_level_value = None

        media_dir_values = []
        error_indices = set()
        for index, (type_part, path) in enumerate(data["media_dirs"]):
            value = format_media_dir(type_part, path)
            try:
                validate_media_dir(value, check_fs=True)
            except ValidationError as exc:
                error_indices.add(index)
                errors.append(str(exc))
            else:
                media_dir_values.append(value)
        self.view.set_media_dir_errors(error_indices)

        if errors:
            show_error_toast(
                self.toast_overlay, "Corrija os campos destacados", None, {"error": "; ".join(errors)}
            )
            return

        friendly_name = data["friendly_name"]
        if friendly_name:
            self.config.set("friendly_name", friendly_name)
        else:
            self.config.remove("friendly_name")

        interface_value = data["network_interface"]
        if interface_value:
            self.config.set("network_interface", interface_value)
        else:
            self.config.remove("network_interface")

        self.config.set("port", port_value)
        if log_level_value:
            self.config.set("log_level", log_level_value)
        else:
            self.config.remove("log_level")
        self.config.remove("media_dir")
        for value in media_dir_values:
            self.config.add("media_dir", value)

        self.view.set_save_sensitive(False)
        run_async(lambda: service_client.write_config(self.config.serialize()), self._on_save_done)

    def _on_save_done(self, result: dict | None, error: Exception | None) -> bool:
        self.view.set_save_sensitive(True)
        if error is not None or not (result or {}).get("ok"):
            show_error_toast(self.toast_overlay, "Falha ao salvar o config", error, result)
            return False
        sandbox_warning = (result or {}).get("sandbox_warning")
        if sandbox_warning:
            show_error_toast(
                self.toast_overlay,
                "Config salvo, mas o serviço pode não conseguir ler pastas em sua pasta pessoal",
                None,
                {"error": sandbox_warning},
            )
        toast = Adw.Toast(title="Config salvo.", button_label="Reiniciar agora")
        toast.connect("button-clicked", lambda _t: run_async(service_client.restart, self._on_restart_done))
        self.toast_overlay.add_toast(toast)
        return False

    def _on_restart_done(self, result: dict | None, error: Exception | None) -> bool:
        if error is not None or not (result or {}).get("ok"):
            show_error_toast(self.toast_overlay, "Falha ao reiniciar o MiniDLNA", error, result)
        else:
            show_toast(self.toast_overlay, "MiniDLNA reiniciado.")
        return False
