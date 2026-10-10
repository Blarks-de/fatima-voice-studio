# Fatima Voice Studio — macOS

A compatibility layer that runs Fatima Voice Studio on Apple Silicon Macs without touching `studio/`. See
`ARCHITECTURE.md` for how it works, and the main `README.md` for what the app itself does.

## Requirements

- Apple Silicon Mac (Intel Macs aren't supported by this layer)
- [Homebrew](https://brew.sh)
- `uv` (`brew install uv`)
- `llama.cpp` with a `llama-tts` binary, build b10270 or newer (`brew install llama.cpp`, or `./build-llama.sh`
  if Homebrew's bottle doesn't have one new enough — see "Tested status" below for what this Mac needed)
- `whisper-cpp` for subtitles and transcripts (`brew install whisper-cpp`, or `./build-whisper.sh`) — optional,
  speech works without it
- `ffmpeg` for video files and M4A (`brew install ffmpeg`)

## Setup

```bash
cd macos
./setup.sh               # venv + dependencies + a check of the tools above
./setup.sh --service     # also install a LaunchAgent that keeps the app running in the background
```

## Running

```bash
./fatima-voice-studio              # tray icon, opens the browser
./fatima-voice-studio --no-tray    # no tray icon, Ctrl+C quits
./fatima-voice-studio --stop       # stop a running instance
```

"Start at login" in the tray menu installs a separate LaunchAgent (`~/Library/LaunchAgents/de.blarks.fatima-voice-studio.plist`).
`./setup.sh --service` installs another one with `KeepAlive`
(`~/Library/LaunchAgents/de.blarks.fatima-voice-studio.service.plist`), for running in the background
independent of login.

## Environment variables

Same overrides as `linux/`, plus two macOS-specific ones used for testing:

- `FVS_HOME` — data folder (default `~/Library/Application Support/Fatima Voice Studio`)
- `FVS_MUSIC_DIR` — audio folder's parent (default `~/Music`)
- `FVS_LLAMA_TTS` / `FVS_WHISPER_CLI` — explicit tool paths instead of PATH / Homebrew / the local `bin/` fallback
- `FVS_LAUNCH_AGENTS_DIR` — where autostart/service plists are read from and written to (default
  `~/Library/LaunchAgents`); only meant for `macos/test_smoke.py`

## Tested status

Not yet tested beyond the automated smoke test (`macos/test_smoke.py`). This table follows the same convention
as `linux/README.md` — updated only with actually tested results, not in advance. See
`docs/superpowers/specs/2026-10-10-macos-port-design.md` for the manual verification checklist still to run on
this Mac (TTS, Whisper batch, voice cloning, tray, LaunchAgent autostart, `--service`, Pause/Resume, `kill -9`
recovery, video/M4A).

| Area | Status |
|---|---|
| Smoke test (`test_smoke.py`) | done |
| Speech synthesis (TTS) | done — Qwen3-TTS Q8 downloaded and spoken on this Mac |
| Voice cloning | not yet tested |
| Whisper subtitles/transcripts | not yet tested (whisper-small downloaded, not yet run) |
| Pause/resume, `kill -9` recovery | not yet tested |
| Video/M4A input | not yet tested |
| Tray icon | not yet tested — crashes with SIGTRAP when started from a sandboxed/headless shell (no WindowServer access); needs a real interactive Terminal session |
| Autostart (LaunchAgent) | not yet tested |
| `--service` (background LaunchAgent) | not yet tested |
