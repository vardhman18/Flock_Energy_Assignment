from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {"Time", "Aggregate"}
NON_POWER_COLUMNS = {"Time", "Unix"}


def find_house_files(raw_dir: Path, house_number: int) -> list[Path]:
    """Find all CSV parts belonging to one REFIT household."""
    patterns = [
        f"RAW_House{house_number}_Part*.csv",
        f"RAW_House_{house_number}_Part*.csv",
    ]
    files: set[Path] = set()
    for pattern in patterns:
        files.update(raw_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(
            f"No raw CSV files found for House {house_number} in {raw_dir}"
        )
    return sorted(files, key=lambda path: path.name)


def _validate_columns(data: pd.DataFrame, source_file: Path) -> None:
    """Raise a useful error when a REFIT file has the wrong schema."""
    missing_columns = REQUIRED_COLUMNS - set(data.columns)
    if missing_columns:
        raise ValueError(
            f"{source_file.name} is missing required columns: "
            f"{sorted(missing_columns)}"
        )


def load_raw_house(raw_dir: Path, house_number: int) -> pd.DataFrame:
    """Load, validate, and type-convert all raw CSV parts for a household."""
    files = find_house_files(raw_dir, house_number)
    frames: list[pd.DataFrame] = []
    for file in files:
        frame = pd.read_csv(file)
        _validate_columns(frame, file)
        frames.append(frame)

    data = pd.concat(frames, ignore_index=True)
    data["Time"] = pd.to_datetime(data["Time"], errors="coerce")
    for column in data.columns:
        if column not in NON_POWER_COLUMNS:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data