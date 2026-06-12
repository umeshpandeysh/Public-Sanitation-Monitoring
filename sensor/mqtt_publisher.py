"""
sensor/mqtt_publisher.py
------------------------
Publishes sensor readings from SensorSimulator to an MQTT broker using
the paho-mqtt client library. Degrades gracefully when paho-mqtt is absent.

Usage (CLI):
    python -m sensor.mqtt_publisher --broker localhost --duration 120 \
        --anomaly-rate 0.05 --locations block_A_toilet_1 block_B_toilet_1
"""

import argparse
import json
import logging
import sys
from typing import Dict, List

logger = logging.getLogger(__name__)

try:
    import paho.mqtt.client as mqtt

    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False
    logger.warning(
        "paho-mqtt is not installed. MQTT publishing is disabled. "
        "Install it with: pip install paho-mqtt"
    )


# ---------------------------------------------------------------------------
# MQTTPublisher
# ---------------------------------------------------------------------------


class MQTTPublisher:
    """
    Thin wrapper around paho-mqtt for publishing sanitation sensor readings.

    Topic structure:
        {topic_prefix}/{location_id}/sensor   → individual readings (JSON)
        {topic_prefix}/batch                  → batch payloads

    Parameters
    ----------
    broker_host : str
        Hostname or IP of the MQTT broker (e.g. 'localhost').
    broker_port : int
        TCP port. Default 1883.
    topic_prefix : str
        Root topic prefix. Default 'sanitation'.
    keepalive : int
        MQTT keepalive interval in seconds. Default 60.
    """

    def __init__(
        self,
        broker_host: str,
        broker_port: int = 1883,
        topic_prefix: str = "sanitation",
        keepalive: int = 60,
    ) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic_prefix = topic_prefix
        self.keepalive = keepalive
        self._client = None
        self._connected = False

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Establish connection to the MQTT broker and start the network loop."""
        if not PAHO_AVAILABLE:
            raise RuntimeError(
                "paho-mqtt is not installed. Run: pip install paho-mqtt"
            )

        def _on_connect(client, userdata, flags, rc):
            if rc == 0:
                self._connected = True
                logger.info(
                    "Connected to MQTT broker at %s:%d",
                    self.broker_host, self.broker_port,
                )
            else:
                logger.error("MQTT connection failed with code %d", rc)

        def _on_disconnect(client, userdata, rc):
            self._connected = False
            logger.info("Disconnected from MQTT broker (rc=%d)", rc)

        self._client = mqtt.Client(client_id="sanitation-publisher")
        self._client.on_connect = _on_connect
        self._client.on_disconnect = _on_disconnect
        self._client.connect(self.broker_host, self.broker_port, self.keepalive)
        self._client.loop_start()

    def disconnect(self) -> None:
        """Stop the network loop and disconnect from the broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            logger.info("MQTT publisher disconnected.")

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish_reading(self, location_id: str, reading: Dict) -> None:
        """
        Publish a single sensor reading as a JSON payload.

        Parameters
        ----------
        location_id : str
        reading : Dict
        """
        if self._client is None or not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        topic = f"{self.topic_prefix}/{location_id}/sensor"
        payload = json.dumps(reading, default=str)
        result = self._client.publish(topic, payload, qos=1)

        if result.rc != 0:
            logger.warning(
                "Publish to %s failed (rc=%d)", topic, result.rc
            )
        else:
            logger.debug("Published → %s : %s", topic, payload)

    def publish_batch(self, readings: List[Dict]) -> None:
        """
        Publish a list of readings, one message per reading.

        Parameters
        ----------
        readings : List[Dict]
        """
        if not readings:
            return

        for reading in readings:
            loc = reading.get("location_id", "unknown")
            self.publish_reading(loc, reading)

        logger.info("Published batch of %d readings.", len(readings))


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def simulate_and_publish(
    simulator,
    publisher: MQTTPublisher,
    duration_sec: int,
    anomaly_rate: float = 0.05,
) -> None:
    """
    Wire a SensorSimulator to a MQTTPublisher for *duration_sec* seconds.

    Parameters
    ----------
    simulator : SensorSimulator
    publisher : MQTTPublisher
    duration_sec : int
    anomaly_rate : float
    """

    def _callback(reading: Dict) -> None:
        publisher.publish_reading(reading["location_id"], reading)

    logger.info(
        "Starting simulate-and-publish for %d seconds (anomaly_rate=%.2f)",
        duration_sec, anomaly_rate,
    )
    simulator.run_simulation(
        duration_sec=duration_sec,
        callback=_callback,
        anomaly_rate=anomaly_rate,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish simulated sanitation sensor readings to an MQTT broker.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--broker", default="localhost", help="MQTT broker hostname")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument(
        "--topic-prefix", default="sanitation", help="MQTT topic prefix"
    )
    parser.add_argument(
        "--duration", type=int, default=60, help="Simulation duration in seconds"
    )
    parser.add_argument(
        "--anomaly-rate",
        type=float,
        default=0.05,
        help="Fraction of readings that simulate anomalies (0.0 – 1.0)",
    )
    parser.add_argument(
        "--locations",
        nargs="+",
        default=[
            "block_A_toilet_1",
            "block_A_toilet_2",
            "block_B_toilet_1",
            "block_B_toilet_2",
        ],
        help="Location IDs to simulate",
    )
    parser.add_argument(
        "--sampling-rate",
        type=float,
        default=1.0,
        help="Readings per second per location",
    )
    return parser


if __name__ == "__main__":
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from sensor.simulator import SensorSimulator  # noqa: E402

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    args = _build_parser().parse_args()

    if not PAHO_AVAILABLE:
        print(
            "[ERROR] paho-mqtt is not installed.\n"
            "Install it with:  pip install paho-mqtt\n"
            "Exiting.",
            file=sys.stderr,
        )
        sys.exit(1)

    sim = SensorSimulator(
        location_ids=args.locations,
        sampling_rate_hz=args.sampling_rate,
    )
    pub = MQTTPublisher(
        broker_host=args.broker,
        broker_port=args.port,
        topic_prefix=args.topic_prefix,
    )

    try:
        pub.connect()
        simulate_and_publish(sim, pub, args.duration, args.anomaly_rate)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        pub.disconnect()
