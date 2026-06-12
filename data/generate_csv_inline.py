"""Auto-generate sample_readings.csv with 1000 rows.

Run: python data/generate_csv_inline.py
"""
from __future__ import annotations

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(42)
LOCS = ["block_A_toilet_1", "block_A_toilet_2", "block_B_toilet_1", "block_B_toilet_2"]
START = datetime(2025, 2, 1, 0, 0, 0)
FIELDS = [
    "timestamp",
    "location_id",
    "nh3_ppm",
    "h2s_ppm",
    "temperature_c",
    "humidity_pct",
    "pm25_ugm3",
    "anomaly_flag",
]


def normal() -> dict:
    """Return normal-range readings dict."""
    return {
        "nh3_ppm": round(max(0.0, random.gauss(8, 2.5)), 2),
        "h2s_ppm": round(max(0.0, random.gauss(0.3, 0.12)), 3),
        "temperature_c": round(random.uniform(24, 30), 1),
        "humidity_pct": round(random.uniform(55, 80), 1),
        "pm25_ugm3": round(max(0.0, random.gauss(15, 4)), 1),
        "anomaly_flag": 0,
    }


def warning() -> dict:
    """Return warning-range readings dict."""
    return {
        "nh3_ppm": round(random.uniform(25, 45), 2),
        "h2s_ppm": round(random.uniform(1, 4), 3),
        "temperature_c": round(random.uniform(24, 30), 1),
        "humidity_pct": round(random.uniform(85, 93), 1),
        "pm25_ugm3": round(random.uniform(25, 50), 1),
        "anomaly_flag": 1,
    }


def critical() -> dict:
    """Return critical-range readings dict."""
    return {
        "nh3_ppm": round(random.uniform(55, 80), 2),
        "h2s_ppm": round(random.uniform(5, 10), 3),
        "temperature_c": round(random.uniform(24, 32), 1),
        "humidity_pct": round(random.uniform(94, 99), 1),
        "pm25_ugm3": round(random.uniform(75, 120), 1),
        "anomaly_flag": 2,
    }


def main() -> None:
    """Generate and write sample_readings.csv."""
    labels = ["normal"] * 950 + ["warning"] * 30 + ["critical"] * 20
    random.shuffle(labels)
    rows = []
    for i, lbl in enumerate(labels):
        ts = START + timedelta(minutes=21 * i)
        if lbl == "normal":
            vals = normal()
        elif lbl == "warning":
            vals = warning()
        else:
            vals = critical()
        rows.append({
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "location_id": LOCS[i % 4],
            **vals,
        })

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_readings.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
