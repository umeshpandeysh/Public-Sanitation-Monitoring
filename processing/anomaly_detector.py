"""
processing/anomaly_detector.py
-------------------------------
Multi-level anomaly detection for sanitation sensor readings.

Detection methods
-----------------
1. **Threshold** — static warning/critical levels per sensor parameter.
2. **Statistical (Z-score)** — deviation from recent rolling history.
3. **Trend** — monotonic increase across a configurable window.
4. **IsolationForest** — unsupervised ML outlier detection (requires scikit-learn).

The public entry point `classify_reading()` combines all available methods and
returns a unified status dict with confidence score.
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from sklearn.ensemble import IsolationForest

    SKLEARN_AVAILABLE = True
    logger.info("scikit-learn detected — IsolationForest detection enabled.")
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.info("scikit-learn not found — IsolationForest detection disabled.")


class AnomalyDetector:
    """
    Detects anomalous sensor readings using threshold, statistical,
    trend-based, and (optionally) ML-based methods.

    Parameters
    ----------
    window_size : int
        Number of historical readings used for trend detection. Default 15.
    z_threshold : float
        Z-score magnitude above which a value is flagged. Default 3.0.
    """

    THRESHOLDS: Dict[str, Dict[str, float]] = {
        "nh3_ppm":       {"warning": 25.0,  "critical": 50.0},
        "h2s_ppm":       {"warning": 1.0,   "critical": 5.0},
        "temperature_c": {"warning": 35.0,  "critical": 42.0},
        "humidity_pct":  {"warning": 85.0,  "critical": 95.0},
        "pm25_ugm3":     {"warning": 25.0,  "critical": 75.0},
    }

    SENSOR_COLUMNS: List[str] = [
        "nh3_ppm",
        "h2s_ppm",
        "temperature_c",
        "humidity_pct",
        "pm25_ugm3",
    ]

    def __init__(
        self,
        window_size: int = 15,
        z_threshold: float = 3.0,
    ) -> None:
        self.window_size = window_size
        self.z_threshold = z_threshold
        self._isolation_forest: Optional[object] = None
        self._if_fitted: bool = False

    # ------------------------------------------------------------------
    # Method 1: Threshold-based detection
    # ------------------------------------------------------------------

    def detect_threshold_anomaly(self, reading: Dict) -> Dict:
        """
        Compare each sensor value against static warning and critical levels.

        Parameters
        ----------
        reading : Dict

        Returns
        -------
        Dict
            {status: 'normal'|'warning'|'critical', violations: List[Dict]}
        """
        violations: List[Dict] = []
        overall_status = "normal"

        for param, levels in self.THRESHOLDS.items():
            val = reading.get(param)
            if val is None:
                continue

            val = float(val)
            if val >= levels["critical"]:
                violations.append(
                    {
                        "parameter": param,
                        "value":     val,
                        "level":     "critical",
                        "threshold": levels["critical"],
                    }
                )
                overall_status = "critical"
            elif val >= levels["warning"]:
                violations.append(
                    {
                        "parameter": param,
                        "value":     val,
                        "level":     "warning",
                        "threshold": levels["warning"],
                    }
                )
                if overall_status != "critical":
                    overall_status = "warning"

        logger.debug(
            "Threshold check — status=%s, violations=%d",
            overall_status, len(violations),
        )
        return {"status": overall_status, "violations": violations}

    # ------------------------------------------------------------------
    # Method 2: Statistical (Z-score) detection
    # ------------------------------------------------------------------

    def detect_statistical_anomaly(
        self,
        reading: Dict,
        history: List[Dict],
    ) -> Dict:
        """
        Flag a reading if any sensor value is more than *z_threshold* standard
        deviations away from the historical mean.

        Parameters
        ----------
        reading : Dict
        history : List[Dict]
            Recent readings used to compute the rolling mean/std.

        Returns
        -------
        Dict
            {status, z_scores: {param: float}, flagged: bool}
        """
        MIN_HISTORY = 5
        if len(history) < MIN_HISTORY:
            logger.debug(
                "Insufficient history (%d < %d) for Z-score detection.",
                len(history), MIN_HISTORY,
            )
            return {"status": "normal", "z_scores": {}, "flagged": False}

        df = pd.DataFrame(history)
        z_scores: Dict[str, float] = {}
        flagged = False

        for col in self.SENSOR_COLUMNS:
            if col not in df.columns or col not in reading or reading[col] is None:
                continue

            mean = float(df[col].mean())
            std = float(df[col].std(ddof=1))
            z = 0.0 if std == 0 else (float(reading[col]) - mean) / std
            z_scores[col] = round(z, 3)

            if abs(z) > self.z_threshold:
                flagged = True
                logger.debug(
                    "Z-score anomaly — %s z=%.3f (threshold=%.1f)",
                    col, z, self.z_threshold,
                )

        status = "warning" if flagged else "normal"
        return {"status": status, "z_scores": z_scores, "flagged": flagged}

    # ------------------------------------------------------------------
    # Method 3: Trend detection
    # ------------------------------------------------------------------

    def detect_trend_anomaly(
        self,
        history: List[Dict],
        parameter: str,
    ) -> bool:
        """
        Return True if *parameter* has been monotonically increasing across
        the most recent *window_size* readings (possible drainage blockage).

        Parameters
        ----------
        history : List[Dict]
        parameter : str

        Returns
        -------
        bool
        """
        if len(history) < self.window_size:
            return False

        values = [
            float(r[parameter])
            for r in history[-self.window_size:]
            if parameter in r and r[parameter] is not None
        ]
        if len(values) < self.window_size:
            return False

        diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
        monotonic_up = all(d >= 0 for d in diffs)

        if monotonic_up:
            logger.debug(
                "Trend anomaly detected on '%s' over last %d readings.",
                parameter, self.window_size,
            )
        return monotonic_up

    # ------------------------------------------------------------------
    # Combined classification
    # ------------------------------------------------------------------

    def classify_reading(
        self,
        reading: Dict,
        history: List[Dict],
    ) -> Dict:
        """
        Run all detection methods and return a unified classification.

        Priority order: critical > warning > normal.
        Confidence is a heuristic score in [0.0, 1.0].

        Parameters
        ----------
        reading : Dict
        history : List[Dict]

        Returns
        -------
        Dict
            {status, method, violations, confidence, trend_flags, z_scores}
        """
        # 1. Threshold
        thr = self.detect_threshold_anomaly(reading)
        status: str = thr["status"]
        method: str = "threshold"
        violations: List[Dict] = thr["violations"]

        # 2. Statistical
        stat = self.detect_statistical_anomaly(reading, history)
        if status == "normal" and stat["flagged"]:
            status = "warning"
            method = "statistical"

        # 3. Trend
        trend_flags: List[str] = [
            p for p in self.SENSOR_COLUMNS
            if self.detect_trend_anomaly(history, p)
        ]
        if trend_flags and status == "normal":
            status = "warning"
            method = "trend"

        # 4. IsolationForest (if fitted)
        if_flag = False
        if SKLEARN_AVAILABLE and self._if_fitted:
            if_flag = self.detect_isolation_forest(reading)
            if if_flag and status == "normal":
                status = "warning"
                method = "isolation_forest"

        # Confidence heuristic
        n_violations = len(violations)
        confidence = min(
            1.0,
            0.4
            + 0.15 * n_violations
            + (0.2 if stat["flagged"] else 0.0)
            + (0.1 if trend_flags else 0.0)
            + (0.1 if if_flag else 0.0),
        )
        if status == "critical":
            confidence = max(confidence, 0.85)

        return {
            "status":      status,
            "method":      method,
            "violations":  violations,
            "confidence":  round(confidence, 3),
            "trend_flags": trend_flags,
            "z_scores":    stat.get("z_scores", {}),
        }

    # ------------------------------------------------------------------
    # IsolationForest (conditional)
    # ------------------------------------------------------------------

    if SKLEARN_AVAILABLE:

        def fit_isolation_forest(
            self,
            historical_data: pd.DataFrame,
            contamination: float = 0.05,
        ) -> None:
            """
            Fit an IsolationForest model on *historical_data*.

            Parameters
            ----------
            historical_data : pd.DataFrame
                Must contain the five sensor columns.
            contamination : float
                Expected fraction of outliers. Default 0.05.
            """
            available = [c for c in self.SENSOR_COLUMNS if c in historical_data.columns]
            X = historical_data[available].dropna()
            if len(X) < 20:
                logger.warning(
                    "Too few samples (%d) to fit IsolationForest reliably.", len(X)
                )
                return

            self._isolation_forest = IsolationForest(
                contamination=contamination,
                random_state=42,
                n_estimators=100,
            )
            self._isolation_forest.fit(X)
            self._if_fitted = True
            logger.info(
                "IsolationForest fitted on %d samples (contamination=%.2f).",
                len(X), contamination,
            )

        def detect_isolation_forest(self, reading: Dict) -> bool:
            """
            Return True if *reading* is classified as an outlier by the
            fitted IsolationForest.

            Parameters
            ----------
            reading : Dict

            Returns
            -------
            bool
            """
            if not self._if_fitted or self._isolation_forest is None:
                logger.warning(
                    "IsolationForest not fitted. Call fit_isolation_forest() first."
                )
                return False

            X = np.array(
                [[float(reading.get(col, 0.0)) for col in self.SENSOR_COLUMNS]]
            )
            prediction = self._isolation_forest.predict(X)
            is_outlier = bool(prediction[0] == -1)
            if is_outlier:
                logger.debug("IsolationForest flagged reading as outlier.")
            return is_outlier
