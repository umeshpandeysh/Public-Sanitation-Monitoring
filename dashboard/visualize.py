"""
visualize.py
Public Sanitation Monitoring — Real-Time Analytics Dashboard

Matplotlib-based dashboard for sensor data visualization and anomaly display.

Usage:
    python dashboard/visualize.py --data_file data/sensor_data.csv
"""

import argparse
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


SENSOR_CHANNELS = ["nh3_ppm", "h2s_ppm", "temperature_c", "humidity_pct", "pm25_ugm3"]
CHANNEL_LABELS = {
    "nh3_ppm": "NH₃ (ppm)",
    "h2s_ppm": "H₂S (ppm)",
    "temperature_c": "Temperature (°C)",
    "humidity_pct": "Humidity (%RH)",
    "pm25_ugm3": "PM2.5 (µg/m³)"
}
THRESHOLDS = {
    "nh3_ppm": 25.0,
    "h2s_ppm": 1.0,
    "humidity_pct": 85.0,
    "pm25_ugm3": 25.0
}


def load_data(filepath: str) -> pd.DataFrame:
    """
    Load sensor data CSV and parse timestamps.

    Args:
        filepath: Path to sensor data CSV.

    Returns:
        DataFrame with parsed timestamps as index.
    """
    df = pd.read_csv(filepath, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def generate_demo_data(n_points: int = 200) -> pd.DataFrame:
    """
    Generate synthetic sensor data for demonstration purposes.

    Args:
        n_points: Number of data points to generate.

    Returns:
        DataFrame with synthetic sensor readings.
    """
    np.random.seed(42)
    timestamps = pd.date_range(start=datetime.now(), periods=n_points, freq="1min")
    data = {
        "timestamp": timestamps,
        "location_id": "block_A_toilet_1",
        "nh3_ppm": np.clip(np.random.normal(15, 8, n_points), 0, 120),
        "h2s_ppm": np.clip(np.random.normal(0.5, 0.4, n_points), 0, 20),
        "temperature_c": np.clip(np.random.normal(29, 3, n_points), 15, 45),
        "humidity_pct": np.clip(np.random.normal(72, 12, n_points), 20, 100),
        "pm25_ugm3": np.clip(np.random.normal(20, 10, n_points), 0, 200),
        "anomaly_flag": "normal"
    }
    df = pd.DataFrame(data)
    # Inject some anomaly events
    df.loc[50:55, "nh3_ppm"] = 65  # Critical event
    df.loc[120:123, "humidity_pct"] = 92
    df.loc[50:55, "anomaly_flag"] = "critical"
    df.loc[120:123, "anomaly_flag"] = "warning"
    return df


def plot_dashboard(df: pd.DataFrame, title: str = "Sanitation Monitoring Dashboard"):
    """
    Generate a multi-panel sensor dashboard plot.

    Args:
        df: Sensor data DataFrame.
        title: Dashboard title.
    """
    channels_to_plot = [c for c in SENSOR_CHANNELS if c in df.columns]
    n_plots = len(channels_to_plot)

    fig, axes = plt.subplots(n_plots, 1, figsize=(14, 3 * n_plots))
    if n_plots == 1:
        axes = [axes]

    fig.suptitle(title, fontsize=14, fontweight="bold", y=1.01)

    for ax, channel in zip(axes, channels_to_plot):
        # Plot sensor readings
        ax.plot(df["timestamp"], df[channel], linewidth=1, color="steelblue", label=channel)

        # Shade anomaly regions
        if "anomaly_flag" in df.columns:
            warnings = df[df["anomaly_flag"] == "warning"]
            criticals = df[df["anomaly_flag"] == "critical"]
            ax.scatter(warnings["timestamp"], warnings[channel],
                       color="orange", s=30, zorder=5, label="Warning")
            ax.scatter(criticals["timestamp"], criticals[channel],
                       color="red", s=50, zorder=5, label="Critical", marker="x")

        # Threshold line
        if channel in THRESHOLDS:
            ax.axhline(y=THRESHOLDS[channel], color="red", linestyle="--",
                       alpha=0.5, linewidth=1, label=f"Threshold ({THRESHOLDS[channel]})")

        ax.set_ylabel(CHANNEL_LABELS.get(channel, channel))
        ax.legend(fontsize=7, loc="upper right")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.grid(True, alpha=0.3)

    axes[-1].set_xlabel("Time")
    plt.tight_layout()
    plt.savefig("dashboard/sanitation_dashboard.png", dpi=150, bbox_inches="tight")
    print("[INFO] Dashboard saved to dashboard/sanitation_dashboard.png")
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sanitation Monitoring Dashboard")
    parser.add_argument("--data_file", type=str, default=None,
                        help="Path to sensor CSV (uses demo data if not provided)")
    args = parser.parse_args()

    if args.data_file and Path(args.data_file).exists():
        df = load_data(args.data_file)
        print(f"[INFO] Loaded {len(df)} readings from {args.data_file}")
    else:
        print("[INFO] No data file provided — generating synthetic demo data")
        df = generate_demo_data(n_points=200)

    plot_dashboard(df)
