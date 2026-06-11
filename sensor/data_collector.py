"""
data_collector.py
Public Sanitation Monitoring — Sensor Data Ingestion Module

Subscribes to MQTT broker topics and collects sensor readings
from the IIoT sensor network. Saves data to timestamped CSV files.

Usage:
    python sensor/data_collector.py
"""

import json
import csv
import os
from datetime import datetime
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("[WARN] paho-mqtt not installed. Run: pip install paho-mqtt")


# --- Configuration ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sanitation/#")

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

THRESHOLDS = {
    "nh3_ppm":      {"warning": 25.0,  "critical": 50.0},
    "h2s_ppm":      {"warning": 1.0,   "critical": 5.0},
    "humidity_pct": {"warning": 85.0,  "critical": 95.0},
    "pm25_ugm3":    {"warning": 25.0,  "critical": 75.0},
}

# CSV output file
csv_path = DATA_DIR / f"sensor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
CSV_FIELDS = ["timestamp", "location_id", "nh3_ppm", "h2s_ppm",
              "temperature_c", "humidity_pct", "pm25_ugm3", "anomaly_flag"]


def check_anomaly(reading: dict) -> str:
    """
    Apply threshold-based anomaly detection to a sensor reading.

    Args:
        reading: Dictionary of sensor values.

    Returns:
        'normal', 'warning', or 'critical'
    """
    status = "normal"
    for field, thresholds in THRESHOLDS.items():
        value = reading.get(field)
        if value is None:
            continue
        if value >= thresholds["critical"]:
            return "critical"  # Highest severity, return immediately
        elif value >= thresholds["warning"]:
            status = "warning"
    return status


def log_to_csv(reading: dict, anomaly_flag: str):
    """
    Append a sensor reading to the CSV log file.

    Args:
        reading: Dictionary of sensor values.
        anomaly_flag: Anomaly status string.
    """
    file_exists = csv_path.exists()
    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        row = {field: reading.get(field, "") for field in CSV_FIELDS}
        row["anomaly_flag"] = anomaly_flag
        if "timestamp" not in row or not row["timestamp"]:
            row["timestamp"] = datetime.utcnow().isoformat()
        writer.writerow(row)


def on_message(client, userdata, message):
    """
    MQTT message callback — processes incoming sensor readings.

    Args:
        client: MQTT client instance.
        userdata: User-defined data.
        message: Incoming MQTT message.
    """
    try:
        payload = json.loads(message.payload.decode("utf-8"))
        anomaly = check_anomaly(payload)
        log_to_csv(payload, anomaly)
        status_symbol = {"normal": "✅", "warning": "⚠️", "critical": "🚨"}.get(anomaly, "?")
        loc = payload.get("location_id", "unknown")
        ts = payload.get("timestamp", "")
        print(f"{status_symbol} [{ts}] {loc} | NH3: {payload.get('nh3_ppm', '?')} ppm | "
              f"Humidity: {payload.get('humidity_pct', '?')}% | Status: {anomaly.upper()}")
        if anomaly in ["warning", "critical"]:
            trigger_alert(payload, anomaly)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse MQTT payload: {e}")


def trigger_alert(reading: dict, severity: str):
    """
    Trigger an alert for a detected anomaly.
    Extend this function to send SMS/email notifications.

    Args:
        reading: Sensor reading that triggered the alert.
        severity: 'warning' or 'critical'
    """
    loc = reading.get("location_id", "unknown")
    print(f"[ALERT] {severity.upper()} at {loc} — "
          f"NH3: {reading.get('nh3_ppm')} ppm, "
          f"H2S: {reading.get('h2s_ppm')} ppm")
    # TODO: Integrate SMS/email/push notification service


def run_collector():
    """
    Start the MQTT data collection loop.
    """
    if not MQTT_AVAILABLE:
        print("[ERROR] Cannot start collector — paho-mqtt not installed.")
        print("[INFO] Install with: pip install paho-mqtt")
        return

    print(f"[INFO] Connecting to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"[INFO] Subscribing to topic: {MQTT_TOPIC}")
    print(f"[INFO] Logging to: {csv_path}")

    client = mqtt.Client(client_id="sanitation_collector")
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.subscribe(MQTT_TOPIC)
        print("[INFO] Data collector running. Press Ctrl+C to stop.")
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Data collector stopped.")
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        print(f"[INFO] Ensure MQTT broker is running at {MQTT_BROKER}:{MQTT_PORT}")


if __name__ == "__main__":
    run_collector()
