# Sensor Hardware Setup Guide

## Components Required

| Component | Model | Purpose | Qty |
|-----------|-------|---------|-----|
| Gas Sensor | MQ-135 | Detect NH3, H2S, CO2, benzene vapours | 1 |
| Temp & Humidity | DHT22 (AM2302) | Ambient temperature and humidity | 1 |
| Particulate Matter | PMS5003 | PM1.0, PM2.5, PM10 concentration | 1 |
| Microcontroller | ESP32 (WROOM-32) | Wi-Fi/BLE gateway for MQTT | 1 |
| Breadboard | Half-size | Prototyping | 1 |
| Resistors | 10 kΩ | Pull-up for DHT22 data line | 2 |
| Power Supply | 5V 2A USB | Power rails | 1 |
| Jumper Wires | M-M, M-F | Connections | 30+ |
| USB-UART | CP2102 / CH340 | Flash ESP32 firmware | 1 |

---

## Wiring Diagram (ASCII)

```
                         ┌──────────────────────────────────┐
                         │            ESP32 WROOM-32         │
                         │                                    │
   MQ-135                │  3.3V ──────────────── 3V3        │
   ┌──────┐              │  GND  ──────────────── GND        │
   │ VCC  │──────────────│  3V3                              │
   │ GND  │──────────────│  GND                              │
   │ DOUT │──────────────│  GPIO34 (ADC1_CH6)               │
   │ AOUT │  [optional]  │                                    │
   └──────┘              │                                    │
                         │                                    │
   DHT22                 │                                    │
   ┌──────┐  10kΩ        │                                    │
   │ VCC  │──┬───────────│  3V3                              │
   │ DATA │──┤───────────│  GPIO4  (pull-up to 3V3)         │
   │  NC  │  │           │                                    │
   │ GND  │──┴───────────│  GND                              │
   └──────┘  GND         │                                    │
                         │                                    │
   PMS5003               │                                    │
   ┌──────┐              │                                    │
   │ VCC  │──────────────│  5V  (use external 5V rail)      │
   │ GND  │──────────────│  GND                              │
   │  TX  │──────────────│  GPIO16 (UART2 RX)               │
   │  RX  │──────────────│  GPIO17 (UART2 TX)               │
   │  SET │──────────────│  3V3  (active = normal mode)     │
   │ RESET│──────────────│  3V3  (active LOW, pull HIGH)    │
   └──────┘              │                                    │
                         └──────────────────────────────────┘
```

> ⚠️ **Note**: PMS5003 requires a 5V supply. Use a level shifter or a voltage divider on the TX→ESP32 RX line if needed.

---

## ESP32 Firmware Setup

### Option A: MicroPython

1. **Install MicroPython firmware:**
   ```bash
   esptool.py --port COM3 erase_flash
   esptool.py --port COM3 --baud 460800 write_flash -z 0x1000 esp32-micropython-latest.bin
   ```

2. **Install required libraries** (via `mpremote` or Thonny):
   ```
   - umqtt.simple
   - dht (built-in)
   - machine (built-in)
   ```

3. **Upload `main.py`** that reads all three sensors and publishes to MQTT:
   ```python
   import dht, machine, ujson, time
   from umqtt.simple import MQTTClient

   # Sensor pins
   dht_sensor = dht.DHT22(machine.Pin(4))
   mq135_adc  = machine.ADC(machine.Pin(34))
   mq135_adc.atten(machine.ADC.ATTN_11DB)

   client = MQTTClient("esp32_node", "192.168.1.100", port=1883)
   client.connect()

   while True:
       dht_sensor.measure()
       payload = ujson.dumps({
           "location_id": "block_A_toilet_1",
           "temperature_c": dht_sensor.temperature(),
           "humidity_pct": dht_sensor.humidity(),
           "nh3_raw_adc": mq135_adc.read(),
       })
       client.publish(b"sanitation/block_A_toilet_1", payload.encode())
       time.sleep(5)
   ```

### Option B: Arduino IDE

1. Install **Arduino ESP32 core** via Board Manager URL:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```

2. Install libraries via Library Manager:
   - `DHT sensor library` by Adafruit
   - `PubSubClient` by Nick O'Leary
   - `PMS Library` by Mariusz Kacki

3. Configure `secrets.h`:
   ```cpp
   #define WIFI_SSID "your_ssid"
   #define WIFI_PASS "your_password"
   #define MQTT_HOST "192.168.1.100"
   #define MQTT_PORT 1883
   ```

---

## MQTT Broker Setup (Mosquitto)

### Install Mosquitto

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y mosquitto mosquitto-clients

# macOS (Homebrew)
brew install mosquitto

# Windows
# Download installer from https://mosquitto.org/download/
```

### Configure `/etc/mosquitto/mosquitto.conf`

```conf
listener 1883
allow_anonymous true
log_type all
log_dest file /var/log/mosquitto/mosquitto.log
```

### Start Broker

```bash
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# Test with
mosquitto_sub -h localhost -t "sanitation/#" -v &
mosquitto_pub -h localhost -t "sanitation/test" -m '{"test": true}'
```

---

## Sensor Calibration

### MQ-135 (NH3 / H2S)

1. Power the sensor for **24–48 hours** in clean air (burn-in period).
2. Measure `R0` (sensor resistance in clean air):
   ```python
   import machine
   adc = machine.ADC(machine.Pin(34))
   adc.atten(machine.ADC.ATTN_11DB)
   raw = adc.read()          # 0–4095
   voltage = raw * 3.3 / 4095
   Rs = (3.3 - voltage) / voltage * 10_000  # Load resistor = 10kΩ
   R0 = Rs / 3.6             # Rs/R0 ratio for NH3 in clean air ≈ 3.6
   print(f"R0 = {R0:.1f} Ω")
   ```
3. Store `R0` in firmware constants. Recalibrate monthly.

### DHT22

- Factory-calibrated; no field calibration required.
- Verify readings against a reference thermometer. Typical accuracy: ±0.5 °C, ±2–5% RH.
- Discard the first reading after power-on (often erroneous).

### PMS5003

- Factory-calibrated with NIST-traceable standards.
- Allow **30 seconds** of fan run-in before recording data.
- Clean the optical chamber quarterly using compressed air.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| MQ-135 always reads 0 | ADC pin wrong or floating | Check GPIO34 connection; use `ATTN_11DB` |
| DHT22 returns `NaN` | Timing issue or missing pull-up | Add 10 kΩ resistor; slow down polling to ≥ 2 s |
| PMS5003 no data | UART baud rate mismatch | Set `Serial2.begin(9600)` for PMS5003 |
| MQTT connection refused | Broker not running or wrong IP | `systemctl status mosquitto`; check IP |
| Readings wildly high | MQ-135 still warming up | Wait 48 h burn-in; check load resistor value |
| ESP32 keeps rebooting | Insufficient power | Use dedicated 5V 2A supply; add 100 µF capacitor near ESP32 |
