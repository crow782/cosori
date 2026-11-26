# Cosori CNS-R101S – ESPHome / Home Assistant

Independent investigation of the **Cosori Nutrition Scale CNS-R101S** for a local BLE integration with ESP32, ESPHome and Home Assistant.

> Project status: **BLE identification, connection, GATT map and first weight-correlated notification payloads confirmed; packet decoding still in progress.**

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
| BLE address | `C0:60:40:03:9F:6D` | Confirmed |
| Address type | `PUBLIC` | Confirmed |
| Advertised service UUID | `0x1910` | Confirmed in scan |
| GATT connection | Connection opened successfully | Confirmed |
| Service discovery | Completed successfully | Confirmed |
| Negotiated MTU | `131` | Confirmed |

## GATT map captured with nRF Connect

The following services and characteristics were visible in nRF Connect for the connected scale.

### Standard services

| Service | Characteristic | UUID | Properties |
|---|---|---|---|
| Generic Access (`0x1800`) | Device Name | `0x2A00` | READ |
| Generic Access (`0x1800`) | Appearance | `0x2A01` | READ |
| Generic Access (`0x1800`) | Peripheral Privacy Flag | `0x2A02` | READ |
| Generic Access (`0x1800`) | Peripheral Preferred Connection Parameters | `0x2A04` | READ |
| Generic Attribute (`0x1801`) | No characteristics shown | — | — |
| Device Information (`0x180A`) | Hardware Revision String | `0x2A27` | READ |
| Device Information (`0x180A`) | Firmware Revision String | `0x2A26` | READ |

### Cosori service `0x1910`

| Characteristic | UUID | Properties | Initial interpretation |
|---|---|---|---|
| Service Cycle Data | `0x2C11` | WRITE, WRITE WITHOUT RESPONSE | Writable characteristic; possible command/input |
| IMD Control | `0x2C12` | NOTIFY | Notification source; must capture payloads |
| Work Cycle Data | `0x2C10` | READ | Readable data; content not yet inspected |

Descriptors shown:
- `0x2901` Characteristic User Description
- `0x2902` Client Characteristic Configuration (on the notifying characteristic)

### Additional proprietary service

- Service UUID: `f000ffc0-0451-4000-b000-000000000000`

| Characteristic UUID | Properties |
|---|---|
| `f000ffc1-0451-4000-b000-000000000000` | NOTIFY, WRITE, WRITE WITHOUT RESPONSE |
| `f000ffc2-0451-4000-b000-000000000000` | NOTIFY, WRITE, WRITE WITHOUT RESPONSE |

Both characteristics show descriptors `0x2902` (Client Characteristic Configuration) and `0x2901` (Characteristic User Description).

**Important:** the GATT map confirms the available properties, not which characteristic carries the weight. Initial notification payloads have now been captured on `0x2C12`; see the payload section below. No command should be written until the protocol is understood.

## Work completed

1. Set up ESPHome BLE scanning on the ESP32.
2. Identified the scale by advertised name and BLE address.
3. Established a direct ESPHome `ble_client` connection.
4. Confirmed GATT connection and service discovery.
5. Used nRF Connect to inspect the GATT services and characteristic properties.
6. Identified three candidate notification/read paths: `0x1910/0x2C12`, proprietary `ffc1` and `ffc2`, plus readable `0x1910/0x2C10`.

## Diagnostic configuration

A starting ESPHome configuration is provided in [`esphome/cosori-diagnostic.yaml`](esphome/cosori-diagnostic.yaml). It uses `!secret` references for Wi-Fi credentials. Never commit credentials or API encryption keys.

The Bluetooth Proxy is intentionally omitted while the ESP32 is being tested as a direct GATT client.

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

ESPHome requires component-specific log levels not to be more verbose than the global level. This filter reduces advertisement noise; it does not itself enable or guarantee a GATT characteristic dump.

## First notification payloads captured on `0x1910/0x2C12`

nRF Connect showed notifications enabled on the IMD Control characteristic (`0x2C12`). Two payloads were captured under different load conditions:

| Scale condition | Raw notification (hex) |
|---|---|
| Unloaded (displayed 0 g) | `FE EF 00 84 D0 05 00 00 00 00 01 D6` |
| Loaded (displayed 520 g) | `FE EF 00 84 D0 05 00 14 50 00 01 3A` |

The bytes at offsets 7–8 (zero-based) change from `00 00` to `14 50`. Interpreted as a big-endian unsigned integer, these are 0 and 5200 respectively. Since the scale displayed 520 g in the second test, a tentative hypothesis is that this field represents tenths of a gram (raw value / 10).

**This is only a preliminary hypothesis based on two samples.** More known weights are required to confirm byte order, scale factor, stability/streaming behavior and any status/tare fields. The final byte also changes (`D6` to `3A`); its role (checksum, counter or other field) is unknown.

These captures establish that `0x2C12` emits changing notifications correlated with the scale load. Continue capturing this characteristic before investigating the other proprietary notification characteristics.

## Unverified protocol details

The following are not yet confirmed:
- Which notification characteristic carries live weight measurements.
- Whether a write/initialization command is required.
- Measurement packet format, units, sign and precision.
- Whether the proprietary `ffc1` / `ffc2` service is involved in weighing.

Do not treat any assumed packet type or scale factor as established until raw data is captured.

## Next steps

1. Enable notifications on one candidate characteristic at a time (`0x1910/0x2C12`, then proprietary `ffc1` and `ffc2`).
2. Record raw notification bytes while the scale is idle, touched, and loaded with known weights.
3. Read `0x1910/0x2C10` and inspect the `0x2901` user-description descriptors where available.
4. Determine whether a documented/observed write command is necessary; do not send arbitrary bytes.
5. Decode and validate the payload against known weights.
6. Implement and test the ESPHome sensor before documenting final Home Assistant setup.

## Security and privacy

- Never commit Wi-Fi passwords, API encryption keys, tokens or personal secrets.
- Keep local credentials in ESPHome's `secrets.yaml`, excluded from version control.
- This is an independent community reverse-engineering effort and is not affiliated with or endorsed by Cosori.
