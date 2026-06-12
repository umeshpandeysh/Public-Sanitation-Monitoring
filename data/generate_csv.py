"""
data/generate_csv.py
---------------------
Generates 1000 synthetic sensor readings and writes them to sample_readings.csv.
Run this script once to regenerate the dataset.

    python data/generate_csv.py
"""

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(42)

LOCATIONS = [
    "block_A_toilet_1",
    "block_A_toilet_2",
    "block_B_toilet_1",
    "block_B_toilet_2",
]

START_TS = datetime(2025, 2, 1, 0, 0, 0)
INTERVAL_MINUTES = 21   # ~1000 readings over 15 days

FIELDNAMES = [
    "timestamp",
    "location_id",
    "nh3_ppm",
    "h2s_ppm",
    "temperature_c",
    "humidity_pct",
    "pm25_ugm3",
    "anomaly_flag",
]

N_TOTAL   = 1000
N_NORMAL  = 950
N_WARNING = 30
N_CRITICAL = 20


def _normal_reading() -> dict:
    return {
        "nh3_ppm":       round(max(0, random.gauss(8.0, 2.5)),   2),
        "h2s_ppm":       round(max(0, random.gauss(0.3, 0.12)),  3),
        "temperature_c": round(random.uniform(24.0, 30.0),        1),
        "humidity_pct":  round(random.uniform(55.0, 80.0),        1),
        "pm25_ugm3":     round(max(0, random.gauss(15.0, 4.0)),   1),
        "anomaly_flag":  0,
    }


def _warning_reading() -> dict:
    return {
        "nh3_ppm":       round(random.uniform(25.0, 45.0),  2),
        "h2s_ppm":       round(random.uniform(1.0,  4.0),   3),
        "temperature_c": round(random.uniform(24.0, 30.0),  1),
        "humidity_pct":  round(random.uniform(85.0, 93.0),  1),
        "pm25_ugm3":     round(random.uniform(25.0, 50.0),  1),
        "anomaly_flag":  1,
    }


def _critical_reading() -> dict:
    return {
        "nh3_ppm":       round(random.uniform(55.0, 80.0),  2),
        "h2s_ppm":       round(random.uniform(5.0,  10.0),  3),
        "temperature_c": round(random.uniform(24.0, 32.0),  1),
        "humidity_pct":  round(random.uniform(94.0, 99.0),  1),
        "pm25_ugm3":     round(random.uniform(75.0, 120.0), 1),
        "anomaly_flag":  2,
    }


def main():
    # Build label list and shuffle
    labels = (
        ["normal"]   * N_NORMAL  +
        ["warning"]  * N_WARNING +
        ["critical"] * N_CRITICAL
    )
    random.shuffle(labels)

    rows = []
    for i, label in enumerate(labels):
        ts = START_TS + timedelta(minutes=INTERVAL_MINUTES * i)
        loc = LOCATIONS[i % len(LOCATIONS)]
        if label == "normal":
            vals = _normal_reading()
        elif label == "warning":
            vals = _warning_reading()
        else:
            vals = _critical_reading()

        rows.append(
            {
                "timestamp":   ts.strftime("%Y-%m-%d %H:%M:%S"),
                "location_id": loc,
                **vals,
            }
        )

    out_path = os.path.join(os.path.dirname(__file__), "sample_readings.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅  Wrote {len(rows)} rows → {out_path}")


if __name__ == "__main__":
    main()
