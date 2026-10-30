from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

try:
    from .data_loading import load_raw_house
except ImportError:
    from data_loading import load_raw_house

DEFAULT_FREQUENCY = "1min"
DEFAULT_MAX_GAP_MINUTES = 5
DEFAULT_MAX_POWER_WATTS = 10_000
TIME_COLUMN = "Time"
NON_POWER_COLUMNS = {"Time", "Unix"}

# Inspection helpers

def _power_columns(data: pd.DataFrame) -> list[str]:
    """Return columns containing power readings."""
    return [column for column in data.columns if column not in NON_POWER_COLUMNS]


def _validate_input(data: pd.DataFrame) -> None:
    """Validate the columns required by the cleaning pipeline."""
    missing_columns = {"Time", "Aggregate"} - set(data.columns)
    if missing_columns:
        raise ValueError(
            f"Input data is missing required columns: {sorted(missing_columns)}"
        )


def inspect_raw(
    data: pd.DataFrame,
    max_power_watts: float = DEFAULT_MAX_POWER_WATTS,
) -> dict[str, object]:
    """Summarise raw timestamps, missing values, and suspicious power values."""
    _validate_input(data)
    timestamps = data[TIME_COLUMN].dropna().sort_values()
    intervals = timestamps.diff().dropna().dt.total_seconds()
    power_columns = _power_columns(data)

    negative_counts = {
        column: int((data[column] < 0).sum()) for column in power_columns
    }
    extreme_counts = {
        column: int((data[column] > max_power_watts).sum())
        for column in power_columns
    }

    return {
        "rows": int(len(data)),
        "invalid_timestamps": int(data[TIME_COLUMN].isna().sum()),
        "duplicate_timestamps": int(
            data[TIME_COLUMN].duplicated(keep=False).sum()
        ),
        "missing_values": {
            column: int(data[column].isna().sum()) for column in data.columns
        },
        "timestamp_start": (
            timestamps.iloc[0].isoformat() if not timestamps.empty else None
        ),
        "timestamp_end": (
            timestamps.iloc[-1].isoformat() if not timestamps.empty else None
        ),
        "interval_seconds": {
            "count": int(intervals.size),
            "median": float(intervals.median()) if not intervals.empty else None,
            "minimum": float(intervals.min()) if not intervals.empty else None,
            "maximum": float(intervals.max()) if not intervals.empty else None,
            "irregular_count": int((intervals != intervals.median()).sum())
            if not intervals.empty
            else 0,
        },
        "negative_values": negative_counts,
        "values_above_limit_watts": extreme_counts,
        "power_limit_watts": max_power_watts,
    }


# Cleaning helpers

def _interpolate_short_gaps(
    data: pd.DataFrame,
    value_columns: list[str],
    max_gap_minutes: int,
) -> tuple[pd.DataFrame, pd.Series]:
    """Interpolate only runs of missing one-minute readings up to max_gap_minutes."""
    filled = data.copy()
    short_gap_filled = pd.Series(False, index=filled.index)

    for column in value_columns:
        missing = filled[column].isna()
        group_id = missing.ne(missing.shift()).cumsum()
        missing_lengths = missing.groupby(group_id).transform("sum")
        eligible = missing & (missing_lengths <= max_gap_minutes)
        interpolated = filled[column].interpolate(method="time", limit_area="inside")
        filled.loc[eligible, column] = interpolated.loc[eligible]
        short_gap_filled |= eligible & filled[column].notna()

    return filled, short_gap_filled


def _prepare_readings(
    raw: pd.DataFrame,
    max_power_watts: float,
) -> tuple[pd.DataFrame, int]:
    """Drop invalid timestamps, sort readings, de-duplicate, and flag outliers."""
    readings = raw.dropna(subset=[TIME_COLUMN]).sort_values(TIME_COLUMN).copy()
    duplicate_rows_removed = int(
        readings[TIME_COLUMN].duplicated(keep="first").sum()
    )
    readings = readings.drop_duplicates(subset=[TIME_COLUMN], keep="first")

    for column in _power_columns(readings):
        impossible = (readings[column] < 0) | (readings[column] > max_power_watts)
        readings.loc[impossible, column] = float("nan")

    return readings, duplicate_rows_removed


def _build_quality_flags(
    readings: pd.DataFrame,
    value_columns: list[str],
    short_gap_filled: pd.Series,
) -> pd.DataFrame:
    """Add row-level flags that explain whether a minute is reliable."""
    flags = pd.DataFrame(index=readings.index)
    flags["short_gap_filled"] = short_gap_filled
    flags["long_gap_missing"] = readings[value_columns].isna().any(axis=1)
    flags["observed"] = ~flags["short_gap_filled"] & ~flags["long_gap_missing"]
    return flags


