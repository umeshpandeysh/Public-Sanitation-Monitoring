"""
processing/alert_manager.py
----------------------------
Manages alert creation, logging, retrieval, and notification for the
public sanitation monitoring system.

Alerts are persisted to a CSV file so they survive process restarts.
Console notifications use ANSI colour codes; email support is stubbed
for future integration (SMTP / SendGrid / etc.).
"""

import csv
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Creates, logs, retrieves, and dispatches alerts for anomalous readings.

    Parameters
    ----------
    alert_log_path : str
        Path to the CSV file where alerts are persisted. Default 'data/alerts.csv'.
    """

    SEVERITY_LEVELS: Dict[str, int] = {
        "normal":   0,
        "warning":  1,
        "critical": 2,
    }

    CSV_FIELDS: List[str] = [
        "alert_id",
        "timestamp",
        "location_id",
        "severity",
        "parameter",
        "value",
        "threshold",
        "message",
    ]

    # ANSI colour codes for console output
    _COLOURS: Dict[str, str] = {
        "normal":   "\033[92m",   # green
        "warning":  "\033[93m",   # yellow
        "critical": "\033[91m",   # red
    }
    _RESET = "\033[0m"

    def __init__(self, alert_log_path: str = "data/alerts.csv") -> None:
        self.alert_log_path = alert_log_path
        self._alerts: List[Dict] = []

        # Ensure the directory and header exist
        log_dir = os.path.dirname(alert_log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        if not os.path.exists(alert_log_path):
            with open(alert_log_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=self.CSV_FIELDS)
                writer.writeheader()
            logger.info("Created alert log at '%s'.", alert_log_path)
        else:
            # Load existing alerts into memory on startup
            self._load_existing_alerts()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_existing_alerts(self) -> None:
        """Read persisted alerts from the CSV into the in-memory list."""
        try:
            with open(self.alert_log_path, "r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                self._alerts = list(reader)
            logger.info(
                "Loaded %d existing alerts from '%s'.",
                len(self._alerts), self.alert_log_path,
            )
        except Exception as exc:
            logger.warning("Could not load existing alerts: %s", exc)

    # ------------------------------------------------------------------
    # Alert creation
    # ------------------------------------------------------------------

    def create_alert(
        self,
        location_id: str,
        reading: Dict,
        anomaly_result: Dict,
    ) -> Dict:
        """
        Build an alert dict from an anomaly detection result.

        Parameters
        ----------
        location_id : str
        reading : Dict
            The raw (or cleaned) sensor reading that triggered the alert.
        anomaly_result : Dict
            Output of AnomalyDetector.classify_reading().

        Returns
        -------
        Dict
            Alert record with a unique alert_id (UUID4).
        """
        severity = anomaly_result.get("status", "normal")
        violations = anomaly_result.get("violations", [])

        # Primary violating parameter
        if violations:
            param = violations[0]["parameter"]
            threshold = violations[0]["threshold"]
        else:
            param = "unknown"
            threshold = 0.0

        value = reading.get(param, None)

        alert: Dict = {
            "alert_id":    str(uuid.uuid4()),
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "location_id": location_id,
            "severity":    severity,
            "parameter":   param,
            "value":       value,
            "threshold":   threshold,
            "message":     "",
        }
        alert["message"] = self.format_alert_message(alert)

        logger.debug(
            "Created alert %s — %s [%s]", alert["alert_id"], severity, location_id
        )
        return alert

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def log_alert(self, alert: Dict) -> None:
        """
        Append *alert* to the in-memory list and persist it to the CSV log.

        Parameters
        ----------
        alert : Dict
        """
        self._alerts.append(alert)
        try:
            with open(self.alert_log_path, "a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=self.CSV_FIELDS)
                row = {k: alert.get(k, "") for k in self.CSV_FIELDS}
                writer.writerow(row)
            logger.info(
                "Alert logged: %s  severity=%s  location=%s",
                alert["alert_id"], alert["severity"], alert["location_id"],
            )
        except OSError as exc:
            logger.error("Failed to write alert to CSV: %s", exc)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_alert_history(
        self,
        location_id: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[Dict]:
        """
        Return alerts filtered by optional *location_id* and/or *severity*.

        Parameters
        ----------
        location_id : Optional[str]
        severity : Optional[str]
            One of 'normal', 'warning', 'critical'.

        Returns
        -------
        List[Dict]
        """
        results = self._alerts
        if location_id:
            results = [a for a in results if a.get("location_id") == location_id]
        if severity:
            results = [a for a in results if a.get("severity") == severity]
        return results

    def get_summary_stats(self) -> Dict:
        """
        Return aggregate statistics over all logged alerts.

        Returns
        -------
        Dict
            {total, by_severity: {}, by_location: {}}
        """
        total = len(self._alerts)
        by_severity = {
            lvl: sum(1 for a in self._alerts if a.get("severity") == lvl)
            for lvl in self.SEVERITY_LEVELS
        }
        locations = sorted({a.get("location_id", "unknown") for a in self._alerts})
        by_location = {
            loc: sum(1 for a in self._alerts if a.get("location_id") == loc)
            for loc in locations
        }
        return {
            "total":       total,
            "by_severity": by_severity,
            "by_location": by_location,
        }

    # ------------------------------------------------------------------
    # Notification
    # ------------------------------------------------------------------

    def format_alert_message(self, alert: Dict) -> str:
        """
        Return a human-readable alert message string.

        Parameters
        ----------
        alert : Dict

        Returns
        -------
        str
        """
        severity = alert.get("severity", "unknown").upper()
        loc = alert.get("location_id", "N/A")
        param = alert.get("parameter", "N/A")
        value = alert.get("value", "N/A")
        threshold = alert.get("threshold", "N/A")
        ts = alert.get("timestamp", "")
        return (
            f"[{severity}] {loc} — {param} = {value} "
            f"(threshold: {threshold}) at {ts}"
        )

    def console_notify(self, alert: Dict) -> None:
        """
        Print a colour-coded alert message to stdout.

        Parameters
        ----------
        alert : Dict
        """
        severity = alert.get("severity", "normal")
        colour = self._COLOURS.get(severity, "")
        message = self.format_alert_message(alert)
        print(f"{colour}{message}{self._RESET}")

    def email_notify_stub(self, alert: Dict, recipient: str) -> None:
        """
        Placeholder for email notification — prints what would be sent.

        Parameters
        ----------
        alert : Dict
        recipient : str
            Destination email address.
        """
        message = self.format_alert_message(alert)
        print(f"Would send email to {recipient}: {message}")
        logger.info(
            "Email stub triggered → %s  recipient=%s", alert.get("alert_id"), recipient
        )
