from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from core import service_client
from core.config_parser import MiniDLNAConfig
from core.validator import (
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


class ConfigWindow(Adw.Window):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Configuração do MiniDLNA")
        self.set_default_size(560, 640)

        self.config: MiniDLNAConfig | None = None
        self.media_dir_rows: list[dict] = []

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
        self.log_level_row = Adw.EntryRow(title="Nível de log")
        general_group.add(self.port_row)
        general_group.add(self.log_level_row)

        self.media_dir_group = Adw.PreferencesGroup(title="Diretórios de mídia")
        add_button = Gtk.Button(icon_name="list-add-symbolic")
        add_button.add_css_class("flat")
        add_button.connect("clicked", lambda _b: self._add_media_dir_row())
        self.media_dir_group.set_header_suffix(add_button)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content_box.append(general_group)
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
        self.log_level_row.set_text(config.get("log_level") or "")
        for value in config.get_all("media_dir"):
            type_part, path = parse_media_dir(value)
            self._add_media_dir_row(type_part, path)
        return False

    # -- save ---------------------------------------------------------------------

    def _clear_field_errors(self) -> None:
        self.port_row.remove_css_class("error")
        self.log_level_row.remove_css_class("error")
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

        log_level_text = self.log_level_row.get_text().strip()
        if log_level_text:
            try:
                validate_log_level(log_level_text)
            except ValidationError as exc:
                self.log_level_row.add_css_class("error")
                errors.append(str(exc))

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
        if log_level_text:
            self.config.set("log_level", log_level_text)
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
