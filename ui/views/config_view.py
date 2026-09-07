from __future__ import annotations

from typing import ClassVar

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, GObject, Gtk

from core.validator import LOG_CATEGORIES

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


class ConfigView(Gtk.ScrolledWindow):
    """Structured minidlna.conf form — pure display.

    Formatting/parsing of the actual config string values (log_level,
    media_dir) is the controller's job via core.validator; this class
    only works with plain field values (str/set/tuples).
    """

    __gsignals__: ClassVar[dict] = {
        "save-clicked": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "media-dir-selected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(vexpand=True, **kwargs)
        self.media_dir_rows: list[dict] = []
        self.log_category_checks: dict[str, Gtk.CheckButton] = {}
        self.interface_values: list[str] = [AUTO_INTERFACE_LABEL]
        self.set_child(self._build_content())

    # -- layout -----------------------------------------------------------------

    def _build_content(self) -> Gtk.Widget:
        save_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, halign=Gtk.Align.END)
        self.save_button = Gtk.Button(label="Salvar")
        self.save_button.add_css_class("suggested-action")
        self.save_button.connect("clicked", lambda _b: self.emit("save-clicked"))
        save_row.append(self.save_button)

        general_group = Adw.PreferencesGroup(title="Geral")
        self.friendly_name_row = Adw.EntryRow(title="Nome do servidor")
        self.port_row = Adw.EntryRow(title="Porta")

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
        add_button.connect("clicked", lambda _b: self.add_media_dir_row())
        self.media_dir_group.set_header_suffix(add_button)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content_box.append(save_row)
        content_box.append(general_group)
        content_box.append(log_group)
        content_box.append(self.media_dir_group)

        clamp = Adw.Clamp(margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
        clamp.set_child(content_box)
        return clamp

    # -- media dir rows: purely internal UI state, no controller round-trip needed --

    def add_media_dir_row(self, type_part: str | None = None, path: str = "") -> None:
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

    def _clear_media_dir_rows(self) -> None:
        for row_data in list(self.media_dir_rows):
            self._remove_media_dir_row(row_data)

    def _browse_media_dir(self, entry_row: Adw.EntryRow) -> None:
        dialog = Gtk.FileDialog(title="Selecionar diretório de mídia")
        dialog.select_folder(
            self.get_root(), None, lambda dlg, result: self._on_folder_selected(dlg, result, entry_row)
        )

    def _on_folder_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, entry_row: Adw.EntryRow) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        path = folder.get_path() if folder is not None else None
        if not path:
            return
        entry_row.set_text(path)
        self.emit("media-dir-selected", path)

    # -- form data API (controller <-> view) -----------------------------------------

    def set_interface_options(self, options: list[str]) -> None:
        self.interface_values = [AUTO_INTERFACE_LABEL, *options]
        self.interface_dropdown.set_model(Gtk.StringList.new(self.interface_values))

    def set_form_data(self, data: dict) -> None:
        self.friendly_name_row.set_text(data.get("friendly_name", ""))
        self.port_row.set_text(data.get("port", ""))

        interface = data.get("network_interface", "")
        if interface and interface in self.interface_values:
            self.interface_dropdown.set_selected(self.interface_values.index(interface))
        else:
            self.interface_dropdown.set_selected(0)

        log_categories = data.get("log_categories", set())
        for category, check in self.log_category_checks.items():
            check.set_active(category in log_categories)
        level = data.get("log_level", DEFAULT_LOG_LEVEL)
        level_index = LOG_LEVEL_VALUES.index(level) if level in LOG_LEVEL_VALUES else LOG_LEVEL_VALUES.index(
            DEFAULT_LOG_LEVEL
        )
        self.log_level_dropdown.set_selected(level_index)

        self._clear_media_dir_rows()
        for type_part, path in data.get("media_dirs", []):
            self.add_media_dir_row(type_part, path)

    def get_form_data(self) -> dict:
        return {
            "friendly_name": self.friendly_name_row.get_text().strip(),
            "port": self.port_row.get_text().strip(),
            "network_interface": self._interface_value(),
            "log_categories": {c for c, check in self.log_category_checks.items() if check.get_active()},
            "log_level": LOG_LEVEL_VALUES[self.log_level_dropdown.get_selected()],
            "media_dirs": [self._media_dir_row_value(row) for row in self.media_dir_rows],
        }

    def _interface_value(self) -> str:
        selected = self.interface_values[self.interface_dropdown.get_selected()]
        return "" if selected == AUTO_INTERFACE_LABEL else selected

    def _media_dir_row_value(self, row_data: dict) -> tuple[str | None, str]:
        type_part = MEDIA_DIR_TYPE_VALUES[row_data["type_dropdown"].get_selected()]
        path = row_data["entry_row"].get_text().strip()
        return type_part, path

    # -- error / sensitivity API -----------------------------------------------------

    def set_port_error(self, has_error: bool) -> None:
        if has_error:
            self.port_row.add_css_class("error")
        else:
            self.port_row.remove_css_class("error")

    def set_media_dir_errors(self, indices: set[int]) -> None:
        for index, row_data in enumerate(self.media_dir_rows):
            if index in indices:
                row_data["entry_row"].add_css_class("error")
            else:
                row_data["entry_row"].remove_css_class("error")

    def clear_errors(self) -> None:
        self.set_port_error(False)
        self.set_media_dir_errors(set())

    def set_save_sensitive(self, sensitive: bool) -> None:
        self.save_button.set_sensitive(sensitive)
