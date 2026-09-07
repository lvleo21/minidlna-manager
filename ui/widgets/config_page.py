from __future__ import annotations

import socket

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from core import service_client
from core.config_parser import MiniDLNAConfig
from core.media_access import grant_directory_access
from core.validator import (
    LOG_CATEGORIES,
    ValidationError,
    parse_media_dir,
    validate_log_level,
    validate_media_dir,
    validate_port,
)
from ui.async_utils import run_async
from ui.toast_utils import show_error_toast, show_toast

MEDIA_DIR_TYPE_LABELS = ["(todos)", "Áudio (A)", "Vídeo (V)", "Fotos (P)"]
MEDIA_DIR_TYPE_VALUES = [None, "A", "V", "P"]

LOG_CATEGORY_LABELS = {
    "general": "Geral",
    "artwork": "Capas",
    "database": "Banco de dados",
    "inotify": "Monitoramento de arquivos",
    "scanner": "Scanner de mídia",
    "metadata": "Metadados",
    "http": "HTTP",
    "ssdp": "SSDP",
    "tivo": "TiVo",
}
LOG_LEVEL_VALUES = ["off", "fatal", "error", "warn", "info", "debug"]
LOG_LEVEL_LABELS = ["Desligado", "Fatal", "Erro", "Aviso", "Info", "Depuração"]
DEFAULT_LOG_LEVEL = "warn"

AUTO_INTERFACE_LABEL = "(automático)"


def _available_network_interfaces() -> list[str]:
    try:
        return sorted(name for _, name in socket.if_nameindex())
    except OSError:
        return []


