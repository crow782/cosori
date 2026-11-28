"""Runtime acquisition coordinator for the Food Diary integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .acquisition import ScanSession, normalize_barcode, parse_weight_grams
from .const import (
    CONF_AUTO_SAVE,
    CONF_BARCODE_ENTITY,
    CONF_DEFAULT_MEAL,
    CONF_OFF_COUNTRY,
    CONF_OFF_ENABLED,
    CONF_OFF_LANGUAGE,
    CONF_SCAN_COUNT_ENTITY,
    CONF_WEIGHT_ENTITY,
    CONF_WEIGHT_TIMEOUT,
    CONF_ZERO_THRESHOLD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
SCAN_EVENT = "esphome.barcode_scanned"
OFF_FIELDS = "code,product_name,brands,nutriments"


class FoodDiaryCoordinator:
    """Correlate selected scan counter, barcode and stable scale sensor."""

    def __init__(
        self, hass: HomeAssistant, config: dict[str, Any], store: Any
    ) -> None:
        self.hass = hass
        self.config = config
        self.store = store
        self.weight_entity = config[CONF_WEIGHT_ENTITY]
        self.barcode_entity = config[CONF_BARCODE_ENTITY]
        self.counter_entity = config[CONF_SCAN_COUNT_ENTITY]
        self._unsubscribers: list[Any] = []
        self._listeners: list[Any] = []
        self._fallback_cancel: Any = None
        self._timeout_cancel: Any = None
        self._pending_counter_events = 0
        self._last_counter: int | None = None
        self._weight_g: float | None = None
        self._session: ScanSession | None = None
        self._lock = asyncio.Lock()
        self._stopped = False
        self.state = "initializing"
        self.last_barcode: str | None = None
        self.last_error: str | None = None
        self.last_entry: dict[str, Any] | None = None
        self.last_weight_g: float | None = None
        self.last_scan_count: int | None = None

    @property
    def attributes(self) -> dict[str, Any]:
        """Return safe diagnostic attributes for sensor entities."""
        session = self._session
        return {
            "weight_entity": self.weight_entity,
            "barcode_entity": self.barcode_entity,
            "scan_count_entity": self.counter_entity,
            "pending_barcode": session.barcode if session else None,
            "pending_product": session.food.get("name") if session and session.food else None,
            "pending_weight_g": session.weight_g if session else None,
            "zero_seen": session.zero_seen if session else None,
            "last_error": self.last_error,
            "last_entry_id": self.last_entry.get("id") if self.last_entry else None,
        }

    def async_add_listener(self, listener):
        """Register an entity listener and return an unsubscribe callback."""
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    async def async_start(self) -> None:
        """Attach state/event listeners and initialize baselines without scanning."""
        counter_state = self.hass.states.get(self.counter_entity)
        self._last_counter = self._parse_counter(counter_state.state) if counter_state else None
        self.last_scan_count = self._last_counter
        self._weight_g = self._read_weight_state()
        self.last_weight_g = self._weight_g
        self.state = "ready" if self._weight_g is not None else "waiting_for_scale"
        self._unsubscribers.append(
            async_track_state_change_event(
                self.hass,
                [self.counter_entity, self.barcode_entity, self.weight_entity],
                self._handle_state_change,
            )
        )
        self._unsubscribers.append(
            self.hass.bus.async_listen(SCAN_EVENT, self._handle_scan_event)
        )
        self._notify()

    async def async_stop(self) -> None:
        """Remove listeners and cancel timers/tasks on config-entry unload."""
        self._stopped = True
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        if self._fallback_cancel:
            self._fallback_cancel()
            self._fallback_cancel = None
        if self._timeout_cancel:
            self._timeout_cancel()
            self._timeout_cancel = None
        self._listeners.clear()

    @staticmethod
    def _parse_counter(value: Any) -> int | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not number.is_integer():
            return None
        return int(number)

    def _read_weight(self, state) -> float | None:
        if state is None or state.state in {"unknown", "unavailable"}:
            return None
        return parse_weight_grams(
            state.state, state.attributes.get("unit_of_measurement")
        )

    def _read_weight_state(self) -> float | None:
        return self._read_weight(self.hass.states.get(self.weight_entity))

    @callback
    def _handle_state_change(self, event: Event) -> None:
        entity_id = event.data["entity_id"]
        new_state = event.data.get("new_state")
        if entity_id == self.counter_entity:
            self.hass.async_create_task(self._async_counter_changed(new_state))
        elif entity_id == self.weight_entity:
            self._weight_g = self._read_weight(new_state)
            self.last_weight_g = self._weight_g
            self.hass.async_create_task(self._async_observe_weight(self._weight_g))
        # The barcode state is deliberately read only after the scan counter
        # or ESPHome event: the firmware publishes the counter before barcode.

    async def _async_counter_changed(self, new_state) -> None:
        if self._stopped or new_state is None:
            return
        current = self._parse_counter(new_state.state)
        if current is None:
            self.last_error = "invalid_scan_counter"
            self.state = "sensor_error"
            self._notify()
            return
        if self._last_counter is None:
            self._last_counter = current
            self.last_scan_count = current
            self._notify()
            return
        previous = self._last_counter
        self._last_counter = current
        self.last_scan_count = current
        if current < previous:
            # ESPHome reboot/restore reset: rebase, never interpret as a scan.
            self._pending_counter_events = 0
            self.last_error = "scan_counter_reset"
            self.state = "ready"
            self._notify()
            return
        increment = current - previous
        if increment <= 0:
            return
        self._pending_counter_events += increment
        self.state = "scan_event_pending"
        if self._fallback_cancel:
            self._fallback_cancel()
        delay = 0.8
        self._fallback_cancel = async_call_later(
            self.hass, delay, self._async_fallback_scan
        )
        self._notify()

    @callback
    def _handle_scan_event(self, event: Event) -> None:
        """Consume the firmware's delayed barcode event when it is available."""
        barcode = normalize_barcode(event.data.get("barcode"))
        if barcode is None:
            self.last_error = "invalid_barcode_event"
            self._notify()
            return
        self.hass.async_create_task(self._async_accept_event_barcode(barcode))

    async def _async_accept_event_barcode(self, barcode: str) -> None:
        if self._stopped or self._pending_counter_events <= 0:
            return
        # The current ESPHome firmware sends this event 300 ms after publishing
        # both selected sensor states. Match it to the selected barcode entity
        # to avoid accepting an unrelated esphome.barcode_scanned event.
        selected = self.hass.states.get(self.barcode_entity)
        selected_barcode = normalize_barcode(selected.state if selected else None)
        if selected_barcode != barcode:
            self.last_error = "barcode_event_entity_mismatch"
            self._notify()
            return
        self._pending_counter_events -= 1
        if self._fallback_cancel:
            self._fallback_cancel()
            self._fallback_cancel = None
        await self._async_begin_scan(barcode)
        if self._pending_counter_events:
            self._fallback_cancel = async_call_later(
                self.hass, 0.8, self._async_fallback_scan
            )

    @callback
    def _async_fallback_scan(self, _now) -> None:
        """Fallback for generic scanners that expose entities but no HA event."""
        self._fallback_cancel = None
        self.hass.async_create_task(self._async_process_fallback())

    async def _async_process_fallback(self) -> None:
        if self._stopped or self._pending_counter_events <= 0:
            return
        pending = self._pending_counter_events
        self._pending_counter_events = 0
        barcode_state = self.hass.states.get(self.barcode_entity)
        barcode = normalize_barcode(barcode_state.state if barcode_state else None)
        if pending != 1:
            self.last_error = "multiple_scans_without_matching_events"
            self.state = "scan_sequence_ambiguous"
            self._notify()
            return
        if barcode is None:
            self.last_error = "invalid_barcode_sensor_state"
            self.state = "sensor_error"
            self._notify()
            return
        await self._async_begin_scan(barcode)

    async def _async_begin_scan(self, barcode: str) -> None:
        async with self._lock:
            if self._session is not None:
                self.last_error = "previous_scan_still_pending"
                self.state = "session_busy"
                self._notify()
                return
            self.last_barcode = barcode
            self.last_error = None
            self.last_entry = None
            self._session = ScanSession(
                barcode=barcode,
                zero_seen=(
                    self._weight_g is not None
                    and self._weight_g <= float(self.config[CONF_ZERO_THRESHOLD])
                ),
            )
            self.state = "looking_up_product"
            timeout = int(self.config[CONF_WEIGHT_TIMEOUT])
            self._timeout_cancel = async_call_later(
                self.hass, timeout, self._async_timeout
            )
            self._notify()
        await self._async_lookup_product(barcode)

    @callback
    def _async_timeout(self, _now) -> None:
        self._timeout_cancel = None
        self.hass.async_create_task(self._async_expire_session())

    async def _async_expire_session(self) -> None:
        if self._session is None:
            return
        self._session = None
        self.last_error = "scan_session_timeout"
        self.state = "timeout"
        self._notify()

    async def _async_lookup_product(self, barcode: str) -> None:
        try:
            food = await self.hass.async_add_executor_job(
                self.store.find_food_by_barcode, barcode
            )
            if food is None and self.config.get(CONF_OFF_ENABLED, True):
                food = await self._async_lookup_openfoodfacts(barcode)
        except (OSError, ValueError, aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.warning("Food Diary product lookup failed: %s", err)
            self.last_error = "product_lookup_failed"
            food = None
        if self._session is None or self._session.barcode != barcode:
            return
        if food is None:
            self._session.status = "unknown_product"
            self.state = "unknown_product"
            self.last_error = self.last_error or "product_not_found"
        else:
            self._session.food = food
            self._session.status = "waiting_for_weight"
            self.state = "waiting_for_zero" if not self._session.zero_seen else "waiting_for_weight"
            self.last_error = None
        await self._async_maybe_complete()
        self._notify()

    async def _async_lookup_openfoodfacts(self, barcode: str) -> dict[str, Any] | None:
        if not barcode.isdigit() or not 8 <= len(barcode) <= 14:
            return None
        country = str(self.config.get(CONF_OFF_COUNTRY, "it")).lower()
        language = str(self.config.get(CONF_OFF_LANGUAGE, "it")).lower()
        url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        session = async_get_clientsession(self.hass)
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(
            url,
            params={"fields": OFF_FIELDS, "cc": country, "lc": language},
            timeout=timeout,
        ) as response:
            if response.status == 404:
                return None
            response.raise_for_status()
            payload = await response.json(content_type=None)
        if payload.get("status") != 1:
            return None
        product = payload.get("product") or {}
        name = (product.get("product_name") or "").strip()
        if not name:
            return None
        nutriments = product.get("nutriments") or {}
        energy = nutriments.get("energy-kcal_100g")
        if energy is None and nutriments.get("energy-kj_100g") is not None:
            energy = float(nutriments["energy-kj_100g"]) / 4.184
        nutrient_map = {
            "energy_kcal": energy,
            "protein_g": nutriments.get("proteins_100g"),
            "carbohydrates_g": nutriments.get("carbohydrates_100g"),
            "sugars_g": nutriments.get("sugars_100g"),
            "fat_g": nutriments.get("fat_100g"),
            "saturated_fat_g": nutriments.get("saturated-fat_100g"),
            "fiber_g": nutriments.get("fiber_100g"),
            "salt_g": nutriments.get("salt_100g"),
        }
        food = await self.hass.async_add_executor_job(
            self.store.add_food,
            name,
        ) if False else None
        # add_food has keyword-only optional fields; keep it in a small closure
        def save_food():
            return self.store.add_food(
                name,
                brand=product.get("brands"),
                barcode=barcode,
                nutrients_per_100g=nutrient_map,
                source="openfoodfacts",
            )
        try:
            return await self.hass.async_add_executor_job(save_food)
        except Exception:
            # Another lookup may have inserted the same barcode concurrently.
            return await self.hass.async_add_executor_job(
                self.store.find_food_by_barcode, barcode
            )

    async def _async_observe_weight(self, weight_g: float | None) -> None:
        if self._stopped or self._session is None:
            self._notify()
            return
        self._session.observe_weight(
            weight_g, float(self.config[CONF_ZERO_THRESHOLD])
        )
        if not self._session.zero_seen:
            self.state = "waiting_for_zero"
        elif self._session.weight_g is not None:
            self.state = "waiting_for_product" if self._session.food is None else "ready_to_save"
        else:
            self.state = "waiting_for_weight" if self._session.food else "unknown_product"
        await self._async_maybe_complete()
        self._notify()

    async def _async_maybe_complete(self) -> None:
        if self._session is None or not self._session.can_save:
            return
        if not self.config.get(CONF_AUTO_SAVE, True):
            self.state = "ready_to_save"
            return
        await self.async_save_pending()

    async def async_catalog_changed(self, barcode: str | None = None) -> None:
        """Resolve an unknown pending product after manual/catalog insertion."""
        if self._session is None or (barcode and barcode != self._session.barcode):
            return
        food = await self.hass.async_add_executor_job(
            self.store.find_food_by_barcode, self._session.barcode
        )
        if food is not None and self._session is not None:
            self._session.food = food
            await self._async_maybe_complete()
            self._notify()

    async def async_save_pending(self) -> dict[str, Any] | None:
        """Persist the pending portion once, preserving its product snapshot."""
        session = self._session
        if session is None or not session.can_save:
            return None
        if self._timeout_cancel:
            self._timeout_cancel()
            self._timeout_cancel = None
        entry = await self.hass.async_add_executor_job(
            self.store.add_entry,
            session.food["id"],
            session.weight_g,
            self.config.get(CONF_DEFAULT_MEAL, "snack"),
            source="scan",
        )
        self.last_entry = entry
        self.state = "saved"
        self.last_error = None
        self._session = None
        self._notify()
        return entry

    async def async_discard_pending(self) -> None:
        """Discard the current pending scan without writing a diary entry."""
        self._session = None
        if self._timeout_cancel:
            self._timeout_cancel()
            self._timeout_cancel = None
        self.state = "discarded"
        self.last_error = None
        self._notify()
