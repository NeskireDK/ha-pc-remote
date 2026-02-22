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
| {App Name} | Switch | Launch/kill configured apps |

App switches are created dynamically based on apps configured in the Windows service.

## Roadmap

### Wake-and-play

The Steam media player caches the game list locally, so the source list remains populated even when the PC is off and across HA restarts. The next step is full wake-and-play: selecting a game while the PC is off will automatically wake and launch it.

Planned steps:

- [ ] When a game is selected and `online = false`, send a WoL magic packet
- [ ] Poll `/api/health` until the service responds (PC is up)
- [ ] Poll `/api/steam/running` until Steam is reachable (Steam may take longer to start than the service)
- [ ] Launch the game via `/api/steam/run/{appId}`

## Known Issues

### Steam: Selecting a source does not launch the game

`async_select_source` correctly finds the `appId` and calls `POST /api/steam/run/{appId}`.
The service endpoint returns 200 OK immediately, so the integration thinks the launch succeeded.

The actual launch is executed by the **tray app** via IPC (`IpcSteamPlatform`). If the tray is
not running, `IpcSteamPlatform.Send` silently returns `null` (logs a warning) and the endpoint
still returns 200. No game launches. There is no error visible in HA.

Fix options (service-side):
- Return 503 from the endpoint when IPC is unavailable, so HA can surface the error
- Or ensure the tray is always running as a prerequisite before the service accepts Steam requests

### Steam: Currently playing game is not highlighted in the source list

`media_player.source` returns `running.get("name")` from `GET /api/steam/running`.
`media_player.source_list` returns game names from `GET /api/steam/games`.

The running game name is resolved on the service via `SteamService._cachedGames`. Two scenarios
where the name won't match an entry in `source_list`:

1. **Cache not yet warm**: If `GetRunningGameAsync` is called before `GetGamesAsync` has
   run at least once in this service process, `_cachedGames` is `null` and the name falls back
   to `"Unknown ({appId})"`. This is unlikely during normal coordinator polling (games are
   fetched first), but possible on service cold-start with a game already running.

2. **Running game outside top-20**: `GetGamesAsync` returns only the 20 most recently played
   games sorted by `LastUpdated`. If the currently running game has not been played recently
   enough to appear in the list, `source` returns a valid name but it is absent from
   `source_list`. HA displays the state but the dropdown has no match highlighted.

Fix options (service-side):
- `GetRunningGameAsync` should call `GetGamesAsync()` internally to ensure cache is warm
- Include the running game in the list even if it falls outside the top-20 cutoff

### Monitor profiles: entity shows empty option list

`GET /api/monitor/profiles` returns an empty list if the `ProfilesPath` directory does not exist next to the service exe. The entity has no options to select.

Fix: create the `monitor-profiles/` directory next to `HaPcRemote.Service.exe` and add `.cfg` files exported from MultiMonitorTool.

## License

MIT
