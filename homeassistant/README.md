# Home Assistant - Food diary bridge

This folder contains the first Home Assistant bridge for combining the GM67 barcode scanner with the Cosori CNS-R101S scale.

## Installation

Copy `packages/food_diary.yaml` into your Home Assistant configuration, keeping the directory structure, and enable packages in `configuration.yaml` if they are not already enabled:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

If you already have a `homeassistant:` section, add `packages:` to that existing section rather than creating a duplicate.

The package expects the ESPHome entities/event below:
- Barcode scanner event: `esphome.barcode_scanned`, with `barcode`.
- Stable scale entity: `sensor.cosori_weight_stable`.

Check the actual entity ID in Home Assistant and adjust the package if you renamed the ESPHome entity.

## Operating sequence

1. Put the empty plate/container on the scale.
2. Tare the scale.
3. Scan the product barcode.
4. Add the food to the plate.
5. When `Cosori Weight Stable` becomes positive, Home Assistant emits `esphome.food_diary_weight_ready` with `barcode` and `weight_g`.

The pending barcode is cleared after the pairing event. This prevents the same barcode from being paired with later weight changes. Tare again before scanning the next product.

## Current scope and limitations

This is deliberately a bridge stage, not yet the complete nutrition diary:
- It pairs one scanned barcode with the next positive stable weight.
- It does not yet query Open Food Facts.
- It does not yet save a persistent food log or calculate meal/day nutrition totals.
- If a barcode is scanned and no food is placed on the scale, the pending barcode remains until another scan replaces it or it is manually cleared.
- The stable sensor rounds to whole grams; readings below 1 g may remain 0 g and will not trigger the pairing automation.

The next stage is to add product lookup, fallback/manual product entry, persistent meal records and nutrition summaries.
