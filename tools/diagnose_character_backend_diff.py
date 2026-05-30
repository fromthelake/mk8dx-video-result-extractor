from __future__ import annotations

import argparse
import csv
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mk8dx_video_result_extractor.extract_common import find_score_bundle_anchor_path
from mk8dx_video_result_extractor.extract_text import resolve_character_variant_family_name
from mk8dx_video_result_extractor.ocr_scoreboard_consensus import (
    _should_reject_character_match_as_mii,
    best_character_matches,
    character_row_roi,
    load_character_templates,
    player_identity_key,
)
from mk8dx_video_result_extractor.score_layouts import score_layout_id_from_filename

DEFAULT_CUDA_XLSX = PROJECT_ROOT / "Output_Results" / "20260529_201434_Tournament_Results.xlsx"
DEFAULT_CPU_DEBUG_CSV = (
    PROJECT_ROOT
    / ".ab_runs"
    / "eind_ronde_cpu_validation_20260529_231328"
    / "cpu_race"
    / "Debug_Selected"
    / "20260529_232045_Tournament_Results_Debug.csv"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / ".ab_runs"
    / "eind_ronde_cpu_validation_20260529_231328"
    / "diagnosis"
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _int_text(value: Any) -> str:
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return _text(value)


def _float_text(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return _text(value)


def _row_key(row: pd.Series) -> tuple[str, str, str]:
    return (_text(row.get("Video")), _int_text(row.get("Race")), _int_text(row.get("Position")))


def _family_key(character_name: str) -> str:
    character_name = _text(character_name)
    if not character_name:
        return ""
    family_name = resolve_character_variant_family_name(character_name)
    return f"family:{family_name}" if family_name else f"character:{character_name}"


def _same_character_or_family(candidate: str, expected: str) -> bool:
    candidate = _text(candidate)
    expected = _text(expected)
    if not candidate or not expected:
        return False
    return candidate == expected or _family_key(candidate) == _family_key(expected)


def _load_cuda_results(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name="Results")


def _load_cpu_debug(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _indexed_rows(df: pd.DataFrame) -> dict[tuple[str, str, str], pd.Series]:
    result: dict[tuple[str, str, str], pd.Series] = {}
    for _idx, row in df.iterrows():
        key = _row_key(row)
        if all(key):
            result[key] = row
    return result


def _crop_character_roi(video: str, race: int, position: int) -> tuple[Any | None, Path | None, str, str]:
    frame_path = find_score_bundle_anchor_path(video, race, "2RaceScore")
    if frame_path is None:
        return None, None, "", "missing_anchor_frame"
    frame_image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
    if frame_image is None:
        return None, frame_path, score_layout_id_from_filename(frame_path), "unreadable_anchor_frame"
    score_layout_id = score_layout_id_from_filename(frame_path)
    (x1, y1), (x2, y2) = character_row_roi(position - 1, score_layout_id=score_layout_id)
    height, width = frame_image.shape[:2]
    crop_x1 = max(0, min(width, x1))
    crop_x2 = max(crop_x1, min(width, x2))
    crop_y1 = max(0, min(height, y1))
    crop_y2 = max(crop_y1, min(height, y2))
    row_roi = frame_image[crop_y1:crop_y2, crop_x1:crop_x2]
    if row_roi.size == 0:
        return None, frame_path, score_layout_id, "empty_character_roi"
    return row_roi, frame_path, score_layout_id, ""


def _top_matches_text(matches: list[dict[str, object]]) -> str:
    return " | ".join(
        f"{_text(match.get('Character'))}:{_float_text(match.get('CharacterMatchConfidence'))}"
        for match in matches
    )


def _crosses_prior_confidence_threshold(cuda_confidence: str, cpu_confidence: str) -> bool:
    try:
        cuda_value = float(cuda_confidence)
        cpu_value = float(cpu_confidence)
    except (TypeError, ValueError):
        return False
    return (cuda_value >= 80.0) != (cpu_value >= 80.0)


def _classify_row(
    *,
    cuda_character: str,
    cpu_character: str,
    cpu_method: str,
    raw_matches: list[dict[str, object]],
    name_changed: bool,
    cpu_name_confidence: str,
    crop_status: str,
    cuda_debug_available: bool,
    cuda_raw_prior_key: str,
    cpu_raw_prior_key: str,
    cuda_name_confidence: str,
) -> str:
    if crop_status:
        return f"unknown_{crop_status}"
    if name_changed:
        return "name_or_identity_possible"
    raw_best = _text(raw_matches[0].get("Character")) if raw_matches else ""
    raw_supports_cuda = any(_same_character_or_family(_text(match.get("Character")), cuda_character) for match in raw_matches[:5])
    raw_supports_cpu = any(_same_character_or_family(_text(match.get("Character")), cpu_character) for match in raw_matches[:5])
    cpu_is_mii = cpu_character == "Mii"
    cuda_is_mii = cuda_character == "Mii"
    method_is_prior_mii = "character_prior_mii_likely" in cpu_method
    method_is_open_set = "open_set_mii_reject" in cpu_method
    open_set_supported = _should_reject_character_match_as_mii(raw_matches)

    if cuda_debug_available:
        if cuda_raw_prior_key and cpu_raw_prior_key and cuda_raw_prior_key != cpu_raw_prior_key:
            return "raw_name_prior_key_diff_possible"
        if _crosses_prior_confidence_threshold(cuda_name_confidence, cpu_name_confidence):
            return "raw_name_confidence_prior_timing_possible"
    else:
        try:
            low_name_confidence = bool(cpu_name_confidence and float(cpu_name_confidence) < 80.0)
        except ValueError:
            low_name_confidence = False
        if low_name_confidence:
            return "name_or_identity_possible"
    if cpu_is_mii and method_is_prior_mii and raw_supports_cuda:
        if cuda_debug_available and cuda_raw_prior_key and cuda_raw_prior_key == cpu_raw_prior_key:
            return "prior_shortcut_with_same_raw_name_key"
        return "prior_shortcut_without_template_support"
    if cpu_is_mii and method_is_open_set and open_set_supported:
        return "open_set_reject_supported"
    if cpu_is_mii and raw_supports_cuda:
        return "same_template_supports_cuda"
    if not cpu_is_mii and cuda_is_mii and raw_supports_cpu:
        return "inverse_cpu_closed_set_supported"
    if raw_supports_cuda:
        return "same_template_supports_cuda"
    if raw_supports_cpu:
        return "same_template_supports_cpu"
    if raw_best:
        return "raw_template_supports_other"
    return "unknown_needs_manual_crop_review"


def _write_crop(
    output_dir: Path,
    row_roi: Any,
    *,
    player: str,
    video: str,
    race: int,
    position: int,
    counter: Counter[str],
    limit_per_player: int,
) -> str:
    if limit_per_player <= 0:
        return ""
    safe_player = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in player) or "player"
    if counter[safe_player] >= limit_per_player:
        return ""
    counter[safe_player] += 1
    crops_dir = output_dir / "crops" / safe_player
    crops_dir.mkdir(parents=True, exist_ok=True)
    safe_video = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in video)[-80:]
    crop_path = crops_dir / f"{safe_video}_race_{race:03d}_pos_{position:02d}.png"
    cv2.imwrite(str(crop_path), row_roi)
    return str(crop_path)


def diagnose(args: argparse.Namespace) -> int:
    cuda_xlsx = Path(args.cuda_xlsx)
    cpu_debug_csv = Path(args.cpu_debug_csv)
    cuda_debug_csv = Path(args.cuda_debug_csv) if args.cuda_debug_csv else None
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cuda_df = _load_cuda_results(cuda_xlsx)
    cpu_df = _load_cpu_debug(cpu_debug_csv)
    cuda_debug_df = _load_cpu_debug(cuda_debug_csv) if cuda_debug_csv else None
    cuda_by_key = _indexed_rows(cuda_df)
    cpu_by_key = _indexed_rows(cpu_df)
    cuda_debug_by_key = _indexed_rows(cuda_debug_df) if cuda_debug_df is not None else {}
    templates = load_character_templates()

    shared_keys = sorted(set(cuda_by_key) & set(cpu_by_key))
    diff_rows: list[dict[str, object]] = []
    cause_counts: Counter[str] = Counter()
    player_cause_counts: Counter[tuple[str, str]] = Counter()
    crop_counter: Counter[str] = Counter()

    for key in shared_keys:
        cuda_row = cuda_by_key[key]
        cpu_row = cpu_by_key[key]
        cuda_character = _text(cuda_row.get("Character"))
        cpu_character = _text(cpu_row.get("Character"))
        if cuda_character == cpu_character:
            continue
        video, race_text, position_text = key
        try:
            race = int(race_text)
            position = int(position_text)
        except ValueError:
            continue
        row_roi, frame_path, score_layout_id, crop_status = _crop_character_roi(video, race, position)
        raw_matches = best_character_matches(row_roi, templates, limit=5) if row_roi is not None else []

        cuda_player = _text(cuda_row.get("Player"))
        cpu_player = _text(cpu_row.get("Standardized Player") or cpu_row.get("Player"))
        raw_player = _text(cpu_row.get("Raw Player OCR"))
        cuda_debug_row = cuda_debug_by_key.get(key)
        cuda_raw_player = _text(cuda_debug_row.get("Raw Player OCR")) if cuda_debug_row is not None else ""
        cuda_standardized_player = (
            _text(cuda_debug_row.get("Standardized Player"))
            if cuda_debug_row is not None
            else cuda_player
        )
        cuda_method = _text(cuda_debug_row.get("Character Match Method")) if cuda_debug_row is not None else ""
        cuda_name_confidence = _text(cuda_debug_row.get("Name Confidence")) if cuda_debug_row is not None else ""
        cuda_character_debug = _text(cuda_debug_row.get("Character")) if cuda_debug_row is not None else ""
        cpu_method = _text(cpu_row.get("Character Match Method"))
        name_confidence = _text(cpu_row.get("Name Confidence"))
        cuda_raw_prior_key = player_identity_key(cuda_raw_player)
        cpu_raw_prior_key = player_identity_key(raw_player)
        cause = _classify_row(
            cuda_character=cuda_character,
            cpu_character=cpu_character,
            cpu_method=cpu_method,
            raw_matches=raw_matches,
            name_changed=bool(cuda_player and cpu_player and cuda_player != cpu_player),
            cpu_name_confidence=name_confidence,
            crop_status=crop_status,
            cuda_debug_available=cuda_debug_row is not None,
            cuda_raw_prior_key=cuda_raw_prior_key,
            cpu_raw_prior_key=cpu_raw_prior_key,
            cuda_name_confidence=cuda_name_confidence,
        )
        cause_counts[cause] += 1
        player_cause_counts[(cpu_player or cuda_player, cause)] += 1

        crop_path = ""
        if row_roi is not None and args.write_crops:
            crop_path = _write_crop(
                output_dir,
                row_roi,
                player=cpu_player or cuda_player,
                video=video,
                race=race,
                position=position,
                counter=crop_counter,
                limit_per_player=int(args.crop_limit),
            )

        raw_best = raw_matches[0] if raw_matches else {}
        raw_second = raw_matches[1] if len(raw_matches) > 1 else {}
        raw_fifth = raw_matches[4] if len(raw_matches) > 4 else raw_best
        raw_best_conf = float(raw_best.get("CharacterMatchConfidence", 0.0) or 0.0) if raw_best else 0.0
        raw_second_conf = float(raw_second.get("CharacterMatchConfidence", 0.0) or 0.0) if raw_second else 0.0
        raw_fifth_conf = float(raw_fifth.get("CharacterMatchConfidence", raw_best_conf) or raw_best_conf) if raw_fifth else 0.0
        diff_rows.append(
            {
                "Video": video,
                "Race": race,
                "Position": position,
                "CUDAPlayer": cuda_player,
                "CUDAStandardizedPlayer": cuda_standardized_player,
                "CPUPlayer": cpu_player,
                "CUDARawPlayerOCR": cuda_raw_player,
                "CPURawPlayerOCR": raw_player,
                "CUDARawPriorKey": cuda_raw_prior_key,
                "CPURawPriorKey": cpu_raw_prior_key,
                "RawPriorKeyDiff": str(bool(cuda_raw_prior_key and cpu_raw_prior_key and cuda_raw_prior_key != cpu_raw_prior_key)),
                "CUDANameConfidence": cuda_name_confidence,
                "CPUNameConfidence": name_confidence,
                "NameConfidenceThresholdDiff": str(_crosses_prior_confidence_threshold(cuda_name_confidence, name_confidence)),
                "CUDACharacter": cuda_character,
                "CUDACharacterDebug": cuda_character_debug,
                "CPUCharacter": cpu_character,
                "CUDACharacterMethod": cuda_method,
                "CPUCharacterMethod": cpu_method,
                "CPUCharacterConfidence": _text(cpu_row.get("Character Match Confidence")),
                "CPUFamilyBest": _text(cpu_row.get("Character Family Best")),
                "CPUFamilyBestCoeff": _text(cpu_row.get("Character Family Best Coeff")),
                "CPUFamilyMargin": _text(cpu_row.get("Character Family Margin")),
                "RawTop1": _text(raw_best.get("Character")),
                "RawTop1Confidence": _float_text(raw_best.get("CharacterMatchConfidence")),
                "RawTop2Margin": f"{raw_best_conf - raw_second_conf:.1f}" if raw_matches else "",
                "RawTop5Spread": f"{raw_best_conf - raw_fifth_conf:.1f}" if raw_matches else "",
                "RawOpenSetMiiReject": str(bool(raw_matches and _should_reject_character_match_as_mii(raw_matches))),
                "RawTop5": _top_matches_text(raw_matches),
                "ScoreLayout": score_layout_id,
                "FramePath": str(frame_path or ""),
                "CropStatus": crop_status,
                "Cause": cause,
                "CropPath": crop_path,
            }
        )

    diagnosis_csv = output_dir / "character_diff_diagnosis.csv"
    fieldnames = list(diff_rows[0].keys()) if diff_rows else [
        "Video",
        "Race",
        "Position",
        "CUDACharacter",
        "CPUCharacter",
        "Cause",
    ]
    with diagnosis_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(diff_rows)

    by_player_path = output_dir / "character_diff_by_player.csv"
    with by_player_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Player", "Cause", "Rows"])
        writer.writeheader()
        for (player, cause), count in sorted(player_cause_counts.items(), key=lambda item: (-item[1], item[0])):
            writer.writerow({"Player": player, "Cause": cause, "Rows": count})

    summary_path = output_dir / "summary.txt"
    with summary_path.open("w", encoding="utf-8") as handle:
        handle.write(f"cuda_xlsx: {cuda_xlsx}\n")
        handle.write(f"cuda_debug_csv: {cuda_debug_csv or ''}\n")
        handle.write(f"cpu_debug_csv: {cpu_debug_csv}\n")
        handle.write(f"diagnosis_csv: {diagnosis_csv}\n\n")
        handle.write("row_counts:\n")
        handle.write(f"  cuda_rows: {len(cuda_df.index)}\n")
        handle.write(f"  cuda_debug_rows: {len(cuda_debug_df.index) if cuda_debug_df is not None else 0}\n")
        handle.write(f"  cpu_rows: {len(cpu_df.index)}\n")
        handle.write(f"  shared_rows_by_video_race_position: {len(shared_keys)}\n")
        handle.write(f"  character_diff_rows: {len(diff_rows)}\n\n")
        raw_key_diff_count = sum(1 for row in diff_rows if row.get("RawPriorKeyDiff") == "True")
        confidence_threshold_diff_count = sum(
            1 for row in diff_rows if row.get("NameConfidenceThresholdDiff") == "True"
        )
        handle.write("raw_name_prior_checks:\n")
        handle.write(f"  raw_prior_key_diff_rows: {raw_key_diff_count}\n")
        handle.write(f"  name_confidence_threshold_diff_rows: {confidence_threshold_diff_count}\n\n")
        handle.write("causes:\n")
        for cause, count in cause_counts.most_common():
            handle.write(f"  {cause}: {count}\n")
        handle.write("\nplayers_by_cause:\n")
        for (player, cause), count in sorted(player_cause_counts.items(), key=lambda item: (-item[1], item[0]))[:50]:
            handle.write(f"  {player} | {cause}: {count}\n")
        handle.write("\nfirst_30_rows:\n")
        for row in diff_rows[:30]:
            handle.write(
                "  "
                f"{row['Video']} race {row['Race']} pos {row['Position']} "
                f"{row['CUDACharacter']} -> {row['CPUCharacter']} | "
                f"cause={row['Cause']} | "
                f"cuda_raw={row.get('CUDARawPlayerOCR', '')}/{row.get('CUDARawPriorKey', '')}/"
                f"{row.get('CUDANameConfidence', '')} | "
                f"cpu_raw={row.get('CPURawPlayerOCR', '')}/{row.get('CPURawPriorKey', '')}/"
                f"{row.get('CPUNameConfidence', '')} | "
                f"raw_top5={row['RawTop5']} | method={row['CPUCharacterMethod']}\n"
            )

    latest_dir = output_dir.parent / "diagnosis_latest"
    if args.update_latest:
        if latest_dir.exists():
            shutil.rmtree(latest_dir)
        shutil.copytree(output_dir, latest_dir)

    print(f"Wrote {diagnosis_csv}")
    print(f"Wrote {summary_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose CPU-vs-CUDA character differences using saved frames and raw template matches.",
    )
    parser.add_argument("--cuda-xlsx", default=str(DEFAULT_CUDA_XLSX), help="CUDA baseline workbook with a Results sheet.")
    parser.add_argument("--cuda-debug-csv", default="", help="Optional CUDA debug CSV from a matching OCR run.")
    parser.add_argument("--cpu-debug-csv", default=str(DEFAULT_CPU_DEBUG_CSV), help="CPU debug CSV from an OCR run.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for diagnosis outputs.")
    parser.add_argument("--write-crops", action="store_true", help="Write sample character crops for diff rows.")
    parser.add_argument("--crop-limit", type=int, default=3, help="Maximum crop images to write per player.")
    parser.add_argument("--update-latest", action="store_true", help="Copy output directory to diagnosis_latest beside it.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(diagnose(parse_args()))
