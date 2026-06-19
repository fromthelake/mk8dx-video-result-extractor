"""Runs the extractor pipeline as a child process and streams its output.

The heavy work (frame extraction, OCR, export) is executed by re-invoking the
existing CLI (``python -m mk8dx_video_result_extractor.main <flags>``) as a
separate process. This keeps the Qt event loop completely free — the window
never freezes — and keeps cancellation isolated from the GUI process itself.

A :class:`QProcess` is used rather than ``subprocess`` + a thread because Qt
delivers the child's stdout to the GUI thread via signals, so there is no
cross-thread marshalling to get wrong.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

# Matches the per-race percentage the pipeline already prints, e.g. "Perc  16%".
_PERCENT_RE = re.compile(r"Perc\s+(\d+)%")


class PipelineRunner(QObject):
    """Owns a single QProcess running one pipeline action at a time."""

    line = Signal(str)          # one line of (decoded, ANSI-free) child output
    progress = Signal(int)      # 0-100 when a percentage is detected
    started = Signal(str)       # human-readable label of the action that started
    finished = Signal(bool, int)  # (success, exit_code)

    def __init__(self, project_python: str, working_dir: Path, parent: QObject | None = None):
        super().__init__(parent)
        self._python = project_python
        self._working_dir = str(working_dir)
        self._process: QProcess | None = None
        self._buffer = ""
        self._cancelled = False
        self._label = ""

    # -- state ---------------------------------------------------------------
    def is_running(self) -> bool:
        return self._process is not None and self._process.state() != QProcess.NotRunning

    # -- control -------------------------------------------------------------
    def start(self, label: str, cli_args: list[str], env_overrides: dict[str, str] | None = None) -> None:
        """Run a pipeline action via ``python -m ...main <cli_args>``."""
        self._launch(
            label,
            self._python,
            ["-u", "-m", "mk8dx_video_result_extractor.main", *cli_args],
            env_overrides,
        )

    def start_external(self, label: str, program: str, args: list[str], env_overrides: dict[str, str] | None = None) -> None:
        """Run an arbitrary external command (e.g. ffmpeg) and stream its output."""
        self._launch(label, program, list(args), env_overrides)

    def _launch(self, label: str, program: str, args: list[str], env_overrides: dict[str, str] | None) -> None:
        if self.is_running():
            return
        self._cancelled = False
        self._buffer = ""
        self._label = label

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.setWorkingDirectory(self._working_dir)
        process.setProgram(program)
        process.setArguments(args)

        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        environment.insert("PYTHONIOENCODING", "utf-8")
        # Ask the pipeline to emit ANSI colour codes even through a pipe; the log
        # widget parses them so the GUI shows the same colours as the console.
        environment.insert("MK8_FORCE_COLOR", "1")
        environment.remove("NO_COLOR")
        for key, value in (env_overrides or {}).items():
            environment.insert(key, value)
        process.setProcessEnvironment(environment)

        process.readyReadStandardOutput.connect(self._on_ready_read)
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)

        self._process = process
        process.start()
        self.started.emit(label)

    def cancel(self) -> None:
        if not self.is_running() or self._process is None:
            return
        self._cancelled = True
        self.line.emit("\n[GUI] Cancelling… terminating the running process.\n")
        _kill_process_tree(self._process)

    # -- internals -----------------------------------------------------------
    def _on_ready_read(self) -> None:
        if self._process is None:
            return
        raw = bytes(self._process.readAllStandardOutput().data())
        self._buffer += raw.decode("utf-8", errors="replace")
        *complete_lines, self._buffer = self._buffer.split("\n")
        for raw_line in complete_lines:
            text = raw_line.rstrip("\r")
            self.line.emit(text)
            match = _PERCENT_RE.search(text)
            if match:
                self.progress.emit(max(0, min(100, int(match.group(1)))))

    def _on_error(self, _error) -> None:
        if self._process is None:
            return
        self.line.emit(f"[GUI] Process error: {self._process.errorString()}")

    def _on_finished(self, exit_code: int, _exit_status) -> None:
        if self._buffer:
            self.line.emit(self._buffer)
            self._buffer = ""
        success = (exit_code == 0) and not self._cancelled
        process = self._process
        self._process = None
        if process is not None:
            process.deleteLater()
        self.finished.emit(success, exit_code)


def _kill_process_tree(process: QProcess) -> None:
    """Best-effort termination of the child process.

    The pipeline can launch its own subprocess (the OCR module) and worker
    processes, so simply killing the direct child can leave orphans. On Windows
    we use ``taskkill /T``. On Unix-like platforms this PySide6 binding does
    not expose a portable way to start the child in a new process group, so a
    process-group kill could target the GUI's own group. There we terminate only
    the direct child.
    """
    pid = int(process.processId())
    if pid <= 0:
        process.kill()
        return
    if sys.platform.startswith("win"):
        try:
            import subprocess

            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return
        except Exception:
            pass
    if not sys.platform.startswith("win"):
        process.terminate()
        if not process.waitForFinished(1500):
            process.kill()
        return
    process.kill()
