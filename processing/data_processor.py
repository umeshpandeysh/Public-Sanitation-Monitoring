"""
processing/data_processor.py
-----------------------------
Validates, cleans, buffers, and aggregates raw sensor readings.
Provides a DataProcessor class designed for both real-time streaming
and batch CSV-based analytics pipelines.
"""

import logging
from collections import deque
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    Central data-handling component for the sanitation monitoring pipeline.

    Responsibilities
    ----------------
    * Validate incoming readings against allowed value ranges.
    * Clamp / fill outlier / null values (clean_reading).
    * Maintain per-location sliding-window buffers (add_to_buffer).
    * Compute rolling window statistics (compute_window_stats).
    * Aggregate readings to hourly granularity (aggregate_hourly).
    * Load from / save to CSV files (load_from_csv, save_processed).
    * Clean an entire DataFrame in batch mode (preprocess_dataframe).

    Parameters
    ----------
    window_size : int
        Maximum number of readings retained per location buffer. Default 60.
    """

    SENSOR_COLUMNS: List[str] = [
        "nh3_ppm",
        "h2s_ppm",
        "temperature_c",
        "humidity_pct",
        "pm25_ugm3",
    ]

    REQUIRED_FIELDS: List[str] = [
        "timestamp",
        "location_id",
        "nh3_ppm",
        "h2s_ppm",
        "temperature_c",
        "humidity_pct",
        "pm25_ugm3",
    ]

    # (inclusive lower bound, inclusive upper bound) — sensor physics limits
    VALUE_RANGES: Dict[str, tuple] = {
        "nh3_ppm":       (0.0, 200.0),
        "h2s_ppm":       (0.0, 50.0),
        "temperature_c": (-10.0, 70.0),
        "humidity_pct":  (0.0, 100.0),
        "pm25_ugm3":     (0.0, 500.0),
    }

    # Upper and lower clamps applied during cleaning (tighter than physics limits)
    CLAMP_RANGES: Dict[str, tuple] = {
        "nh3_ppm":       (0.0, 150.0),
        "h2s_ppm":       (0.0, 30.0),
        "temperature_c": (0.0, 60.0),
        "humidity_pct":  (0.0, 100.0),
        "pm25_ugm3":     (0.0, 300.0),
    }

    # Fallback values used when a field is None / NaN after clamping
    DEFAULTS: Dict[str, float] = {
        "nh3_ppm":       8.0,
        "h2s_ppm":       0.3,
        "temperature_c": 26.0,
        "humidity_pct":  65.0,
        "pm25_ugm3":     15.0,
    }

    def __init__(self, window_size: int = 60) -> None:
        if window_size <= 0:
            raise ValueError("window_size must be a positive integer.")
        self.window_size = window_size
        self._buffers: Dict[str, deque] = {}
        logger.info("DataProcessor initialised (window_size=%d).", window_size)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_reading(self, reading: Dict) -> bool:
        """
        Return True if *reading* contains all required fields with values
        within valid physical ranges.

        Parameters
        ----------
        reading : Dict

        Returns
        -------
        bool
        """
        for field in self.REQUIRED_FIELDS:
            if field not in reading:
                logger.warning("Validation failed — missing field: '%s'", field)
                return False

        for col, (lo, hi) in self.VALUE_RANGES.items():
            val = reading.get(col)
            if val is not None:
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    logger.warning(
                        "Validation failed — '%s' is not numeric: %r", col, val
                    )
                    return False
                if not (lo <= val <= hi):
                    logger.warning(
                        "Validation failed — %s=%.4f outside [%.1f, %.1f]",
                        col, val, lo, hi,
                    )
                    return False
        return True

    # ------------------------------------------------------------------
    # Cleaning
    # ------------------------------------------------------------------

    def clean_reading(self, reading: Dict) -> Dict:
        """
        Return a cleaned copy of *reading* with extreme values clamped
        and None values replaced by sensible defaults.

        Parameters
        ----------
        reading : Dict

        Returns
        -------
        Dict
        """
        cleaned = dict(reading)
        for col, (lo, hi) in self.CLAMP_RANGES.items():
            val = cleaned.get(col)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                cleaned[col] = self.DEFAULTS[col]
                logger.debug("Filled missing %s with default %.2f", col, self.DEFAULTS[col])
            else:
                clamped = float(np.clip(float(val), lo, hi))
                if clamped != val:
                    logger.debug(
                        "Clamped %s: %.4f → %.4f", col, val, clamped
                    )
                cleaned[col] = clamped
        return cleaned

    # ------------------------------------------------------------------
    # Sliding-window buffer
    # ------------------------------------------------------------------

    def add_to_buffer(self, reading: Dict) -> None:
        """
        Append a (cleaned) reading to the per-location sliding-window buffer.

        If the buffer for the location does not yet exist it is created.

        Parameters
        ----------
        reading : Dict
        """
        loc = reading.get("location_id", "unknown")
        if loc not in self._buffers:
            self._buffers[loc] = deque(maxlen=self.window_size)
        self._buffers[loc].append(self.clean_reading(reading))
        logger.debug(
            "Buffer[%s] size: %d/%d", loc, len(self._buffers[loc]), self.window_size
        )

    def compute_window_stats(self, location_id: str) -> Dict:
        """
        Compute mean, std, min, and max across the current window buffer
        for *location_id*.

        Parameters
        ----------
        location_id : str

        Returns
        -------
        Dict
            {column: {mean, std, min, max}} or {} if buffer is empty.
        """
        buf = self._buffers.get(location_id, deque())
        if not buf:
            logger.warning("No buffer data for location '%s'.", location_id)
            return {}

        df = pd.DataFrame(list(buf))
        available = [c for c in self.SENSOR_COLUMNS if c in df.columns]
        stats: Dict = {}
        for col in available:
            series = df[col].dropna().astype(float)
            stats[col] = {
                "mean": round(float(series.mean()), 4),
                "std":  round(float(series.std(ddof=1)) if len(series) > 1 else 0.0, 4),
                "min":  round(float(series.min()), 4),
                "max":  round(float(series.max()), 4),
                "count": int(len(series)),
            }
        return stats

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def aggregate_hourly(self, readings: List[Dict]) -> pd.DataFrame:
        """
        Group *readings* by hour and return per-hour averages for all
        sensor columns.

        Parameters
        ----------
        readings : List[Dict]

        Returns
        -------
        pd.DataFrame
            Columns: timestamp (period start), nh3_ppm, h2s_ppm, …
        """
        if not readings:
            return pd.DataFrame(columns=["timestamp"] + self.SENSOR_COLUMNS)

        df = pd.DataFrame(readings)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["timestamp"])
        df = df.set_index("timestamp")

        available = [c for c in self.SENSOR_COLUMNS if c in df.columns]
        hourly = (
            df[available]
            .resample("H")
            .mean()
            .reset_index()
        )
        hourly = hourly.rename(columns={"timestamp": "hour"})
        return hourly

    # ------------------------------------------------------------------
    # CSV I/O
    # ------------------------------------------------------------------

    def load_from_csv(self, filepath: str) -> pd.DataFrame:
        """
        Load sensor readings from a CSV file.

        Parameters
        ----------
        filepath : str

        Returns
        -------
        pd.DataFrame
        """
        df = pd.read_csv(filepath, parse_dates=["timestamp"])
        logger.info("Loaded %d rows from '%s'.", len(df), filepath)
        return df

    def save_processed(self, df: pd.DataFrame, filepath: str) -> None:
        """
        Save a processed DataFrame to *filepath* as CSV.

        Parameters
        ----------
        df : pd.DataFrame
        filepath : str
        """
        df.to_csv(filepath, index=False)
        logger.info("Saved %d rows to '%s'.", len(df), filepath)

    # ------------------------------------------------------------------
    # Batch DataFrame preprocessing
    # ------------------------------------------------------------------

    def preprocess_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply cleaning (clamp + fill-missing) to an entire DataFrame.

        Parameters
        ----------
        df : pd.DataFrame

        Returns
        -------
        pd.DataFrame
        """
        df = df.copy()
        for col, (lo, hi) in self.CLAMP_RANGES.items():
            if col in df.columns:
                df[col] = df[col].fillna(self.DEFAULTS[col])
                df[col] = df[col].clip(lower=lo, upper=hi).astype(float)
        logger.info("preprocess_dataframe applied to %d rows.", len(df))
        return df
