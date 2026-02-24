# ha-pc-remote

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant custom integration for controlling a PC remotely via [ha-pc-remote-service](https://github.com/NeskireDK/ha-pc-remote-service). Supports Windows (tray app) and Linux (headless daemon).

## Requirements

- [ha-pc-remote-service](https://github.com/NeskireDK/ha-pc-remote-service) v1.0+ running on the target PC
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
| Steam | Media Player | Launch Steam games via source list or media browser; wakes PC if offline |
| Idle Time | Sensor | Seconds since last keyboard/mouse input on the PC |
| {App Name} | Switch | Launch/kill configured apps |

App switches are created dynamically based on apps configured in the service. PC Mode options come from the `Modes` config section.

## Blueprints

Two automation blueprints are included:

- **Couch Gaming** — switches PC Mode, wakes the PC, and launches a Steam game in one action
- **Post-Session Sleep** — when the Steam player goes idle, waits N minutes and sleeps the PC

## Roadmap

- [x] Wake-and-play: WoL + poll + Steam launch when PC is off *(v0.9.0)*
- [x] PC Mode select entity *(v1.0)*
- [x] Aggregated state coordinator (single poll call) *(v1.0)*
- [x] Couch Gaming + Post-Session Sleep blueprints *(v1.0)*
- [x] User Idle Time sensor *(v1.0.2)*
- [x] Steam media browser (browse + play) *(v1.0.2)*

## License

MIT
