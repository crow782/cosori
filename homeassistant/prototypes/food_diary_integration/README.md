# Food Diary – Home Assistant integration prototype

> **Experimental only. Do not install in the active Home Assistant instance.**
> This folder is separate from the current packages and ESPHome firmware. The
> component is not yet validated against Home Assistant Core 2026.11.3.
>
> Distribution target and packaging decisions: [HACS_ARCHITECTURE.md](HACS_ARCHITECTURE.md).

## Purpose

This prototype wraps the independent SQLite data layer in a custom Home
Assistant integration. It is intended to expose the local food catalogue and
meal diary through Home Assistant actions, so a future dashboard and
automations can use one stable API.

## Layout

- `custom_components/food_diary/manifest.json`: integration metadata.
- `__init__.py`: config-entry lifecycle and SQLite initialization.
- `config_flow.py`: UI setup flow (single local instance).
- `services.py`: Home Assistant actions and input validation, including pending-session controls.
- `coordinator.py`: selected-entity listeners, scan/weight correlation, local and Open Food Facts lookup, and session lifecycle.
- `acquisition.py`: pure barcode/weight/Open Food Facts parsing and zero-baseline gate.
- `sensor.py`: lightweight acquisition diagnostic sensors.
- `test_acquisition.py`: dependency-free unit tests for acquisition rules.
- `services.yaml`: action descriptions and selectors.
- `translations/en.json` and `translations/it.json`: English and Italian UI/action translations.
- `storage.py`: isolated SQLite repository copied from the tested-design
  prototype; it has no Home Assistant imports.

## Planned installation shape

When approved and tested, the integration folder will be copied to:

```text
/config/custom_components/food_diary/
```

The database will be created under:

```text
/config/food_diary/food_diary.db
```

Neither path is used by this prototype in the repository. No active HA files
have been changed.

## Example action calls

Search the local food catalogue (the action supports response data):

```yaml
action: food_diary.search_foods
data:
  query: yogurt
  limit: 50
response_variable: food_search
```

Record a portion after selecting a known food:

```yaml
action: food_diary.add_entry
data:
  food_id: "<food-id-from-search>"
  weight_g: 125
  meal_type: breakfast
  source: catalog
```

Retrieve a local calendar-week summary:

```yaml
action: food_diary.period_summary
data:
  period: week
  anchor_date: "2026-11-25"
  timezone: Europe/Rome
response_variable: food_week
```

