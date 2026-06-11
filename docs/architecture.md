# Public Sanitation Monitoring — System Architecture

## System Layers

1. **Perception Layer**: Physical sensors (gas, humidity, temperature, PM) on ESP32/Arduino nodes
2. **Network Layer**: MQTT protocol over Wi-Fi for lightweight, low-latency data transmission
3. **Processing Layer**: Python data ingestion, cleaning, and anomaly detection
4. **Storage Layer**: Time-series CSV / database for historical analysis
5. **Application Layer**: Matplotlib dashboard + REST API for alerts and reporting

## Anomaly Detection Strategy

- **Level 1 (Static)**: Configurable threshold comparison per sensor per location
- **Level 2 (Statistical)**: Z-score anomaly detection using rolling baseline
- **Level 3 (Trend)**: Monotonic increase detection over sliding window

## Design Principles

- Low-cost hardware (ESP32, ~$5 per node)
- Low-power MQTT protocol (ideal for battery-powered nodes)
- Configurable thresholds per deployment location
- Modular alerting (SMS/email/app notification pluggable)
- No vendor lock-in — works with any MQTT broker (Mosquitto, HiveMQ, AWS IoT)
