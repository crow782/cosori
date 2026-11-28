"""Config and options flows for Food Diary."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    BooleanSelector,
    DeviceSelector,
    DeviceSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
)

from .const import (
    CONF_AUTO_SAVE,
    CONF_DEFAULT_MEAL,
    CONF_OFF_COUNTRY,
    CONF_OFF_ENABLED,
    CONF_OFF_LANGUAGE,
    CONF_SCANNER_DEVICE,
    CONF_WEIGHT_ENTITY,
    CONF_WEIGHT_TIMEOUT,
    CONF_ZERO_THRESHOLD,
    DEFAULT_OPTIONS,
    DOMAIN,
    MEALS,
)


def _device_schema() -> vol.Schema:
    """Return selectors for the two required ESPHome devices."""
    return vol.Schema(
        {
            vol.Required(CONF_WEIGHT_ENTITY): EntitySelector(
                EntitySelectorConfig(
                    domain="sensor",
                    device_class=SensorDeviceClass.WEIGHT,
                    integration="esphome",
                )
            ),
            vol.Required(CONF_SCANNER_DEVICE): DeviceSelector(
                DeviceSelectorConfig(integration="esphome")
            ),
        }
    )


def _options_schema() -> vol.Schema:
    """Return runtime options, including the replaceable device selections."""
    schema: dict[vol.Marker, Any] = {
        vol.Required(CONF_WEIGHT_ENTITY): EntitySelector(
            EntitySelectorConfig(
                domain="sensor",
                device_class=SensorDeviceClass.WEIGHT,
                integration="esphome",
            )
        ),
        vol.Required(CONF_SCANNER_DEVICE): DeviceSelector(
            DeviceSelectorConfig(integration="esphome")
        ),
        vol.Required(CONF_DEFAULT_MEAL): vol.In(MEALS),
        vol.Required(CONF_AUTO_SAVE): BooleanSelector(),
        vol.Required(CONF_WEIGHT_TIMEOUT): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=600)
        ),
        vol.Required(CONF_ZERO_THRESHOLD): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=20)
        ),
        vol.Required(CONF_OFF_ENABLED): BooleanSelector(),
        vol.Required(CONF_OFF_COUNTRY): vol.All(
            str, vol.Length(min=2, max=2)
        ),
        vol.Required(CONF_OFF_LANGUAGE): vol.All(
            str, vol.Length(min=2, max=5)
        ),
    }
    return vol.Schema(schema)


async def _validate_device_selection(
    hass, weight_entity: str, scanner_device_id: str
) -> str | None:
    """Validate selections against registries; selectors are not a security boundary."""
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(weight_entity)
    if (
        entity is None
        or not entity.entity_id.startswith("sensor.")
        or entity.platform != "esphome"
    ):
        return "invalid_weight_entity"

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(scanner_device_id)
    if device is None:
        return "invalid_scanner_device"

    scanner_is_esphome = any(
        (entry := hass.config_entries.async_get_entry(config_entry_id)) is not None
        and entry.domain == "esphome"
        for config_entry_id in device.config_entries
    )
    if not scanner_is_esphome:
        return "invalid_scanner_device"

    return None


class FoodDiaryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up one local Food Diary instance."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select the ESPHome weight sensor and barcode scanner."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors: dict[str, str] = {}
        if user_input is not None:
            error = await _validate_device_selection(
                self.hass,
                user_input[CONF_WEIGHT_ENTITY],
                user_input[CONF_SCANNER_DEVICE],
            )
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Food Diary",
                    data=user_input,
                    options=dict(DEFAULT_OPTIONS),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_device_schema(),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return FoodDiaryOptionsFlow()


class FoodDiaryOptionsFlow(OptionsFlow):
    """Allow changing devices and acquisition preferences after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Validate and save the complete set of options."""
        current = {
            **DEFAULT_OPTIONS,
            **self.config_entry.data,
            **self.config_entry.options,
        }
        errors: dict[str, str] = {}

        if user_input is not None:
            error = await _validate_device_selection(
                self.hass,
                user_input[CONF_WEIGHT_ENTITY],
                user_input[CONF_SCANNER_DEVICE],
            )
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _options_schema(), current
            ),
            errors=errors,
        )
