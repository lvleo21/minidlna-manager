"""Widget shims so the app runs on older GTK4/libadwaita stacks.

The UI is written against modern libadwaita, but Ubuntu 22.04 and Linux
Mint 21.x ship libadwaita 1.1 / GTK 4.6, where several of the rows and
containers used here simply don't exist yet. Each name below resolves to
the real widget when the running libadwaita provides it, and to an
equivalent built from 1.0-era primitives when it doesn't -- so new
systems keep the native look and old ones still get a working app.

Minimum required by these fallbacks: GTK 4.6, libadwaita 1.0, GLib 2.66.
"""
from __future__ import annotations

from typing import ClassVar

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, GObject, Gtk

# Feature probes, named after the libadwaita release that introduced each
# widget, rather than a version comparison: a distro may backport.
HAVE_ENTRY_ROW = hasattr(Adw, "EntryRow")  # 1.2
HAVE_BANNER = hasattr(Adw, "Banner")  # 1.3
HAVE_SWITCH_ROW = hasattr(Adw, "SwitchRow")  # 1.4
HAVE_TOOLBAR_VIEW = hasattr(Adw, "ToolbarView")  # 1.4
HAVE_FILE_DIALOG = hasattr(Gtk, "FileDialog")  # GTK 4.10

# G_APPLICATION_DEFAULT_FLAGS is GLib 2.74; FLAGS_NONE is the same value and
# is only deprecated, not removed, on newer GLib.
APPLICATION_DEFAULT_FLAGS = getattr(
    Gio.ApplicationFlags, "DEFAULT_FLAGS", Gio.ApplicationFlags.FLAGS_NONE
)


# -- rows -------------------------------------------------------------------------

if HAVE_ENTRY_ROW:

    class EntryRow(Adw.EntryRow):
        """Adw.EntryRow plus the set_error() the fallback also provides."""

        def set_error(self, has_error: bool) -> None:
            _toggle_css(self, "error", has_error)

else:

    class EntryRow(Adw.ActionRow):
        """Adw.EntryRow rebuilt on ActionRow + Gtk.Entry for libadwaita < 1.2."""

        def __init__(self, title: str = "", **kwargs) -> None:
            super().__init__(title=title, **kwargs)
            self._entry = Gtk.Entry(valign=Gtk.Align.CENTER, hexpand=True)
            self.add_suffix(self._entry)
            self.set_activatable_widget(self._entry)

        def get_text(self) -> str:
            return self._entry.get_text()

        def set_text(self, text: str) -> None:
            self._entry.set_text(text)

        def set_error(self, has_error: bool) -> None:
            # The real EntryRow paints the whole row; here the entry is the
            # only part that reads as a field, so mark both.
            _toggle_css(self, "error", has_error)
            _toggle_css(self._entry, "error", has_error)


if HAVE_SWITCH_ROW:
    SwitchRow = Adw.SwitchRow
else:

    class SwitchRow(Adw.ActionRow):
        """Adw.SwitchRow rebuilt on ActionRow + Gtk.Switch for libadwaita < 1.4.

        Mirrors the switch state onto an `active` property so callers can use
        `notify::active` exactly as they would with the real widget.
        """

        active = GObject.Property(type=bool, default=False)

        def __init__(self, title: str = "", **kwargs) -> None:
            super().__init__(title=title, **kwargs)
            self._switch = Gtk.Switch(valign=Gtk.Align.CENTER)
            self.add_suffix(self._switch)
            self.set_activatable_widget(self._switch)
            self._switch.connect("notify::active", self._on_switch_toggled)

        def _on_switch_toggled(self, *_args) -> None:
            if self.props.active != self._switch.get_active():
                self.props.active = self._switch.get_active()

        def get_active(self) -> bool:
            return self._switch.get_active()

        def set_active(self, active: bool) -> None:
            self._switch.set_active(active)


# -- containers -------------------------------------------------------------------

if HAVE_TOOLBAR_VIEW:
    ToolbarView = Adw.ToolbarView