The action response feature is the current Home Assistant mechanism for
returning collections and structured results that should not be represented
as entity states. See the official [integration service actions guide](https://developers.home-assistant.io/docs/dev_101_services/).

## Guided setup prototype

The config flow now asks for:
- an ESPHome sensor entity filtered to the weight device class;
- a generic Home Assistant `sensor` entity that publishes the last scanned barcode (for example `sensor.barcode_scanner_last_barcode`);
- a generic Home Assistant `sensor` entity used as the scan counter trigger (for example `sensor.barcode_scanner_scan_count`).

The options flow allows changing all three entity selections and configuring default meal,
automatic save, weight timeout, zero threshold, and Open Food Facts country,
language and enablement. All three entities are validated against Home Assistant's
entity registry.

The scanner is configured through two generic sensor entities: `sensor.barcode_scanner_last_barcode` supplies the latest code, while `sensor.barcode_scanner_scan_count` increments on every scan, including repeated identical barcodes. The user confirmed this behavior on the current ESPHome device. Runtime should listen to `state_changed` on the selected counter and then read the selected barcode entity. Publication ordering must be tested to avoid pairing a new counter value with a stale barcode. This design does not require changes to the active firmware.

## Actions

| Action | Purpose | Response |
|---|---|---|
| `add_food` | Add catalogue item | Optional created food |
| `update_food` | Update catalogue item | Optional updated food |
| `delete_food` | Delete catalogue item | None |
| `search_foods` | Search by name/brand | Food list |
| `find_food_by_barcode` | Exact barcode lookup | Food or null |
| `search_openfoodfacts` | Search alternative products by text | Product candidates |
| `add_entry` | Save a weighed portion | Optional created entry |
| `list_entries` | Read entries in a time range | Entry list |
| `delete_entry` | Delete one diary entry | None |
| `period_summary` | Day/week/month totals | Summary object |
| `get_dashboard_data` | Period summary, entries and local catalogue | Dashboard payload |
| `save_pending` | Save a complete pending scan session | Optional saved entry |
| `discard_pending` | Discard the pending scan session | None |
| `get_status` | Read acquisition status and diagnostics | Status object |

Read-only actions use Home Assistant's response-data support. Mutating actions
that return a created/updated record use optional response data. SQLite work is
always dispatched through Home Assistant's executor so synchronous database
operations do not block the event loop.

## Data and safety rules

- The database lives inside the HA configuration directory when installed.
- Nutrients unknown at source remain null, not zero.
- Diary entries retain product/nutrient snapshots.
- The database schema is versioned; version 1 timestamps migrate to version 2.
- Open Food Facts v3 barcode lookup is implemented in the experimental runtime coordinator.
- An experimental coordinator now listens to the selected scan counter and the ESPHome barcode event.
- No Lovelace dashboard or custom frontend is connected yet; the Aurora mockup remains separate.
- The package `homeassistant/packages/food_diary.yaml` remains untouched.

## HACS distribution target

The final product is intended to be a complete, UI-configurable Home Assistant
integration distributed from a dedicated public GitHub repository. The current
Cosori repository will remain the development/prototype home; it is not the
planned HACS package because it also contains firmware and unrelated project
files.

The planned package includes the integration and its Aurora panel in one HACS
integration repository. Setup will let the user select the ESPHome weight
sensor, the last-barcode sensor and the scan-counter sensor through Home Assistant selectors. It will not ask
for BLE MAC addresses or GATT UUIDs.

See [HACS_ARCHITECTURE.md](HACS_ARCHITECTURE.md) for the repository layout,
configurable fields, panel strategy, compatibility policy and release gates.

For the exact handoff state and the next tasks, see [RESUME.md](RESUME.md).

## Validation status

This is a source prototype, not a released integration. It has not been loaded
inside Home Assistant and has not passed hassfest, mypy, config-flow tests, or integration tests.
Before installation, confirm the exact Home Assistant Core version and run
the integration in a disposable/test instance. In particular, service response
APIs and config-entry behavior must be checked against that Core version.

The SQLite storage module is copied into this integration directory to make
the prototype self-contained. Keep it synchronized with
`homeassistant/prototypes/food_diary_sqlite/storage.py` until the integration
is promoted out of the prototypes area.


## Acquisition runtime prototype

The prototype coordinator now listens to the selected scan-count sensor and the selected stable-weight sensor. It also listens for the current ESPHome event esphome.barcode_scanned. The current firmware increments the counter, publishes Last Barcode, then emits a delayed event that reads the current Last Barcode value at event time. The counter gates the event; because the event reads the entity at send time, it is accepted only when one increment is pending and its value matches the selected barcode sensor.

One scan session is accepted at a time. A session requires a zero reading at or below the configured threshold after the scan, followed by a positive stable-weight reading. This protects against a non-empty scale at scan time: the first positive value is ignored until zero is observed and a later positive value arrives. The integration does not command tare; tare remains physical.

Product lookup checks the local catalogue first, then Open Food Facts v3 using Home Assistant's shared aiohttp session. A separate search_openfoodfacts action uses the legacy full-text search endpoint to return alternative candidates without inserting them automatically. Missing or invalid nutrient values remain unknown. Unknown products remain pending for manual catalogue insertion using the same barcode. If a positive weight has already been captured, the timeout is cancelled while waiting for manual product entry.

When automatic save is disabled, or manual review is wanted, use food_diary.save_pending and food_diary.discard_pending. food_diary.get_status returns the acquisition state. Diagnostic sensor entities expose state, last barcode, last stable weight, scan count and pending-session attributes.

Generic scanner fallback: if no ESPHome event arrives, one pending counter increment is resolved from the selected barcode entity after 800 ms. Multiple unmatched increments are marked ambiguous and are never auto-saved.

The current pending session is held in memory; a Home Assistant restart during an incomplete/unknown-product session loses that pending session. The actual catalogue and diary remain in SQLite.

Runtime code is still experimental and has not been loaded in Home Assistant or tested with the physical devices.

Open Food Facts compatibility note: barcode lookup uses the current v3 product API. The text alternative search currently uses the legacy full-text endpoint because Open Food Facts documents full-text search as unavailable in v2/v3 and still served by the legacy endpoint. Keep this isolated behind the coordinator method so it can be replaced when the dedicated search service is available.


Important scan ordering safeguard: the ESPHome event is delayed and reads the current Last Barcode value when it fires; it is not an immutable snapshot of the original scan. The coordinator therefore accepts an event only when exactly one scan-counter increment is pending and the event barcode matches the selected Last Barcode entity. If a second increment overlaps, the sequence is marked ambiguous and nothing is auto-saved.


## Aurora Lovelace card prototype

The integration serves its bundled custom card at `/food_diary/food-diary-card.js`. After installing the integration, add this resource once in Settings → Dashboards → Resources, URL `/food_diary/food-diary-card.js?v=0.1.0`, type JavaScript module. Then import the example view from `homeassistant/prototypes/food_diary_dashboard/dashboard.yaml` or add a card with type `custom:food-diary-aurora`. In YAML Lovelace mode, add the same resource under `lovelace.resources` in configuration.yaml. The resource is served without authentication and contains no secrets. Automatic resource registration is intentionally not used because the documented custom-card workflow uses an explicit dashboard resource; we avoid relying on internal Lovelace resource APIs.

## Durable pending scan recovery

The integration stores one active scanner session in the same SQLite database as the food catalogue and diary. It records only the session ID, barcode, creation timestamp and a 24-hour expiry; it deliberately does not persist the measured weight or assume that a previous scale reading is still valid.

After a Home Assistant restart or config-entry reload, an unexpired session is restored with the product resolved from the local catalogue when available. The user must tare the scale again and obtain a new stable positive weight before the portion can be saved. If the product is unknown, the barcode remains available for manual entry or Open Food Facts search. Sessions expire after 24 hours; the ordinary weight-wait timeout remains separately configurable.

Saving a scanned portion and deleting its pending session happen in the same SQLite transaction. This prevents a restart between those operations from leaving a completed portion queued for a second save. Discarding and timeout also remove the persisted session. Existing database schema version 2 is migrated to version 3 automatically without deleting foods or diary entries.
