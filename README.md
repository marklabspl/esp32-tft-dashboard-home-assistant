# esp32-tft-dashboard-home-assistant
ESP32 TFT dashboard for Home Assistant (2.8" display, ~$12 build). MQTT, no YAML, no automations. Supports sensors, charts, weather, powerflow and energy prices.
# 📟 ESP32 TFT Dashboard for Home Assistant (No YAML)

💸 Build your own Home Assistant dashboard for **~$12 **  
📟 Works on **ESP32 + 2.8" TFT display**  
⚡ No YAML, no automations — everything configured from UI  

---

## 📸 Preview

*(add screenshot or GIF here — highly recommended)*

---

## 🔧 Why this project?

This project was created for my own use as a small dashboard in my workshop.

I wanted a simple screen where I could see key Home Assistant data in real time while working — without opening the app or using a tablet.

So I built a lightweight ESP32 + TFT display that:
- shows important data at a glance  
- works independently  
- requires no complex setup  

---

## ⚠️ Beta status

This project is currently in **beta**.

It was originally created for personal use and is now shared publicly in its current form.  
While it has been tested and works stable in my environment, it may not behave the same way in all setups.

### What this means

- some features may still be incomplete  
- certain configurations may not be fully supported  
- unexpected bugs may occur  

The project is under active development and will be improved over time.

---

## 🧪 Stability

The dashboard is:
- tested on real hardware  
- used in daily operation  
- stable in my setup  

However:

- stability may vary depending on your hardware and Home Assistant configuration  
- edge cases and uncommon setups may not be fully handled yet  

---

## 🧠 Project scope

This is a:
- personal project  
- non-commercial solution  
- work in progress  

It is not intended to be a fully polished, production-ready product at this stage.

---

## ⚠️ Disclaimer

Use this project at your own risk.

The author is not responsible for:
- hardware damage  
- data loss  
- misconfiguration issues  

---

## ✨ Features

### 📊 Data & widgets

- Sensors (temperature, humidity, power, energy)
- Binary sensors (doors, motion, switches)
- Gauges (battery, pressure, levels)
- Charts:
  - line (history)
  - bar

---

### ⚡ Energy dashboard (Powerflow)

- PV production  
- Home consumption  
- Grid import/export  
- Battery  

---

### 🌤️ Weather

- current conditions  
- 5-day forecast  
- wind, humidity, pressure  
- precipitation probability  

---

### 💰 Energy prices

Supports:
- ha_rce integration  

---

## 🧠 How it works:
1. Select entities in Home Assistant  
2. Integration publishes data to MQTT  
3. ESP32 displays it on screen  

---

## 💸 Cost

You can build the entire dashboard for around:

- ESP32 → ~$5  
- TFT display → ~$7  

👉 Total: **~$12**

---

## 🔧 Requirements

### Hardware

- ESP32 (WROOM-32 / DevKitC)
- TFT display **2.8" ST7789 (SPI)**
- USB cable (data)

---

### Software

- Home Assistant (2024+)
- MQTT broker (Mosquitto)
- MQTT integration in HA
- Chrome / Edge browser

---

## 🚀 Installation

### 1. Flash firmware

👉 Go to: https://twojadomena.pl/flash
Click **Flash firmware** and select your ESP32.

---

### 2. Configure WiFi

- Connect to: `TFT-Dashboard-XXXX`
- Open: `http://192.168.4.1`
- Enter WiFi credentials

---

### 3. Configure MQTT

Open: http://[ESP32-IP]
Set:
- broker IP  
- port (1883)  
- login/password (if needed)

---

## 🔌 Home Assistant integration

## 🧩 Home Assistant integration (HACS)

The easiest way to install the integration is via HACS.

### 📦 Installation via HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=YOUR_USERNAME&repository=esp32-tft-dashboard-home-assistant&category=integration)

1. Open Home Assistant  
2. Go to:
   HACS → Integrations → ⋮ (top right) → Custom repositories

3. Add this repository:

   Repository:
   https://github.com/YOUR_USERNAME/esp32-tft-dashboard-home-assistant

   Category:
   Integration

4. Click Add

5. Find:
   TFT Dashboard MQTT Bridge

6. Click Install

7. Restart Home Assistant

---

### ⚙️ Add integration

After restart:

1. Go to:
   Settings → Devices & Services → Add Integration

2. Search for:
   TFT Dashboard MQTT Bridge

3. Configure:
   - MQTT topic prefix  
   - retain (recommended ON)  
   - publish on startup (recommended ON)  

---

### ➕ Add entities

Use the built-in wizard:

1. Click Configure  
2. Click Add entity  
3. Select:
   - entity from Home Assistant  
   - role (sensor, chart, weather, powerflow, etc.)  
4. Confirm MQTT topic  

👉 No YAML or automations required

---

## 📡 Supported data

### 🌤️ Weather

Uses:
- OpenWeatherMap integration  

---

### 💰 Energy prices

Uses:
- ha_rce integration  

---

### 📊 Other data

Supports standard Home Assistant entities:
sensor.* binary_sensor.* switch.*
---

## 🛠️ Troubleshooting

### No MQTT data
- check broker IP  
- check HA integration  
- subscribe to `tft/#`

---

### ESP32 not detected
- install CH340 / CP2102 drivers  
- use data USB cable  

---

### Empty charts
- wait for data  
- check Recorder in HA  

---

### WiFi issues
- ESP32 supports only 2.4 GHz

  ---

## 💬 Feedback

Feedback, bug reports and suggestions are welcome.

If something does not work as expected:
- open an issue on GitHub  
- include logs and configuration details  

---

## 👤 Author

Marek  
https://marklabs.pl


