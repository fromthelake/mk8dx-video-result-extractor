"""Adapter between the Qt GUI and the existing pipeline/CLI code in ``main``.

The GUI only ever touches the core through this module, so the coupling lives in
one place. Everything here is lightweight (path discovery, config read/write,
opening folders) — the heavy pipeline work is never run in-process from the GUI;
it is launched as a child process via :mod:`process_runner`.
"""

from __future__ import annotations

from pathlib import Path

from .. import main as core


def input_dir() -> Path:
    return core.INPUT_DIR


def output_dir() -> Path:
    return core.OUTPUT_DIR


def frames_dir() -> Path:
    return core.FRAMES_DIR


def project_python() -> str:
    return core.resolve_project_python()


def latest_results_path() -> Path:
    return core.find_latest_results_xlsx(core.OUTPUT_DIR)


def open_in_file_manager(path: Path) -> None:
    core.open_path(path)


def list_videos(*, include_subfolders: bool) -> list[tuple[str, str]]:
    """Return ``(display_name, selector_value)`` for each discoverable video.

    ``selector_value`` is what gets passed to the CLI ``--videos`` flag: the
    file name when subfolders are off, or the Input_Videos-relative POSIX path
    when they are on (matching how the pipeline identifies selected videos).
    """
    videos = core.discover_input_video_files(include_subfolders=include_subfolders)
    rows: list[tuple[str, str]] = []
    base = core.INPUT_DIR
    for path in videos:
        if include_subfolders:
            try:
                value = str(path.relative_to(base)).replace("\\", "/")
            except ValueError:
                value = path.name
        else:
            value = path.name
        rows.append((value, value))
    return rows


def current_modes() -> tuple[str, str]:
    """Return ``(execution_mode, easyocr_gpu_mode)`` in upper case for the UI."""
    config = core.load_app_config()
    return config.execution_mode.upper(), config.easyocr_gpu_mode.upper()


def persist_modes(execution_mode: str, easyocr_mode: str) -> None:
    """Persist runtime mode settings so child processes pick them up."""
    execution = execution_mode.strip().lower()
    easyocr = easyocr_mode.strip().lower()
    core.update_app_config_values(
        {"execution_mode": execution, "easyocr_gpu_mode": easyocr}
    )


def mode_env(execution_mode: str, easyocr_mode: str) -> dict[str, str]:
    """Environment overrides to hand a child process for the chosen modes."""
    return {
        "MK8_EXECUTION_MODE": execution_mode.strip().lower(),
        "MK8_EASYOCR_GPU_MODE": easyocr_mode.strip().lower(),
    }
