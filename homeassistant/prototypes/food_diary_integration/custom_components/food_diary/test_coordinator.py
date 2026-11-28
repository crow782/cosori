"""Focused coordinator concurrency and recovery tests with a minimal HA test double."""
from __future__ import annotations

import asyncio
import importlib
import inspect
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


def _load_module():
    core = types.ModuleType("homeassistant.core")
    core.Event = object
    core.HomeAssistant = object
    core.callback = lambda fn: fn
    aio = types.ModuleType("homeassistant.helpers.aiohttp_client")
    aio.async_get_clientsession = lambda hass: None
    http = types.ModuleType("aiohttp")
    http.ClientError = OSError
    http.TimeoutError = asyncio.TimeoutError
    http.ClientTimeout = lambda **kwargs: None
    sys.modules.setdefault("aiohttp", http)
    events = types.ModuleType("homeassistant.helpers.event")
    events.async_call_later = lambda *args: (lambda: None)
    events.async_track_state_change_event = lambda *args: (lambda: None)
    ha = types.ModuleType("homeassistant")
    ha.__path__ = []
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    sys.modules.update({
        "homeassistant": ha, "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.aiohttp_client": aio,
        "homeassistant.helpers.event": events,
    })
    package_dir = Path(__file__).resolve().parent
    package = types.ModuleType("food_diary")
    package.__path__ = [str(package_dir)]
    sys.modules["food_diary"] = package
    for name in ("food_diary.acquisition", "food_diary.const", "food_diary.coordinator"):
        sys.modules.pop(name, None)
    return importlib.import_module("food_diary.coordinator")


mod = _load_module()
FoodDiaryCoordinator = mod.FoodDiaryCoordinator
from food_diary.acquisition import ScanSession
from food_diary.const import (
    CONF_AUTO_SAVE, CONF_BARCODE_ENTITY, CONF_DEFAULT_MEAL, CONF_OFF_ENABLED,
    CONF_SCAN_COUNT_ENTITY, CONF_WEIGHT_ENTITY, CONF_WEIGHT_TIMEOUT,
    CONF_ZERO_THRESHOLD,
)


class Hass:
    def __init__(self):
        self.states = SimpleNamespace(get=lambda entity: {
            "sensor.weight": SimpleNamespace(state="0", attributes={"unit_of_measurement": "g"}),
            "sensor.barcode": SimpleNamespace(state="8017596008299", attributes={}),
            "sensor.count": SimpleNamespace(state="0", attributes={}),
        }.get(entity))
        self.bus = SimpleNamespace(async_listen=lambda *args: (lambda: None))

    async def async_add_executor_job(self, fn, *args):
        await asyncio.sleep(0)
        result = fn(*args)
        return await result if inspect.isawaitable(result) else result

    def async_create_task(self, coro):
        return asyncio.create_task(coro)


class Store:
    def __init__(self):
        self.pending = None
        self.entries = []
        self.delete_error = None

    def get_pending_session(self):
        return self.pending

    def save_pending_session(self, sid, barcode, created, expires):
        self.pending = dict(session_id=sid, barcode=barcode, created_at=created, expires_at=expires)

    def delete_pending_session(self, sid):
        if self.delete_error:
            raise self.delete_error
        if self.pending and self.pending["session_id"] == sid:
            self.pending = None
            return True
        return False

    def find_food_by_barcode(self, barcode):
        return {"id": 7, "name": "Yogurt", "barcode": barcode}

    def add_entry(self, food_id, weight, meal, **kwargs):
        item = {"id": len(self.entries) + 1, "food_id": food_id, "weight": weight}
        self.entries.append(item)
        self.pending = None
        return item


def make(store=None):
    hass, store = Hass(), store or Store()
    config = {
        CONF_WEIGHT_ENTITY: "sensor.weight",
        CONF_BARCODE_ENTITY: "sensor.barcode",
        CONF_SCAN_COUNT_ENTITY: "sensor.count",
        CONF_AUTO_SAVE: False, CONF_DEFAULT_MEAL: "snack",
        CONF_WEIGHT_TIMEOUT: 45, CONF_ZERO_THRESHOLD: 2.0,
        CONF_OFF_ENABLED: False,
    }
    return FoodDiaryCoordinator(hass, config, store), store


class CoordinatorConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_restore_discards_old_weight_and_requires_fresh_zero(self):
        coordinator, store = make()
        now = datetime.now(timezone.utc)
        store.pending = {
            "session_id": "restored", "barcode": "8017596008299",
            "created_at": (now - timedelta(minutes=1)).isoformat(),
            "expires_at": (now + timedelta(hours=23)).isoformat(),
        }
        await coordinator._async_restore_pending_session()
        self.assertFalse(coordinator._session.zero_seen)
        self.assertIsNone(coordinator._session.weight_g)
        self.assertEqual(coordinator.state, "restored_waiting_for_zero")

    async def test_unload_and_restart_restore_persisted_barcode(self):
        coordinator, store = make()

        async def no_lookup(barcode):
            return None

        coordinator._async_lookup_product = no_lookup
        await coordinator._async_begin_scan("8017596008299")
        self.assertIsNotNone(store.pending)
        await coordinator.async_stop()
        self.assertIsNone(coordinator._session)
        self.assertIsNotNone(store.pending)

        restarted, _ = make(store)
        await restarted._async_restore_pending_session()
        self.assertEqual(restarted._session.barcode, "8017596008299")
        self.assertFalse(restarted._session.zero_seen)
        self.assertIsNone(restarted._session.weight_g)

    async def test_duplicate_barcode_event_is_consumed_once(self):
        coordinator, _ = make()
        coordinator._pending_counter_events = 1
        calls = []

        async def begin(barcode):
            calls.append(barcode)
            coordinator._session = ScanSession(barcode, zero_seen=False)

        coordinator._async_begin_scan = begin
        await coordinator._async_accept_event_barcode("8017596008299")
        await coordinator._async_accept_event_barcode("8017596008299")
        self.assertEqual(calls, ["8017596008299"])

    async def test_counter_burst_with_duplicate_barcode_is_rejected_as_ambiguous(self):
        coordinator, _ = make()
        coordinator._last_counter = 10
        await coordinator._async_counter_changed(SimpleNamespace(state="12"))
        self.assertEqual(coordinator.state, "scan_sequence_ambiguous")
        self.assertEqual(coordinator._pending_counter_events, 0)
        self.assertIsNone(coordinator._session)

    async def test_two_simultaneous_saves_write_one_entry(self):
        coordinator, store = make()
        session = ScanSession("8017596008299", True, 120, {"id": 7}, "ready")
        coordinator._session = session
        coordinator._session_id = "save"
        coordinator._session_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        store.save_pending_session("save", session.barcode, "2026-11-28T00:00:00+00:00",
                                  coordinator._session_expires_at.isoformat())
        a, b = await asyncio.gather(
            coordinator.async_save_pending(), coordinator.async_save_pending()
        )
        self.assertEqual(len(store.entries), 1)
        self.assertIsNotNone(a)
        self.assertIsNone(b)
        self.assertIsNone(store.pending)

    async def test_discard_sqlite_error_keeps_pending_session(self):
        coordinator, store = make()
        coordinator._session = ScanSession("8017596008299", False)
        coordinator._session_id = "discard"
        store.save_pending_session("discard", "8017596008299",
                                   "2026-11-28T00:00:00+00:00",
                                   "2026-11-29T00:00:00+00:00")
        store.delete_error = OSError("database is locked")
        with self.assertRaises(OSError):
            await coordinator.async_discard_pending()
        self.assertIsNotNone(coordinator._session)
        self.assertIsNotNone(store.pending)
        self.assertEqual(coordinator.state, "storage_error")

    async def test_expired_session_is_not_saved(self):
        coordinator, store = make()
        session = ScanSession("8017596008299", True, 100, {"id": 7}, "ready")
        coordinator._session = session
        coordinator._session_id = "expired"
        coordinator._session_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        store.save_pending_session("expired", session.barcode, "2026-11-27T00:00:00+00:00",
                                   coordinator._session_expires_at.isoformat())
        result = await coordinator.async_save_pending()
        self.assertIsNone(result)
        self.assertEqual(store.entries, [])
        self.assertIsNone(store.pending)
        self.assertEqual(coordinator.state, "expired")

    async def test_expiry_sqlite_error_retains_session(self):
        coordinator, store = make()
        coordinator._session = ScanSession("8017596008299", False)
        coordinator._session_id = "expiry"
        store.save_pending_session("expiry", "8017596008299",
                                   "2026-11-28T00:00:00+00:00",
                                   "2026-11-29T00:00:00+00:00")
        store.delete_error = OSError("disk I/O error")
        await coordinator._async_expire_persisted_session()
        self.assertIsNotNone(coordinator._session)
        self.assertIsNotNone(store.pending)
        self.assertEqual(coordinator.state, "storage_error")

    async def test_stale_catalog_lookup_does_not_update_new_session(self):
        coordinator, store = make()
        old = ScanSession("8017596008299", False)
        coordinator._session, coordinator._session_id = old, "old"
        gate = asyncio.Event()

        async def delayed_find(barcode):
            await gate.wait()
            return {"id": 99, "name": "stale"}

        store.find_food_by_barcode = delayed_find
        task = asyncio.create_task(coordinator.async_catalog_changed())
        await asyncio.sleep(0)
        replacement = ScanSession("8017596008299", False)
        coordinator._session, coordinator._session_id = replacement, "new"
        gate.set()
        await task
        self.assertIsNone(replacement.food)


if __name__ == "__main__":
    unittest.main()
