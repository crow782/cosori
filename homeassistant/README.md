# Home Assistant - Food diary

This folder contains the Home Assistant package for combining the GM67 barcode scanner, Cosori CNS-R101S scale and Open Food Facts.

## Installation

Copy `packages/food_diary.yaml` into your Home Assistant configuration, keeping the directory structure, and enable packages in `configuration.yaml` if they are not already enabled:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

If you already have a `homeassistant:` section, add `packages:` to that existing section rather than creating a duplicate.

The package also defines a `rest_command` for Open Food Facts. No API key is needed for product reads.

## Required ESPHome setup

The package expects:
- Barcode scanner event: `esphome.barcode_scanned`, with `barcode`.
- Stable scale entity: `sensor.cosori_weight_stable`.
- ESPHome action on the scanner: `esphome.barcode_scanner_show_food_result` (created by the updated scanner firmware).

Check the actual entity ID in Home Assistant and adjust the package if you renamed the ESPHome entity. In the ESPHome device integration options, enable **Allow the device to perform Home Assistant actions** for the barcode scanner; otherwise it cannot fire the event.

## Operating sequence

1. Put the empty plate/container on the scale.
2. Tare the scale.
3. Scan the product barcode.
4. Add the food to the plate.
5. When `Cosori Weight Stable` becomes positive, Home Assistant pairs barcode and net weight.
6. Home Assistant calls Open Food Facts API v3 and loads product name, brand, package quantity and available nutrient values per 100 g.
7. Home Assistant calculates the calories for the weighed portion, adds them to the cumulative kcal helper when energy data exists, and calls the ESPHome action to update the OLED.
8. The OLED shows product, weight, portion kcal and cumulative kcal. Products without energy data and unknown barcodes are reported without increasing the total.

The pending barcode is cleared after pairing, so it cannot be reused by a later weight change. Tare again before scanning the next product.

## Entities created

Helpers:
- `input_text.food_diary_pending_barcode`
- `input_text.food_diary_last_barcode`
- `input_text.food_diary_product_name`
- `input_text.food_diary_product_brand`
- `input_text.food_diary_product_quantity`
- `input_text.food_diary_nutriments_json`
- `input_text.food_diary_lookup_status`
- `input_number.food_diary_last_weight_g`
- `input_number.food_diary_total_kcal` (persistent cumulative calorie total)
- `input_button.food_diary_reset_total_kcal` (manual reset)

Calculated portion sensors:
- `sensor.food_diary_portion_energy` (kcal)
- `sensor.food_diary_portion_protein` (g)
- `sensor.food_diary_portion_carbohydrates` (g)
- `sensor.food_diary_portion_sugars` (g)
- `sensor.food_diary_portion_fat` (g)
- `sensor.food_diary_portion_saturated_fat` (g)
- `sensor.food_diary_portion_fiber` (g)
- `sensor.food_diary_portion_salt` (g)

If Open Food Facts does not provide a nutrient, its portion sensor remains `unknown`; missing values are never treated as zero.

## Open Food Facts and request limits

The integration uses `GET /api/v3/product/{barcode}` on `world.openfoodfacts.org`, requests only the fields needed, and sends a descriptive User-Agent. The API does not require a key for read requests. Open Food Facts currently documents a limit of 15 product-read requests per minute per IP; this workflow makes one lookup per weighed item, so normal household use is comfortably below it.

## Current scope and limitations

This version performs barcode lookup, calculates nutrient amounts for the latest weighed portion and maintains a cumulative kcal counter until manually reset. It does **not yet**:
- save a multi-entry historical food diary;
- group entries by breakfast/lunch/dinner/snack or calculate daily totals;
- provide the manual product-entry form or alternative text search when a barcode is absent.

When a barcode is not found, `input_text.food_diary_lookup_status` reports it and the product name shows `Prodotto non trovato`. The next step is to add a manual product form and persistent meal records.

## Testing

After installing the package, use **Settings → System → Repairs → Check configuration** (or the YAML configuration check in your Home Assistant version) before restarting. Then test with a known barcode while listening to `esphome.barcode_scanned` and `esphome.food_diary_weight_ready` in Developer Tools → Events.

This repository change has not been compiled or executed against your live Home Assistant instance. Validate the configuration before relying on it for food logging.
