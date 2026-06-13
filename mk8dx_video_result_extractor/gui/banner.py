"""Mario Kart 8 themed header banner.

Paints the MK8 Deluxe pattern artwork cover-scaled behind the title, with a dark
gradient overlay so text stays readable, and a Rainbow Road colour strip along
the bottom edge (a nod to the animated rainbow bars of the classic GUI, but
painted once on resize — no per-frame CPU cost).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from .images import load_asset_pixmap

# Rainbow Road stops (red → violet), used for the banner strip and progress bar.
RAINBOW_STOPS = [
    (0.00, "#ff3b3b"), (0.17, "#ff9e2c"), (0.34, "#ffe23b"),
    (0.51, "#4cd964"), (0.68, "#34a8ff"), (0.85, "#7a5cff"), (1.00, "#ff4ce0"),
]


class HeaderBanner(QFrame):
    STRIP_HEIGHT = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(92)
        self._pixmap: QPixmap | None = load_asset_pixmap("gui", "bg.jpg")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 12)

        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("MARIO KART 8 DELUXE")
        title.setObjectName("bannerTitle")
        subtitle = QLabel("LAN TOURNAMENT · VIDEO RESULT EXTRACTOR")
        subtitle.setObjectName("bannerSubtitle")
        title_block.addStretch(1)
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        title_block.addStretch(1)
        layout.addLayout(title_block)
        layout.addStretch(1)

        flag = QLabel("🏁")
        flag.setObjectName("bannerFlag")
        flag.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(flag)

    def paintEvent(self, event):  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        rect = self.rect()

        if self._pixmap is not None and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                rect.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            x = (scaled.width() - rect.width()) // 2
            y = (scaled.height() - rect.height()) // 2
            painter.drawPixmap(rect, scaled, QRect(x, y, rect.width(), rect.height()))
        else:
            painter.fillRect(rect, QColor("#101a26"))

        overlay = QLinearGradient(QPointF(0, 0), QPointF(rect.width(), 0))
        overlay.setColorAt(0.0, QColor(7, 10, 18, 235))
        overlay.setColorAt(0.6, QColor(7, 10, 18, 170))
        overlay.setColorAt(1.0, QColor(7, 10, 18, 120))
        painter.fillRect(rect, overlay)

        strip = QRect(0, rect.height() - self.STRIP_HEIGHT, rect.width(), self.STRIP_HEIGHT)
        rainbow = QLinearGradient(QPointF(strip.left(), 0), QPointF(strip.right(), 0))
        for position, color in RAINBOW_STOPS:
            rainbow.setColorAt(position, QColor(color))
        painter.fillRect(strip, rainbow)
        painter.end()
