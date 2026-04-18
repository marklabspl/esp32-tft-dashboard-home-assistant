"""Config-flow validation: MQTT prefix shape, role vs entity domain, numeric history."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_SEGMENT_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_FLOAT_STATE_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")

_ROLES_NEED_NUMERIC_DOMAIN = frozenset(
    {
        ROLE_SENSOR,
        ROLE_GAUGE,
        ROLE_CHART_LINE,
        ROLE_CHART_BAR,
        ROLE_ENERGY_PRICE,
        ROLE_POWERFLOW_PV,
        ROLE_POWERFLOW_LOAD,
        ROLE_POWERFLOW_GRID,
        ROLE_POWERFLOW_BAT,
    }
)

_NUMERIC_ENTITY_DOMAINS = frozenset({"sensor", "number", "input_number"})


def mqtt_prefix_error(prefix: str) -> str | None:
    """Return translation error key or None if prefix is valid (must end with /)."""
    if len(prefix) > 64:
        return "prefix_too_long"
    if not prefix.endswith("/"):
        return "prefix_invalid_chars"
    core = prefix[:-1]
    if not core:
        return "prefix_invalid_chars"
    for segment in core.split("/"):
        if not segment or not _SEGMENT_RE.match(segment):
            return "prefix_invalid_chars"
    return None


def _parse_numeric_fragment(raw: str) -> float | None:
    s = str(raw).strip().replace(",", ".")
    m = _FLOAT_STATE_RE.search(s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def history_state_float(raw: str | None) -> float | None:
    """Parse HA state string for chart/history (aligned with coordinator / Recorder)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() in ("unknown", "unavailable", "none"):
        return None
    return _parse_numeric_fragment(s)


def entity_reports_numeric_state(hass: HomeAssistant, entity_id: str) -> bool:
    """True if unknown/unavailable (allow setup before first report) or state parses as float."""
    st = hass.states.get(entity_id)
    if st is None:
        return True
    v = st.state
    if v in ("unknown", "unavailable", ""):
        return True
    return history_state_float(v) is not None


def validate_role_entity(hass: HomeAssistant, entity_id: str, role: str) -> str | None:
    """Return config_subentries.entity.error key or None."""
    if role == ROLE_CUSTOM:
        return None

    domain = entity_id.partition(".")[0]

    if role == ROLE_WEATHER:
        return None if domain == "weather" else "role_weather_mismatch"

    if role == ROLE_BINARY:
        return (
            None
            if domain in ("binary_sensor", "input_boolean", "switch")
            else "role_binary_mismatch"
        )

    if role in _ROLES_NEED_NUMERIC_DOMAIN:
        if domain == "weather":
            return "role_numeric_mismatch"
        if domain not in _NUMERIC_ENTITY_DOMAINS:
            return "role_numeric_mismatch"
        if not entity_reports_numeric_state(hass, entity_id):
            return "role_requires_numeric_state"

    return None


def validate_recorder_history_entity(hass: HomeAssistant, entity_id: str) -> str | None:
    """Block Recorder history when the entity cannot produce numeric points."""
    return (
        "history_requires_numeric"
        if not entity_reports_numeric_state(hass, entity_id)
        else None
    )


def payload_utf8_byte_length(payload: str) -> int:
    return len(payload.encode("utf-8"))
