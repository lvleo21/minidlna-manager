"""Opens the installed app's main window and exercises the shimmed widgets.

Run by test-deb.sh under xvfb. Importing the modules is not enough: every
widget incompatibility this package has shipped (Adw.SwitchRow, ToolbarView,
Gtk.FileDialog, ApplicationFlags.DEFAULT_FLAGS) was invisible to an import and
only failed once the window was actually built.
"""
import sys

sys.path.insert(0, "/usr/share/minidlna-manager")

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from ui import compat
from ui.app import MiniDLNAManagerApp
from ui.windows.main_window import MainWindow

gtk_version = f"{Gtk.MAJOR_VERSION}.{Gtk.MINOR_VERSION}.{Gtk.MICRO_VERSION}"
adw_version = f"{Adw.MAJOR_VERSION}.{Adw.MINOR_VERSION}.{Adw.MICRO_VERSION}"
native_rows = compat.HAVE_SWITCH_ROW and compat.HAVE_ENTRY_ROW
print(f"    GTK {gtk_version}, libadwaita {adw_version}, native rows: {native_rows}")

failures: list[Exception] = []


def on_activate(app: MiniDLNAManagerApp) -> None:
    try:
        window = MainWindow(application=app)
        window.present()

        config_view = window.config_controller.view
        config_view.set_form_data(
            {
                "friendly_name": "casa",
                "port": "8200",
                "log_level": "info",
                "log_categories": {"general"},
                "media_dirs": [("A", "/srv/audio")],
            }
        )
        data = config_view.get_form_data()
        assert data["friendly_name"] == "casa", data
        assert data["media_dirs"] == [("A", "/srv/audio")], data
        config_view.set_port_error(True)
        config_view.clear_errors()

        status_view = window.status_controller.view
        status_view.set_boot_switch(True)
        assert status_view.boot_switch_row.get_active() is True

        window.install_banner.set_revealed(True)
        window.install_banner.set_button_label("Instalar MiniDLNA")
    except Exception as exc:  # noqa: BLE001 - traceback is printed, exit code is the verdict
        import traceback

        traceback.print_exc()
        failures.append(exc)
    GLib.timeout_add(200, app.quit)


application = MiniDLNAManagerApp()
application.connect("activate", on_activate)
application.run([])
sys.exit(1 if failures else 0)
