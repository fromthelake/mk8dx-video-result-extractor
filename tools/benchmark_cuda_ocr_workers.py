#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd


DEFAULT_EIND_RONDE_CLASSES = [
    "2026-03-28__eind_ronde__Kampioen_2026-03-27_21-50-56",
    "2026-03-28__eind_ronde__Talent_2026-03-27_21-50-56",
    "2026-03-28__eind_ronde__Wild_2026-03-27_21-50-56",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark CUDA EasyOCR worker and reader-lock variants on saved frame bundles."
    )
    parser.add_argument(
        "--race-class",
        action="append",
        dest="race_classes",
        help="Race class to OCR. Supply multiple times. Defaults to the 2026-03-28/eind_ronde validation set.",
    )
    parser.add_argument(
        "--variants",
        default="default,2,4,8,2-nolock,4-nolock",
        help="Comma-separated variants: default, N, or N-nolock.",
    )
    parser.add_argument(
        "--baseline-debug-csv",
        type=Path,
        help="Optional debug CSV to compare against.",
    )
    parser.add_argument(
        "--expected-mii-player",
        action="append",
        default=[],
        help="Expected Mii player in name=count form, e.g. 'jan willem=16'.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=1800.0,
        help="Per-run timeout.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Benchmark artifact directory. Defaults under .ab_runs.",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(".venv") / "Scripts" / "python.exe",
        help="Python interpreter to run the OCR command.",
    )
    return parser.parse_args()


def parse_variants(raw_value: str) -> list[dict[str, object]]:
    variants = []
    for raw_part in str(raw_value).split(","):
        token = raw_part.strip().lower()
        if not token:
            continue
        if token == "default":
            variants.append({"label": "default", "workers": None, "disable_lock": False})
            continue
        disable_lock = token.endswith("-nolock")
        worker_token = token.removesuffix("-nolock")
        worker_count = int(worker_token)
        if worker_count <= 0:
            raise ValueError(f"Worker count must be positive: {token}")
        label = f"workers_{worker_count}{'_nolock' if disable_lock else ''}"
        variants.append({"label": label, "workers": worker_count, "disable_lock": disable_lock})
    if not variants:
        raise ValueError("No benchmark variants supplied.")
    return variants


def parse_expected_mii_players(raw_values: list[str]) -> dict[str, int]:
    expected = {}
    for value in raw_values:
        if "=" not in value:
            raise ValueError(f"Expected Mii player must use name=count: {value}")
        name, count = value.rsplit("=", 1)
        expected[str(name).strip()] = int(count)
    return expected


def quote_csv_value(value: object) -> str:
    text = "" if value is None else str(value)
    if any(char in text for char in [",", '"', "\n"]):
        return '"' + text.replace('"', '""') + '"'
    return text


def latest_debug_csv_since(project_root: Path, start_timestamp: float) -> Path | None:
    debug_dir = project_root / "Output_Results" / "Debug"
    candidates = []
    for path in debug_dir.glob("*_Tournament_Results_Debug.csv"):
        if path.stat().st_mtime >= start_timestamp - 1.0:
            candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def build_env(variant: dict[str, object]) -> dict[str, str]:
    env = os.environ.copy()
    env["MK8_EASYOCR_GPU_MODE"] = "auto"
    env["MK8_CHARACTER_PRIOR_REPLAY"] = "1"
    env["MK8_WRITE_DEBUG_CSV"] = "1"
    env["MK8_WRITE_DEBUG_SCORE_IMAGES"] = "0"
    env["MK8_WRITE_DEBUG_LINKING_EXCEL"] = "0"
    env["MK8_HEADLESS_DEBUG"] = "1"
    if variant["workers"] is None:
        env.pop("MK8_CUDA_OCR_WORKERS", None)
    else:
        env["MK8_CUDA_OCR_WORKERS"] = str(variant["workers"])
    if variant["disable_lock"]:
        env["MK8_DISABLE_EASYOCR_READER_LOCK"] = "1"
    else:
        env.pop("MK8_DISABLE_EASYOCR_READER_LOCK", None)
    return env


def compare_debug_csv(baseline_path: Path, candidate_path: Path) -> dict[str, int]:
    baseline = pd.read_csv(baseline_path)
    candidate = pd.read_csv(candidate_path)
    keys = ["Video", "Race", "Position"]
    columns = {
        "player_diffs": ("Standardized Player", "Standardized Player"),
        "character_diffs": ("Character", "Character"),
        "race_points_diffs": ("Race Points", "Race Points"),
        "total_after_diffs": ("Tournament Total After Race", "Tournament Total After Race"),
        "position_after_diffs": ("Position After Race", "Position After Race"),
    }
    left = baseline[keys + [left_col for left_col, _right_col in columns.values()]].copy()
    right = candidate[keys + [right_col for _left_col, right_col in columns.values()]].copy()
    merged = left.merge(right, on=keys, suffixes=("_baseline", "_candidate"))
    result = {
        "baseline_rows": int(len(baseline)),
        "candidate_rows": int(len(candidate)),
        "shared_rows": int(len(merged)),
    }
    for metric, (left_col, right_col) in columns.items():
        left_name = f"{left_col}_baseline" if left_col == right_col else left_col
        right_name = f"{right_col}_candidate" if left_col == right_col else right_col
        result[metric] = int(
            (
                merged[left_name].fillna("").astype(str)
                != merged[right_name].fillna("").astype(str)
            ).sum()
        )
    return result


