"""Home Assistant actions exposed by the experimental Food Diary integration."""
from __future__ import annotations

import asyncio
from functools import partial
import sqlite3
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

MEALS = ("breakfast", "lunch", "dinner", "snack")
FOOD_SOURCES = ("manual", "openfoodfacts")
ENTRY_SOURCES = ("scan", "catalog", "manual")
PERIODS = ("day", "week", "month")


def _store(hass: HomeAssistant):
    store = hass.data.get(DOMAIN, {}).get("store")
    if store is None:
        raise ServiceValidationError(
            "Food Diary is not configured or its config entry is not loaded"
        )
    return store


async def _run(hass: HomeAssistant, func, *args, **kwargs):
    """Run synchronous SQLite work outside the event loop and normalize user errors."""
    try:
        return await hass.async_add_executor_job(partial(func, *args, **kwargs))
    except (ValueError, KeyError, sqlite3.IntegrityError) as err:
        raise ServiceValidationError(str(err)) from err


def async_setup_services(hass: HomeAssistant) -> None:
    """Register all Food Diary actions."""

    async def add_food(call: ServiceCall):
        store = _store(hass)
        food = await _run(
            hass,
            store.add_food,
            call.data["name"],
            brand=call.data.get("brand"),
            barcode=call.data.get("barcode"),
            nutrients_per_100g=call.data.get("nutrients_per_100g"),
            source=call.data.get("source", "manual"),
        )
        coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
        if coordinator is not None and food.get("barcode"):
            await coordinator.async_catalog_changed(food["barcode"])
        return food if call.return_response else None

    async def update_food(call: ServiceCall):
        store = _store(hass)
        changes = {
            key: call.data[key]
            for key in ("name", "brand", "barcode", "nutrients_per_100g", "source")
            if key in call.data
        }
        food = await _run(hass, store.update_food, call.data["food_id"], **changes)
        coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
        if coordinator is not None and food.get("barcode"):
            await coordinator.async_catalog_changed(food["barcode"])
        return food if call.return_response else None

    async def delete_food(call: ServiceCall):
        await _run(hass, _store(hass).delete_food, call.data["food_id"])

    async def search_foods(call: ServiceCall):
        return {
            "foods": await _run(
                hass,
                _store(hass).search_foods,
                call.data.get("query", ""),
                limit=call.data.get("limit", 100),
            )
        }

    async def search_openfoodfacts(call: ServiceCall):
        coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
        if coordinator is None:
            raise ServiceValidationError("Food Diary coordinator is not loaded")
        try:
            products = await coordinator.async_search_openfoodfacts(
                call.data["query"], call.data.get("limit", 20)
            )
        except (ValueError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ServiceValidationError(str(err)) from err
        return {"products": products}

    async def find_food_by_barcode(call: ServiceCall):
        food = await _run(
            hass, _store(hass).find_food_by_barcode, call.data["barcode"]
        )
        return {"food": food}

    async def add_entry(call: ServiceCall):
        entry = await _run(
            hass,
            _store(hass).add_entry,
            call.data["food_id"],
            call.data["weight_g"],
            call.data["meal_type"],
            consumed_at=call.data.get("consumed_at"),
            source=call.data.get("source", "catalog"),
        )
        return entry if call.return_response else None

    async def list_entries(call: ServiceCall):
        return {
            "entries": await _run(
                hass,
                _store(hass).list_entries,
                call.data["start"],
                call.data["end"],
            )
        }

    async def delete_entry(call: ServiceCall):
        await _run(hass, _store(hass).delete_entry, call.data["entry_id"])

    async def save_pending(call: ServiceCall):
        coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
        if coordinator is None:
            raise ServiceValidationError("Food Diary coordinator is not loaded")
        entry = await coordinator.async_save_pending()
        if entry is None:
            raise ServiceValidationError("No complete pending scan is ready to save")
        return entry if call.return_response else None

    async def discard_pending(call: ServiceCall):
        coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
        if coordinator is None:
            raise ServiceValidationError("Food Diary coordinator is not loaded")
        await coordinator.async_discard_pending()

    async def get_status(call: ServiceCall):
        coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
        if coordinator is None:
            raise ServiceValidationError("Food Diary coordinator is not loaded")
        return {
            "state": coordinator.state,
            "last_barcode": coordinator.last_barcode,
            "last_weight_g": coordinator.last_weight_g,
            "scan_count": coordinator.last_scan_count,
            **coordinator.attributes,
        }

    async def period_summary(call: ServiceCall):
        return await _run(
            hass,
            _store(hass).period_summary,
            call.data["period"],
            call.data["anchor_date"],
            call.data["timezone"],
        )

    schemas: dict[str, tuple[Any, Any, SupportsResponse]] = {
        "add_food": (
            vol.Schema({
                vol.Required("name"): cv.string,
                vol.Optional("brand"): cv.string,
                vol.Optional("barcode"): cv.string,
                vol.Optional("nutrients_per_100g"): dict,
                vol.Optional("source", default="manual"): vol.In(FOOD_SOURCES),
            }),
            add_food,
            SupportsResponse.OPTIONAL,
        ),
        "update_food": (
            vol.Schema({
                vol.Required("food_id"): cv.string,
                vol.Optional("name"): cv.string,
                vol.Optional("brand"): vol.Any(cv.string, None),
                vol.Optional("barcode"): vol.Any(cv.string, None),
                vol.Optional("nutrients_per_100g"): dict,
                vol.Optional("source"): vol.In(FOOD_SOURCES),
            }),
            update_food,
            SupportsResponse.OPTIONAL,
        ),
        "delete_food": (
            vol.Schema({vol.Required("food_id"): cv.string}),
            delete_food,
            SupportsResponse.NONE,
        ),
        "search_foods": (
            vol.Schema({
                vol.Optional("query", default=""): cv.string,
                vol.Optional("limit", default=100): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=500)
                ),
            }),
            search_foods,
            SupportsResponse.ONLY,
        ),
        "search_openfoodfacts": (
            vol.Schema({
                vol.Required("query"): vol.All(cv.string, vol.Length(min=2, max=100)),
                vol.Optional("limit", default=20): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
            }),
            search_openfoodfacts,
            SupportsResponse.ONLY,
        ),
        "find_food_by_barcode": (
            vol.Schema({vol.Required("barcode"): cv.string}),
            find_food_by_barcode,
            SupportsResponse.ONLY,
        ),
        "add_entry": (
            vol.Schema({
                vol.Required("food_id"): cv.string,
                vol.Required("weight_g"): vol.All(
                    vol.Coerce(float), vol.Range(min=0.000001)
                ),
                vol.Required("meal_type"): vol.In(MEALS),
                vol.Optional("consumed_at"): cv.string,
                vol.Optional("source", default="catalog"): vol.In(ENTRY_SOURCES),
            }),
            add_entry,
            SupportsResponse.OPTIONAL,
        ),
        "list_entries": (
            vol.Schema({
                vol.Required("start"): cv.string,
                vol.Required("end"): cv.string,
            }),
            list_entries,
            SupportsResponse.ONLY,
        ),
        "delete_entry": (
            vol.Schema({vol.Required("entry_id"): cv.string}),
            delete_entry,
            SupportsResponse.NONE,
        ),
        "save_pending": (
            vol.Schema({}),
            save_pending,
            SupportsResponse.OPTIONAL,
        ),
        "discard_pending": (
            vol.Schema({}),
            discard_pending,
            SupportsResponse.NONE,
        ),
        "get_status": (
            vol.Schema({}),
            get_status,
            SupportsResponse.ONLY,
        ),
        "period_summary": (
            vol.Schema({
                vol.Required("period"): vol.In(PERIODS),
                vol.Required("anchor_date"): cv.string,
                vol.Required("timezone"): cv.string,
            }),
            period_summary,
            SupportsResponse.ONLY,
        ),
    }

    for service_name, (schema, handler, response_mode) in schemas.items():
        hass.services.async_register(
            DOMAIN,
            service_name,
            handler,
            schema=schema,
            supports_response=response_mode,
        )


def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister Food Diary actions when the config entry is unloaded."""
    for service_name in (
        "add_food",
        "update_food",
        "delete_food",
        "search_foods",
        "find_food_by_barcode",
        "search_openfoodfacts",
        "add_entry",
        "list_entries",
        "delete_entry",
        "period_summary",
        "save_pending",
        "discard_pending",
        "get_status",
    ):
        hass.services.async_remove(DOMAIN, service_name)
