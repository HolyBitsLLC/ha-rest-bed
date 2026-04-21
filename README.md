# ha-rest-bed

Home Assistant custom integration for **ReST Performance** smart beds. Provides full local control of ReST bed pumps via their HTTP REST API — no cloud, no app dependency.

## Features

- **SSE push updates** — real-time state via Server-Sent Events (no polling lag)
- **Mode hierarchy support** — manual, automatic, position, and pressure modes
- **Automatic tuning controls** — firmness and sensitivity controls surfaced directly in HA
- **Per-zone firmness control** — 4-zone sliders for Manual mode plus a Position profile editor for Back/Side tuning
- **Guided calibration** — captures an empty-bed surface baseline, then applies calibrated targets to Manual plus the detected Back/Side profile
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
| Number | 20 | Firmness, Sensitivity, Manual per-zone, Position per-zone, advanced Back/Side editors |
| Select | 2 | Mode, Position Profile |
| Sensor | 11 | Heart rate, respiration, position, CPU temp, zone pressures, firmware |
| Binary Sensor | 4 | Occupancy, moving, air filling, overheated |
| Switch | 1 | Quiet mode |

## WiFi Setup Utility

A standalone CLI tool (`tools/rest_bed_setup.py`) replicates the official Android app's WiFi setup flow. Zero external dependencies — uses only the Python standard library.

### When you need it

If a pump loses its WiFi connection it falls back to **AP / hotspot mode**, broadcasting an SSID like `ReST-XXXXXX`. The official app may not always be available, so this utility lets you reconfigure WiFi from any computer with Python 3.

### Quick start

```bash
# 1. Connect your computer to the pump's hotspot (ReST-XXXXXX)
# 2. Interactive setup (pump defaults to 10.0.0.1):
python3 tools/rest_bed_setup.py setup

# Non-interactive — set WiFi directly:
python3 tools/rest_bed_setup.py wifi --host 10.0.0.1 \
  --ssid "MyNetwork" --password "MyPassword"
```

### All commands

| Command | Description |
|---------|-------------|
| `setup` | Interactive first-time WiFi setup (connect to pump AP first) |
| `wifi` | Set WiFi credentials on a reachable pump |
| `status` | Show device info, WiFi, firmware, cloud, temperatures |
| `scan` | List WiFi networks visible to the pump |
| `direct` | Switch pump to AP / hotspot mode |
| `indirect` | Switch pump to WiFi client mode |
| `dump` | Dump full `/api` state as JSON |

### Examples

```bash
# Check status of a pump on your network
python3 tools/rest_bed_setup.py status --host 10.0.17.182

# Scan what WiFi networks the pump can see
python3 tools/rest_bed_setup.py scan --host 10.0.17.182

# Force a pump back into AP mode (for troubleshooting)
python3 tools/rest_bed_setup.py direct --host 10.0.17.182

# Dump full device state as JSON
python3 tools/rest_bed_setup.py dump --host 10.0.17.182
```

### WiFi setup protocol

| Step | Endpoint | Method | Payload |
|------|----------|--------|---------|
| 1 | Pump broadcasts AP `ReST-<mac>` at `10.0.0.1` | — | — |
| 2 | `/api/wifi/list` | GET | Returns visible SSIDs |
| 3 | `/api/wifi` | PUT | `{"ssid": "...", "password": "..."}` |
| 4 | `/api/wifi/mode` | PUT | `"indirect"` (switches from AP to client) |

Position-mode editing is exposed two ways:

- **Primary workflow** — switch the bed to `position`, choose `Position Profile` (`back` or `side`), then adjust the 4 `Position ...` sliders.
- **Advanced workflow** — raw `Back ...` and `Side ...` number entities still exist for direct editing, but are disabled by default on new installs to keep the primary UI closer to the mobile app.

## Protocol

The pump exposes an unauthenticated HTTP API on port 80. Real-time updates stream via SSE at `/api/sse`. See the [full protocol specification](https://github.com/HolyBitsLLC/ha-rest-bed/blob/main/docs/protocol.md) for details.

## Tested Hardware

| Model | Firmware | Zones | Status |
|-------|----------|-------|--------|
| P3 (`mab`) | 0.08.003 | 5-zone | ✅ Verified |

## License

MIT
