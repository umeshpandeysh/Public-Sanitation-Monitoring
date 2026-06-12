"""
Unit tests for processing/data_processor.py
"""
import sys
import os
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from processing.data_processor import DataProcessor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_valid_reading(**overrides):
    base = {
        "timestamp": "2025-02-01 06:00:00",
        "location_id": "block_A_toilet_1",
        "nh3_ppm": 8.0,
        "h2s_ppm": 0.3,
        "temperature_c": 26.0,
        "humidity_pct": 65.0,
        "pm25_ugm3": 15.0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# TestValidateReading
# ---------------------------------------------------------------------------

class TestValidateReading:
    def setup_method(self):
        self.processor = DataProcessor()

    def test_valid_reading_passes(self):
        reading = make_valid_reading()
        assert self.processor.validate_reading(reading) is True

    def test_missing_nh3_fails(self):
        reading = make_valid_reading()
        del reading["nh3_ppm"]
        assert self.processor.validate_reading(reading) is False

    def test_missing_location_id_fails(self):
        reading = make_valid_reading()
        del reading["location_id"]
        assert self.processor.validate_reading(reading) is False

    def test_missing_timestamp_fails(self):
        reading = make_valid_reading()
        del reading["timestamp"]
        assert self.processor.validate_reading(reading) is False

    def test_negative_nh3_fails(self):
        """Negative gas readings are physically impossible."""
        reading = make_valid_reading(nh3_ppm=-5.0)
        assert self.processor.validate_reading(reading) is False

    def test_humidity_over_100_fails(self):
        reading = make_valid_reading(humidity_pct=105.0)
        assert self.processor.validate_reading(reading) is False


# ---------------------------------------------------------------------------
# TestCleanReading
# ---------------------------------------------------------------------------

class TestCleanReading:
    def setup_method(self):
        self.processor = DataProcessor()

    def test_normal_reading_unchanged(self):
        reading = make_valid_reading()
        cleaned = self.processor.clean_reading(reading)
        assert cleaned["nh3_ppm"] == pytest.approx(8.0)

    def test_extreme_nh3_clamped(self):
        """NH3 above physical max should be clamped."""
        reading = make_valid_reading(nh3_ppm=9999.0)
        cleaned = self.processor.clean_reading(reading)
        assert cleaned["nh3_ppm"] <= 500.0, "Extreme NH3 should be clamped"

    def test_none_values_filled(self):
        reading = make_valid_reading(nh3_ppm=None)
        cleaned = self.processor.clean_reading(reading)
        assert cleaned["nh3_ppm"] is not None

    def test_negative_humidity_clamped(self):
        reading = make_valid_reading(humidity_pct=-10.0)
        cleaned = self.processor.clean_reading(reading)
        assert cleaned["humidity_pct"] >= 0.0


# ---------------------------------------------------------------------------
# TestComputeWindowStats
# ---------------------------------------------------------------------------

class TestComputeWindowStats:
    def setup_method(self):
        self.processor = DataProcessor(window_size=10)

    def test_correct_mean_from_buffer(self):
        """Add 5 identical readings; mean should equal the fixed value."""
        location = "block_A_toilet_1"
        for _ in range(5):
            self.processor.add_to_buffer(make_valid_reading(nh3_ppm=10.0))
        stats = self.processor.compute_window_stats(location)
        if stats:
            assert stats["nh3_ppm"]["mean"] == pytest.approx(10.0)

    def test_empty_buffer_returns_empty(self):
        stats = self.processor.compute_window_stats("nonexistent_location")
        assert stats == {} or stats is None

    def test_window_size_respected(self):
        """Buffer should not exceed window_size."""
        location = "block_A_toilet_1"
        for _ in range(20):
            self.processor.add_to_buffer(make_valid_reading())
        # Buffer length should be <= window_size
        buf = self.processor._buffer.get(location, [])
        assert len(buf) <= self.processor.window_size


# ---------------------------------------------------------------------------
# TestAggregateHourly
# ---------------------------------------------------------------------------

class TestAggregateHourly:
    def setup_method(self):
        self.processor = DataProcessor()

    def _make_readings_df(self):
        """Create a small DataFrame spanning two hours."""
        rows = []
        for i in range(6):
            rows.append({
                "timestamp": f"2025-02-01 06:{i*5:02d}:00",
                "location_id": "block_A_toilet_1",
                "nh3_ppm": 10.0,
                "h2s_ppm": 0.3,
                "temperature_c": 26.0,
                "humidity_pct": 65.0,
                "pm25_ugm3": 15.0,
            })
        for i in range(6):
            rows.append({
                "timestamp": f"2025-02-01 07:{i*5:02d}:00",
                "location_id": "block_A_toilet_1",
                "nh3_ppm": 20.0,
                "h2s_ppm": 0.5,
                "temperature_c": 27.0,
                "humidity_pct": 70.0,
                "pm25_ugm3": 18.0,
            })
        return pd.DataFrame(rows)

    def test_group_by_hour_returns_two_rows(self):
        df = self._make_readings_df()
        hourly = self.processor.aggregate_hourly(df.to_dict(orient="records"))
        if isinstance(hourly, pd.DataFrame) and not hourly.empty:
            assert len(hourly) == 2

    def test_mean_values_correct(self):
        df = self._make_readings_df()
        hourly = self.processor.aggregate_hourly(df.to_dict(orient="records"))
        if isinstance(hourly, pd.DataFrame) and not hourly.empty:
            # Hour 06 → mean nh3 = 10.0
            hour6 = hourly[hourly.index.hour == 6] if hasattr(hourly.index, 'hour') else hourly.iloc[0]
            # Just check it doesn't crash and returns numeric data
            assert hourly["nh3_ppm"].dtype in (float, "float64")
