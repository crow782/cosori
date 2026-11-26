# Cosori CNS-R101S – ESPHome / Home Assistant

Independent investigation of the Cosori Nutrition Scale CNS-R101S for local BLE integration with ESP32, ESPHome and Home Assistant.

> Project status: BLE identification, GATT map and weight-field decoding validated against three samples. Discovery and integration configurations have been added; compile/device validation is the next step.

## Firmware files

- [esphome/cosori-discovery.yaml](esphome/cosori-discovery.yaml): scans for a Cosori scale and logs its BLE address and advertised service UUIDs. Use this for a new physical scale.
- [esphome/cosori-cns-r101s.yaml](esphome/cosori-cns-r101s.yaml): main CNS-R101S integration; connects to the configured MAC, decodes weight notifications, and exposes raw and stable weight sensors.
- [esphome/cosori-diagnostic.yaml](esphome/cosori-diagnostic.yaml): earlier connection/GATT diagnostic configuration.

All configurations require wifi_ssid, wifi_password and fallback_ap_password in ESPHome secrets.yaml. The barcode scanner also requires api_encryption_key (generate it with openssl rand -base64 32). Never commit credentials or API keys.

## Finding another scale

Flash cosori-discovery.yaml to an ESP32 and open ESPHome logs. It reports a candidate when the advertised name contains COSORI (the observed full name is COSORI Nutrition Scale) or an advertised service UUID contains 1910. The log includes the BLE address, RSSI and advertised service UUIDs.

Copy the discovered address into mac_address in cosori-cns-r101s.yaml. Do not reuse the MAC from another physical scale: C0:60:40:03:9F:6D belongs only to the unit used for this investigation. The name and service UUID are discovery clues; the MAC is the connection target for the main firmware.

## Confirmed BLE observations

| Item | Observed value | Status |
|---|---|---|
| Advertised device name | COSORI Nutrition Scale | Confirmed |
| BLE address of test unit | C0:60:40:03:9F:6D | Confirmed |
| Address type | PUBLIC | Confirmed |
| Advertised service UUID | 0x1910 | Confirmed |
| GATT connection and service discovery | Successful | Confirmed |
| Negotiated MTU | 131 | Confirmed |

## GATT map

Service 0x1910:

| Characteristic | UUID | Properties |
|---|---|---|
| Service Cycle Data | 0x2C11 | WRITE, WRITE WITHOUT RESPONSE |
| IMD Control | 0x2C12 | NOTIFY |
| Work Cycle Data | 0x2C10 | READ |

Additional proprietary service f000ffc0-0451-4000-b000-000000000000:

| Characteristic UUID | Properties |
|---|---|
| f000ffc1-0451-4000-b000-000000000000 | NOTIFY, WRITE, WRITE WITHOUT RESPONSE |
| f000ffc2-0451-4000-b000-000000000000 | NOTIFY, WRITE, WRITE WITHOUT RESPONSE |

Weight notifications captured so far come from 0x1910/0x2C12. The current firmware sends no BLE writes.

## Captured payloads and decoder

| Scale reading | Raw notification (hex) | Bytes 7–8 | Big-endian integer |
|---:|---|---|---:|
| 0 g | FE EF 00 84 D0 05 00 00 00 00 01 D6 | 00 00 | 0 |
| 520 g | FE EF 00 84 D0 05 00 14 50 00 01 3A | 14 50 | 5200 |
| 1001 g | FE EF 00 84 D0 05 00 27 1A 00 01 17 | 27 1A | 10010 |

The field at zero-based offsets 7–8, interpreted as an unsigned big-endian 16-bit integer and divided by 10, matches all three readings:

weight_g = ((payload[7] << 8) | payload[8]) / 10.0

This is a strongly supported preliminary decoder for the observed positive integer-weight samples. Fractional weights, negative/overload/status values, tare behavior and the role of the final byte still need validation. The final byte varies and is not assumed to be a checksum.

## Main firmware sensors and stability

The main firmware exposes two entities:
- Cosori Weight Raw: decoded value from every valid notification at 0.1 g resolution, useful for diagnostics and observing fluctuations. It declares unit g, device_class weight and state_class measurement.
- Cosori Weight Stable: rounds each decoded reading to the nearest whole gram and publishes only after the rounded value has remained unchanged for 1.5 seconds. It declares unit g, device_class weight and state_class measurement, with zero decimal places.

Stability timing is event-driven: the raw sensor's on_value handler starts or resets the timer only when the rounded whole-gram candidate changes. A separate 100 ms interval checks whether 1.5 seconds have elapsed and publishes the stable integer-gram value. This avoids resetting the timer for sub-gram BLE fluctuations and avoids relying on polling the raw sensor to detect changes. Use Cosori Weight Stable in Home Assistant automations; keep Raw for diagnostics.

The firmware validates the observed packet header and minimum length before decoding. It does not send BLE writes to the scale. The revised stability logic is committed but still requires compilation and on-device validation.

## Security

- Never commit Wi-Fi passwords, API encryption keys, tokens or personal secrets.
- Keep credentials in ESPHome secrets.yaml, excluded from version control.
- This is an independent community reverse-engineering effort and is not affiliated with or endorsed by Cosori.

## Barcode scanner and food diary

The optional GM67 barcode scanner firmware is in [barcode scanner.yaml](barcode%20scanner.yaml). It sends `esphome.barcode_scanned` directly through the ESPHome API; no HTTP middleware is required.

The first Home Assistant bridge is in [homeassistant/README.md](homeassistant/README.md), with the package at [homeassistant/packages/food_diary.yaml](homeassistant/packages/food_diary.yaml). The intended workflow is: tare the empty plate, scan the product, add the food, then pair the barcode with the next positive stable scale reading.

The Home Assistant package now performs Open Food Facts v3 lookup and calculates nutrient amounts for the latest weighed portion. Manual product entry, persistent multi-entry diary storage and meal/day totals are still planned.