else:

    class ToolbarView(Gtk.Box):
        """Adw.ToolbarView reduced to what this app uses: top bars stacked
        above a single content child, for libadwaita < 1.4.
        """

        def __init__(self, **kwargs) -> None:
            super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
            self._content: Gtk.Widget | None = None

        def add_top_bar(self, widget: Gtk.Widget) -> None:
            # Top bars are always added before the content in this app, so
            # appending keeps them above it.
            self.append(widget)

        def set_content(self, widget: Gtk.Widget | None) -> None:
            if self._content is not None:
                self.remove(self._content)
            self._content = widget
            if widget is not None:
                widget.set_vexpand(True)
                self.append(widget)


if HAVE_BANNER:
    Banner = Adw.Banner
else:

    class Banner(Gtk.Revealer):
        """Adw.Banner rebuilt on a Revealer for libadwaita < 1.3."""

        __gsignals__: ClassVar[dict] = {
            "button-clicked": (GObject.SignalFlags.RUN_FIRST, None, ())
        }

        def __init__(self, title: str = "", **kwargs) -> None:
            super().__init__(reveal_child=False, **kwargs)
            self._label = Gtk.Label(label=title, xalign=0.0, hexpand=True, wrap=True)
            self._button = Gtk.Button(valign=Gtk.Align.CENTER, visible=False)
            self._button.connect("clicked", lambda _b: self.emit("button-clicked"))

            box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=12,
                margin_top=8,
                margin_bottom=8,
                margin_start=12,
                margin_end=12,
            )
            box.append(self._label)
            box.append(self._button)
            box.add_css_class("toolbar")
            self.set_child(box)

        def set_title(self, title: str) -> None:
            self._label.set_label(title)

        def set_button_label(self, label: str | None) -> None:
            self._button.set_label(label or "")
            self._button.set_visible(bool(label))

        def set_revealed(self, revealed: bool) -> None:
            self.set_reveal_child(revealed)

        def get_revealed(self) -> bool:
            return self.get_reveal_child()


# -- helpers ----------------------------------------------------------------------

def add_page(stack: Adw.ViewStack, child: Gtk.Widget, name: str, title: str, icon: str) -> None:
    """Adw.ViewStack.add_titled_with_icon() is 1.2; set the icon on the page
    itself where it isn't available.
    """
    if hasattr(stack, "add_titled_with_icon"):
        stack.add_titled_with_icon(child, name, title, icon)
    else:
        stack.add_titled(child, name, title).set_icon_name(icon)


# Native folder choosers are owned by the caller until they respond; without a
# reference of our own the Python wrapper can be collected while still open.
_pending_choosers: set[Gtk.NativeDialog] = set()


def select_folder(parent: Gtk.Window | None, title: str, on_selected) -> None:
    """Ask for a directory and call on_selected(path); silent if cancelled.

    Gtk.FileDialog is GTK 4.10; FileChooserNative is the pre-4.10 route and
    is deprecated but still functional on newer GTK.
    """
    if HAVE_FILE_DIALOG:
        dialog = Gtk.FileDialog(title=title)

        def _finished(dlg: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
            try:
                folder = dlg.select_folder_finish(result)
            except GLib.Error:
                return
            path = folder.get_path() if folder is not None else None
            if path:
                on_selected(path)

        dialog.select_folder(parent, None, _finished)
        return

    chooser = Gtk.FileChooserNative(
        title=title, transient_for=parent, action=Gtk.FileChooserAction.SELECT_FOLDER
    )
    _pending_choosers.add(chooser)

    def _responded(dlg: Gtk.FileChooserNative, response: int) -> None:
        _pending_choosers.discard(dlg)
        if response == Gtk.ResponseType.ACCEPT:
            folder = dlg.get_file()
            path = folder.get_path() if folder is not None else None
            if path:
                on_selected(path)
        dlg.destroy()

    chooser.connect("response", _responded)
    chooser.show()


def _toggle_css(widget: Gtk.Widget, css_class: str, enabled: bool) -> None:
    if enabled:
        widget.add_css_class(css_class)
    else:
        widget.remove_css_class(css_class)
