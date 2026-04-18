# TFT Dashboard (MQTT Bridge)

Custom component for Home Assistant: mirrors selected entity states to MQTT topics for the ESP32 TFT Dashboard firmware.

**Wersja:** `0.1.1` — poprawki integracji (start/historia/MQTT/energy_price JSON); semver: patche `0.1.x`, większe zmiany `0.2.0` itd.

## Weather payload and `json.dumps(..., default=str)`

For entities with role **weather**, the bridge builds a JSON object from the HA state and attributes (`temperature`, `humidity`, `wind_speed`, `wind_bearing`, `pressure`, …) plus an optional **daily** forecast from the `weather.get_forecasts` service.

Some integrations expose attributes as non-numeric types (e.g. string `"unknown"`, or unusual objects). Serialization uses `json.dumps(..., default=str)` so publishing does not crash Home Assistant; values may then appear as strings in JSON (e.g. `"wind_bearing": "NaN"`). The ESP32 firmware tolerates missing or non-numeric fields when parsing. If your panel shows odd values, check the entity’s attributes in **Developer tools → States** and prefer a weather integration that exposes numeric attributes where possible.

## Validation (HACS / hassfest)

When this folder is the Git root (layout: `custom_components/tft_dashboard/`), GitHub Actions can run the official **hassfest** check — see `.github/workflows/validate.yml` in the parent `tft_dashboard` package directory.
