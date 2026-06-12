"""
Unit tests for processing/anomaly_detector.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from processing.anomaly_detector import AnomalyDetector  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_normal_reading(**overrides):
    base = {
        "nh3_ppm": 8.0,
        "h2s_ppm": 0.3,
        "temperature_c": 26.0,
        "humidity_pct": 65.0,
        "pm25_ugm3": 15.0,
    }
    base.update(overrides)
    return base


def make_history(n=20, **fixed_vals):
    """Return a list of n identical readings (flat history)."""
    return [make_normal_reading(**fixed_vals) for _ in range(n)]


# ---------------------------------------------------------------------------
# TestThresholdDetection
# ---------------------------------------------------------------------------

class TestThresholdDetection:
    def setup_method(self):
        self.detector = AnomalyDetector()

    def test_normal_reading_returns_normal(self):
        reading = make_normal_reading()
        result = self.detector.detect_threshold_anomaly(reading)
        assert result["status"] == "normal"
        assert result["violations"] == []

    def test_warning_threshold_nh3(self):
        """NH3 = 30 ppm should trigger a warning (warning threshold = 25)."""
        reading = make_normal_reading(nh3_ppm=30.0)
        result = self.detector.detect_threshold_anomaly(reading)
        assert result["status"] in ("warning", "critical")
        params = [v["parameter"] for v in result["violations"]]
        assert "nh3_ppm" in params

    def test_critical_threshold_nh3(self):
        """NH3 = 60 ppm should trigger a critical alert (critical threshold = 50)."""
        reading = make_normal_reading(nh3_ppm=60.0)
        result = self.detector.detect_threshold_anomaly(reading)
        assert result["status"] == "critical"

    def test_warning_threshold_h2s(self):
        """H2S = 2 ppm triggers warning (warning = 1.0)."""
        reading = make_normal_reading(h2s_ppm=2.0)
        result = self.detector.detect_threshold_anomaly(reading)
        assert result["status"] in ("warning", "critical")

    def test_critical_threshold_h2s(self):
        """H2S = 6 ppm triggers critical (critical = 5.0)."""
        reading = make_normal_reading(h2s_ppm=6.0)
        result = self.detector.detect_threshold_anomaly(reading)
        assert result["status"] == "critical"

    def test_multiple_violations_in_single_reading(self):
        """Both NH3 and H2S above threshold should both appear in violations."""
        reading = make_normal_reading(nh3_ppm=60.0, h2s_ppm=6.0)
        result = self.detector.detect_threshold_anomaly(reading)
        params = [v["parameter"] for v in result["violations"]]
        assert "nh3_ppm" in params
        assert "h2s_ppm" in params


# ---------------------------------------------------------------------------
# TestStatisticalAnomaly
# ---------------------------------------------------------------------------

class TestStatisticalAnomaly:
    def setup_method(self):
        self.detector = AnomalyDetector(z_threshold=3.0)

    def test_flat_history_normal_reading(self):
        """Same value repeated: std ≈ 0, reading equals mean → normal."""
        history = make_history(20, nh3_ppm=8.0)
        reading = make_normal_reading(nh3_ppm=8.0)
        result = self.detector.detect_statistical_anomaly(reading, history)
        # Either "normal" or a graceful result when std == 0
        assert "status" in result

    def test_flat_history_extreme_reading(self):
        """History std ≈ 0 but reading is far away — should not crash."""
        history = make_history(20, nh3_ppm=8.0)
        reading = make_normal_reading(nh3_ppm=80.0)
        result = self.detector.detect_statistical_anomaly(reading, history)
        assert "status" in result

    def test_normal_reading_within_z_bounds(self):
        """Reading within 1 std of history mean → no statistical anomaly."""
        history = [make_normal_reading(nh3_ppm=8.0 + i * 0.1) for i in range(20)]
        reading = make_normal_reading(nh3_ppm=8.5)
        result = self.detector.detect_statistical_anomaly(reading, history)
        assert result["status"] == "normal"

    def test_empty_history_handled_gracefully(self):
        reading = make_normal_reading()
        result = self.detector.detect_statistical_anomaly(reading, [])
        assert "status" in result


# ---------------------------------------------------------------------------
# TestZScoreLogic
# ---------------------------------------------------------------------------

class TestZScoreLogic:
    def setup_method(self):
        self.detector = AnomalyDetector(z_threshold=2.0)

    def test_zscore_above_threshold_flagged(self):
        """
        History: 20 readings at nh3=8.0 with tiny jitter (std ≈ 0.5).
        A reading of 50.0 ppm is >> 2 std away → should flag anomaly.
        """
        import random
        random.seed(0)
        history = [make_normal_reading(nh3_ppm=8.0 + random.gauss(0, 0.5))
                   for _ in range(20)]
        reading = make_normal_reading(nh3_ppm=50.0)
        result = self.detector.detect_statistical_anomaly(reading, history)
        # The result status should not be "normal"
        assert result["status"] != "normal"


# ---------------------------------------------------------------------------
# TestClassifyReading
# ---------------------------------------------------------------------------

class TestClassifyReading:
    def setup_method(self):
        self.detector = AnomalyDetector()

    def test_classify_normal_reading(self):
        history = make_history(15)
        reading = make_normal_reading()
        result = self.detector.classify_reading(reading, history)
        assert "status" in result
        assert "confidence" in result
        assert result["status"] == "normal"

    def test_classify_critical_reading(self):
        history = make_history(15)
        reading = make_normal_reading(nh3_ppm=70.0, h2s_ppm=8.0, humidity_pct=97.0)
        result = self.detector.classify_reading(reading, history)
        assert result["status"] == "critical"
        assert result["confidence"] >= 0.0
        assert result["confidence"] <= 1.0

    def test_classify_returns_required_keys(self):
        history = make_history(15)
        reading = make_normal_reading()
        result = self.detector.classify_reading(reading, history)
        for key in ("status", "method", "violations", "confidence"):
            assert key in result, f"Missing key: {key}"
