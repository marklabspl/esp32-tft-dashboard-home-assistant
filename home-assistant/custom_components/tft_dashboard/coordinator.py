"""Coordinator: mirror entity states to MQTT (optional Recorder history for charts)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components import mqtt
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENTITY_ID,
    CONF_ENTITY_ROLE,
    CONF_HISTORY_ENABLED,
    CONF_HISTORY_FROM_RECORDER,
    CONF_HISTORY_HOURLY,
    CONF_HISTORY_HOURS,
    CONF_HISTORY_POLL_INTERVAL,
    CONF_MQTT_PREFIX,
    CONF_PUBLISH_ON_START,
    CONF_RELAXED_LIMITS,
    CONF_RETAIN,
    CONF_SUFFIX,
    DEFAULT_HISTORY_FROM_RECORDER,
    DEFAULT_HISTORY_HOURLY,
    DEFAULT_HISTORY_HOURS,
    DEFAULT_HISTORY_POLL_INTERVAL,
    DEFAULT_MQTT_PREFIX,
    DEFAULT_PUBLISH_ON_START,
    DEFAULT_RETAIN,
    HISTORY_INTERVAL_S,
    HISTORY_LOOKBACK_H,
    HISTORY_MAX_RAW_STATES,
    HISTORY_POINTS,
    MAX_HISTORY_HOURS,
    MAX_HISTORY_SENSORS,
    MAX_HISTORY_SENSORS_EXPERT,
    QUERY_TIMEOUT_S,
    ROLE_ENERGY_PRICE,
    ROLE_WEATHER,
    SUBENTRY_TYPE_ENTITY,
)
from .entity_validation import history_state_float, payload_utf8_byte_length

_LOGGER = logging.getLogger(__name__)

# Firmware: PubSubClient buffer 16384 (mqtt.cpp); topic + MQTT framing — cap payload below that.
# ha_rce (96×15 min × 2 dni + maski) potrafi ~3.8–4.5 kB; zostawiamy zapas pod większe encje.
_MAX_PAYLOAD_BYTES = 12288

# Home Assistant custom integration ha_rce (jacek2511/ha_rce) — atrybuty sensor.rce_electricity_market_price
# przekazywane w jednym JSON do panelu TFT (ceny dzisiaj/jutro, maski „taniego okna”).
_ENERGY_PRICE_ATTR_KEYS = (
    "prices_today",
    "cheap_mask_today",
    "prices_tomorrow",
    "cheap_mask_tomorrow",
    "average",
    "min",
    "max",
    "median",
    "peak_range",
    "low_price_cutoff",
    "price_mode",
    "operation_mode",
)


def _energy_price_mqtt_body(state: Any) -> dict[str, Any]:
    """JSON dla panelu energy_price: stan + atrybuty zgodne z ha_rce."""
    body: dict[str, Any] = {"state": state.state}
    attrs = getattr(state, "attributes", None) or {}
    for key in _ENERGY_PRICE_ATTR_KEYS:
        if key not in attrs:
            continue
        body[key] = attrs[key]
    return body


def _coerce_float_list(raw: Any) -> list[float]:
    """Lista liczb do JSON (bez default=str — zwykłe floaty, krótszy zapis)."""
    if raw is None or not isinstance(raw, (list, tuple)):
        return []
    out: list[float] = []
    for x in raw:
        if x is None:
            continue
        if isinstance(x, bool):
            continue
        if isinstance(x, (int, float)):
            out.append(float(x))
            continue
        v = history_state_float(str(x))
        if v is not None:
            out.append(v)
    return out


def _coerce_cheap_mask_today(raw: Any) -> list[int] | None:
    if raw is None or not isinstance(raw, (list, tuple)):
        return None
    out: list[int] = []
    for x in raw:
        if isinstance(x, bool):
            out.append(int(x))
        elif isinstance(x, (int, float)):
            out.append(1 if int(x) else 0)
        else:
            s = str(x).strip().lower()
            if s in ("1", "true", "yes", "on"):
                out.append(1)
            elif s in ("0", "false", "no", "off", ""):
                out.append(0)
            else:
                out.append(1 if s else 0)
    return out


def _history_scalar_for_json(val: Any) -> float | int | str | bool | None:
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        return val
    return str(val)


# Historia MQTT dla wykresu: bez jutra, bez duplikatu values/prices_today, liczby jako JSON numbers.
_ENERGY_PRICE_HISTORY_ATTR_KEYS = (
    "average",
    "min",
    "max",
    "median",
    "peak_range",
    "low_price_cutoff",
    "price_mode",
    "operation_mode",
)


def _energy_price_history_mqtt_body(
    live: Any, points: list[float], lookback_h: int, chart_day: str
) -> dict[str, Any]:
    ex = _energy_price_mqtt_body(live)
    chart_prices = _coerce_float_list(ex.get("prices_today"))
    if not chart_prices:
        chart_prices = list(points)

    st = getattr(live, "state", None)
    body: dict[str, Any] = {
        "state": str(st) if st is not None and st != "" else (str(chart_prices[-1]) if chart_prices else ""),
        "prices_today": chart_prices,
        "history_hours": lookback_h,
        "chart_day": chart_day,
    }

    mask = _coerce_cheap_mask_today(ex.get("cheap_mask_today"))
    if mask is not None:
        body["cheap_mask_today"] = mask

    for key in _ENERGY_PRICE_HISTORY_ATTR_KEYS:
        if key not in ex:
            continue
        val = ex[key]
        if val is None:
            continue
        if key == "peak_range" and isinstance(val, (list, tuple)):
            pr = _coerce_float_list(val)
            if pr:
                body[key] = pr
            continue
        typed = _history_scalar_for_json(val)
        if typed is not None:
            body[key] = typed

    return body


# Cap concurrent MQTT publishes (state storm + history cycle).
_MQTT_PUBLISH_CONCURRENCY = 16


def _hourly_points_from_states(states: list[Any], end: datetime, num_hours: int) -> list[float]:
    """One value per hour (oldest to newest), buckets [end−Nh, end)."""
    if not states or num_hours < 1:
        return []

    end = dt_util.as_utc(end)
    sorted_states = sorted(states, key=lambda s: dt_util.as_utc(s.last_changed))

    bucket_vals: list[float | None] = []
    for i in range(num_hours):
        seg_start = end - timedelta(hours=num_hours - i)
        seg_end = end - timedelta(hours=num_hours - 1 - i)
        val_f: float | None = None
        for st in sorted_states:
            t = dt_util.as_utc(st.last_changed)
            if seg_start <= t < seg_end:
                parsed = history_state_float(st.state)
                if parsed is not None:
                    val_f = parsed
        bucket_vals.append(val_f)

    last: float | None = None
    for i in range(num_hours):
        if bucket_vals[i] is not None:
            last = bucket_vals[i]
        elif last is not None:
            bucket_vals[i] = last
    nxt: float | None = None
    for i in range(num_hours - 1, -1, -1):
        if bucket_vals[i] is not None:
            nxt = bucket_vals[i]
        elif nxt is not None:
            bucket_vals[i] = nxt

    if all(v is None for v in bucket_vals):
        return []
    if any(v is None for v in bucket_vals):
        return []
    return [float(v) for v in bucket_vals]


class TftDashboardCoordinator:
    def __init__(self, hass: HomeAssistant, entry: Any) -> None:
        self.hass = hass
        self._entry = entry
        self._unsub: list[Any] = []
        self._history_bootstrap_task: asyncio.Task | None = None
        self._history_task: asyncio.Task | None = None
        self._publication_prefix: str = ""
        self._map: dict[str, str] = {}
        self._role_map: dict[str, str] = {}
        self._history_map: dict[str, str] = {}
        self._history_hours: dict[str, int] = {}
        self._history_hourly: dict[str, bool] = {}
        self._mqtt_publish_sem = asyncio.Semaphore(_MQTT_PUBLISH_CONCURRENCY)

    def _max_history_slots(self) -> int:
        if self._entry.options.get(CONF_RELAXED_LIMITS, False):
            return MAX_HISTORY_SENSORS_EXPERT
        return MAX_HISTORY_SENSORS

    def _history_poll_interval_s(self) -> int:
        raw = self._entry.options.get(
            CONF_HISTORY_POLL_INTERVAL, DEFAULT_HISTORY_POLL_INTERVAL
        )
        try:
            v = int(raw)
        except (TypeError, ValueError):
            v = HISTORY_INTERVAL_S
        return max(30, min(7200, v))

    @property
    def prefix(self) -> str:
        return self._entry.data.get(CONF_MQTT_PREFIX, DEFAULT_MQTT_PREFIX)

    @property
    def retain(self) -> bool:
        return self._entry.data.get(CONF_RETAIN, DEFAULT_RETAIN)

    @property
    def publish_on_start(self) -> bool:
        return self._entry.data.get(CONF_PUBLISH_ON_START, DEFAULT_PUBLISH_ON_START)

    def _build_maps(self) -> None:
        self._map = {}
        self._role_map = {}
        self._history_map = {}
        self._history_hours = {}
        self._history_hourly = {}
        history_count = 0

        for subentry in self._entry.subentries.values():
            if subentry.subentry_type != SUBENTRY_TYPE_ENTITY:
                continue
            entity_id = subentry.data.get(CONF_ENTITY_ID)
            suffix = subentry.data.get(CONF_SUFFIX)
            if not entity_id or not suffix:
                continue

            self._map[entity_id] = suffix
            self._role_map[entity_id] = subentry.data.get(CONF_ENTITY_ROLE, "")

            use_recorder = subentry.data.get(
                CONF_HISTORY_FROM_RECORDER, DEFAULT_HISTORY_FROM_RECORDER
            )
            if subentry.data.get(CONF_HISTORY_ENABLED, False) and use_recorder:
                if history_count < self._max_history_slots():
                    self._history_map[entity_id] = suffix
                    hrs = int(subentry.data.get(CONF_HISTORY_HOURS, DEFAULT_HISTORY_HOURS))
                    self._history_hours[entity_id] = max(1, min(MAX_HISTORY_HOURS, hrs))
                    self._history_hourly[entity_id] = subentry.data.get(
                        CONF_HISTORY_HOURLY, DEFAULT_HISTORY_HOURLY
                    )
                    history_count += 1
                else:
                    _LOGGER.warning(
                        "History slot limit (%d) reached, skipping %s",
                        self._max_history_slots(),
                        entity_id,
                    )

        self._publication_prefix = self.prefix

        _LOGGER.debug(
            "Maps built: %d entities, %d with Recorder history",
            len(self._map),
            len(self._history_map),
        )

    async def async_start(self) -> None:
        self._build_maps()
        self._register_listeners()

        if self._history_map:

            async def _history_bootstrap() -> None:
                try:
                    await self._run_history_cycle()
                    self._history_task = self.hass.async_create_task(
                        self._history_loop(), eager_start=False
                    )

                    async def _history_retry_after_recorder() -> None:
                        await asyncio.sleep(25)
                        if self._history_map:
                            await self._run_history_cycle()

                    self.hass.async_create_task(
                        _history_retry_after_recorder(), eager_start=False
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    _LOGGER.exception("TFT Dashboard history bootstrap failed")

            @callback
            def _schedule_history_bootstrap(_event: Event | None = None) -> None:
                if self._history_bootstrap_task and not self._history_bootstrap_task.done():
                    return
                self._history_bootstrap_task = self.hass.async_create_task(
                    _history_bootstrap(), eager_start=False
                )

            if self.hass.state == CoreState.running:
                _schedule_history_bootstrap()
            else:
                rm = self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STARTED, _schedule_history_bootstrap
                )
                if rm is not None:
                    self._unsub.append(rm)

        if self.publish_on_start:
            await self._publish_all()

    async def async_stop(self) -> None:
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()

        if self._history_bootstrap_task and not self._history_bootstrap_task.done():
            self._history_bootstrap_task.cancel()
            try:
                await self._history_bootstrap_task
            except asyncio.CancelledError:
                pass
        self._history_bootstrap_task = None

        if self._history_task and not self._history_task.done():
            self._history_task.cancel()
            try:
                await self._history_task
            except asyncio.CancelledError:
                pass
        self._history_task = None

    async def async_reload(self) -> None:
        old_map = dict(self._map)
        old_prefix = self._publication_prefix
        await self.async_stop()
        self._build_maps()
        new_prefix = self.prefix

        if old_prefix and old_map:
            if old_prefix != new_prefix:
                to_clear = set(old_map.values())
            else:
                to_clear = set(old_map.values()) - set(self._map.values())
        else:
            to_clear = set()

        for suffix in to_clear:
            topic = f"{old_prefix}{suffix}"
            try:
                await mqtt.async_publish(self.hass, topic, "", retain=True, qos=0)
                _LOGGER.info("Cleared retained topic %s", topic)
            except (HomeAssistantError, OSError) as err:
                _LOGGER.error("Failed to clear topic %s: %s", topic, err)
            except Exception:
                _LOGGER.exception("Unexpected error clearing topic %s", topic)

        self._register_listeners()

        if self._history_map:
            await self._run_history_cycle()
            self._history_task = self.hass.async_create_task(
                self._history_loop(), eager_start=False
            )

    def _register_listeners(self) -> None:
        if not self._map:
            _LOGGER.debug("No entities to track")
            return
        unsub = async_track_state_change_event(
            self.hass, list(self._map.keys()), self._on_state_change
        )
        self._unsub.append(unsub)
        _LOGGER.info(
            "Tracking %d entities (%d with history), prefix '%s'",
            len(self._map),
            len(self._history_map),
            self.prefix,
        )

    @callback
    def _on_state_change(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        entity_id: str = event.data["entity_id"]
        role = self._role_map.get(entity_id, "")
        if role == ROLE_WEATHER:
            self.hass.async_create_task(self._publish_weather(entity_id, new_state))
        else:
            self.hass.async_create_task(self._publish(entity_id, new_state))

    async def _publish(self, entity_id: str, state: Any) -> None:
        suffix = self._map.get(entity_id)
        if not suffix or state is None or state.state in ("unknown", "unavailable"):
            return
        role = self._role_map.get(entity_id, "")
        retain_live = self.retain and entity_id not in self._history_map
        if role == ROLE_ENERGY_PRICE:
            payload = json.dumps(
                _energy_price_mqtt_body(state), default=str, separators=(",", ":")
            )
            await self._mqtt_publish(
                f"{self.prefix}{suffix}", payload, entity_id, retain=retain_live
            )
        else:
            await self._mqtt_publish(
                f"{self.prefix}{suffix}", state.state, entity_id, retain=retain_live
            )

    async def _publish_all(self) -> None:
        for entity_id in self._map:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            role = self._role_map.get(entity_id, "")
            if role == ROLE_WEATHER:
                await self._publish_weather(entity_id, state)
            else:
                await self._publish(entity_id, state)

    async def _publish_weather(self, entity_id: str, state: Any) -> None:
        suffix = self._map.get(entity_id)
        if not suffix or state is None or state.state in ("unknown", "unavailable"):
            return

        a = state.attributes
        data: dict[str, Any] = {
            "state": state.state,
            "temperature": a.get("temperature", 0),
            "humidity": a.get("humidity", 0),
            "wind_speed": a.get("wind_speed", 0),
            "wind_bearing": a.get("wind_bearing", 0),
            "pressure": a.get("pressure", 0),
        }

        try:
            async with asyncio.timeout(QUERY_TIMEOUT_S):
                result = await self.hass.services.async_call(
                    "weather",
                    "get_forecasts",
                    {"entity_id": entity_id, "type": "daily"},
                    blocking=True,
                    return_response=True,
                )
            forecasts = (result or {}).get(entity_id, {}).get("forecast", [])
        except TimeoutError:
            _LOGGER.warning("Weather forecast timeout: %s", entity_id)
            forecasts = a.get("forecast", [])
        except HomeAssistantError as err:
            _LOGGER.warning("Weather forecast service failed for %s: %s", entity_id, err)
            forecasts = a.get("forecast", [])
        except Exception:
            _LOGGER.exception("Unexpected error fetching weather forecast for %s", entity_id)
            forecasts = a.get("forecast", [])

        if forecasts:
            data["forecast"] = [
                {
                    "date": d.get("datetime", ""),
                    "condition": d.get("condition", "unknown"),
                    "templow": d.get("templow", 0),
                    "temperature": d.get("temperature", 0),
                    "precipitation_probability": d.get("precipitation_probability", 0),
                    "precipitation": d.get("precipitation", 0),
                    "wind_speed": d.get("wind_speed", 0),
                    "wind_bearing": d.get("wind_bearing", 0),
                }
                for d in forecasts[:5]
            ]

        # default=str: encje HA mogą zwracać nietypowe typy w atrybutach — nie blokujemy publikacji;
        # firmware ESP i tak parsuje liczby tolerancyjnie (patrz README integracji).
        await self._mqtt_publish(
            f"{self.prefix}{suffix}", json.dumps(data, default=str), entity_id
        )

    async def _history_loop(self) -> None:
        while True:
            await asyncio.sleep(self._history_poll_interval_s())
            await self._run_history_cycle()

    async def _run_history_cycle(self) -> None:
        if not self._history_map:
            return

        _LOGGER.debug("History cycle for %d entities", len(self._history_map))

        async def _one(entity_id: str, suffix: str) -> None:
            try:
                async with asyncio.timeout(QUERY_TIMEOUT_S):
                    await self._publish_history(entity_id, suffix)
            except asyncio.TimeoutError:
                _LOGGER.warning("History query timeout: %s", entity_id)
            except HomeAssistantError as err:
                _LOGGER.error("History error for %s: %s", entity_id, err)
            except Exception:
                _LOGGER.exception("Unexpected history error for %s", entity_id)

        await asyncio.gather(
            *(_one(eid, sfx) for eid, sfx in self._history_map.items()),
        )

    async def _publish_history(self, entity_id: str, suffix: str) -> None:
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.history import get_significant_states
        except ImportError:
            _LOGGER.warning("Recorder not available for %s", entity_id)
            return

        try:
            from homeassistant.components.recorder import is_entity_recorded

            if not is_entity_recorded(self.hass, entity_id):
                _LOGGER.warning("%s is not recorded by Recorder", entity_id)
                return
        except ImportError:
            pass

        end = datetime.now(timezone.utc)
        lookback_h = self._history_hours.get(entity_id, HISTORY_LOOKBACK_H)
        hourly = self._history_hourly.get(entity_id, False)
        start = end - timedelta(hours=lookback_h)

        instance = get_instance(self.hass)

        states = await instance.async_add_executor_job(
            get_significant_states,
            self.hass,
            start,
            end,
            [entity_id],
            None,
            False,
        )

        raw_list = states.get(entity_id, [])
        if len(raw_list) > HISTORY_MAX_RAW_STATES:
            step = len(raw_list) / HISTORY_MAX_RAW_STATES
            raw_list = [raw_list[int(i * step)] for i in range(HISTORY_MAX_RAW_STATES)]

        if hourly:
            points = _hourly_points_from_states(raw_list, end, lookback_h)
        else:
            points = []
            for state in raw_list:
                v = history_state_float(state.state)
                if v is not None:
                    points.append(v)

        if not points:
            live_fallback = self.hass.states.get(entity_id)
            v = history_state_float(live_fallback.state if live_fallback else None)
            if v is not None:
                points = [v]
                _LOGGER.debug(
                    "No numeric history for %s; publishing live state as single point",
                    entity_id,
                )

        if not points:
            _LOGGER.warning(
                "No chart data for %s (check Recorder and entity state format)",
                entity_id,
            )
            return

        if not hourly and len(points) > HISTORY_POINTS:
            step = len(points) / HISTORY_POINTS
            points = [points[int(i * step)] for i in range(HISTORY_POINTS)]

        live = self.hass.states.get(entity_id)
        state_str = live.state if live else str(points[-1])

        role = self._role_map.get(entity_id, "")
        chart_day = dt_util.now().date().isoformat()

        if role == ROLE_ENERGY_PRICE:
            # Jedna tablica na wykres (prices_today); bez prices_tomorrow / cheap_mask_tomorrow;
            # liczby jako JSON numbers — mniejszy payload niż default=str na całym dict.
            if live:
                body = _energy_price_history_mqtt_body(live, points, lookback_h, chart_day)
            else:
                body = {
                    "state": state_str,
                    "prices_today": list(points),
                    "history_hours": lookback_h,
                    "chart_day": chart_day,
                }
            payload = json.dumps(body, separators=(",", ":"))
        else:
            body = {
                "state": state_str,
                "values": points,
                "history_hours": lookback_h,
                "chart_day": chart_day,
            }
            payload = json.dumps(body, default=str)

        await self._mqtt_publish(
            f"{self.prefix}{suffix}", payload, entity_id, retain=True
        )

    async def _mqtt_publish(
        self, topic: str, payload: str, entity_id: str, retain: bool | None = None
    ) -> None:
        plen = payload_utf8_byte_length(payload)
        if plen > _MAX_PAYLOAD_BYTES:
            _LOGGER.warning(
                "MQTT payload too large (%d bytes) for %s, not publishing",
                plen,
                entity_id,
            )
            return

        use_retain = self.retain if retain is None else retain
        try:
            async with self._mqtt_publish_sem:
                await mqtt.async_publish(
                    self.hass, topic, payload, retain=use_retain, qos=0
                )
            _LOGGER.debug("%s → %s (%d bytes)", entity_id, topic, plen)
        except (HomeAssistantError, OSError) as err:
            _LOGGER.error("MQTT publish failed %s: %s", topic, err)
        except Exception:
            _LOGGER.exception("Unexpected error during MQTT publish to %s", topic)
