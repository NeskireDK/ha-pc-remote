# ha-windows-remote

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for controlling a Windows PC via the [ha-windows-remote-service](https://github.com/NeskireDK/ha-windows-remote-service).

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Install "Windows Remote"
3. Restart Home Assistant
4. Go to Settings → Integrations → Add → Windows Remote
5. Enter the IP, port, and API key from the Windows service

### Manual

Copy `custom_components/windows_remote/` to your Home Assistant `custom_components/` directory.

## Entities

| Entity | Type | Description | Status |
|--------|------|-------------|--------|
| `binary_sensor.windows_remote_online` | Binary Sensor | PC online status | Done |
| `button.windows_remote_sleep` | Button | Suspend the PC | Done |
| `select.windows_remote_audio_output` | Select | Switch audio output device | Planned |
| `number.windows_remote_volume` | Number | Master volume (0-100) | Planned |
| `select.windows_remote_monitor_profile` | Select | Switch monitor profile | Planned |
| `button.windows_remote_launch_{key}` | Button | Launch predefined app | Planned |
| `binary_sensor.windows_remote_{key}` | Binary Sensor | App running status | Planned |

## Roadmap

- [x] Config flow (host, port, API key)
- [x] Online binary sensor (health polling)
- [x] Sleep button
- [x] HACS-compliant structure
- [x] GitHub Actions release
- [ ] Audio output device selector
- [ ] Volume control
- [ ] Monitor profile selector
- [ ] App launch buttons
- [ ] App running sensors
- [ ] mDNS/Zeroconf auto-discovery

## License

MIT
