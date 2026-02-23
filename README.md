# ha-pc-remote

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant custom integration for controlling a Windows PC via [ha-pc-remote-service](https://github.com/NeskireDK/ha-pc-remote-service).

## Requirements

- [ha-pc-remote-service](https://github.com/NeskireDK/ha-pc-remote-service) running on the target Windows PC
- Home Assistant 2024.1.0+

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Install "PC Remote"
3. Restart Home Assistant
4. Go to Settings > Integrations > Add > PC Remote

### Manual

Copy `custom_components/pc_remote/` to your Home Assistant `custom_components/` directory.

## Setup

Two ways to add the integration:

- **Zeroconf** -- Auto-discovered on your network. Just confirm and enter the API key.
- **Manual** -- Enter host, port, and API key from the Windows service.

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| Online | Binary Sensor | PC connectivity status |
| Sleep | Button | Put PC to sleep |
| Audio Output | Select | Switch default audio output device |
| Volume | Number | Master volume (0-100) |
| Monitor Profile | Select | Apply a saved `.cfg` monitor profile |
| Active Monitor | Select | Switch to a single monitor (solo mode) |
| Steam | Media Player | Launch Steam games; shows BUFFERING + wakes PC if offline |
| {App Name} | Switch | Launch/kill configured apps |

App switches are created dynamically based on apps configured in the Windows service.

## Roadmap

### Wake-and-play (implemented in v0.9.0)

The Steam media player caches the game list locally, so the source list remains populated even when the PC is off and across HA restarts. Selecting a game while the PC is off automatically wakes and launches it.

- [x] When a game is selected and `online = false`, send a WoL magic packet
- [x] Poll `/api/health` until the service responds (PC is up)
- [x] Poll `/api/steam/running` until Steam is reachable (Steam may take longer to start than the service)
- [x] Launch the game via `/api/steam/run/{appId}`

## License

MIT
