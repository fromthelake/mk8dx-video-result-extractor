"""A read-only log view that renders ANSI/SGR colour codes.

The pipeline already prints richly coloured console output (per-video neon
colours, cyan scope tags, yellow warnings…). When launched from the GUI it emits
those same ANSI escape codes, and this widget parses them into Qt text
formatting so the activity log looks like the console — while still preserving
the exact spacing the pipeline uses for aligned tables (we insert plain text
with per-run colours rather than HTML, which would collapse whitespace).
"""

from __future__ import annotations

import re

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

_SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")

# Default log foreground, matched to the log panel styling.
_DEFAULT_FG = QColor("#cdd6e5")

# Bright 16-colour ANSI palette (the logger uses the bold/bright variants).
_BASIC = {
    30: "#3b4252", 31: "#e0555a", 32: "#5fd07a", 33: "#e8c44a",
    34: "#5b9bf0", 35: "#c678dd", 36: "#56c8d8", 37: "#cdd6e5",
    90: "#6b7689", 91: "#ff6b6b", 92: "#6bff9a", 93: "#ffe066",
    94: "#74a9ff", 95: "#e89bff", 96: "#6ff0ff", 97: "#ffffff",
}


def _xterm256(index: int) -> QColor:
    if index < 16:
        key = 30 + index if index < 8 else 90 + (index - 8)
        return QColor(_BASIC.get(key, "#cdd6e5"))
    if index >= 232:
        value = 8 + 10 * (index - 232)
        return QColor(value, value, value)
    index -= 16
    red = index // 36
    green = (index % 36) // 6
    blue = index % 6
    convert = lambda channel: 0 if channel == 0 else 55 + 40 * channel
    return QColor(convert(red), convert(green), convert(blue))


class AnsiLogView(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(6000)
        self._fg = QColor(_DEFAULT_FG)
        self._bold = False
        self._dim = False

    def append_ansi(self, line: str) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        if not self.document().isEmpty():
            cursor.insertText("\n")

        position = 0
        for match in _SGR_RE.finditer(line):
            if match.start() > position:
                cursor.insertText(line[position:match.start()], self._char_format())
            self._apply_codes(match.group(1))
            position = match.end()
        if position < len(line):
            cursor.insertText(line[position:], self._char_format())

        self.moveCursor(QTextCursor.End)

    def reset_styles(self) -> None:
        self._fg = QColor(_DEFAULT_FG)
        self._bold = False
        self._dim = False

    # -- internals -----------------------------------------------------------
    def _char_format(self) -> QTextCharFormat:
        fmt = QTextCharFormat()
        color = QColor(self._fg)
        if self._dim:
            color = QColor(
                (color.red() + 9) // 2,
                (color.green() + 9) // 2,
                (color.blue() + 9) // 2,
            )
        fmt.setForeground(color)
        if self._bold:
            fmt.setFontWeight(75)
        return fmt

    def _apply_codes(self, raw: str) -> None:
        codes = [int(part) for part in raw.split(";") if part != ""] or [0]
        index = 0
        while index < len(codes):
            code = codes[index]
            if code == 0:
                self.reset_styles()
            elif code == 1:
                self._bold = True
            elif code == 2:
                self._dim = True
            elif code == 22:
                self._bold = False
                self._dim = False
            elif code == 39:
                self._fg = QColor(_DEFAULT_FG)
            elif code in _BASIC:
                self._fg = QColor(_BASIC[code])
            elif code == 38 and index + 1 < len(codes):
                mode = codes[index + 1]
                if mode == 5 and index + 2 < len(codes):
                    self._fg = _xterm256(codes[index + 2])
                    index += 2
                elif mode == 2 and index + 4 < len(codes):
                    self._fg = QColor(codes[index + 2], codes[index + 3], codes[index + 4])
                    index += 4
            index += 1
