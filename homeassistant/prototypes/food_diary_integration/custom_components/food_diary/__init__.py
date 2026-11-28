"""Home Assistant integration for the local Food Diary."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import async_setup_services, async_unload_services
from .storage import FoodDiaryStore

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Prepare integration domain data."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialize the database and register Food Diary actions."""
    database_path = hass.config.path("food_diary", "food_diary.db")
    store = await hass.async_add_executor_job(FoodDiaryStore, database_path)
    hass.data.setdefault(DOMAIN, {})["store"] = store
    async_setup_services(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unregister actions and release the store reference."""
    async_unload_services(hass)
    hass.data.get(DOMAIN, {}).pop("store", None)
    return True
