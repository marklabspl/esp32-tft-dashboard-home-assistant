"""Beginner-friendly TFT / MQTT hints for the config flow (Polish + English)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import (
    ROLE_BINARY,
    ROLE_CHART_BAR,
    ROLE_CHART_LINE,
    ROLE_CUSTOM,
    ROLE_ENERGY_PRICE,
    ROLE_GAUGE,
    ROLE_POWERFLOW_BAT,
    ROLE_POWERFLOW_GRID,
    ROLE_POWERFLOW_LOAD,
    ROLE_POWERFLOW_PV,
    ROLE_SENSOR,
    ROLE_WEATHER,
)


def _lang(hass: HomeAssistant) -> str:
    raw = getattr(hass.config, "language", None) or "en"
    return str(raw).lower()


# {topic} = full MQTT state topic published by this integration.
_HINTS_PL: dict[str, str] = {
    ROLE_SENSOR: (
        "**Na wyświetlaczu:** w przeglądarce otwórz stronę konfiguracji ESP (IP lub nazwa `.local` na pasku TFT). "
        "Dodaj kafelek **sensor** i w pole **Topic** wklej dokładnie:\n`{topic}`\n"
        "To ten sam adres, który integracja wysyła na brokera MQTT — nie musisz pisać szablonów ręcznie."
    ),
    ROLE_GAUGE: (
        "**Na wyświetlaczu:** kafelek **gauge** (półokrągły wskaźnik). **Topic:**\n`{topic}`\n"
        "Wartość musi być liczbą (np. procent baterii)."
    ),
    ROLE_CHART_LINE: (
        "**Na wyświetlaczu:** kafelek **chart_line**. **Topic:**\n`{topic}`\n"
        "Jeśli włączysz historię z Recordera, wykres wypełni się z Home Assistant; inaczej rośnie z każdą zmianą stanu encji."
    ),
    ROLE_CHART_BAR: (
        "**Na wyświetlaczu:** kafelek **chart_bar**. **Topic:**\n`{topic}`\n"
        "Działa jak wykres liniowy pod kątem MQTT — różnica to styl słupków na TFT."
    ),
    ROLE_BINARY: (
        "**Na wyświetlaczu:** kafelek **binary** (np. brama, okno). **Topic:**\n`{topic}`\n"
        "Stan **on**/**off** (lub **open**/**closed**) z HA pojawi się na ikonie."
    ),
    ROLE_POWERFLOW_PV: (
        "**Na wyświetlaczu:** panel **Przepływ energii** — pole mocy **PV**. **Topic:**\n`{topic}`\n"
        "Wpisz tę samą ścieżkę MQTT w konfiguracji panelu na ESP."
    ),
    ROLE_POWERFLOW_LOAD: (
        "**Na wyświetlaczu:** panel **Przepływ energii** — zużycie **dom**. **Topic:**\n`{topic}`"
    ),
    ROLE_POWERFLOW_GRID: (
        "**Na wyświetlaczu:** panel **Przepływ energii** — **sieć** (import/eksport). **Topic:**\n`{topic}`"
    ),
    ROLE_POWERFLOW_BAT: (
        "**Na wyświetlaczu:** panel **Przepływ energii** — **bateria**. **Topic:**\n`{topic}`"
    ),
    ROLE_WEATHER: (
        "**Na wyświetlaczu:** panel **Pogoda** (pełny ekran). Jeden **Topic:**\n`{topic}`\n"
        "Encja `weather.*` w HA jest zwykle z **OpenWeatherMap** (integracja + lokalizacja) — integracja TFT publikuje jej JSON na MQTT."
    ),
    ROLE_ENERGY_PRICE: (
        "**Na wyświetlaczu:** panel **Cena energii**. **Topic ceny:**\n`{topic}`\n"
        "Typowe w PL: integracja **ha_rce** (RCE) — JSON ze `state`, `prices_today`, opcjonalnie binary „tanio”. "
        "Z historią Recordera wykres może dostać gotową tablicę z bazy HA."
    ),
    ROLE_CUSTOM: (
        "**Na wyświetlaczu:** wklej ten adres jako topic w miejscu, które odpowiada Twojemu kafelkowi / panelowi:\n`{topic}`"
    ),
}

_HINTS_EN: dict[str, str] = {
    ROLE_SENSOR: (
        "**On the display:** open the ESP config page in a browser (IP or `.local` name from the TFT status bar). "
        "Add a **sensor** tile and paste this into **Topic**:\n`{topic}`\n"
        "That is the same path this integration publishes to MQTT — no hand-written templates required."
    ),
    ROLE_GAUGE: (
        "**On the display:** **gauge** tile (semicircle). **Topic:**\n`{topic}`\n"
        "The entity state should be numeric (e.g. battery %)."
    ),
    ROLE_CHART_LINE: (
        "**On the display:** **chart_line** tile. **Topic:**\n`{topic}`\n"
        "With **Recorder history** enabled, the chart is filled from Home Assistant; otherwise it grows from each state update."
    ),
    ROLE_CHART_BAR: (
        "**On the display:** **chart_bar** tile. **Topic:**\n`{topic}`\n"
        "Same MQTT idea as the line chart; the TFT draws bars instead of a line."
    ),
    ROLE_BINARY: (
        "**On the display:** **binary** tile (gate, window, …). **Topic:**\n`{topic}`\n"
        "**on**/**off** (or **open**/**closed**) from HA drives the icon."
    ),
    ROLE_POWERFLOW_PV: (
        "**On the display:** **Power flow** panel — **PV** power field. **Topic:**\n`{topic}`"
    ),
    ROLE_POWERFLOW_LOAD: (
        "**On the display:** **Power flow** panel — **home** load. **Topic:**\n`{topic}`"
    ),
    ROLE_POWERFLOW_GRID: (
        "**On the display:** **Power flow** panel — **grid** import/export. **Topic:**\n`{topic}`"
    ),
    ROLE_POWERFLOW_BAT: (
        "**On the display:** **Power flow** panel — **battery**. **Topic:**\n`{topic}`"
    ),
    ROLE_WEATHER: (
        "**On the display:** **Weather** full-screen panel — single **topic:**\n`{topic}`\n"
        "In HA, `weather.*` is often from **OpenWeatherMap** (add the integration + location); TFT Dashboard publishes that entity’s JSON over MQTT."
    ),
    ROLE_ENERGY_PRICE: (
        "**On the display:** **Energy price** panel. **Price topic:**\n`{topic}`\n"
        "Common in PL: **ha_rce** (RCE) — JSON with `state`, `prices_today`, optional “cheap” binary. "
        "With Recorder history, the chart can receive a full array from HA."
    ),
    ROLE_CUSTOM: (
        "**On the display:** use this MQTT path wherever your tile/panel expects the topic:\n`{topic}`"
    ),
}


def esp32_panel_hint(hass: HomeAssistant, role: str, topic: str) -> str:
    """Localized instructions: open ESP web UI → paste `{topic}` for the chosen role."""
    table = _HINTS_PL if _lang(hass).startswith("pl") else _HINTS_EN
    template = table.get(role) or _HINTS_EN[ROLE_CUSTOM]
    return template.format(topic=topic)
