# Planned Features

Goal: seamless couch gaming with a desktop PC that power-saves when not in use.
The PC is a multi-function machine — desktop (keyboard + mouse, multiple monitors) and
couch/TV (controller, living room display). Switching between these modes gracefully is
the core use case.

---

## Blockers (fix before v1.0)

These are documented bugs that undermine trust in the integration.

- [x] **Steam: tray 503** — `POST /api/steam/run/{appId}` returns 200 even when the tray
  is not running and no game launches. Fixed in service v0.9.0: `IpcSteamPlatform` throws
  `TrayUnavailableException` → endpoint returns 503. *(service)*

- [x] **Steam: running game not in source list** — `GetRunningGameAsync` falls back to
  `"Unknown ({appId})"` if the games cache isn't warm. Fixed in service v0.9.0:
  `GetRunningGameAsync` warms cache on first call and falls back to direct manifest
  lookup for games outside the top-20. *(service)*

---

## Architecture Refactor — Collapse Service + Tray into Single Process *(done in v0.9.1)*

### Background

The old architecture had a Windows Service (SYSTEM session) and a WinForms tray app (user session) communicating via named pipe IPC. Every meaningful feature required the user session anyway — audio, monitors, Steam, app launch. Collapsed everything into the tray process. Kestrel runs inside the tray. No IPC, no session boundary, no `TrayUnavailableException`. Linux gets a natural headless binary as well.

### Releases

#### ~~0.9.2~~ — Extract `HaPcRemote.Core` library *(shipped in v0.9.1)*

- [x] Create `HaPcRemote.Core` class library
- [x] Move services, interfaces, implementations, endpoints, models into Core
- [x] `HaPcRemote.Tray` references Core
- [x] Update test project references

#### ~~0.9.3~~ — Embed Kestrel in Tray, replace IPC with direct calls *(shipped in v0.9.1)*

- [x] Add ASP.NET Core / Kestrel hosting to `HaPcRemote.Tray`
- [x] Wire all Core services into Tray's DI container
- [x] Replace IPC wrappers with direct calls (`WindowsSteamPlatform`, `CliRunner`, `Process.Start`)
- [x] Migrate config path to `%AppData%\HaPcRemote\`

#### ~~0.9.4~~ — Delete Service project, IPC layer, update installer *(shipped in v0.9.1)*

- [x] Delete `HaPcRemote.Service` project
- [x] Delete IPC layer and wrappers
- [x] Update Inno Setup installer (no service registration, startup via all-users startup folder, config migration)
- [x] Update README

#### 0.9.5 — Linux foundation *(service repo)* *(done)*

Same binary, headless mode, systemd user service.

- [x] Wrap all WinForms/tray code behind `OperatingSystem.IsWindows()` / `[SupportedOSPlatform]`
- [x] Add Linux `IPowerService`: `systemctl suspend` or `loginctl suspend`
- [x] Add Linux `ISteamPlatform`: filesystem path (`~/.steam/steam/`), running game via VDF, launch via `xdg-open steam://run/<id>`
- [x] Add Linux audio (`pactl`-based `LinuxAudioService`)
- [x] Add headless entry point (Linux): plain Kestrel + mDNS, no tray icon, SIGTERM clean exit
- [x] Add systemd user service unit file to release artifacts
- [x] Add Linux build job to GitHub Actions CI
- [x] Document install steps in README

### Key decisions made

- **Why collapse?** Every feature requires the user session. IPC is complexity with no benefit.
- **Config path**: moves to `%AppData%` (user-owned, no elevation needed for reads/writes)
- **Native AOT**: dropped — framework-dependent is fine, .NET 10 auto-install already ships
- **Linux tray**: no system tray on Linux. API key via config file, logs via `journalctl`, updates via package manager — these are Linux-native equivalents, not a degraded experience.
- **Monitor profiles on Linux**: xrandr/Wayland too fragmented — skip initially, document as known gap

---

## v1.0

### 1. PC Mode — `POST /api/system/mode` + `select` entity *(done in v1.0)*

Single endpoint that atomically sequences audio output, monitor profile, volume, and
app launch/kill from a named config block.

```json
"Modes": {
  "couch": {
    "AudioDevice": "HDMI Output",
    "MonitorProfile": "tv-only",
    "Volume": 40,
    "LaunchApp": "steam-bigpicture"
  },
  "desktop": {
    "AudioDevice": "Speakers",
    "MonitorProfile": "desk-full",
    "Volume": 25,
    "KillApp": "steam-bigpicture"
  }
}
```

HA exposes a `select` entity "PC Mode" with options from `GET /api/system/modes`.
Selecting a mode calls the endpoint. The service handles sequencing and waits between
steps — no fragile automation chains.

- [x] Service: add `Modes` config section and `POST /api/system/mode` endpoint *(service)*
- [x] Service: add `GET /api/system/modes` to list available mode names *(service)*
- [x] Integration: `PcRemoteModeSelect` entity in `select.py` *(integration)*
- [x] Integration: `set_mode()` in `api.py` *(integration)*

### 2. Couch Gaming Automation Blueprint *(done in v1.0)*

Blueprint with selector inputs — no hard-coded entity names.

- [x] `blueprints/automation/pc_remote/couch_gaming.yaml` *(integration)*

### 3. Aggregated State Endpoint — `GET /api/system/state` *(done in v1.0)*

Single endpoint replaces the 6+ individual coordinator calls per poll cycle.

- [x] Service: add `GET /api/system/state` endpoint *(service)*
- [x] Integration: refactor `_async_update_data` to use single call *(integration)*

---

## v1.1

### 4. Post-Session Sleep Blueprint *(done in v1.0)*

When the Steam media player transitions `playing → idle`, wait N minutes, confirm
still idle, then sleep the PC. Closes the power-saving loop without manual action.

- [x] `blueprints/automation/pc_remote/post_session_sleep.yaml` *(integration)*

### 5. User Idle Time Sensor

`GetLastInputInfo` Win32 API → seconds since last keyboard/mouse input.
Guards the sleep blueprint against sleeping a PC that someone is actively using at the desk.

- [ ] Service: expose via `GET /api/system/idle` *(service)*
- [ ] Integration: `sensor` entity "Idle Time" (device class `duration`) *(integration)*
