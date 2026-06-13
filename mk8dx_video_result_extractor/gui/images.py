"""Image loading helpers for the GUI.

Loads through Pillow (already a project dependency) and converts to QPixmap, so
we do not depend on Qt's optional image-format plugins (e.g. webp) being
present on every platform.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtGui import QImage, QPixmap


def load_pixmap(path: Path) -> QPixmap | None:
    try:
        image = Image.open(path).convert("RGBA")
    except Exception:
        return None
    data = image.tobytes("raw", "RGBA")
    qimage = QImage(data, image.width, image.height, QImage.Format_RGBA8888)
    # Copy so the QImage owns its buffer once `data` goes out of scope.
    return QPixmap.fromImage(qimage.copy())


def load_asset_pixmap(*relative_parts: str) -> QPixmap | None:
    try:
        from ..data_paths import resolve_asset_file

        return load_pixmap(resolve_asset_file(*relative_parts))
    except Exception:
        return None
