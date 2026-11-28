"""Home Assistant integration for the local Food Diary."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import FoodDiaryCoordinator
from .services import async_setup_services, async_unload_services
from .storage import FoodDiaryStore

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Prepare integration domain data."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialize the database and register Food Diary actions."""
    database_path = hass.config.path("food_diary", "food_diary.db")
    store = await hass.async_add_executor_job(FoodDiaryStore, database_path)
    domain_data = hass.data.setdefault(DOMAIN, {})
    config = {**entry.data, **entry.options}
    coordinator = FoodDiaryCoordinator(hass, config, store)
    domain_data["store"] = store
    domain_data["config"] = config
    domain_data["coordinator"] = coordinator
    await coordinator.async_start()
    async_setup_services(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unregister actions and release the store reference."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False
    domain_data = hass.data.get(DOMAIN, {})
    coordinator = domain_data.get("coordinator")
    if coordinator is not None:
        await coordinator.async_stop()
    async_unload_services(hass)
    domain_data.pop("coordinator", None)
    domain_data.pop("store", None)
    domain_data.pop("config", None)
    return True
