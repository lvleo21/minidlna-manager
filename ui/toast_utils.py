from __future__ import annotations

import gi

gi.require_version("Adw", "1")

from gi.repository import Adw


def show_toast(overlay: Adw.ToastOverlay, message: str) -> None:
    overlay.add_toast(Adw.Toast(title=message))


def show_error_toast(
    overlay: Adw.ToastOverlay, message: str, error: Exception | None, result: dict | None
) -> None:
    detail = str(error) if error is not None else (result or {}).get("error", "")
    text = f"{message}: {detail}" if detail else message
    overlay.add_toast(Adw.Toast(title=text, timeout=0))