def clean_and_resample(
    raw: pd.DataFrame,
    frequency: str = DEFAULT_FREQUENCY,
    max_gap_minutes: int = DEFAULT_MAX_GAP_MINUTES,
    max_power_watts: float = DEFAULT_MAX_POWER_WATTS,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Return one-minute readings and a report describing every cleaning step."""
    if max_gap_minutes < 0:
        raise ValueError("max_gap_minutes must be zero or greater.")
    if max_power_watts <= 0:
        raise ValueError("max_power_watts must be greater than zero.")

    _validate_input(raw)
    data, duplicate_rows_removed = _prepare_readings(raw, max_power_watts)
    value_columns = _power_columns(data)
    indexed = data.set_index(TIME_COLUMN)[value_columns]
    resampled = indexed.resample(frequency).mean()
    resampled, short_gap_filled = _interpolate_short_gaps(
        resampled, value_columns, max_gap_minutes
    )

    quality = _build_quality_flags(resampled, value_columns, short_gap_filled)
    output = resampled.join(quality)

    report = {
        "input_rows": int(len(raw)),
        "invalid_timestamps_removed": int(raw[TIME_COLUMN].isna().sum()),
        "duplicate_rows_removed": duplicate_rows_removed,
        "resampled_rows": int(len(output)),
        "short_gap_rows_filled": int(short_gap_filled.sum()),
        "long_gap_rows_flagged": int(output["long_gap_missing"].sum()),
        "remaining_missing_by_column": {
            column: int(output[column].isna().sum()) for column in value_columns
        },
        "frequency": frequency,
        "short_gap_limit_minutes": max_gap_minutes,
        "impossible_value_rule": (
            f"Values below 0 W or above {max_power_watts:g} W were set to missing."
        ),
    }
    return output, report


# Output and plotting

def write_json(payload: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def plot_before_after(
    raw: pd.DataFrame,
    cleaned: pd.DataFrame,
    output_path: Path,
    start: pd.Timestamp,
    end: pd.Timestamp,
    channels: list[str],
) -> None:
    """Plot selected raw channels beside their cleaned one-minute versions."""
    if not channels:
        raise ValueError("At least one channel is required for the plot.")
    missing_channels = set(channels) - set(raw.columns)
    if missing_channels:
        raise ValueError(f"Channels not found in raw data: {sorted(missing_channels)}")

    raw_window = raw[(raw["Time"] >= start) & (raw["Time"] <= end)]
    cleaned_window = cleaned.loc[start:end]
    figure, axes = plt.subplots(
        len(channels), 2, figsize=(16, 3 * len(channels)), sharex="col"
    )
    axes = axes if len(channels) > 1 else [axes]
    for row, channel in enumerate(channels):
        axes[row][0].plot(raw_window["Time"], raw_window[channel], linewidth=0.8)
        axes[row][0].set_title(f"Raw: {channel}")
        axes[row][1].plot(cleaned_window.index, cleaned_window[channel], linewidth=0.8)
        axes[row][1].set_title(f"Cleaned, 1-minute mean: {channel}")
        for axis in axes[row]:
            axis.set_ylabel("Power (W)")
            axis.grid(alpha=0.25)
    axes[-1][0].set_xlabel("Time")
    axes[-1][1].set_xlabel("Time")
    figure.suptitle("REFIT House 1: raw versus cleaned readings")
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


# Command-line workflow

def _select_plot_channels(raw: pd.DataFrame) -> list[str]:
    """Select aggregate power and the first two available appliance channels."""
    appliance_channels = [
        column for column in raw.columns if column.startswith("Appliance")
    ]
    return ["Aggregate", *appliance_channels[:2]]


def run(
    input_dir: Path,
    output_dir: Path,
    plots_dir: Path,
) -> None:
    """Run the complete raw House 1 cleaning workflow."""
    raw = load_raw_house(input_dir, house_number=1)
    raw_report = inspect_raw(raw)
    cleaned, cleaning_report = clean_and_resample(raw)

    output_dir.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(output_dir / "house1_cleaned_1min.csv", index_label="Time")
    write_json(raw_report, output_dir / "house1_raw_quality_report.json")
    write_json(cleaning_report, output_dir / "house1_cleaning_report.json")

    valid_times = raw["Time"].dropna()
    if valid_times.empty:
        raise ValueError("House 1 has no valid timestamps to plot.")
    start = valid_times.min()
    end = min(start + timedelta(days=1), valid_times.max())
    plot_before_after(
        raw,
        cleaned,
        plots_dir / "house1_raw_vs_cleaned.png",
        start,
        end,
        _select_plot_channels(raw),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean raw REFIT House 1 data.")
    parser.add_argument(
        "--input-dir", type=Path, default=Path("data/raw/REFIT_RAW_081116")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/cleaned"))
    parser.add_argument("--plots-dir", type=Path, default=Path("plots"))
    args = parser.parse_args()
    run(args.input_dir, args.output_dir, args.plots_dir)


if __name__ == "__main__":
    main()