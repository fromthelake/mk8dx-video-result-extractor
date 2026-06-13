"""Window-icon helper. Best-effort: silently does nothing if no asset is found."""

from __future__ import annotations


def set_window_icon(window) -> None:
    try:
        from PySide6.QtGui import QIcon

        from ..data_paths import resolve_asset_file

        icon_path = resolve_asset_file("gui", "bg.jpg")
        window.setWindowIcon(QIcon(str(icon_path)))
    except Exception:
        pass
