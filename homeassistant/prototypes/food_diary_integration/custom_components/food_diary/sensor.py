"""Diagnostic sensors for Food Diary acquisition."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry



DESCRIPTIONS = (
    SensorEntityDescription(
        key="status",
        name="Food Diary Status",
        icon="mdi:information-outline",
    ),
    SensorEntityDescription(
        key="last_barcode",
        name="Food Diary Last Barcode",
        icon="mdi:barcode",
    ),
    SensorEntityDescription(
        key="last_weight",
        name="Food Diary Last Stable Weight",
        icon="mdi:scale",
        native_unit_of_measurement="g",
    ),
    SensorEntityDescription(
        key="scan_count",
        name="Food Diary Scan Count",
        icon="mdi:counter",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities(
        FoodDiaryDiagnosticSensor(coordinator, description)
        for description in DESCRIPTIONS
    )


class FoodDiaryDiagnosticSensor(SensorEntity):
    """Expose lightweight acquisition status and last-seen values."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator, description: SensorEntityDescription) -> None:
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"food_diary_{description.key}"

    @property
    def native_value(self):
        if self.entity_description.key == "status":
            return self.coordinator.state
        if self.entity_description.key == "last_barcode":
            return self.coordinator.last_barcode
        if self.entity_description.key == "last_weight":
            return self.coordinator.last_weight_g
        if self.entity_description.key == "scan_count":
            return self.coordinator.last_scan_count
        return None

    @property
    def extra_state_attributes(self):
        return self.coordinator.attributes

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_update))

    def _handle_update(self) -> None:
        self.async_write_ha_state()
