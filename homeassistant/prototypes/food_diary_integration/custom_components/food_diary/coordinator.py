"""Runtime acquisition coordinator for the Food Diary integration."""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any

import aiohttp

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .acquisition import (
    ScanSession,
    classify_counter_change,
    normalize_barcode,
    parse_openfoodfacts_product,
    parse_weight_grams,
)
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
OFF_FIELDS = "code,product_name,brands,nutrition"
OFF_SEARCH_FIELDS = "code,product_name,brands,nutriments"


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
        self._session_expiry_cancel: Any = None
        self._session_id: str | None = None
        self._session_created_at: datetime | None = None
        self._session_expires_at: datetime | None = None
        self._session_restored = False
        self._pending_counter_events = 0
        self._last_counter: int | None = None
        self._weight_g: float | None = None
        self._session: ScanSession | None = None
        self._lock = asyncio.Lock()
        self._save_lock = asyncio.Lock()
        self._saving = False
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
            "pending_session_restored": self._session_restored if session else None,
            "pending_session_expires_at": (
                self._session_expires_at.isoformat() if session and self._session_expires_at else None
            ),
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
        await self._async_restore_pending_session()
        self._unsubscribers.append(
            async_track_state_change_event(
                self.hass,
                [self.counter_entity, self.weight_entity],
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
        if self._session_expiry_cancel:
            self._session_expiry_cancel()
            self._session_expiry_cancel = None
        async with self._save_lock:
            # Keep the durable SQLite record for a later config-entry reload.
            self._session = None
            self._pending_counter_events = 0
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
        change, increment = classify_counter_change(self._last_counter, current)
        if change == "invalid":
            self._pending_counter_events = 0
            if self._fallback_cancel:
                self._fallback_cancel()
                self._fallback_cancel = None
            self.last_error = "invalid_scan_counter"
            self.state = "sensor_error"
            self._notify()
            return
        if change == "baseline":
            self._last_counter = current
            self.last_scan_count = current
            self._notify()
            return
        self._last_counter = current
        self.last_scan_count = current
        if change == "reset":
            # ESPHome reboot/restore reset: rebase, never interpret as a scan.
            self._pending_counter_events = 0
            if self._fallback_cancel:
                self._fallback_cancel()
                self._fallback_cancel = None
            self.last_error = "scan_counter_reset"
            self.state = "ready"
            self._notify()
            return
        if increment <= 0:
            return
        self._pending_counter_events += increment
        if self._pending_counter_events > 1:
            # The firmware's delayed event reads the current Last Barcode
            # value, not a per-scan snapshot. If multiple increments overlap,
            # exact barcode-to-counter correlation is no longer provable.
            self._pending_counter_events = 0
            if self._fallback_cancel:
                self._fallback_cancel()
                self._fallback_cancel = None
            self.last_error = "multiple_scans_before_previous_scan_resolved"
            self.state = "scan_sequence_ambiguous"
            self._notify()
            return
        self.state = "scan_event_pending"
        if self._fallback_cancel:
            self._fallback_cancel()
        self._fallback_cancel = async_call_later(
            self.hass, 0.8, self._async_fallback_scan
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
        # The firmware emits this event after a delay and reads Last Barcode
        # at event time; it is not a guaranteed per-scan snapshot. Accept it
        # only when exactly one counter increment is pending and it matches
        # the selected entity. Bursts are rejected earlier as ambiguous.
        if self._pending_counter_events != 1:
            return
        selected = self.hass.states.get(self.barcode_entity)
        selected_barcode = normalize_barcode(selected.state if selected else None)
        if selected_barcode != barcode:
            self.last_error = "barcode_event_entity_mismatch"
            self._notify()
            return
        self._pending_counter_events = 0
        if self._fallback_cancel:
            self._fallback_cancel()
            self._fallback_cancel = None
        await self._async_begin_scan(barcode)

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

    def _clear_session_metadata(self) -> None:
        """Clear in-memory metadata and cancel the long-lived session expiry."""
        self._session_id = None
        self._session_created_at = None
        self._session_expires_at = None
        self._session_restored = False
        if self._session_expiry_cancel:
            self._session_expiry_cancel()
            self._session_expiry_cancel = None

    def _schedule_session_expiry(self) -> None:
        """Schedule the hard 24-hour expiry independently of the weight timeout."""
        if self._session_expiry_cancel:
            self._session_expiry_cancel()
            self._session_expiry_cancel = None
        if self._session_expires_at is None:
            return
        remaining = max(
            0.0,
            (self._session_expires_at - datetime.now(timezone.utc)).total_seconds(),
        )
        self._session_expiry_cancel = async_call_later(
            self.hass, remaining, self._async_session_expired
        )

    async def _async_persist_session(self) -> None:
        """Persist the pending barcode and its expiry; never persist a trusted weight."""
        if not self._session or not self._session_id or not self._session_created_at or not self._session_expires_at:
            return
        await self.hass.async_add_executor_job(
            partial(
                self.store.save_pending_session,
                self._session_id,
                self._session.barcode,
                self._session_created_at.isoformat(),
                self._session_expires_at.isoformat(),
            )
        )

    async def _async_restore_pending_session(self) -> None:
        """Restore an unexpired barcode, requiring a fresh zero and fresh weighing."""
        try:
            record = await self.hass.async_add_executor_job(self.store.get_pending_session)
        except Exception:
            _LOGGER.exception("Unable to read pending Food Diary scan from SQLite")
            self.last_error = "pending_session_restore_failed"
            self.state = "storage_error"
            self._notify()
            return
        if not record:
            return

        session_id = record.get("session_id")
        try:
            created_at = datetime.fromisoformat(record["created_at"]).astimezone(timezone.utc)
            expires_at = datetime.fromisoformat(record["expires_at"]).astimezone(timezone.utc)
            if not session_id or expires_at <= created_at:
                raise ValueError("invalid pending session timestamps or ID")
        except (KeyError, TypeError, ValueError, OverflowError):
            _LOGGER.warning("Discarding malformed pending Food Diary scan record")
            try:
                if session_id:
                    await self.hass.async_add_executor_job(
                        self.store.delete_pending_session, session_id
                    )
            except Exception:
                _LOGGER.exception("Unable to remove malformed pending scan record")
                self.last_error = "pending_session_cleanup_failed"
                self.state = "storage_error"
                self._notify()
                return
            self.last_error = "restored_scan_session_invalid"
            self._notify()
            return

        if expires_at <= datetime.now(timezone.utc):
            try:
                await self.hass.async_add_executor_job(
                    self.store.delete_pending_session, session_id
                )
            except Exception:
                _LOGGER.exception("Unable to remove expired pending scan record")
                self.last_error = "pending_session_cleanup_failed"
                self.state = "storage_error"
                self._notify()
                return
            self.last_error = "restored_scan_session_expired"
            self._notify()
            return

        barcode = normalize_barcode(record.get("barcode"))
        if barcode is None:
            try:
                await self.hass.async_add_executor_job(
                    self.store.delete_pending_session, session_id
                )
            except Exception:
                _LOGGER.exception("Unable to remove invalid pending scan record")
                self.last_error = "pending_session_cleanup_failed"
                self.state = "storage_error"
                self._notify()
                return
            self.last_error = "restored_scan_session_invalid"
            self._notify()
            return

        self._session_id = session_id
        self._session_created_at = created_at
        self._session_expires_at = expires_at
        self._session_restored = True
        self._session = ScanSession(
            barcode=barcode,
            zero_seen=False,
            weight_g=None,
            status="restored_requires_reweigh",
        )
        try:
            food = await self.hass.async_add_executor_job(
                self.store.find_food_by_barcode, barcode
            )
        except sqlite3.Error:
            _LOGGER.exception("Unable to resolve restored barcode in SQLite")
            self._session.status = "storage_error"
            self.last_error = "catalog_lookup_failed"
            self.state = "storage_error"
            self._schedule_session_expiry()
            self._notify()
            return
        if food is not None:
            self._session.food = food
            self._session.status = "restored_requires_reweigh"
            self.state = "restored_waiting_for_zero"
        else:
            self._session.status = "unknown_product"
            self.state = "unknown_product"
        self.last_barcode = barcode
        self.last_error = "restored_session_requires_fresh_tare_and_weighing"
        self._schedule_session_expiry()
        self._notify()

    @callback
    def _async_session_expired(self, _now) -> None:
        self._session_expiry_cancel = None
        self.hass.async_create_task(self._async_expire_persisted_session())

    async def _async_expire_persisted_session(self) -> None:
        """Expire the pending session atomically with save and discard."""
        async with self._save_lock:
            session_id = self._session_id
            if self._session is None or session_id is None:
                return
            try:
                await self.hass.async_add_executor_job(
                    self.store.delete_pending_session, session_id
                )
            except Exception:
                _LOGGER.exception("Unable to expire pending Food Diary scan")
                self.last_error = "pending_session_expiry_failed"
                self.state = "storage_error"
                self._notify()
                return
            self._session = None
            self._clear_session_metadata()
            self._cancel_timeout()
            self.last_error = "scan_session_retention_expired"
            self.state = "expired"
            self._notify()

    async def _async_begin_scan(self, barcode: str) -> None:
        # Serialize creation/persistence with save and discard so a fast UI
        # action cannot delete a row before this task writes it afterwards.
        async with self._save_lock:
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
                self._session_id = str(uuid.uuid4())
                self._session_created_at = datetime.now(timezone.utc)
                self._session_expires_at = self._session_created_at + timedelta(hours=24)
                self._session_restored = False
                self.state = "looking_up_product"
                timeout = int(self.config[CONF_WEIGHT_TIMEOUT])
                self._timeout_cancel = async_call_later(
                    self.hass, timeout, self._async_timeout
                )
                self._schedule_session_expiry()
                self._notify()
            try:
                await self._async_persist_session()
            except Exception:
                _LOGGER.exception("Unable to persist pending Food Diary scan")
                # A failed executor operation must not leave an orphaned row
                # that unexpectedly reappears after a later HA restart.
                if self._session_id:
                    try:
                        await self.hass.async_add_executor_job(
                            self.store.delete_pending_session, self._session_id
                        )
                    except Exception:
                        _LOGGER.exception("Unable to clean up failed pending scan")
                self._session = None
                self._clear_session_metadata()
                self._cancel_timeout()
                self.last_error = "pending_session_persist_failed"
                self.state = "storage_error"
                self._notify()
                return
        await self._async_lookup_product(barcode)

    @callback
    def _async_timeout(self, _now) -> None:
        """Stop the current weight wait without deleting the durable scan session."""
        self._timeout_cancel = None
        if self._session is None or self._session.weight_g is not None:
            return
        # The short acquisition timeout is not the 24-hour retention period.
        # Keep the barcode in SQLite so a later scale update or HA restart can
        # resume the session. A fresh zero and positive stable weight are still
        # required; no pre-timeout or pre-restart weight is trusted.
        self.last_error = "weight_acquisition_timeout"
        self.state = "weight_timeout"
        self._notify()

    async def _async_lookup_product(self, barcode: str) -> None:
        # Bind this asynchronous lookup to the exact session that started it.
        # Barcode equality alone is insufficient: a later scan can reuse it.
        session = self._session
        if session is None or session.barcode != barcode:
            return
        try:
            food = await self.hass.async_add_executor_job(
                self.store.find_food_by_barcode, barcode
            )
        except sqlite3.Error:
            _LOGGER.exception("Food Diary catalogue read failed")
            if self._session is session:
                self.last_error = "catalog_lookup_failed"
                self.state = "storage_error"
                self._notify()
            return

        lookup_failed = False
        if food is None and self.config.get(CONF_OFF_ENABLED, True):
            try:
                food = await self._async_lookup_openfoodfacts(barcode)
            except (OSError, ValueError, aiohttp.ClientError, asyncio.TimeoutError) as err:
                _LOGGER.warning("Food Diary product lookup failed: %s", err)
                lookup_failed = True
                food = None
        if self._session is not session:
            return
        if lookup_failed:
            self.last_error = "product_lookup_failed"
        if food is None:
            session.status = "unknown_product"
            self.state = "unknown_product"
            self.last_error = self.last_error or "product_not_found"
            if session.weight_g is not None:
                self._cancel_timeout()
        else:
            session.food = food
            session.status = "waiting_for_weight"
            self.state = "waiting_for_zero" if not session.zero_seen else "waiting_for_weight"
            self.last_error = None
        await self._async_maybe_complete()
        self._notify()

    async def _async_lookup_openfoodfacts(self, barcode: str) -> dict[str, Any] | None:
        if not barcode.isdigit() or not 8 <= len(barcode) <= 14:
            return None
        country = str(self.config.get(CONF_OFF_COUNTRY, "it")).lower()
        language = str(self.config.get(CONF_OFF_LANGUAGE, "it")).lower()
        url = f"https://world.openfoodfacts.org/api/v3/product/{barcode}"
        session = async_get_clientsession(self.hass)
        timeout = aiohttp.ClientTimeout(total=10)
        async with session.get(
            url,
            params={"fields": OFF_FIELDS, "cc": country, "lc": language},
            headers={"User-Agent": "HomeAssistant-FoodDiary/0.1.0 (https://github.com/crow782/cosori)"},
            timeout=timeout,
        ) as response:
            if response.status == 404:
                return None
            response.raise_for_status()
            payload = await response.json(content_type=None)
        parsed = parse_openfoodfacts_product(payload, barcode)
        if parsed is None:
            return None

        # add_food has keyword-only optional fields; keep it in a small closure
        def save_food():
            return self.store.add_food(
                parsed["name"],
                brand=parsed["brand"],
                barcode=parsed["barcode"],
                nutrients_per_100g=parsed["nutrients_per_100g"],
                source=parsed["source"],
            )
        try:
            return await self.hass.async_add_executor_job(save_food)
        except Exception:
            # Another lookup may have inserted the same barcode concurrently.
            return await self.hass.async_add_executor_job(
                self.store.find_food_by_barcode, barcode
            )

    async def async_search_openfoodfacts(
        self, query: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Search OFF's legacy full-text endpoint for manual alternatives."""
        query = str(query).strip()
        if len(query) < 2:
            raise ValueError("query must contain at least two characters")
        if len(query) > 100:
            raise ValueError("query must not exceed 100 characters")
        limit = max(1, min(int(limit), 50))
        if not self.config.get(CONF_OFF_ENABLED, True):
            raise ValueError("Open Food Facts lookup is disabled in integration options")
        url = "https://world.openfoodfacts.org/cgi/search.pl"
        session = async_get_clientsession(self.hass)
        timeout = aiohttp.ClientTimeout(total=12)
        async with session.get(
            url,
            params={
                "search_terms": query,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": limit,
                "fields": OFF_SEARCH_FIELDS,
                "cc": str(self.config.get(CONF_OFF_COUNTRY, "it")).lower(),
                "lc": str(self.config.get(CONF_OFF_LANGUAGE, "it")).lower(),
            },
            headers={"User-Agent": "HomeAssistant-FoodDiary/0.1.0 (https://github.com/crow782/cosori)"},
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            payload = await response.json(content_type=None)
        products: list[dict[str, Any]] = []
        for raw_product in payload.get("products", []):
            barcode = str(raw_product.get("code") or "").strip()
            parsed = parse_openfoodfacts_product(
                {"status": 1, "product": raw_product}, barcode
            )
            if parsed is None or not barcode:
                continue
            products.append(parsed)
        return products

    async def _async_observe_weight(self, weight_g: float | None) -> None:
        if self._stopped or self._session is None:
            self._notify()
            return
        self._session.observe_weight(
            weight_g, float(self.config[CONF_ZERO_THRESHOLD])
        )
        if self._session.weight_g is not None:
            self._cancel_timeout()
            if self._session.zero_seen:
                self.state = "waiting_for_product" if self._session.food is None else "ready_to_save"
        else:
            self.state = (
                "waiting_for_zero"
                if not self._session.zero_seen
                else ("waiting_for_weight" if self._session.food else "unknown_product")
            )
            if self._timeout_cancel is None:
                self._timeout_cancel = async_call_later(
                    self.hass, int(self.config[CONF_WEIGHT_TIMEOUT]), self._async_timeout
                )
        await self._async_maybe_complete()
        self._notify()

    async def _async_maybe_complete(self) -> None:
        if self._session is None or not self._session.can_save:
            return
        self._cancel_timeout()
        if not self.config.get(CONF_AUTO_SAVE, True):
            self.state = "ready_to_save"
            return
        await self.async_save_pending()

    async def async_catalog_changed(self, barcode: str | None = None) -> None:
        """Resolve an unknown pending product after manual/catalog insertion."""
        session = self._session
        session_id = self._session_id
        if session is None or (barcode and barcode != session.barcode):
            return
        try:
            food = await self.hass.async_add_executor_job(
                self.store.find_food_by_barcode, session.barcode
            )
        except sqlite3.Error:
            _LOGGER.exception("Food Diary catalogue lookup failed after manual insertion")
            if self._session is session and self._session_id == session_id:
                self.last_error = "catalog_lookup_failed"
                self.state = "storage_error"
                self._notify()
            return
        # The DB lookup yields control; do not apply its result to a replacement
        # session, even if the replacement happens to use the same barcode.
        if food is not None and self._session is session and self._session_id == session_id:
            session.food = food
            session.status = "waiting_for_weight"
            self.state = "waiting_for_zero" if not session.zero_seen else "waiting_for_weight"
            await self._async_maybe_complete()
            self._notify()

    def _cancel_timeout(self) -> None:
        if self._timeout_cancel:
            self._timeout_cancel()
            self._timeout_cancel = None

    async def async_save_pending(self) -> dict[str, Any] | None:
        """Persist the pending portion once, preserving its product snapshot."""
        async with self._save_lock:
            session = self._session
            if session is None or not session.can_save or self._saving:
                return None
            # A callback may be delayed while another operation owns the lock.
            # Enforce retention here too, so a save cannot win after 24 hours.
            if (
                self._session_expires_at is not None
                and self._session_expires_at <= datetime.now(timezone.utc)
            ):
                session_id = self._session_id
                try:
                    if session_id:
                        await self.hass.async_add_executor_job(
                            self.store.delete_pending_session, session_id
                        )
                except Exception:
                    _LOGGER.exception("Unable to expire pending scan before save")
                    self.last_error = "pending_session_expiry_failed"
                    self.state = "storage_error"
                    self._notify()
                    return None
                self._session = None
                self._clear_session_metadata()
                self._cancel_timeout()
                self.last_error = "scan_session_retention_expired"
                self.state = "expired"
                self._notify()
                return None
            self._saving = True
            self._cancel_timeout()
            try:
                entry = await self.hass.async_add_executor_job(
                    partial(
                        self.store.add_entry,
                        session.food["id"],
                        session.weight_g,
                        self.config.get(CONF_DEFAULT_MEAL, "snack"),
                        source="scan",
                        pending_session_id=self._session_id,
                    )
                )
            except Exception:
                self.last_error = "entry_save_failed"
                self.state = "save_error"
                self._notify()
                raise
            finally:
                self._saving = False
            if self._session is session:
                self.last_entry = entry
                self.state = "saved"
                self.last_error = None
                self._session = None
                self._clear_session_metadata()
                self._notify()
            return entry

    async def async_discard_pending(self) -> None:
        """Discard the current pending scan without writing a diary entry."""
        async with self._save_lock:
            if self._session is None:
                return
            session_id = self._session_id
            try:
                if session_id:
                    await self.hass.async_add_executor_job(
                        self.store.delete_pending_session, session_id
                    )
            except Exception:
                # Keep the in-memory session if SQLite is unavailable. The
                # durable row is still needed for retry/recovery after reload.
                _LOGGER.exception("Unable to discard pending Food Diary scan")
                self.last_error = "pending_session_discard_failed"
                self.state = "storage_error"
                self._notify()
                raise
            self._session = None
            self._clear_session_metadata()
            self._cancel_timeout()
            self.state = "discarded"
            self.last_error = None
            self._notify()
