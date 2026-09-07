from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from core import service_client
from core.config_parser import MiniDLNAConfig
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


class ConfigWindow(Adw.Window):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Configuração do MiniDLNA")
        self.set_default_size(560, 720)

        self.config: MiniDLNAConfig | None = None
        self.media_dir_rows: list[dict] = []
        self.log_category_checks: dict[str, Gtk.CheckButton] = {}

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self._build_content())
        self._load_config()

    # -- layout -----------------------------------------------------------------

    def _build_content(self) -> Gtk.Widget:
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.save_button = Gtk.Button(label="Salvar")
        self.save_button.add_css_class("suggested-action")
        self.save_button.connect("clicked", self._on_save_clicked)
        header.pack_end(self.save_button)
        toolbar_view.add_top_bar(header)

        general_group = Adw.PreferencesGroup(title="Geral")
        self.port_row = Adw.EntryRow(title="Porta")
        general_group.add(self.port_row)

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
        content_box.append(general_group)
        content_box.append(log_group)
        content_box.append(self.media_dir_group)

        clamp = Adw.Clamp(margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
        clamp.set_child(content_box)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_child(clamp)

        toolbar_view.set_content(scroller)
        self.toast_overlay.set_child(toolbar_view)
        return self.toast_overlay

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
        dialog.select_folder(self, None, lambda dlg, result: self._on_folder_selected(dlg, result, entry_row))

    def _on_folder_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, entry_row: Adw.EntryRow) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        if folder is not None and folder.get_path():
            entry_row.set_text(folder.get_path())

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

    def _load_config(self) -> None:
        run_async(MiniDLNAConfig.load, self._on_config_loaded)

    def _on_config_loaded(self, config: MiniDLNAConfig | None, error: Exception | None) -> bool:
        if error is not None or config is None:
            show_error_toast(self.toast_overlay, "Não foi possível carregar o config atual", error, None)
            self.save_button.set_sensitive(False)
            return False
        self.config = config
        self.port_row.set_text(config.get("port") or "")
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