class ConfigPage(Gtk.ScrolledWindow):
    """Structured minidlna.conf editor: general server settings, log
    level and the list of media directories."""

    def __init__(self, toast_overlay: Adw.ToastOverlay, **kwargs) -> None:
        super().__init__(vexpand=True, **kwargs)
        self.toast_overlay = toast_overlay
        self.config: MiniDLNAConfig | None = None
        self.media_dir_rows: list[dict] = []
        self.log_category_checks: dict[str, Gtk.CheckButton] = {}
        self.interface_values: list[str] = [AUTO_INTERFACE_LABEL]
        self.set_child(self._build_content())

    # -- layout -----------------------------------------------------------------

    def _build_content(self) -> Gtk.Widget:
        save_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, halign=Gtk.Align.END)
        self.save_button = Gtk.Button(label="Salvar")
        self.save_button.add_css_class("suggested-action")
        self.save_button.connect("clicked", self._on_save_clicked)
        save_row.append(self.save_button)

        general_group = Adw.PreferencesGroup(title="Geral")
        self.friendly_name_row = Adw.EntryRow(title="Nome do servidor")
        self.port_row = Adw.EntryRow(title="Porta")

        self.interface_values = [AUTO_INTERFACE_LABEL, *_available_network_interfaces()]
        self.interface_dropdown = Gtk.DropDown.new_from_strings(self.interface_values)
        interface_row = Adw.ActionRow(title="Interface de rede")
        interface_row.add_suffix(self.interface_dropdown)

        general_group.add(self.friendly_name_row)
        general_group.add(self.port_row)
        general_group.add(interface_row)

        log_group = Adw.PreferencesGroup(
            title="Nível de log", description="Categorias monitoradas e verbosidade"
        )
        self.log_level_dropdown = Gtk.DropDown.new_from_strings(LOG_LEVEL_LABELS)
        self.log_level_dropdown.set_selected(LOG_LEVEL_VALUES.index(DEFAULT_LOG_LEVEL))
        level_row = Adw.ActionRow(title="Verbosidade")
        level_row.add_suffix(self.log_level_dropdown)
        log_group.add(level_row)

        categories_flow = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            max_children_per_line=3,
            row_spacing=6,
            column_spacing=12,
            margin_top=6,
            margin_bottom=6,
            margin_start=12,
            margin_end=12,
        )
        for category in sorted(LOG_CATEGORIES):
            check = Gtk.CheckButton(label=LOG_CATEGORY_LABELS.get(category, category))
            self.log_category_checks[category] = check
            categories_flow.append(check)
        log_group.add(categories_flow)

        self.media_dir_group = Adw.PreferencesGroup(title="Diretórios de mídia")
        add_button = Gtk.Button(icon_name="list-add-symbolic")
        add_button.add_css_class("flat")
        add_button.connect("clicked", lambda _b: self._add_media_dir_row())
        self.media_dir_group.set_header_suffix(add_button)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content_box.append(save_row)
        content_box.append(general_group)
        content_box.append(log_group)
        content_box.append(self.media_dir_group)

        clamp = Adw.Clamp(margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
        clamp.set_child(content_box)
        return clamp

    def _add_media_dir_row(self, type_part: str | None = None, path: str = "") -> None:
        entry_row = Adw.EntryRow(title="Diretório")
        entry_row.set_text(path)

        type_dropdown = Gtk.DropDown.new_from_strings(MEDIA_DIR_TYPE_LABELS)
        index = MEDIA_DIR_TYPE_VALUES.index(type_part) if type_part in MEDIA_DIR_TYPE_VALUES else 0
        type_dropdown.set_selected(index)
        entry_row.add_prefix(type_dropdown)

        browse_button = Gtk.Button(icon_name="folder-open-symbolic")
        browse_button.set_tooltip_text("Selecionar pasta")
        browse_button.add_css_class("flat")
        browse_button.connect("clicked", lambda _b: self._browse_media_dir(entry_row))
        entry_row.add_suffix(browse_button)

        remove_button = Gtk.Button(icon_name="user-trash-symbolic")
        remove_button.add_css_class("flat")
        entry_row.add_suffix(remove_button)

        row_data = {"entry_row": entry_row, "type_dropdown": type_dropdown}
        remove_button.connect("clicked", lambda _b: self._remove_media_dir_row(row_data))

        self.media_dir_rows.append(row_data)
        self.media_dir_group.add(entry_row)

    def _remove_media_dir_row(self, row_data: dict) -> None:
        self.media_dir_group.remove(row_data["entry_row"])
        self.media_dir_rows.remove(row_data)

    def _media_dir_value(self, row_data: dict) -> str:
        type_part = MEDIA_DIR_TYPE_VALUES[row_data["type_dropdown"].get_selected()]
        path = row_data["entry_row"].get_text().strip()
        return f"{type_part},{path}" if type_part else path

    def _browse_media_dir(self, entry_row: Adw.EntryRow) -> None:
        dialog = Gtk.FileDialog(title="Selecionar diretório de mídia")
        root = self.get_root()
        dialog.select_folder(root, None, lambda dlg, result: self._on_folder_selected(dlg, result, entry_row))

    def _on_folder_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, entry_row: Adw.EntryRow) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        path = folder.get_path() if folder is not None else None
        if not path:
            return
        entry_row.set_text(path)
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

    # -- network interface ------------------------------------------------------------

    def _apply_interface_to_form(self, value: str) -> None:
        if value and value in self.interface_values:
            self.interface_dropdown.set_selected(self.interface_values.index(value))
        else:
            self.interface_dropdown.set_selected(0)

    def _interface_value(self) -> str:
        selected = self.interface_values[self.interface_dropdown.get_selected()]
        return "" if selected == AUTO_INTERFACE_LABEL else selected

    # -- log level ------------------------------------------------------------------

    def _apply_log_level_to_form(self, value: str) -> None:
        selected_categories: set[str] = set()
        level = DEFAULT_LOG_LEVEL
        for token in value.split(","):
            token = token.strip()
            if not token:
                continue
            if "=" in token:
                category, _, token_level = token.partition("=")
                category = category.strip()
                token_level = token_level.strip()
                if category:
                    selected_categories.add(category)
                if token_level in LOG_LEVEL_VALUES:
                    level = token_level
            else:
                selected_categories.add(token)
        for category, check in self.log_category_checks.items():
            check.set_active(category in selected_categories)
        self.log_level_dropdown.set_selected(LOG_LEVEL_VALUES.index(level))

    def _log_level_value(self) -> str:
        selected = sorted(c for c, check in self.log_category_checks.items() if check.get_active())
        if not selected:
            return ""
        level = LOG_LEVEL_VALUES[self.log_level_dropdown.get_selected()]
        return ",".join(selected) + f"={level}"

    # -- load ---------------------------------------------------------------------

    def set_installed(self, installed: bool) -> None:
        self.save_button.set_sensitive(installed)
        if installed:
            self._load_config()

    def _load_config(self) -> None:
        run_async(MiniDLNAConfig.load, self._on_config_loaded)

    def _on_config_loaded(self, config: MiniDLNAConfig | None, error: Exception | None) -> bool:
        if error is not None or config is None:
            show_error_toast(self.toast_overlay, "Não foi possível carregar o config atual", error, None)
            self.save_button.set_sensitive(False)
            return False
        self.config = config
        self.friendly_name_row.set_text(config.get("friendly_name") or "")
        self.port_row.set_text(config.get("port") or "")
        self._apply_interface_to_form(config.get("network_interface") or "")
        self._apply_log_level_to_form(config.get("log_level") or "")
        for value in config.get_all("media_dir"):
            type_part, path = parse_media_dir(value)
            self._add_media_dir_row(type_part, path)
        return False

    # -- save ---------------------------------------------------------------------

    def _clear_field_errors(self) -> None:
        self.port_row.remove_css_class("error")
        for row_data in self.media_dir_rows:
            row_data["entry_row"].remove_css_class("error")

    def _on_save_clicked(self, _button: Gtk.Button) -> None:
        if self.config is None:
            return
        self._clear_field_errors()
        errors = []

        port_text = self.port_row.get_text().strip()
        try:
            port_value = str(validate_port(port_text, check_in_use=False))
        except ValidationError as exc:
            self.port_row.add_css_class("error")
            errors.append(str(exc))
            port_value = None

        log_level_value = self._log_level_value()
        if log_level_value:
            try:
                validate_log_level(log_level_value)
            except ValidationError as exc:
                errors.append(str(exc))
                log_level_value = None

        media_dir_values = []
        for row_data in self.media_dir_rows:
            value = self._media_dir_value(row_data)
            try:
                validate_media_dir(value, check_fs=True)
            except ValidationError as exc:
                row_data["entry_row"].add_css_class("error")
                errors.append(str(exc))
            else:
                media_dir_values.append(value)

        if errors:
            show_error_toast(
                self.toast_overlay, "Corrija os campos destacados", None, {"error": "; ".join(errors)}
            )
            return

        friendly_name = self.friendly_name_row.get_text().strip()
        if friendly_name:
            self.config.set("friendly_name", friendly_name)
        else:
            self.config.remove("friendly_name")

        interface_value = self._interface_value()
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

        self.save_button.set_sensitive(False)
        run_async(lambda: service_client.write_config(self.config.serialize()), self._on_save_done)

    def _on_save_done(self, result: dict | None, error: Exception | None) -> bool:
        self.save_button.set_sensitive(True)
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
