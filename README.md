# ha-rest-bed

Home Assistant custom integration for **ReST Performance** smart beds. Provides full local control of ReST bed pumps via their HTTP REST API — no cloud, no app dependency.

## Features

- **SSE push updates** — real-time state via Server-Sent Events (no polling lag)
- **Per-zone firmness control** — 4-zone sliders for manual, back, and side profiles (0–50)
- **Mode selection** — manual, automatic, position, pressure
- **Sleep vitals** — heart rate, respiration, body position, occupancy detection
- **Diagnostics** — CPU/enclosure temperature, firmware version, air pressure per zone
- **Multi-pump** — each side of a split bed is a separate device

## Installation

### HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `HolyBitsLLC/ha-rest-bed` as an **Integration**
3. Install **ReST Performance Bed**
4. Restart Home Assistant

### Manual

Copy `custom_components/rest_bed/` into your HA `config/custom_components/` directory and restart.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **ReST Performance Bed**
3. Enter your pump's IP address
4. Repeat for the second pump (split beds have two pumps)

## Entities per pump

| Platform | Count | Examples |
|----------|-------|---------|
| Number | 16 | Firmness, Distortion, Manual/Back/Side per zone |
| Select | 1 | Mode (manual / automatic / position / pressure) |
| Sensor | 11 | Heart rate, respiration, position, CPU temp, zone pressures, firmware |
| Binary Sensor | 4 | Occupancy, moving, air filling, overheated |
| Switch | 1 | Quiet mode |

## Protocol

The pump exposes an unauthenticated HTTP API on port 80. Real-time updates stream via SSE at `/api/sse`. See the [full protocol specification](https://github.com/HolyBitsLLC/ha-rest-bed/blob/main/docs/protocol.md) for details.

## Tested Hardware

| Model | Firmware | Zones | Status |
|-------|----------|-------|--------|
| P3 (`mab`) | 0.08.003 | 5-zone | ✅ Verified |

## License

MIT
