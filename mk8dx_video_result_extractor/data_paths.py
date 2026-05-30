from importlib.resources import files
from pathlib import Path

from .project_paths import PROJECT_ROOT


def _package_root():
    return files("mk8dx_video_result_extractor_data")


def resolve_data_file(*relative_parts: str) -> Path:
    """Resolve data from the repo checkout first, then from installed package data."""
    local_candidate = PROJECT_ROOT.joinpath(*relative_parts)
    if local_candidate.exists():
        return local_candidate

    package_candidate = _package_root().joinpath(*relative_parts)
    if package_candidate.is_file():
        return Path(str(package_candidate))
    raise FileNotFoundError(f"Missing data file: {local_candidate}")


def resolve_asset_file(*relative_parts: str) -> Path:
    """
    Resolve runtime assets from the repository checkout.

    This project intentionally treats ``PROJECT_ROOT/assets`` as the canonical
    source for templates, character cutouts, and GUI images.
    """
    asset_candidate = PROJECT_ROOT.joinpath("assets", *relative_parts)
    if asset_candidate.exists():
        return asset_candidate
    raise FileNotFoundError(f"Missing asset file: {asset_candidate}")


def resolve_reference_file(*relative_parts: str) -> Path:
    """
    Resolve reference data from checkout first, then packaged fallback.
    """
    return resolve_data_file("reference_data", *relative_parts)


def resolve_game_catalog_file() -> Path:
    return resolve_reference_file("game_catalog.json")


def resolve_track_metadata_file() -> Path:
    return resolve_game_catalog_file()
