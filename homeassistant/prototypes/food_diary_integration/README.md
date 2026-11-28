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
- `services.py`: Home Assistant actions and input validation.
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
- an ESPHome device selected as the barcode scanner.

The options flow allows changing both selections and configuring default meal,
automatic save, weight timeout, zero threshold, and Open Food Facts country,
language and enablement. Device selections are checked against Home Assistant's
entity and device registries.

This is still not end-to-end functional: the current ESPHome firmware event
contains only `barcode`, so it does not yet identify which ESPHome node sent
the scan. The firmware/event contract must add a stable scanner node identifier
before the selected scanner can be enforced at runtime. No active firmware was
changed.

## Actions

| Action | Purpose | Response |
|---|---|---|
| `add_food` | Add catalogue item | Optional created food |
| `update_food` | Update catalogue item | Optional updated food |
| `delete_food` | Delete catalogue item | None |
| `search_foods` | Search by name/brand | Food list |
| `find_food_by_barcode` | Exact barcode lookup | Food or null |
| `add_entry` | Save a weighed portion | Optional created entry |
| `list_entries` | Read entries in a time range | Entry list |
| `delete_entry` | Delete one diary entry | None |
| `period_summary` | Day/week/month totals | Summary object |

Read-only actions use Home Assistant's response-data support. Mutating actions
that return a created/updated record use optional response data. SQLite work is
always dispatched through Home Assistant's executor so synchronous database
operations do not block the event loop.

## Data and safety rules

- The database lives inside the HA configuration directory when installed.
- Nutrients unknown at source remain null, not zero.
- Diary entries retain product/nutrient snapshots.
- The database schema is versioned; version 1 timestamps migrate to version 2.
- No barcode lookup to Open Food Facts is implemented in this integration yet.
- No automatic Cosori/GM67 event subscription is implemented yet.
- No Lovelace dashboard or custom frontend is included yet.
- The package `homeassistant/packages/food_diary.yaml` remains untouched.

## HACS distribution target

The final product is intended to be a complete, UI-configurable Home Assistant
integration distributed from a dedicated public GitHub repository. The current
Cosori repository will remain the development/prototype home; it is not the
planned HACS package because it also contains firmware and unrelated project
files.

The planned package includes the integration and its Aurora panel in one HACS
integration repository. Setup will let the user select the ESPHome weight
sensor and scanner device through Home Assistant selectors. It will not ask
for BLE MAC addresses or GATT UUIDs.

See [HACS_ARCHITECTURE.md](HACS_ARCHITECTURE.md) for the repository layout,
configurable fields, panel strategy, compatibility policy and release gates.

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
