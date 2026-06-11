# System Diagram — Public Sanitation Monitoring

## Network Topology

```
[Toilet Block A]          [Toilet Block B]        [Toilet Block C]
  Sensor Node 1            Sensor Node 2            Sensor Node 3
  (ESP32 + sensors)        (ESP32 + sensors)        (ESP32 + sensors)
       |                        |                        |
       +------------------------+------------------------+
                                |
                       [Wi-Fi Network]
                                |
                      [MQTT Broker Server]
                                |
                    [Python Data Collector]
                                |
              +-----------------+-----------------+
              |                                   |
     [Time-Series Storage]              [Anomaly Detection Engine]
              |                                   |
     [Dashboard / Analytics]            [Alert Service]
                                                  |
                                    [SMS / Email / App Notification]
```

## Data Flow Timing

| Stage | Latency | Frequency |
|-------|---------|----------|
| Sensor → MQTT | < 100ms | 1 Hz |
| MQTT → Collector | < 200ms | 1 Hz |
| Anomaly Check | < 50ms | Per reading |
| Alert Dispatch | < 1s | On anomaly |
| Dashboard Refresh | 5s | Polling |
| Historical Report | N/A | Hourly batch |
