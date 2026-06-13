"""Main application window for the Qt GUI.

The layout guides the user through the natural race order, top to bottom:

    [ MK8 banner ]
    ① Prepare videos  →  ② Choose videos  →  ③ Run  →  🏁 Results
    [ live activity log ]
    [ Rainbow Road progress bar + start-light status ]

All long-running work is delegated to :class:`PipelineRunner`, which runs the
existing CLI as a child process, so the window stays responsive and shows a
live, coloured log, a progress bar, and a working Cancel button.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from . import core_bridge as core
from .ansi_log import AnsiLogView
from .banner import HeaderBanner
from .process_runner import PipelineRunner
from .start_light import StartLight

_MODE_CHOICES = ["AUTO", "GPU", "CPU"]


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("cardHint")
    label.setWordWrap(True)
    return label


def _numbered_card(number: str, title: str, hint: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    """A stage card with a numbered badge header, returning (frame, body layout)."""
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(13, 9, 13, 10)
    layout.setSpacing(6)

    header = QHBoxLayout()
    header.setSpacing(8)
    badge = QLabel(number)
    badge.setObjectName("stepBadge")
    title_label = QLabel(title)
    title_label.setObjectName("cardTitle")
    header.addWidget(badge)
    header.addWidget(title_label)
    header.addStretch(1)
    layout.addLayout(header)
    if hint:
        layout.addWidget(_hint(hint))
    return frame, layout


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("Mario Kart 8 Deluxe — Tournament Video Extractor")
        self.resize(1060, 700)
        self.setMinimumSize(900, 600)

        self._runner = PipelineRunner(core.project_python(), core.input_dir())
        self._runner.line.connect(self._on_line)
        self._runner.progress.connect(self._on_progress)
        self._runner.started.connect(self._on_started)
        self._runner.finished.connect(self._on_finished)

        self._run_start_time = 0.0
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        self._busy_buttons: list[QPushButton] = []

        self._build_ui()
        self._reload_video_list()
        self._set_status("ready", "On the line — ready")

    # -- construction --------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 10)
        outer.setSpacing(10)

        outer.addWidget(HeaderBanner())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left_column())
        splitter.addWidget(self._build_log_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        splitter.setChildrenCollapsible(False)
        outer.addWidget(splitter, stretch=1)

        outer.addLayout(self._build_footer())

    def _build_left_column(self) -> QWidget:
        container = QWidget()
        container.setObjectName("scrollBody")
        column = QVBoxLayout(container)
        column.setContentsMargins(0, 0, 6, 0)
        column.setSpacing(9)
        column.addWidget(self._build_prepare_card())
        column.addWidget(self._build_videos_card())
        column.addWidget(self._build_run_card())
        column.addWidget(self._build_results_card())
        column.addWidget(self._build_settings_card())
        column.addStretch(1)

        # A scroll area keeps every card at its natural size and adds a scrollbar
        # when the window is short, instead of compressing cards until they overlap.
        scroll = QScrollArea()
        scroll.setObjectName("leftScroll")
        scroll.setWidget(container)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)
        return scroll

    def _build_prepare_card(self) -> QFrame:
        frame, layout = _numbered_card(
            "1", "Prepare videos",
            "Drop your tournament recordings into the Input_Videos folder. "
            "Use Combine Clips to join split recordings into one race session.",
        )
        row = QHBoxLayout()
        open_folder = QPushButton("📂  Open Input_Videos")
        open_folder.clicked.connect(self._open_video_folder)
        combine = QPushButton("🎬  Combine Clips…")
        combine.clicked.connect(self._combine_clips)
        row.addWidget(open_folder)
        row.addWidget(combine)
        layout.addLayout(row)
        self._combine_btn = combine
        return frame

    def _build_videos_card(self) -> QFrame:
        frame, layout = _numbered_card(
            "2", "Choose videos",
            "Tick the videos to include in the next run.",
        )

        self._video_list = QListWidget()
        self._video_list.setSelectionMode(QListWidget.NoSelection)
        self._video_list.setMinimumHeight(84)
        self._video_list.setMaximumHeight(150)
        self._video_list.itemChanged.connect(self._update_selection_summary)
        layout.addWidget(self._video_list)

        controls = QHBoxLayout()
        self._summary_label = _hint("")
        controls.addWidget(self._summary_label, stretch=1)
        select_all = QPushButton("All")
        select_all.clicked.connect(lambda: self._set_all_checked(True))
        select_none = QPushButton("None")
        select_none.clicked.connect(lambda: self._set_all_checked(False))
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._reload_video_list)
        for button in (select_all, select_none, refresh):
            button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
            controls.addWidget(button)
        layout.addLayout(controls)
        return frame

    def _build_run_card(self) -> QFrame:
        frame, layout = _numbered_card(
            "3", "Run the analysis",
            "Run the full pipeline, or each stage on its own.",
        )

        # Full Run is the headline action — the green start light.
        run_row = QHBoxLayout()
        self._full_run_btn = QPushButton("▶  FULL RUN")
        self._full_run_btn.setObjectName("primary")
        self._full_run_btn.setToolTip("Extract race frames, run OCR, and export the workbook")
        self._full_run_btn.clicked.connect(self._run_full)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("danger")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._runner.cancel)
        run_row.addWidget(self._full_run_btn, stretch=1)
        run_row.addWidget(self._cancel_btn)
        layout.addLayout(run_row)

        # Individual stages, shown as an ordered Extract → OCR sequence.
        steps_row = QHBoxLayout()
        steps_row.setSpacing(6)
        self._extract_btn = QPushButton("Extract frames")
        self._extract_btn.clicked.connect(self._run_extract)
        arrow = QLabel("→")
        arrow.setObjectName("stageArrow")
        self._ocr_btn = QPushButton("OCR && export")
        self._ocr_btn.clicked.connect(self._run_ocr)
        steps_row.addWidget(self._extract_btn, stretch=1)
        steps_row.addWidget(arrow)
        steps_row.addWidget(self._ocr_btn, stretch=1)
        layout.addLayout(steps_row)
        return frame

    def _build_results_card(self) -> QFrame:
        frame, layout = _numbered_card(
            "🏁", "Results",
            "Open the exported workbook or the extracted frames.",
        )
        row = QHBoxLayout()
        open_excel = QPushButton("📊  Open Latest Excel")
        open_excel.clicked.connect(self._open_excel)
        open_frames = QPushButton("🖼  Open Frames")
        open_frames.clicked.connect(self._open_frames)
        row.addWidget(open_excel)
        row.addWidget(open_frames)
        layout.addLayout(row)
        return frame

    def _build_settings_card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(13, 9, 13, 10)
        layout.setSpacing(6)

        title = QLabel("Settings & cleanup")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        self._subfolders_check = QCheckBox("Also look in subfolders of Input_Videos")
        self._subfolders_check.toggled.connect(self._reload_video_list)
        layout.addWidget(self._subfolders_check)

        execution_mode, easyocr_mode = core.current_modes()
        modes_row = QHBoxLayout()
        modes_row.setSpacing(14)
        modes_row.addWidget(_hint("Extraction"))
        self._extract_mode = self._mode_combo(execution_mode)
        modes_row.addWidget(self._extract_mode)
        modes_row.addWidget(_hint("EasyOCR"))
        self._easyocr_mode = self._mode_combo(easyocr_mode)
        modes_row.addWidget(self._easyocr_mode)
        modes_row.addStretch(1)
        layout.addLayout(modes_row)

        cleanup_row = QHBoxLayout()
        clear_frames = QPushButton("Delete frames")
        clear_frames.setObjectName("danger")
        clear_frames.clicked.connect(self._clear_frames)
        clear_output = QPushButton("Clear output")
        clear_output.setObjectName("danger")
        clear_output.clicked.connect(self._clear_output)
        cleanup_row.addStretch(1)
        cleanup_row.addWidget(clear_frames)
        cleanup_row.addWidget(clear_output)
        layout.addLayout(cleanup_row)

        self._busy_buttons = [
            self._extract_btn, self._ocr_btn, self._full_run_btn,
            self._combine_btn, clear_frames, clear_output,
        ]
        return frame

    def _mode_combo(self, current: str) -> QComboBox:
        combo = QComboBox()
        combo.addItems(_MODE_CHOICES)
        combo.setCurrentText(current if current in _MODE_CHOICES else "AUTO")
        combo.currentTextChanged.connect(self._persist_modes)
        return combo

    def _build_log_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(13, 9, 13, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("Activity log")
        title.setObjectName("cardTitle")
        header.addWidget(title)
        header.addStretch(1)
        clear_log = QPushButton("Clear")
        clear_log.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        header.addWidget(clear_log)
        layout.addLayout(header)

        self._log = AnsiLogView()
        self._log.setObjectName("log")
        self._log.setPlaceholderText("Output from the running pipeline appears here, in colour.")
        clear_log.clicked.connect(self._log.clear)
        layout.addWidget(self._log, stretch=1)
        return frame

    def _build_footer(self) -> QVBoxLayout:
        footer = QVBoxLayout()
        footer.setSpacing(8)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat("")
        footer.addWidget(self._progress)

        status_row = QHBoxLayout()
        self._start_light = StartLight()
        self._status_text = QLabel("Ready")
        self._status_text.setObjectName("sectionHint")
        self._elapsed_label = QLabel("")
        self._elapsed_label.setObjectName("sectionHint")
        status_row.addWidget(self._start_light)
        status_row.addSpacing(8)
        status_row.addWidget(self._status_text)
        status_row.addStretch(1)
        status_row.addWidget(self._elapsed_label)
        footer.addLayout(status_row)
        return footer

    # -- video selection -----------------------------------------------------
    def _reload_video_list(self) -> None:
        self._video_list.blockSignals(True)
        self._video_list.clear()
        rows = core.list_videos(include_subfolders=self._subfolders_check.isChecked())
        for display, value in rows:
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, value)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self._video_list.addItem(item)
        self._video_list.blockSignals(False)
        if not rows:
            self._log.append_ansi("[GUI] No videos found in Input_Videos.")
        self._update_selection_summary()

    def _set_all_checked(self, checked: bool) -> None:
        state = Qt.Checked if checked else Qt.Unchecked
        for index in range(self._video_list.count()):
            self._video_list.item(index).setCheckState(state)

    def _selected_video_values(self) -> list[str]:
        values: list[str] = []
        for index in range(self._video_list.count()):
            item = self._video_list.item(index)
            if item.checkState() == Qt.Checked:
                values.append(str(item.data(Qt.UserRole)))
        return values

    def _update_selection_summary(self, *_args) -> None:
        total = self._video_list.count()
        selected = len(self._selected_video_values())
        self._summary_label.setText(f"{selected} of {total} selected")

    # -- pipeline actions ----------------------------------------------------
    def _common_run_args(self) -> tuple[list[str], list[str]]:
        scope_args: list[str] = []
        if self._subfolders_check.isChecked():
            scope_args.append("--subfolders")
        return scope_args, self._selected_video_values()

    def _is_subset_selected(self, selected: list[str]) -> bool:
        return 0 < len(selected) < self._video_list.count()

    def _guard_ready(self) -> bool:
        if self._runner.is_running():
            return False
        if self._video_list.count() == 0:
            QMessageBox.warning(self, "No videos", "Place videos in Input_Videos first.")
            return False
        if not self._selected_video_values():
            QMessageBox.warning(self, "Nothing selected", "Tick at least one video to process.")
            return False
        return True

    def _run_extract(self) -> None:
        if not self._guard_ready():
            return
        scope, selected = self._common_run_args()
        args = ["--extract", *scope]
        if self._is_subset_selected(selected):
            args += ["--videos", *selected]
        self._start("Extracting race frames", args)

    def _run_ocr(self) -> None:
        if not self._guard_ready():
            return
        scope, selected = self._common_run_args()
        if self._is_subset_selected(selected):
            args = ["--ocr", "--selection", *scope, "--videos", *selected]
        else:
            args = ["--ocr", *scope]
        self._start("Running OCR and export", args)

    def _run_full(self) -> None:
        if not self._guard_ready():
            return
        scope, selected = self._common_run_args()
        args = ["--selection", *scope]
        if self._is_subset_selected(selected):
            args += ["--videos", *selected]
        self._start("Full run (extract + OCR + export)", args)

    def _start(self, label: str, args: list[str]) -> None:
        env = core.mode_env(self._extract_mode.currentText(), self._easyocr_mode.currentText())
        self._runner.start(label, args, env)

    # -- folder / file helpers ----------------------------------------------
    def _open_video_folder(self) -> None:
        self._open_path(core.input_dir(), "Input_Videos folder does not exist.")

    def _open_frames(self) -> None:
        self._open_path(core.frames_dir(), "The frames folder does not exist yet.")

    def _open_excel(self) -> None:
        latest = core.latest_results_path()
        if latest.exists():
            self._open_path(latest, "")
        else:
            QMessageBox.information(self, "No results", "Run OCR & Export first to create a workbook.")

    def _open_path(self, path: Path, missing_message: str) -> None:
        if not path.exists():
            if missing_message:
                QMessageBox.warning(self, "Not found", missing_message)
            return
        try:
            core.open_in_file_manager(path)
        except Exception as exc:  # pragma: no cover - platform dependent
            QMessageBox.critical(self, "Error", f"Unable to open {path}:\n{exc}")

    def _combine_clips(self) -> None:
        import shutil

        if self._runner.is_running():
            return
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            QMessageBox.critical(self, "ffmpeg missing", "ffmpeg was not found on PATH.")
            return
        sources, _ = QFileDialog.getOpenFileNames(
            self, "Select clips to combine", str(core.input_dir()),
            "Video files (*.mp4 *.mkv *.avi *.mov *.webm)",
        )
        if not sources:
            return
        target, _ = QFileDialog.getSaveFileName(
            self, "Save combined video as", str(core.input_dir() / "combined.mp4"),
            "MP4 files (*.mp4)",
        )
        if not target:
            return
        list_file = core.input_dir() / "_gui_concat_list.txt"
        try:
            list_file.write_text(
                "".join(f"file '{Path(src).as_posix()}'\n" for src in sources),
                encoding="utf-8",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not write concat list:\n{exc}")
            return
        args = ["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", "-y", target]
        self._runner.start_external("Combining clips with ffmpeg", ffmpeg, args)

    def _clear_frames(self) -> None:
        if self._runner.is_running():
            return
        if QMessageBox.question(
            self, "Delete frames",
            "Delete all extracted race screenshots?\nThis cannot be undone.",
        ) != QMessageBox.Yes:
            return
        try:
            from .. import main as core_module
            removed = (
                core_module.remove_tree_contents(core_module.FRAMES_DIR)
                if core_module.FRAMES_DIR.exists() else False
            )
            self._log.append_ansi("[GUI] Frames deleted." if removed else "[GUI] No frames to delete.")
            self._set_status("ready", "On the line — ready")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Unable to clear frames:\n{exc}")

    def _clear_output(self) -> None:
        if self._runner.is_running():
            return
        if QMessageBox.question(
            self, "Clear output",
            "Delete everything under Output_Results (frames, workbooks, CSVs)?\nThis cannot be undone.",
        ) != QMessageBox.Yes:
            return
        try:
            from .. import main as core_module
            removed = (
                core_module.remove_tree_contents(core_module.OUTPUT_DIR)
                if core_module.OUTPUT_DIR.exists() else False
            )
            core_module.ensure_output_results_structure()
            self._log.append_ansi(
                "[GUI] Output_Results cleared." if removed else "[GUI] Output_Results was already empty."
            )
            self._set_status("ready", "On the line — ready")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Unable to clear output:\n{exc}")

    def _persist_modes(self, *_args) -> None:
        core.persist_modes(self._extract_mode.currentText(), self._easyocr_mode.currentText())

    # -- runner signal handlers ---------------------------------------------
    def _on_line(self, text: str) -> None:
        self._log.append_ansi(text)

    def _on_started(self, label: str) -> None:
        self._set_busy(True)
        self._set_status("running", label)
        self._progress.setRange(0, 0)  # indeterminate until a percentage arrives
        self._progress.setFormat("")
        self._run_start_time = time.monotonic()
        self._elapsed_timer.start()
        self._log.reset_styles()
        self._log.append_ansi(f"\n=== ▶ {label} ===")

    def _on_progress(self, percent: int) -> None:
        if self._progress.maximum() == 0:
            self._progress.setRange(0, 100)
        self._progress.setValue(percent)
        self._progress.setFormat(f"{percent}%")

    def _on_finished(self, success: bool, exit_code: int) -> None:
        self._elapsed_timer.stop()
        self._set_busy(False)
        self._progress.setRange(0, 100)
        if success:
            self._progress.setValue(100)
            self._progress.setFormat("🏁 Finished")
            self._set_status("done", "Finished")
            self._log.append_ansi("=== 🏁 Completed successfully ===\n")
        elif exit_code == 0:
            self._progress.setValue(0)
            self._progress.setFormat("")
            self._set_status("cancelled", "Cancelled")
            self._log.append_ansi("=== ■ Cancelled ===\n")
        else:
            self._progress.setValue(0)
            self._progress.setFormat("Failed")
            self._set_status("error", f"Failed (exit {exit_code})")
            self._log.append_ansi(f"=== ✖ Failed with exit code {exit_code} ===\n")

    def _set_busy(self, busy: bool) -> None:
        for button in self._busy_buttons:
            button.setEnabled(not busy)
        self._cancel_btn.setEnabled(busy)

    # -- status --------------------------------------------------------------
    def _set_status(self, kind: str, text: str) -> None:
        self._start_light.set_state(kind)
        self._status_text.setText(text)
        if kind not in ("running",):
            self._elapsed_label.setText("")

    def _tick_elapsed(self) -> None:
        seconds = int(time.monotonic() - self._run_start_time)
        self._elapsed_label.setText(f"⏱ {seconds // 60:02d}:{seconds % 60:02d}")

    # -- window lifecycle ----------------------------------------------------
    def closeEvent(self, event):  # noqa: N802 (Qt naming)
        if self._runner.is_running():
            if QMessageBox.question(
                self, "Quit",
                "A run is still in progress. Stop it and quit?",
            ) != QMessageBox.Yes:
                event.ignore()
                return
            self._runner.cancel()
        event.accept()
