"""Reusable functions for washing-machine exploratory analysis."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


# Constants

TIME_COLUMN = "Time"
BASE_COLUMNS = ["Time", "Unix", "Aggregate", "Issues"]
POWER_COLUMNS = ["Aggregate"]
CYCLE_COLUMNS = [
    "cycle_id",
    "start",
    "end",
    "duration_minutes",
    "energy_wh",
    "peak_power_watts",
    "mean_power_watts",
    "start_hour",
    "start_day",
]
DAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


# Loading and resampling

def load_house(
    clean_dir: Path,
    house_number: int,
    washer_column: str,
) -> pd.DataFrame:
    """Load and type-convert the columns needed for one cleaned house."""
    file_path = clean_dir / f"CLEAN_House{house_number}.csv"
    if not file_path.exists():
        raise FileNotFoundError(f"Cleaned house file not found: {file_path}")

    use_columns = [*BASE_COLUMNS, washer_column]
    data = pd.read_csv(file_path, usecols=use_columns, parse_dates=[TIME_COLUMN])
    data = data.dropna(subset=[TIME_COLUMN]).sort_values(TIME_COLUMN)
    data["Aggregate"] = pd.to_numeric(data["Aggregate"], errors="coerce")
    data[washer_column] = pd.to_numeric(data[washer_column], errors="coerce")
    data["Issues"] = pd.to_numeric(data["Issues"], errors="coerce").fillna(0)
    return data


def _interpolate_short_gaps(
    data: pd.DataFrame,
    columns: list[str],
    max_gap_minutes: int,
) -> tuple[pd.DataFrame, pd.Series]:
    """Fill internal missing runs no longer than ``max_gap_minutes``."""
    result = data.copy()
    filled_rows = pd.Series(False, index=result.index)

    for column in columns:
        missing = result[column].isna()
        group_id = missing.ne(missing.shift()).cumsum()
        run_length = missing.groupby(group_id).transform("sum")
        eligible = missing & (run_length <= max_gap_minutes)
        interpolated = result[column].interpolate(method="time", limit_area="inside")
        result.loc[eligible, column] = interpolated.loc[eligible]
        filled_rows |= eligible & result[column].notna()

    return result, filled_rows


def _validate_resampling_input(data: pd.DataFrame, washer_column: str) -> None:
    """Check the columns required before resampling."""
    required = {TIME_COLUMN, "Aggregate", "Issues", washer_column}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Input data is missing columns: {sorted(missing)}")


def resample_house(
    data: pd.DataFrame,
    washer_column: str,
    max_gap_minutes: int = 3,
) -> tuple[pd.DataFrame, dict[str, int | float | str]]:
    """Return one-minute aggregate and washer readings with quality flags."""
    if max_gap_minutes < 0:
        raise ValueError("max_gap_minutes must be zero or greater.")
    _validate_resampling_input(data, washer_column)

    readings = (
        data.dropna(subset=[TIME_COLUMN])
        .drop_duplicates(subset=[TIME_COLUMN], keep="first")
        .sort_values(TIME_COLUMN)
        .set_index(TIME_COLUMN)
    )
    issue_rows = readings["Issues"].eq(1)
    readings.loc[issue_rows, ["Aggregate", washer_column]] = float("nan")

    minute_data = readings[[*POWER_COLUMNS, washer_column]].resample("1min").mean()
    minute_data, short_gap_filled = _interpolate_short_gaps(
        minute_data,
        [*POWER_COLUMNS, washer_column],
        max_gap_minutes,
    )
    minute_data["short_gap_filled"] = short_gap_filled
    minute_data["long_gap_missing"] = minute_data[
        [*POWER_COLUMNS, washer_column]
    ].isna().any(axis=1)
    minute_data["observed"] = (
        ~minute_data["short_gap_filled"] & ~minute_data["long_gap_missing"]
    )

    start = minute_data.index.min()
    end = minute_data.index.max()
    report: dict[str, int | float | str] = {
        "start": start.isoformat() if pd.notna(start) else "",
        "end": end.isoformat() if pd.notna(end) else "",
        "minutes": len(minute_data),
        "issue_rows_removed": int(issue_rows.sum()),
        "missing_minutes": int(minute_data["long_gap_missing"].sum()),
        "short_gap_minutes_filled": int(short_gap_filled.sum()),
        "max_gap_minutes": max_gap_minutes,
    }
    return minute_data, report


# Cycle detection and features

def _validate_cycle_settings(
    merge_pause_minutes: int,
    minimum_cycle_minutes: int,
    minimum_cycle_energy_wh: float,
) -> None:
    """Validate thresholds used by cycle detection."""
    if merge_pause_minutes < 0:
        raise ValueError("merge_pause_minutes must be zero or greater.")
    if minimum_cycle_minutes < 1:
        raise ValueError("minimum_cycle_minutes must be at least one.")
    if minimum_cycle_energy_wh < 0:
        raise ValueError("minimum_cycle_energy_wh must be zero or greater.")


def _find_candidate_intervals(
    active: pd.Series,
    valid: pd.Series,
    merge_pause_minutes: int,
) -> list[tuple[int, int]]:
    """Find active intervals, joining valid inactive pauses within the limit."""
    active_values = active.to_numpy()
    valid_values = valid.to_numpy()
    intervals: list[tuple[int, int]] = []
    position = 0

    while position < len(active_values):
        if not active_values[position]:
            position += 1
            continue

        start = position
        end = position
        position += 1
        while position < len(active_values):
            if active_values[position]:
                end = position
                position += 1
                continue

            pause_start = position
            while position < len(active_values) and not active_values[position]:
                if not valid_values[position]:
                    break
                position += 1
            pause_length = position - pause_start
            can_merge = (
                position < len(active_values)
                and active_values[position]
                and pause_length <= merge_pause_minutes
            )
            if can_merge:
                end = position
                position += 1
                continue

            end = pause_start - 1
            break
        intervals.append((start, end))

    return intervals


def _cycle_record(
    power: pd.Series,
    cycle_id: int,
    start: int,
    end: int,
) -> dict[str, object]:
    """Calculate summary features for one candidate cycle."""
    values = power.iloc[start : end + 1]
    timestamp = power.index[start]
    return {
        "cycle_id": cycle_id,
        "start": timestamp,
        "end": power.index[end],
        "duration_minutes": len(values),
        "energy_wh": float(values.clip(lower=0).sum() / 60),
        "peak_power_watts": float(values.max()),
        "mean_power_watts": float(values.mean()),
        "start_hour": int(timestamp.hour),
        "start_day": timestamp.day_name(),
    }


def detect_cycles(
    minute_data: pd.DataFrame,
    washer_column: str,
    active_power_watts: float = 20.0,
    merge_pause_minutes: int = 10,
    minimum_cycle_minutes: int = 10,
    minimum_cycle_energy_wh: float = 20.0,
) -> pd.DataFrame:
    """Detect cycles using an active threshold and short-pause merging."""
    _validate_cycle_settings(
        merge_pause_minutes,
        minimum_cycle_minutes,
        minimum_cycle_energy_wh,
    )
    if active_power_watts < 0:
        raise ValueError("active_power_watts must be zero or greater.")
    if washer_column not in minute_data.columns:
        raise ValueError(f"Washer column not found: {washer_column}")
    if "long_gap_missing" not in minute_data.columns:
        raise ValueError("Input data must contain the long_gap_missing flag.")

    power = minute_data[washer_column]
    valid = power.notna() & ~minute_data["long_gap_missing"]
    active = power.gt(active_power_watts) & valid
    candidates = _find_candidate_intervals(active, valid, merge_pause_minutes)

    records: list[dict[str, object]] = []
    for cycle_id, (start, end) in enumerate(candidates, start=1):
        record = _cycle_record(power, cycle_id, start, end)
        if (
            record["duration_minutes"] < minimum_cycle_minutes
            or record["energy_wh"] < minimum_cycle_energy_wh
        ):
            continue
        records.append(record)
    return pd.DataFrame(records, columns=CYCLE_COLUMNS)


# Summaries and usage tables

def availability_summary(
    minute_data: pd.DataFrame,
    washer_column: str,
    cycles: pd.DataFrame,
    active_power_watts: float = 20.0,
) -> dict[str, object]:
    """Summarise coverage, missing minutes, off-time, and cycle count."""
    if washer_column not in minute_data.columns:
        raise ValueError(f"Washer column not found: {washer_column}")
    if "long_gap_missing" not in minute_data.columns:
        raise ValueError("Input data must contain the long_gap_missing flag.")
    if minute_data.empty:
        return {
            "start": None,
            "end": None,
            "total_days": 0.0,
            "total_minutes": 0,
            "missing_minutes": 0,
            "missing_percent": 0.0,
            "valid_minutes": 0,
            "off_minutes": 0,
            "off_percent_of_valid": 0.0,
            "cycle_count": int(len(cycles)),
        }

    missing = minute_data["long_gap_missing"]
    valid_washer = minute_data[washer_column].notna() & ~missing
    off = valid_washer & minute_data[washer_column].le(active_power_watts)
    start = minute_data.index.min()
    end = minute_data.index.max()
    valid_count = int(valid_washer.sum())
    return {
        "start": start,
        "end": end,
        "total_days": (end - start).total_seconds() / 86400,
        "total_minutes": len(minute_data),
        "missing_minutes": int(missing.sum()),
        "missing_percent": float(missing.mean() * 100),
        "valid_minutes": valid_count,
        "off_minutes": int(off.sum()),
        "off_percent_of_valid": float(off.sum() / valid_count * 100)
        if valid_count
        else 0.0,
        "cycle_count": int(len(cycles)),
    }


def cycle_usage_tables(cycles: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return cycle counts by start hour and start day of week."""
    if cycles.empty:
        return (
            pd.DataFrame({"hour": range(24), "cycle_count": 0}),
            pd.DataFrame({"day": DAY_ORDER, "cycle_count": 0}),
        )

    by_hour = (
        cycles.groupby("start_hour")
        .size()
        .reindex(range(24), fill_value=0)
        .rename("cycle_count")
        .reset_index()
        .rename(columns={"start_hour": "hour"})
    )
    by_day = (
        cycles.groupby("start_day")
        .size()
        .reindex(DAY_ORDER, fill_value=0)
        .rename("cycle_count")
        .reset_index()
        .rename(columns={"start_day": "day"})
    )
    return by_hour, by_day
