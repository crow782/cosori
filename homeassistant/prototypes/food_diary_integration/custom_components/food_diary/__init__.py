"""Experimental Home Assistant Food Diary integration.

This component is intentionally kept under prototypes/ and is not installable
from this location. Copying it into custom_components is not part of this phase.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import async_setup_services
from .storage import FoodDiaryStore

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register actions independently of config-entry load state."""
    hass.data.setdefault(DOMAIN, {})
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialize the SQLite store inside the Home Assistant config directory."""
    database_path = hass.config.path("food_diary", "food_diary.db")
    store = await hass.async_add_executor_job(FoodDiaryStore, database_path)
    hass.data.setdefault(DOMAIN, {})["store"] = store
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Release the active store reference."""
    domain_data = hass.data.get(DOMAIN, {})
    domain_data.pop("store", None)
    return True
