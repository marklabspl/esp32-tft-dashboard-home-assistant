"""TFT Dashboard MQTT bridge for ESP32 panels.

Each mapped Home Assistant entity is a config subentry (entity_id + MQTT suffix).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import TftDashboardCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = []


@dataclass
class TftDashboardData:
    coordinator: TftDashboardCoordinator


type TftDashboardConfigEntry = ConfigEntry[TftDashboardData]


async def async_setup_entry(
    hass: HomeAssistant, entry: TftDashboardConfigEntry
) -> bool:
    _LOGGER.debug("Setup entry %s", entry.entry_id)

    coordinator = TftDashboardCoordinator(hass, entry)
    entry.runtime_data = TftDashboardData(coordinator=coordinator)

    entry.async_on_unload(entry.add_update_listener(_on_update))

    await coordinator.async_start()

    _LOGGER.info("Started with MQTT prefix '%s'", coordinator.prefix)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TftDashboardConfigEntry
) -> bool:
    await entry.runtime_data.coordinator.async_stop()
    return True


async def _on_update(
    hass: HomeAssistant, entry: TftDashboardConfigEntry
) -> None:
    _LOGGER.debug("Config changed, reloading coordinator")
    await entry.runtime_data.coordinator.async_reload()
