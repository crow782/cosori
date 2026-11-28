# Food Diary – Home Assistant integration prototype

> **Experimental only. Do not install in the active Home Assistant instance.**
> This folder is separate from the current packages and ESPHome firmware. The
> component is not yet validated against the user's Home Assistant Core version.

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
- `strings.json`: UI translations.
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

## Validation status

This is a source prototype, not a released integration. It has not been loaded
inside Home Assistant and has not passed hassfest, mypy, or integration tests.
Before installation, confirm the exact Home Assistant Core version and run
the integration in a disposable/test instance. In particular, service response
APIs and config-entry behavior must be checked against that Core version.

The SQLite storage module is copied into this integration directory to make
the prototype self-contained. Keep it synchronized with
`homeassistant/prototypes/food_diary_sqlite/storage.py` until the integration
is promoted out of the prototypes area.
