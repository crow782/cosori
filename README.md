# Cosori CNS-R101S – ESPHome / Home Assistant

Independent investigation of the **Cosori Nutrition Scale CNS-R101S** for a local BLE integration with ESP32, ESPHome and Home Assistant.

> Project status: **BLE identification and connection confirmed; GATT characteristic discovery and weight decoding still in progress.**

## Hardware and software

- Scale: Cosori Nutrition Scale, model **CNS-R101S**
- ESP32: ESP32 DevKit / ESP32-WROOM (board configured as `esp32dev`)
- Firmware: ESPHome **2026.11.1**
- Framework: ESP-IDF
- Target: Home Assistant, with local BLE communication

## Confirmed BLE observations

| Item | Observed value | Status |
|---|---|---|
| Advertised device name | `COSORI Nutrition Scale` | Confirmed |
| BLE address | `C0:60:40:03:9F:6D` | Confirmed in scans and connection log |
| Address type | `PUBLIC` | Confirmed |
| Advertised service UUID | `0x1910` | Seen in earlier scanner output |
| RSSI | About `-48` to `-50 dBm` during connection tests | Observed |
| GATT connection | Connection opened successfully | Confirmed |
| Service discovery procedure | `ESP_GATTC_SEARCH_CMPL_EVT`; “Service discovery complete” | Confirmed |
| Negotiated MTU | `131` | Confirmed |

The device name and MAC address identify the target as the Cosori scale. The connection logs prove that the ESP32 can establish a GATT connection and complete ESPHome's service-discovery procedure.

**Important:** the logs collected so far do not include a usable list of GATT characteristics, their handles, or their properties. The advertised UUID `0x1910` is not, by itself, a complete GATT map.

## Work completed

1. Set up ESPHome BLE scanning on the ESP32.
2. Identified the scale among nearby BLE advertisers.
3. Matched the advertiser to the name `COSORI Nutrition Scale` and address `C0:60:40:03:9F:6D`.
4. Established a direct ESPHome `ble_client` connection.
5. Confirmed GATT connection-open and service-discovery-complete events.
6. Observed successful MTU negotiation to 131.
7. Began reducing verbose BLE scan logging to make diagnostic output readable.

## Diagnostic configuration

The current investigation uses ESPHome's `esp32_ble_tracker` and `ble_client` components to connect directly to the scale. The Bluetooth Proxy was removed from the diagnostic configuration so the ESP32 can focus on acting as a GATT client.

A minimal starting configuration is provided in [`esphome/cosori-diagnostic.yaml`](esphome/cosori-diagnostic.yaml).

The YAML intentionally uses `!secret` references for Wi-Fi credentials. Put the actual credentials in the ESPHome secrets file; do not commit credentials or API encryption keys.

## Logging

A useful starting point for quieter logs while retaining client diagnostics is:

```yaml
logger:
  level: DEBUG
  logs:
    esp32_ble_tracker: WARN
    esp32_ble: WARN
    esp32_ble_client: DEBUG
    ble_client: DEBUG
```

ESPHome requires component-specific log levels not to be more verbose than the global level. In particular, `DEBUG` for a component with global `INFO` produces a configuration warning. The global level above is therefore `DEBUG`.

This filter reduces advertisement noise. It does **not** itself enable or guarantee a GATT characteristic dump.

## Unverified protocol hypotheses

The following details were mentioned during preliminary investigation but have **not** been confirmed from a characteristic dump or captured measurement payload:

- Characteristic UUIDs `0x2C12` and `0x2C11`
- Measurement packet type `0xD0`
- Weight scale factor or precision of 0.1 g
- Any required initialization or write command

Do not use these as established protocol facts until verified against the device.

## Next steps

1. Obtain a complete GATT service and characteristic listing, including UUIDs, handles and properties.
2. Identify the characteristic that provides measurement notifications or indications.
3. Determine whether the scale requires a write/initialization command.
4. Capture raw payloads while placing known weights on the scale.
5. Reverse engineer the payload format, units, sign and precision.
6. Implement a robust ESPHome sensor and validate it against known weights.
7. Document Home Assistant entity behavior and setup.

## Security and privacy

- Never commit Wi-Fi passwords, API encryption keys, tokens or personal secrets.
- Keep local credentials in ESPHome's `secrets.yaml`, excluded from version control.
- This is an independent community reverse-engineering effort and is not affiliated with or endorsed by Cosori.
