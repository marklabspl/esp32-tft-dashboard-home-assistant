"""Config flow: MQTT prefix, per-entity subentries, integration options."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

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
    DOMAIN,
    MAX_ENTITIES,
    MAX_ENTITIES_EXPERT,
    MAX_HISTORY_HOURS,
    MAX_HISTORY_SENSORS,
    MAX_HISTORY_SENSORS_EXPERT,
    ROLE_BINARY,
    ROLE_CHART_BAR,
    ROLE_CHART_LINE,
    ROLE_CUSTOM,
    ROLE_ENERGY_PRICE,
    ROLE_GAUGE,
    ROLE_HISTORY_CAPABLE,
    ROLE_POWERFLOW_BAT,
    ROLE_POWERFLOW_GRID,
    ROLE_POWERFLOW_LOAD,
    ROLE_POWERFLOW_PV,
    ROLE_SENSOR,
    ROLE_SUFFIX_DEFAULTS,
    ROLE_WEATHER,
    SUBENTRY_TYPE_ENTITY,
)
from .entity_validation import (
    mqtt_prefix_error,
    validate_recorder_history_entity,
    validate_role_entity,
)
from .user_hints import esp32_panel_hint

_SUFFIX_RE = re.compile(r"^[a-zA-Z0-9_\-/]+$")

_ALL_ROLES = [
    ROLE_SENSOR,
    ROLE_GAUGE,
    ROLE_CHART_LINE,
    ROLE_CHART_BAR,
    ROLE_BINARY,
    ROLE_POWERFLOW_PV,
    ROLE_POWERFLOW_LOAD,
    ROLE_POWERFLOW_GRID,
    ROLE_POWERFLOW_BAT,
    ROLE_WEATHER,
    ROLE_ENERGY_PRICE,
    ROLE_CUSTOM,
]


def _default_suffix(entity_id: str) -> str:
    return entity_id.split(".", 1)[1] if "." in entity_id else entity_id


def _suffix_for_role(role: str, entity_id: str) -> str:
    fixed = ROLE_SUFFIX_DEFAULTS.get(role)
    return fixed if fixed else _default_suffix(entity_id)


def _count_entities(entry: ConfigEntry) -> int:
    return sum(
        1
        for se in entry.subentries.values()
        if se.subentry_type == SUBENTRY_TYPE_ENTITY
    )


def _max_entities(entry: ConfigEntry) -> int:
    if entry.options.get(CONF_RELAXED_LIMITS, False):
        return MAX_ENTITIES_EXPERT
    return MAX_ENTITIES


def _max_history_sensors(entry: ConfigEntry) -> int:
    if entry.options.get(CONF_RELAXED_LIMITS, False):
        return MAX_HISTORY_SENSORS_EXPERT
    return MAX_HISTORY_SENSORS


def _count_history(entry: ConfigEntry, exclude_id: str | None = None) -> int:
    return sum(
        1
        for sid, se in entry.subentries.items()
        if sid != exclude_id
        and se.data.get(CONF_HISTORY_ENABLED, False)
        and se.data.get(CONF_HISTORY_FROM_RECORDER, DEFAULT_HISTORY_FROM_RECORDER)
    )


def _validate_suffix(suffix: str) -> str | None:
    if not suffix:
        return "suffix_empty"
    if not _SUFFIX_RE.match(suffix):
        return "suffix_invalid_chars"
    if len(suffix) > 64:
        return "suffix_too_long"
    return None


def _coerce_history_hours_value(raw: Any) -> tuple[int | None, str | None]:
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return None, "history_hours_invalid"
    return max(1, min(MAX_HISTORY_HOURS, v)), None


def _stored_history_hours(data: dict[str, Any]) -> int:
    v, _ = _coerce_history_hours_value(
        data.get(CONF_HISTORY_HOURS, DEFAULT_HISTORY_HOURS)
    )
    return v if v is not None else DEFAULT_HISTORY_HOURS


_HISTORY_POLL_INTERVAL_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[
            {"value": "60", "label": "60 s (1 min)"},
            {"value": "120", "label": "120 s (2 min)"},
            {"value": "180", "label": "180 s (3 min)"},
            {"value": "300", "label": "300 s (5 min)"},
            {"value": "600", "label": "600 s (10 min)"},
        ],
        mode=SelectSelectorMode.DROPDOWN,
    ),
)


def _poll_interval_str(entry: ConfigEntry) -> str:
    raw = entry.options.get(CONF_HISTORY_POLL_INTERVAL, DEFAULT_HISTORY_POLL_INTERVAL)
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = DEFAULT_HISTORY_POLL_INTERVAL
    allowed = (60, 120, 180, 300, 600)
    v = max(30, min(7200, v))
    if v not in allowed:
        v = min(allowed, key=lambda x: abs(x - v))
    return str(v)


def _parse_poll_interval(user_input: dict[str, Any]) -> int:
    raw = user_input[CONF_HISTORY_POLL_INTERVAL]
    try:
        v = int(raw) if not isinstance(raw, int) else raw
    except (TypeError, ValueError):
        v = DEFAULT_HISTORY_POLL_INTERVAL
    return max(30, min(7200, v))


class TftDashboardConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry: ConfigEntry) -> OptionsFlow:
        return TftDashboardOptionsFlow()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                entry,
                options={
                    **entry.options,
                    CONF_RELAXED_LIMITS: user_input[CONF_RELAXED_LIMITS],
                    CONF_HISTORY_POLL_INTERVAL: _parse_poll_interval(user_input),
                },
            )
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_RELAXED_LIMITS,
                        default=entry.options.get(CONF_RELAXED_LIMITS, False),
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_HISTORY_POLL_INTERVAL,
                        default=_poll_interval_str(entry),
                    ): _HISTORY_POLL_INTERVAL_SELECTOR,
                }
            ),
            description_placeholders={
                "prefix": entry.data.get(CONF_MQTT_PREFIX, ""),
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if MQTT_DOMAIN not in self.hass.config.components:
            return self.async_abort(reason="mqtt_not_configured")

        if user_input is not None:
            prefix = user_input[CONF_MQTT_PREFIX].strip()
            if not prefix.endswith("/"):
                prefix += "/"

            perr = mqtt_prefix_error(prefix)
            if perr:
                errors[CONF_MQTT_PREFIX] = perr

            if not errors:
                return self.async_create_entry(
                    title=f"TFT Dashboard ({prefix})",
                    data={
                        CONF_MQTT_PREFIX: prefix,
                        CONF_RETAIN: user_input[CONF_RETAIN],
                        CONF_PUBLISH_ON_START: user_input[CONF_PUBLISH_ON_START],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MQTT_PREFIX, default=DEFAULT_MQTT_PREFIX
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                    vol.Required(CONF_RETAIN, default=DEFAULT_RETAIN): BooleanSelector(),
                    vol.Required(
                        CONF_PUBLISH_ON_START, default=DEFAULT_PUBLISH_ON_START
                    ): BooleanSelector(),
                }
            ),
            errors=errors,
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_TYPE_ENTITY: TftEntitySubentryFlow}


class TftDashboardOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_RELAXED_LIMITS: user_input[CONF_RELAXED_LIMITS],
                    CONF_HISTORY_POLL_INTERVAL: _parse_poll_interval(user_input),
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_RELAXED_LIMITS): BooleanSelector(),
                vol.Required(CONF_HISTORY_POLL_INTERVAL): _HISTORY_POLL_INTERVAL_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {
                    CONF_RELAXED_LIMITS: self.config_entry.options.get(
                        CONF_RELAXED_LIMITS, False
                    ),
                    CONF_HISTORY_POLL_INTERVAL: _poll_interval_str(self.config_entry),
                },
            ),
        )


class TftEntitySubentryFlow(ConfigSubentryFlow):
    def __init__(self) -> None:
        self._entity_id: str = ""
        self._role: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_entry()

        if user_input is not None:
            if _count_entities(entry) >= _max_entities(entry):
                return self.async_abort(reason="entity_limit_reached")

            entity_id = user_input[CONF_ENTITY_ID]

            if not self.hass.states.get(entity_id):
                errors[CONF_ENTITY_ID] = "entity_not_found"
            else:
                used_ids = {
                    se.data.get(CONF_ENTITY_ID)
                    for se in entry.subentries.values()
                    if se.subentry_type == SUBENTRY_TYPE_ENTITY
                    and se.data.get(CONF_ENTITY_ID)
                }
                if entity_id in used_ids:
                    return self.async_abort(reason="already_configured")

            if not errors:
                self._entity_id = entity_id
                return await self.async_step_role()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(multiple=False)
                    ),
                }
            ),
            description_placeholders={
                "entity_count": str(_count_entities(entry)),
                "entity_max": str(_max_entities(entry)),
            },
            errors=errors,
        )

    async def async_step_role(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._role = user_input[CONF_ENTITY_ROLE]
            role_err = validate_role_entity(self.hass, self._entity_id, self._role)
            if role_err:
                errors[CONF_ENTITY_ROLE] = role_err
            else:
                return await self.async_step_suffix()

        domain = self._entity_id.split(".")[0]
        default_role = {
            "binary_sensor": ROLE_BINARY,
            "input_boolean": ROLE_BINARY,
            "weather": ROLE_WEATHER,
            "sensor": ROLE_SENSOR,
            "input_number": ROLE_SENSOR,
            "number": ROLE_SENSOR,
        }.get(domain, ROLE_SENSOR)
        role_field_default = (
            user_input[CONF_ENTITY_ROLE]
            if user_input is not None and CONF_ENTITY_ROLE in user_input
            else default_role
        )

        return self.async_show_form(
            step_id="role",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENTITY_ROLE, default=role_field_default
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_ALL_ROLES,
                            mode=SelectSelectorMode.LIST,
                            translation_key="entity_role",
                        )
                    ),
                }
            ),
            description_placeholders={
                "entity_id": self._entity_id,
            },
            errors=errors,
        )

    async def async_step_suffix(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_entry()
        prefix = entry.data.get(CONF_MQTT_PREFIX, DEFAULT_MQTT_PREFIX)
        history_capable = self._role in ROLE_HISTORY_CAPABLE

        if user_input is not None:
            suffix = user_input[CONF_SUFFIX].strip().strip("/")
            history = (
                user_input.get(CONF_HISTORY_ENABLED, False) if history_capable else False
            )
            from_recorder = (
                user_input.get(CONF_HISTORY_FROM_RECORDER, DEFAULT_HISTORY_FROM_RECORDER)
                if history_capable
                else DEFAULT_HISTORY_FROM_RECORDER
            )
            hourly = (
                user_input.get(CONF_HISTORY_HOURLY, DEFAULT_HISTORY_HOURLY)
                if history_capable
                else DEFAULT_HISTORY_HOURLY
            )

            hours: int = DEFAULT_HISTORY_HOURS
            if history_capable:
                hv, herr = _coerce_history_hours_value(
                    user_input.get(CONF_HISTORY_HOURS, DEFAULT_HISTORY_HOURS)
                )
                if herr:
                    errors[CONF_HISTORY_HOURS] = herr
                elif hv is not None:
                    hours = hv

            err = _validate_suffix(suffix)
            if err:
                errors[CONF_SUFFIX] = err
            else:
                used = {
                    se.data[CONF_SUFFIX]
                    for se in entry.subentries.values()
                    if CONF_SUFFIX in se.data
                }
                if suffix in used:
                    errors[CONF_SUFFIX] = "suffix_duplicate"

            if history and from_recorder and not errors:
                hist_err = validate_recorder_history_entity(
                    self.hass, self._entity_id
                )
                if hist_err:
                    errors[CONF_HISTORY_ENABLED] = hist_err
                elif _count_history(entry) >= _max_history_sensors(entry):
                    errors[CONF_HISTORY_ENABLED] = "history_limit_reached"

            if not errors:
                data: dict[str, Any] = {
                    CONF_ENTITY_ID: self._entity_id,
                    CONF_SUFFIX: suffix,
                    CONF_ENTITY_ROLE: self._role,
                    CONF_HISTORY_ENABLED: history if history_capable else False,
                    CONF_HISTORY_FROM_RECORDER: (
                        from_recorder if history_capable else DEFAULT_HISTORY_FROM_RECORDER
                    ),
                    CONF_HISTORY_HOURS: (
                        hours if history_capable else DEFAULT_HISTORY_HOURS
                    ),
                    CONF_HISTORY_HOURLY: (
                        hourly if history_capable else DEFAULT_HISTORY_HOURLY
                    ),
                }
                return self.async_create_entry(title=suffix, data=data)

        default_suffix = _suffix_for_role(self._role, self._entity_id)
        topic_preview = f"{prefix}{default_suffix}"
        esp32_hint = esp32_panel_hint(self.hass, self._role, topic_preview)
        history_count = _count_history(entry)

        schema: dict[Any, Any] = {
            vol.Required(CONF_SUFFIX, default=default_suffix): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
        }
        if history_capable:
            history_default = self._role == ROLE_ENERGY_PRICE
            schema[vol.Required(CONF_HISTORY_ENABLED, default=history_default)] = (
                BooleanSelector()
            )
            schema[
                vol.Required(
                    CONF_HISTORY_FROM_RECORDER, default=DEFAULT_HISTORY_FROM_RECORDER
                )
            ] = BooleanSelector()
            schema[vol.Required(CONF_HISTORY_HOURS, default=DEFAULT_HISTORY_HOURS)] = (
                NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=MAX_HISTORY_HOURS,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="h",
                    )
                )
            )
            schema[
                vol.Required(CONF_HISTORY_HOURLY, default=DEFAULT_HISTORY_HOURLY)
            ] = BooleanSelector()

        return self.async_show_form(
            step_id="suffix",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "entity_id": self._entity_id,
                "role": self._role,
                "topic_preview": topic_preview,
                "esp32_hint": esp32_hint,
                "history_count": str(history_count),
                "history_max": str(_max_history_sensors(entry)),
            },
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        subentry = self._get_reconfigure_subentry()
        entry = self._get_entry()
        prefix = entry.data.get(CONF_MQTT_PREFIX, DEFAULT_MQTT_PREFIX)

        current_suffix = subentry.data.get(CONF_SUFFIX, "")
        current_history = subentry.data.get(CONF_HISTORY_ENABLED, False)
        current_from_rec = subentry.data.get(
            CONF_HISTORY_FROM_RECORDER, DEFAULT_HISTORY_FROM_RECORDER
        )
        current_hours = _stored_history_hours(subentry.data)
        current_hourly = subentry.data.get(CONF_HISTORY_HOURLY, DEFAULT_HISTORY_HOURLY)
        current_role = subentry.data.get(CONF_ENTITY_ROLE, ROLE_CUSTOM)
        self._entity_id = subentry.data.get(CONF_ENTITY_ID, "")
        history_capable = current_role in ROLE_HISTORY_CAPABLE

        if user_input is not None:
            suffix = user_input[CONF_SUFFIX].strip().strip("/")
            history = (
                user_input.get(CONF_HISTORY_ENABLED, False) if history_capable else False
            )
            from_recorder = (
                user_input.get(CONF_HISTORY_FROM_RECORDER, DEFAULT_HISTORY_FROM_RECORDER)
                if history_capable
                else DEFAULT_HISTORY_FROM_RECORDER
            )
            hourly = (
                user_input.get(CONF_HISTORY_HOURLY, DEFAULT_HISTORY_HOURLY)
                if history_capable
                else DEFAULT_HISTORY_HOURLY
            )

            hours: int = current_hours
            if history_capable:
                hv, herr = _coerce_history_hours_value(
                    user_input.get(CONF_HISTORY_HOURS, current_hours)
                )
                if herr:
                    errors[CONF_HISTORY_HOURS] = herr
                elif hv is not None:
                    hours = hv

            err = _validate_suffix(suffix)
            if err:
                errors[CONF_SUFFIX] = err
            else:
                used = {
                    se.data[CONF_SUFFIX]
                    for sid, se in entry.subentries.items()
                    if CONF_SUFFIX in se.data and sid != subentry.subentry_id
                }
                if suffix in used:
                    errors[CONF_SUFFIX] = "suffix_duplicate"

            was_recorder = current_history and current_from_rec
            will_recorder = history and from_recorder

            if will_recorder and not errors:
                hist_err = validate_recorder_history_entity(
                    self.hass, self._entity_id
                )
                if hist_err:
                    errors[CONF_HISTORY_ENABLED] = hist_err

            if will_recorder and not was_recorder and not errors:
                if (
                    _count_history(entry, exclude_id=subentry.subentry_id)
                    >= _max_history_sensors(entry)
                ):
                    errors[CONF_HISTORY_ENABLED] = "history_limit_reached"

            if not errors:
                data = {
                    CONF_ENTITY_ID: self._entity_id,
                    CONF_SUFFIX: suffix,
                    CONF_ENTITY_ROLE: current_role,
                    CONF_HISTORY_ENABLED: history if history_capable else False,
                    CONF_HISTORY_FROM_RECORDER: (
                        from_recorder if history_capable else current_from_rec
                    ),
                    CONF_HISTORY_HOURS: hours if history_capable else current_hours,
                    CONF_HISTORY_HOURLY: hourly if history_capable else current_hourly,
                }
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=suffix,
                    data=data,
                )

        topic_preview = f"{prefix}{current_suffix}"
        esp32_hint = esp32_panel_hint(self.hass, current_role, topic_preview)
        history_count = _count_history(entry, exclude_id=subentry.subentry_id)

        schema: dict[Any, Any] = {
            vol.Required(CONF_SUFFIX, default=current_suffix): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
        }
        if history_capable:
            schema[vol.Required(CONF_HISTORY_ENABLED, default=current_history)] = (
                BooleanSelector()
            )
            schema[
                vol.Required(CONF_HISTORY_FROM_RECORDER, default=current_from_rec)
            ] = BooleanSelector()
            schema[vol.Required(CONF_HISTORY_HOURS, default=current_hours)] = (
                NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=MAX_HISTORY_HOURS,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="h",
                    )
                )
            )
            schema[vol.Required(CONF_HISTORY_HOURLY, default=current_hourly)] = (
                BooleanSelector()
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "entity_id": self._entity_id,
                "role": current_role,
                "topic_preview": topic_preview,
                "esp32_hint": esp32_hint,
                "history_count": str(history_count),
                "history_max": str(_max_history_sensors(entry)),
            },
            errors=errors,
        )
