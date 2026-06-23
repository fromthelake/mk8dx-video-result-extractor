"""QApplication bootstrap for the Qt GUI."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from . import theme
from .icon import set_window_icon
from .main_window import MainWindow


def run() -> int:
    # Crisp fractional HiDPI scaling (e.g. 125% / 150% Windows display scaling)
    # must be set before the QApplication is constructed.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("MK8DX Video Result Extractor")

    # An explicit point-based base font tracks the OS text-size setting and keeps
    # the UI legible regardless of the display's pixel density.
    base_font = app.font()
    base_font.setPointSizeF(9.0)
    app.setFont(base_font)

    theme.apply(app)

    window = MainWindow()
    set_window_icon(window)
    window.showMaximized()
    return app.exec()
