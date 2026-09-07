from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw

from ui.compat import APPLICATION_DEFAULT_FLAGS
from ui.windows.main_window import MainWindow


class MiniDLNAManagerApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id="com.lvleo21.minidlnamanager", flags=APPLICATION_DEFAULT_FLAGS
        )

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = MainWindow(application=self)
        window.present()


def main() -> int:
    return MiniDLNAManagerApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
