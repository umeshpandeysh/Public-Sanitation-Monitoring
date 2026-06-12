"""
api/server.py
--------------
Flask REST API for the Public Sanitation Monitoring System.

Endpoints
---------
GET  /api/health          — Service liveness check
GET  /api/data            — Retrieve stored readings (optional filters)
GET  /api/anomalies       — Retrieve detected anomalies (optional filters)
GET  /api/status          — Per-location status summary
POST /api/readings        — Ingest a new sensor reading and run anomaly detection
GET  /api/alerts          — Retrieve alert history

Run with:
    python api/server.py
or for production:
    gunicorn -w 2 'api.server:app'
"""

import logging
import os
import sys
from datetime import datetime, timezone

from flask import Flask, jsonify, request

# ---------------------------------------------------------------------------
# Allow running directly from the api/ sub-directory
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processing.anomaly_detector import AnomalyDetector  # noqa: E402
from processing.alert_manager import AlertManager  # noqa: E402
from processing.data_processor import DataProcessor  # noqa: E402

# ---------------------------------------------------------------------------
# App + logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
START_TIME: datetime = datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# Shared service objects (application-level singletons)
# ---------------------------------------------------------------------------
processor = DataProcessor(window_size=60)
detector = AnomalyDetector()
alert_manager = AlertManager(alert_log_path="data/alerts.csv")

LOCATIONS = [
    "block_A_toilet_1",
    "block_A_toilet_2",
    "block_B_toilet_1",
    "block_B_toilet_2",
]

# In-process readings store: {location_id: [reading, ...]}
_readings_store: dict = {loc: [] for loc in LOCATIONS}

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _success(data: dict, status_code: int = 200):
    return jsonify(data), status_code


def _error(message: str, status_code: int = 400):
    return jsonify({"error": message}), status_code


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/api/health")
def health():
    """
    GET /api/health
    Returns service status, uptime in seconds, and number of monitored locations.
    """
    uptime_sec = (datetime.now(timezone.utc) - START_TIME).total_seconds()
    return _success(
        {
            "status":              "ok",
            "uptime_sec":          round(uptime_sec, 1),
            "locations_monitored": len(LOCATIONS),
            "locations":           LOCATIONS,
        }
    )


@app.route("/api/data")
def get_data():
    """
    GET /api/data?location_id=<str>&limit=<int>
    Returns stored readings for a location (or all locations).
    """
    location_id = request.args.get("location_id")
    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        return _error("'limit' must be an integer.", 400)

    if location_id:
        if location_id not in _readings_store:
            return _error(f"Unknown location_id: '{location_id}'", 404)
        readings = _readings_store[location_id][-limit:]
        return _success(
            {"location_id": location_id, "count": len(readings), "readings": readings}
        )

    # Return all locations
    payload = {
        loc: {"count": len(_readings_store[loc][-limit:]),
              "readings": _readings_store[loc][-limit:]}
        for loc in LOCATIONS
    }
    return _success(payload)


@app.route("/api/anomalies")
def get_anomalies():
    """
    GET /api/anomalies?location_id=<str>&severity=<str>
    Returns detected anomaly alerts, optionally filtered.
    """
    location_id = request.args.get("location_id")
    severity = request.args.get("severity")
    alerts = alert_manager.get_alert_history(
        location_id=location_id or None,
        severity=severity or None,
    )
    return _success({"count": len(alerts), "anomalies": alerts})


@app.route("/api/status")
def get_status():
    """
    GET /api/status
    Returns the latest status for every monitored location.
    """
    status_map = {}
    for loc in LOCATIONS:
        readings = _readings_store[loc]
        if readings:
            last = readings[-1]
            result = detector.detect_threshold_anomaly(last)
            status_map[loc] = {
                "status":          result["status"],
                "last_reading_ts": last.get("timestamp"),
                "latest_values": {
                    k: last.get(k)
                    for k in [
                        "nh3_ppm",
                        "h2s_ppm",
                        "temperature_c",
                        "humidity_pct",
                        "pm25_ugm3",
                    ]
                },
                "violations": result.get("violations", []),
            }
        else:
            status_map[loc] = {
                "status":          "no_data",
                "last_reading_ts": None,
                "latest_values":   {},
                "violations":      [],
            }
    return _success({"locations": status_map})


@app.route("/api/readings", methods=["POST"])
def ingest_reading():
    """
    POST /api/readings
    Body: JSON reading dict
    Validates, cleans, stores the reading, runs anomaly detection,
    and creates an alert if necessary.
    Returns the cleaned reading plus anomaly detection result.
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return _error("Request body must be valid JSON.", 400)

    if not processor.validate_reading(data):
        return _error(
            "Invalid reading: missing required fields or values out of range.", 422
        )

    cleaned = processor.clean_reading(data)
    loc = cleaned.get("location_id", "unknown")

    if loc not in _readings_store:
        _readings_store[loc] = []
    _readings_store[loc].append(cleaned)

    processor.add_to_buffer(cleaned)
    history = _readings_store[loc][:-1]
    result = detector.classify_reading(cleaned, history)

    alert_created = None
    if result["status"] != "normal":
        alert = alert_manager.create_alert(loc, cleaned, result)
        alert_manager.log_alert(alert)
        alert_created = alert["alert_id"]
        logger.info(
            "Alert created: %s  status=%s  location=%s",
            alert_created, result["status"], loc,
        )

    return _success(
        {
            "received":       True,
            "cleaned_reading": cleaned,
            "anomaly_result": result,
            "alert_id":       alert_created,
        },
        201,
    )


@app.route("/api/alerts")
def get_alerts():
    """
    GET /api/alerts
    Returns the full alert history with a count.
    """
    alerts = alert_manager.get_alert_history()
    stats = alert_manager.get_summary_stats()
    return _success(
        {
            "total":  len(alerts),
            "stats":  stats,
            "alerts": alerts,
        }
    )


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


@app.errorhandler(404)
def not_found(exc):
    return _error("Endpoint not found.", 404)


@app.errorhandler(405)
def method_not_allowed(exc):
    return _error("Method not allowed.", 405)


@app.errorhandler(500)
def internal_error(exc):
    logger.exception("Unhandled exception: %s", exc)
    return _error("Internal server error.", 500)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    logger.info("Starting Flask API on port %d (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
