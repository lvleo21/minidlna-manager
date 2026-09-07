"""Runs blocking calls (pkexec, systemctl, journalctl) off the GTK main loop."""
from __future__ import annotations

import threading
from collections.abc import Callable

from gi.repository import GLib


def run_async(func: Callable, callback: Callable, *args, **kwargs) -> None:
    """Run `func(*args, **kwargs)` in a worker thread, then call
    `callback(result, error)` on the GTK main loop once it's done.

    Any exception raised by `func` is caught here rather than left to
    propagate in the worker thread, where it would otherwise vanish
    silently and leave the UI waiting on a callback that never fires.
    """

    def worker() -> None:
        try:
            result = func(*args, **kwargs)
            error = None
        except Exception as exc:  # noqa: BLE001
            result = None
            error = exc
        GLib.idle_add(callback, result, error)

    threading.Thread(target=worker, daemon=True).start()
