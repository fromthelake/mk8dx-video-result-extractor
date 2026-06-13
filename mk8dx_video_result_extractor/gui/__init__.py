"""PySide6 (Qt) desktop interface for the MK8DX Video Result Extractor.

This package is an optional front-end. It is only imported when the GUI is
launched, so headless / CLI usage never requires PySide6 to be installed.

The public entry point is :func:`run`, which boots a ``QApplication`` and shows
the main window. It returns a process exit code so it can be used directly as a
``main()`` return value.
"""

from __future__ import annotations


def run() -> int:
    """Boot the Qt application and run the main window event loop."""
    from .app import run as _run

    return _run()


__all__ = ["run"]
