"""Simple washing-machine disaggregation model and evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


@dataclass(frozen=True)
class Split:
    """A household-level train/test split."""

    train_houses: tuple[int, ...]
    test_house: int


def build_features(
    minute_data: pd.DataFrame,
    washer_column: str,
    lag_minutes: tuple[int, ...] = (0, 1, 2, 3, 5, 10),
) -> tuple[pd.DataFrame, pd.Series]:
    """Build causal aggregate-power and calendar features."""
    if not isinstance(minute_data.index, pd.DatetimeIndex):
        raise TypeError("minute_data must use a DatetimeIndex.")
    if not lag_minutes or any(
        not isinstance(lag, (int, np.integer)) or lag < 0 for lag in lag_minutes
    ):
        raise ValueError("lag_minutes must contain at least one non-negative integer.")

    required = {"Aggregate", washer_column}
    missing = required - set(minute_data.columns)
    if missing:
        raise ValueError(f"Missing feature columns: {sorted(missing)}")

    data = minute_data.copy().sort_index()
    features = pd.DataFrame(index=data.index)
    for lag in lag_minutes:
        features[f"aggregate_lag_{lag}"] = data["Aggregate"].shift(lag)
    features["aggregate_rolling_mean_5"] = data["Aggregate"].rolling(5).mean()
    features["aggregate_rolling_max_5"] = data["Aggregate"].rolling(5).max()
    features["hour"] = data.index.hour
    features["day_of_week"] = data.index.dayofweek

    target = data[washer_column].rename("Washer")
    if "long_gap_missing" in data:
        long_gap_missing = data["long_gap_missing"].fillna(False).astype(bool)
    else:
        long_gap_missing = pd.Series(False, index=data.index)
    valid = features.notna().all(axis=1) & target.notna() & ~long_gap_missing
    features = features.loc[valid]
    target = target.loc[valid]
    if features.empty:
        raise ValueError("No valid rows remain after feature construction.")
    return features, target


def fit_model(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    random_state: int = 42,
) -> HistGradientBoostingRegressor:
    """Fit a gradient-boosting regression model."""
    if x_train.empty or y_train.empty:
        raise ValueError("Training features and targets must not be empty.")
    if len(x_train) != len(y_train):
        raise ValueError("Training features and targets must have equal length.")
    if not np.isfinite(x_train.to_numpy(dtype=float)).all():
        raise ValueError("Training features must contain only finite values.")
    if not np.isfinite(y_train.to_numpy(dtype=float)).all():
        raise ValueError("Training targets must contain only finite values.")

    model = HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=150,
        learning_rate=0.08,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        random_state=random_state,
    )
    model.fit(x_train, y_train.clip(lower=0))
    return model


def predict_non_negative(model, features: pd.DataFrame) -> pd.Series:
    """Predict washer power and clip physically impossible negative values."""
    predictions = model.predict(features)
    return pd.Series(np.maximum(predictions, 0), index=features.index, name="Predicted")


def evaluate_predictions(
    actual: pd.Series,
    predicted: pd.Series,
    active_power_watts: float = 20.0,
) -> dict[str, float]:
    """Calculate power, energy, and active-state metrics."""
    actual, predicted = actual.align(predicted, join="inner")
    if actual.empty:
        raise ValueError("Cannot evaluate empty predictions.")
    if not np.isfinite(actual.to_numpy(dtype=float)).all() or not np.isfinite(
        predicted.to_numpy(dtype=float)
    ).all():
        raise ValueError("Actual and predicted values must be finite.")
    if active_power_watts < 0:
        raise ValueError("active_power_watts must be non-negative.")

    actual_values = actual.to_numpy(dtype=float)
    predicted_values = predicted.to_numpy(dtype=float)
    actual_active = actual_values > active_power_watts
    predicted_active = predicted_values > active_power_watts
    true_positive = np.sum(actual_active & predicted_active)
    precision = true_positive / max(np.sum(predicted_active), 1)
    recall = true_positive / max(np.sum(actual_active), 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    actual_energy = actual_values.sum() / 60
    predicted_energy = predicted_values.sum() / 60

    return {
        "mae_watts": float(mean_absolute_error(actual_values, predicted_values)),
        "rmse_watts": float(np.sqrt(mean_squared_error(actual_values, predicted_values))),
        "actual_energy_wh": float(actual_energy),
        "predicted_energy_wh": float(predicted_energy),
        "energy_error_percent": float(
            abs(predicted_energy - actual_energy) / max(actual_energy, 1e-12) * 100
        ),
        "active_precision": float(precision),
        "active_recall": float(recall),
        "active_f1": float(f1),
    }


def evaluate_baseline(
    actual: pd.Series,
    active_power_watts: float = 20.0,
) -> dict[str, float]:
    """Evaluate the always-off baseline."""
    return evaluate_predictions(
        actual,
        pd.Series(0.0, index=actual.index, name="Predicted"),
        active_power_watts,
    )