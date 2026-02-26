# ha-pc-remote

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant custom integration for controlling a PC remotely via [ha-pc-remote-service](https://github.com/NeskireDK/ha-pc-remote-service). Supports Windows (tray app) and Linux (headless daemon).

## Requirements

- [ha-pc-remote-service](https://github.com/NeskireDK/ha-pc-remote-service) v1.2.2+ running on the target PC
- Home Assistant 2024.6.0+

## Installation

### HACS (Recommended)

1. Open HACS → Integrations → Search "PC Remote"
2. Install and restart Home Assistant
3. Go to Settings > Integrations > Add > PC Remote

### Manual

Copy `custom_components/pc_remote/` to your Home Assistant `custom_components/` directory.

## Setup

Two ways to add the integration:

- **Zeroconf** — Auto-discovered on your network. Just confirm and enter the API key.
- **Manual** — Enter host, port, and API key from the service config.

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| Online | Binary Sensor | PC connectivity status |
| Sleep | Button | Put PC to sleep |
| PC Mode | Select | Apply a named mode (audio + monitors + volume + app) |
| Audio Output | Select | Switch default audio output device |
| Volume | Number | Master volume (0-100) |
| Monitor Profile | Select | Apply a saved `.cfg` monitor profile |
| Active Monitor | Select | Switch to a single monitor (solo mode) |
| Steam | Media Player | Launch Steam + non-Steam games via source list or media browser; artwork thumbnails from local cache; turn on wakes PC via WoL, turn off sleeps PC |
| Idle Duration | Sensor | Seconds since last keyboard/mouse input on the PC |
| {App Name} | Switch | Launch/kill configured apps |

App switches are created dynamically based on apps configured in the service. PC Mode options come from the `Modes` config section.

## Blueprints

Two automation blueprints are included:

- **Couch Gaming** — switches PC Mode, wakes the PC, and launches a Steam game in one action
- **Post-Session Sleep** — when the Steam player goes idle, waits N minutes and sleeps the PC

## Roadmap

See [PLANNED_FEATURES.md](https://github.com/NeskireDK/ha-pc-remote-service/blob/main/PLANNED_FEATURES.md) in the service repo for bugs, planned features, and version roadmap covering both repositories.

## License

MIT
