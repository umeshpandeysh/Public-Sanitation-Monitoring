"""
sensor/simulator.py
-------------------
Simulates MQ-135 (NH3/H2S/CO2), DHT22 (temp/humidity), and PMS5003 (PM2.5)
sensor readings for public sanitation monitoring.
"""

import random
import time
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SensorSimulator:
    """
    Generates synthetic sensor readings that mimic real IIoT hardware
    (MQ-135, DHT22, PMS5003) installed in public toilet facilities.

    Normal readings follow Gaussian distributions around empirically-derived
    baseline values. Anomalous readings simulate hazardous conditions such as
    blocked drainage, poor ventilation, or bio-hazard events.

    Parameters
    ----------
    location_ids : List[str]
        Identifiers for monitored sanitation locations.
    sampling_rate_hz : float
        Number of readings per second during simulation. Default = 1.0 Hz.
    seed : Optional[int]
        Random seed for reproducibility.
    """

    # (mean, std) tuples for each parameter under normal operating conditions
    NORMAL_RANGES: Dict[str, tuple] = {
        "nh3_ppm":       (8.0,  3.0),   # Ammonia — ppm
        "h2s_ppm":       (0.3,  0.2),   # Hydrogen Sulphide — ppm
        "temperature_c": (26.0, 3.0),   # Ambient temperature — °C
        "humidity_pct":  (65.0, 10.0),  # Relative humidity — %
        "pm25_ugm3":     (15.0, 5.0),   # PM2.5 particulate matter — µg/m³
    }

    # Hard lower bounds (sensor physics)
    _LOWER_BOUNDS: Dict[str, float] = {
        "nh3_ppm":       0.0,
        "h2s_ppm":       0.0,
        "temperature_c": -10.0,
        "humidity_pct":  0.0,
        "pm25_ugm3":     0.0,
    }

    def __init__(
        self,
        location_ids: List[str],
        sampling_rate_hz: float = 1.0,
        seed: Optional[int] = None,
    ) -> None:
        if not location_ids:
            raise ValueError("location_ids must be a non-empty list.")
        self.location_ids = location_ids
        self.sampling_rate_hz = max(0.01, sampling_rate_hz)
        self.interval_sec = 1.0 / self.sampling_rate_hz
        if seed is not None:
            random.seed(seed)
        logger.info(
            "SensorSimulator initialised — %d location(s), %.2f Hz sampling",
            len(location_ids),
            sampling_rate_hz,
        )

    # ------------------------------------------------------------------
    # Core reading generation
    # ------------------------------------------------------------------

    def generate_reading(
        self,
        location_id: str,
        inject_anomaly: bool = False,
    ) -> Dict:
        """
        Generate a single sensor reading for *location_id*.

        Parameters
        ----------
        location_id : str
        inject_anomaly : bool
            If True, reading values reflect hazardous conditions.

        Returns
        -------
        dict
            Keys: nh3_ppm, h2s_ppm, temperature_c, humidity_pct, pm25_ugm3,
                  timestamp (ISO-8601 UTC), location_id, anomaly_injected.
        """
        if inject_anomaly:
            values = {
                "nh3_ppm":       round(random.uniform(50.0, 80.0), 2),
                "h2s_ppm":       round(random.uniform(3.0, 8.0), 2),
                "temperature_c": round(
                    max(self._LOWER_BOUNDS["temperature_c"],
                        random.gauss(28.0, 2.0)), 2
                ),
                "humidity_pct":  round(random.uniform(88.0, 98.0), 2),
                "pm25_ugm3":     round(random.uniform(30.0, 90.0), 2),
            }
        else:
            values = {
                param: round(
                    max(self._LOWER_BOUNDS[param],
                        random.gauss(mean, std)), 2
                )
                for param, (mean, std) in self.NORMAL_RANGES.items()
            }

        reading = {
            "timestamp":       datetime.now(timezone.utc).isoformat(),
            "location_id":     location_id,
            "anomaly_injected": inject_anomaly,
            **values,
        }
        logger.debug("Generated reading for %s: %s", location_id, reading)
        return reading

    # ------------------------------------------------------------------
    # Batch generation
    # ------------------------------------------------------------------

    def generate_batch(
        self,
        n_readings: int,
        anomaly_rate: float = 0.05,
    ) -> List[Dict]:
        """
        Generate *n_readings* readings spread across all registered locations.

        Parameters
        ----------
        n_readings : int
        anomaly_rate : float
            Fraction of readings that should simulate anomalous conditions.

        Returns
        -------
        List[Dict]
        """
        if n_readings <= 0:
            raise ValueError("n_readings must be a positive integer.")
        if not 0.0 <= anomaly_rate <= 1.0:
            raise ValueError("anomaly_rate must be in [0.0, 1.0].")

        readings: List[Dict] = []
        for _ in range(n_readings):
            loc = random.choice(self.location_ids)
            inject = random.random() < anomaly_rate
            readings.append(self.generate_reading(loc, inject_anomaly=inject))

        n_anomalies = sum(1 for r in readings if r["anomaly_injected"])
        logger.info(
            "Batch generated: %d readings (%d anomalies, %.1f%%)",
            n_readings, n_anomalies, 100.0 * n_anomalies / n_readings,
        )
        return readings

    # ------------------------------------------------------------------
    # Continuous simulation
    # ------------------------------------------------------------------

    def run_simulation(
        self,
        duration_sec: int,
        callback: Callable[[Dict], None],
        anomaly_rate: float = 0.05,
    ) -> None:
        """
        Continuously generate readings and call *callback* for each.

        One reading is generated per location per sampling interval.

        Parameters
        ----------
        duration_sec : int
            How long to run the simulation (wall-clock seconds).
        callback : Callable[[Dict], None]
            Called synchronously for every reading produced.
        anomaly_rate : float
            Probability of injecting an anomaly on each reading.
        """
        logger.info(
            "Starting simulation: duration=%ds, rate=%.2fHz, anomaly_rate=%.2f",
            duration_sec, self.sampling_rate_hz, anomaly_rate,
        )
        end_time = time.monotonic() + duration_sec
        total_readings = 0

        while time.monotonic() < end_time:
            for loc in self.location_ids:
                inject = random.random() < anomaly_rate
                reading = self.generate_reading(loc, inject_anomaly=inject)
                try:
                    callback(reading)
                except Exception as exc:  # pragma: no cover
                    logger.error("Callback raised an exception: %s", exc)
                total_readings += 1
            time.sleep(self.interval_sec)

        logger.info("Simulation complete — %d readings produced.", total_readings)