def evaluate_output(debug_csv: Path | None, baseline_debug_csv: Path | None, expected_mii: dict[str, int]) -> dict[str, object]:
    if debug_csv is None or not debug_csv.exists():
        return {"rows": "", "races": "", "mii_rows": "", "expected_mii_ok": "", "debug_csv": ""}
    df = pd.read_csv(debug_csv)
    result: dict[str, object] = {
        "debug_csv": str(debug_csv),
        "rows": int(len(df)),
        "races": int(df[["Video", "Race"]].drop_duplicates().shape[0]) if {"Video", "Race"}.issubset(df.columns) else "",
        "mii_rows": int((df["Character"].fillna("").astype(str) == "Mii").sum()) if "Character" in df.columns else "",
    }
    if expected_mii:
        actual_counts = (
            df.loc[df["Character"].fillna("").astype(str) == "Mii", "Standardized Player"]
            .fillna("")
            .astype(str)
            .value_counts()
            .to_dict()
        )
        result["expected_mii_ok"] = all(int(actual_counts.get(name, 0)) == count for name, count in expected_mii.items())
        result["expected_mii_counts"] = "; ".join(f"{name}={int(actual_counts.get(name, 0))}/{count}" for name, count in expected_mii.items())
    else:
        result["expected_mii_ok"] = ""
        result["expected_mii_counts"] = ""
    if baseline_debug_csv and baseline_debug_csv.exists():
        result.update(compare_debug_csv(baseline_debug_csv, debug_csv))
    elif baseline_debug_csv:
        result["baseline_error"] = f"missing baseline debug CSV: {baseline_debug_csv}"
    return result


def extract_logged_duration(stdout: str) -> str:
    matches = re.findall(r"Duration:\s+([0-9:]+)", stdout)
    return matches[-1] if matches else ""


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    python_path = args.python if args.python.is_absolute() else project_root / args.python
    if not python_path.exists():
        raise SystemExit(f"Python interpreter not found: {python_path}")

    race_classes = args.race_classes or DEFAULT_EIND_RONDE_CLASSES
    variants = parse_variants(args.variants)
    expected_mii = parse_expected_mii_players(args.expected_mii_player)
    if args.baseline_debug_csv and not args.baseline_debug_csv.is_absolute():
        args.baseline_debug_csv = project_root / args.baseline_debug_csv
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or (project_root / ".ab_runs" / f"cuda_ocr_worker_benchmark_{timestamp}")
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for variant in variants:
        label = str(variant["label"])
        command = [
            str(python_path),
            "-m",
            "mk8dx_video_result_extractor.extract_text",
        ]
        for race_class in race_classes:
            command.extend(["--race-class", race_class])
        env = build_env(variant)
        start_timestamp = time.time()
        start = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=project_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=args.timeout_seconds,
            )
            timed_out = False
            exit_code = completed.returncode
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
        elapsed = time.perf_counter() - start
        log_path = output_dir / f"{label}.log"
        log_path.write_text(
            "\n".join(
                [
                    "COMMAND " + " ".join(command),
                    f"MK8_CUDA_OCR_WORKERS={env.get('MK8_CUDA_OCR_WORKERS', '')}",
                    f"MK8_DISABLE_EASYOCR_READER_LOCK={env.get('MK8_DISABLE_EASYOCR_READER_LOCK', '')}",
                    "",
                    "=== STDOUT ===",
                    stdout.rstrip(),
                    "",
                    "=== STDERR ===",
                    stderr.rstrip(),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        debug_csv = latest_debug_csv_since(project_root, start_timestamp)
        metrics = evaluate_output(debug_csv, args.baseline_debug_csv, expected_mii)
        row = {
            "variant": label,
            "workers": "" if variant["workers"] is None else str(variant["workers"]),
            "disable_lock": str(bool(variant["disable_lock"])),
            "elapsed_seconds": f"{elapsed:.2f}",
            "logged_duration": extract_logged_duration(stdout),
            "exit_code": str(exit_code),
            "timed_out": str(timed_out),
            "log": str(log_path),
            **{key: str(value) for key, value in metrics.items()},
        }
        rows.append(row)
        print(f"{label}: elapsed={elapsed:.2f}s exit={exit_code} debug_csv={metrics.get('debug_csv', '')}")

    summary_csv = output_dir / "summary.csv"
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with summary_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary_md = output_dir / "summary.md"
    lines = [
        "# CUDA OCR Worker Benchmark",
        "",
        f"Race classes: {', '.join(race_classes)}",
        f"Baseline debug CSV: {args.baseline_debug_csv or ''}",
        "",
        "| Variant | Elapsed (s) | Duration | Exit | Rows | Mii | Character diffs | Expected Mii |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    quote_csv_value(row.get("variant", "")),
                    quote_csv_value(row.get("elapsed_seconds", "")),
                    quote_csv_value(row.get("logged_duration", "")),
                    quote_csv_value(row.get("exit_code", "")),
                    quote_csv_value(row.get("rows", "")),
                    quote_csv_value(row.get("mii_rows", "")),
                    quote_csv_value(row.get("character_diffs", "")),
                    quote_csv_value(row.get("expected_mii_counts", row.get("expected_mii_ok", ""))),
                ]
            )
            + " |"
        )
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Summary CSV: {summary_csv}")
    print(f"Summary MD:  {summary_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
