# 📟 ESP32 TFT Dashboard for Home Assistant

> **Private, non-commercial project** · Built for my own workshop · Shared as-is

💸 Build your own Home Assistant dashboard for **~$12**
📟 Works on **ESP32 + 2.8" TFT display (ST7789)**
⚡ No YAML, no automations — everything configured from the browser UI

---

## 📸 Preview

<div align="center">
  <img src="https://github.com/user-attachments/assets/6039a7c1-481f-4da9-ae39-1f3273a8d09d" width="400" alt="TFT Dashboard preview" />
</div>

---

## ✨ Features

### 📊 Widgets & tiles

| Tile type | Description | HA entity |
|-----------|-------------|-----------|
| `sensor` | Numeric value with unit | `sensor.*` |
| `binary` | On/off state with custom labels | `binary_sensor.*`, `switch.*` |
| `gauge` | Half-circle gauge with min/max/warn | `sensor.*` (numeric) |
| `clock` | Clock + date (NTP) | — no entity needed — |
| `chart_line` | Line chart (history) | `sensor.*` (numeric) |
| `chart_bar` | Bar chart | `sensor.*` (numeric) |
| `weather` | Current weather with icon | `weather.*` |
| `forecast` | 5-day forecast | `weather.*` (same topic) |
| `price` | Current energy price | `sensor.rce_*` or similar |
| `powerflow` | PV → Home → Grid → Battery | 4 × `sensor.*` (W or kW) |

---

### ⚡ Energy dashboard (Powerflow)

- PV production
- Home consumption
- Grid import / export
- Battery state

---

### 🌤️ Weather

- Current conditions with icon
- 5-day forecast
- Wind speed & bearing, humidity, pressure
- Precipitation probability

---

### 💰 Energy prices

- Current price display
- Supports **ha_rce** integration
- Daily price chart from `prices_today` attribute

---

### 🕘 History charts

The Home Assistant integration can fill charts with **last 24h of data** from HA Recorder on startup — no need to wait for data to accumulate.

- Supported for: `chart_line`, `chart_bar`
- Max 5 sensors with history enabled simultaneously
- Refreshes every 5 minutes

---

## 💸 Build cost

| Component | Cost |
|-----------|------|
| ESP32 WROOM-32 / DevKitC | ~$5 |
| 2.8" ST7789 TFT display (SPI) | ~$7 |
| **Total** | **~$12** |

---

## 🔧 Wiring

| TFT pin | ESP32 pin | GPIO | Description |
|---------|-----------|------|-------------|
| MOSI | IO23 | 23 | SPI data |
| SCLK | IO18 | 18 | SPI clock |
| CS | IO15 | 15 | Chip select |
| DC | IO2 | 2 | Data / Command |
| RST | IO4 | 4 | Reset |
| BL | IO32 | 32 | Backlight |
| VCC | 3.3V | — | Power |
| GND | GND | — | Ground |

---

## 🔧 Requirements

### Hardware

- ESP32 (WROOM-32 or DevKitC, 38-pin)
- TFT display: **2.8" ST7789 (SPI), 240×320 px**
- USB cable (data, not charge-only)

### Software

- Home Assistant 2024+
- MQTT broker (Mosquitto add-on or external)
- MQTT integration configured in HA
- Chrome or Edge browser (for flashing and configuration)
- USB drivers: CH340 or CP2102

---

## 🚀 Quick start

### 1. Flash firmware

