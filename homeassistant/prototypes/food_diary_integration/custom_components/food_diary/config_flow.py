"""Config and options flows for Food Diary."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import BooleanSelector, EntitySelector, EntitySelectorConfig

from .const import (
    CONF_AUTO_SAVE, CONF_BARCODE_ENTITY, CONF_SCAN_COUNT_ENTITY, CONF_DEFAULT_MEAL, CONF_OFF_COUNTRY,
    CONF_OFF_ENABLED, CONF_OFF_LANGUAGE, CONF_WEIGHT_ENTITY, CONF_WEIGHT_TIMEOUT,
    CONF_ZERO_THRESHOLD, DEFAULT_OPTIONS, DOMAIN, MEALS,
)


def _device_schema() -> vol.Schema:
    """Return selectors for the scale, barcode and scan counter entities."""
    return vol.Schema({
        vol.Required(CONF_WEIGHT_ENTITY): EntitySelector(EntitySelectorConfig(
            domain="sensor", device_class="weight", integration="esphome"
        )),
        vol.Required(CONF_BARCODE_ENTITY): EntitySelector(
            EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_SCAN_COUNT_ENTITY): EntitySelector(
            EntitySelectorConfig(domain="sensor")
        ),
    })


def _options_schema() -> vol.Schema:
    """Return runtime options, including replaceable entity selections."""
    schema: dict[vol.Marker, Any] = {
        vol.Required(CONF_WEIGHT_ENTITY): EntitySelector(EntitySelectorConfig(
            domain="sensor", device_class="weight", integration="esphome"
        )),
        vol.Required(CONF_BARCODE_ENTITY): EntitySelector(
            EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_SCAN_COUNT_ENTITY): EntitySelector(
            EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_DEFAULT_MEAL): vol.In(MEALS),
        vol.Required(CONF_AUTO_SAVE): BooleanSelector(),
        vol.Required(CONF_WEIGHT_TIMEOUT): vol.All(vol.Coerce(int), vol.Range(min=10, max=600)),
        vol.Required(CONF_ZERO_THRESHOLD): vol.All(vol.Coerce(float), vol.Range(min=0, max=20)),
        vol.Required(CONF_OFF_ENABLED): BooleanSelector(),
        vol.Required(CONF_OFF_COUNTRY): vol.All(str, vol.Length(min=2, max=2)),
        vol.Required(CONF_OFF_LANGUAGE): vol.All(str, vol.Length(min=2, max=5)),
    }
    return vol.Schema(schema)


async def _validate_entity_selection(
    hass, weight_entity: str, barcode_entity: str, scan_count_entity: str
) -> str | None:
    """Validate selected entities against the entity registry."""
    entity_registry = er.async_get(hass)
    weight = entity_registry.async_get(weight_entity)
    if weight is None or not weight.entity_id.startswith("sensor.") or weight.platform != "esphome":
        return "invalid_weight_entity"
    barcode = entity_registry.async_get(barcode_entity)
    if barcode is None or not barcode.entity_id.startswith("sensor."):
        return "invalid_barcode_entity"
    scan_count = entity_registry.async_get(scan_count_entity)
    if scan_count is None or not scan_count.entity_id.startswith("sensor."):
        return "invalid_scan_count_entity"
    if len({weight_entity, barcode_entity, scan_count_entity}) != 3:
        return "duplicate_entities"
    return None


class FoodDiaryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up one local Food Diary instance."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Select the ESPHome weight sensor and barcode sensor entity."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await _validate_entity_selection(
                self.hass, user_input[CONF_WEIGHT_ENTITY],
                user_input[CONF_BARCODE_ENTITY], user_input[CONF_SCAN_COUNT_ENTITY]
            )
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Food Diary", data=user_input, options=dict(DEFAULT_OPTIONS))
        return self.async_show_form(step_id="user", data_schema=_device_schema(), errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return FoodDiaryOptionsFlow()


class FoodDiaryOptionsFlow(OptionsFlow):
    """Allow changing entities and acquisition preferences after setup."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Validate and save the complete set of options."""
        current = {**DEFAULT_OPTIONS, **self.config_entry.data, **self.config_entry.options}
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await _validate_entity_selection(
                self.hass, user_input[CONF_WEIGHT_ENTITY],
                user_input[CONF_BARCODE_ENTITY], user_input[CONF_SCAN_COUNT_ENTITY]
            )
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=self.add_suggested_values_to_schema(_options_schema(), current), errors=errors)