👉 **[marklabs.pl/tftflasher](https://marklabs.pl/en/tftflasher)**

Open the page in Chrome or Edge, connect ESP32 via USB, click **Flash firmware**.
No tools or command line needed.

---

### 2. Configure WiFi

After flashing, ESP32 broadcasts its own WiFi network:

1. Connect to: `TFT-Dashboard-XXXX`
2. Open browser: `http://192.168.4.1`
3. Enter your WiFi credentials and save
4. ESP32 restarts and connects to your home network
5. IP address is shown in the status bar on the TFT display

---

### 3. Configure MQTT

Open the ESP32 configuration panel at `http://[ESP32-IP]` or `http://esp32-dashboard.local`

Set:
- **Broker IP** — your Home Assistant IP (e.g. `192.168.1.10`)
- **Port** — `1883` (default Mosquitto)
- **Login / password** — if required by your broker

---

## 🧩 Home Assistant integration

### Installation via HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=marklabspl&repository=esp32-tft-dashboard-home-assistant&category=integration)

1. Go to: **HACS → Integrations → ⋮ → Custom repositories**
2. Add repository:
   ```
   https://github.com/marklabspl/esp32-tft-dashboard-home-assistant
   ```
   Category: **Integration**
3. Find **TFT Dashboard MQTT Bridge** and click Install
4. Restart Home Assistant

---

### Configuration

After restart: **Settings → Devices & Services → Add Integration → TFT Dashboard MQTT Bridge**

Set:
| Option | Description |
|--------|-------------|
| MQTT topic prefix | e.g. `tft/` — topics will be: `tft/temperature`, `tft/gate` etc. |
| Retain | Recommended ON — ESP32 gets last value immediately on connect |
| Publish on startup | Recommended ON — sends current values when HA starts |

---

### Adding entities — 3-step wizard

Click **Configure → Add entity**:

**Step 1** — Select any entity from Home Assistant

**Step 2** — Choose the role:

| Role | ESP32 tile type |
|------|----------------|
| Sensor / number | `SENSOR` |
| Round gauge | `GAUGE` |
| Line chart | `CHART_LINE` |
| Bar chart | `CHART_BAR` |
| Binary sensor | `BINARY` |
| Energy flow — PV | `POWERFLOW` → Topic (PV) |
| Energy flow — load | `POWERFLOW` → Topic Load |
| Energy flow — grid | `POWERFLOW` → Topic Grid |
| Energy flow — battery | `POWERFLOW` → Topic Battery |
| Weather | `WEATHER` panel |
| Energy price | `ENERGY_PRICE` panel |

**Step 3** — Confirm MQTT topic suffix and settings
- Topic is auto-filled from entity name (e.g. `sensor.temp_salon` → `tft/temp_salon`)
- You can change it to anything (e.g. `tft/temperatura`)
- For charts: optional toggle to fill with 24h history from Recorder

The step 3 screen shows the exact topic to enter in the ESP32 configuration panel.

> No YAML or automations required.

---

## 📡 MQTT payload format

The integration publishes data in different formats depending on entity type:

**Numeric sensors** → plain string
```
tft/temperatura    →  "21.5"
tft/pv_power       →  "3450"
```

**Binary sensors** → `"on"` or `"off"`
```
tft/brama          →  "on"
```

**Weather** → JSON
```json
{
  "state": "sunny",
  "temperature": 18.5,
  "humidity": 65,
  "wind_speed": 12.3,
  "wind_bearing": 270,
  "pressure": 1013.2,
  "forecast": [
    {
      "date": "2026-04-14T10:00:00+00:00",
      "condition": "cloudy",
      "templow": 8.0,
      "temperature": 18.0,
      "precipitation_probability": 30,
      "wind_speed": 15.0
    }
  ]
}
```

**History chart** → JSON (sent on startup and every 5 minutes)
```json
{
  "values": [21.5, 21.3, 21.1, 20.9, ...],
  "current": 21.5
}
```

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| ESP32 not detected on port list | Install CH340 or CP2102 drivers. Try a different cable (some USB cables are charge-only) |
| Display lights up but shows nothing | Check DC/CS/RST wiring. Make sure firmware matches your display (ST7789) |
| No WiFi connection | Check SSID and password. ESP32 supports **2.4 GHz only** (not 5 GHz) |
| No MQTT data on display | Check broker IP in ESP32 panel. Check HA integration is configured and running |
| HA integration: Invalid handler specified | Remove old integration, delete `custom_components/tft_dashboard/` folder, install fresh, **full HA restart** |
| Charts show "Collecting data..." | Without history: data collects in real time — wait a few minutes. With history enabled: check HA Recorder is active |
| ESP32 config panel unreachable | Check IP shown on TFT status bar. Try `http://esp32-dashboard.local`. Ensure same WiFi network |

---

## ⚠️ Beta status

This project is currently in **beta**.

It was originally created for personal use and is now shared publicly in its current form.
While it has been tested and works stable in my environment, it may not behave the same way in all setups.

- some features may still be incomplete
- certain configurations may not be fully supported
- unexpected bugs may occur

The project is under active development.

---

## ⚠️ Disclaimer

Use this project at your own risk.

The author is not responsible for hardware damage, data loss, or misconfiguration issues.

---

## 💬 Feedback

Feedback, bug reports and suggestions are welcome.

If something does not work as expected:
- open an **Issue** on GitHub
- include HA logs (`Settings → System → Logs`, search for `tft_dashboard`) and your configuration

---

## 👤 Author

Marek · [marklabs.pl](https://marklabs.pl)
