# macOS Port of Fatima Voice Studio — Design

Date: 2026-10-10

## Context

Fatima Voice Studio is a Windows-oriented voice synthesis and voice cloning
app (upstream: https://github.com/hassanxs/fatima-voice-studio, MIT license).
The Linux port (`linux/`) is done, PR #3 was merged into `main` by maintainer
Hassan Latif, issue #1 is closed, and Linux is now officially
community-supported. Background and test log (German):
`Agenten/fatima-voice-studio.md`, `linux/SESSION.md`.

Hassan explicitly approved this pattern for the Linux port:
- one add-on folder per platform (`linux/`)
- `studio/` stays untouched
- no `sys.platform` branches inside the Windows code

This document describes the same approach for macOS, developed and tested on
the Mac mini this is written on (Apple M6, 32 GB unified memory, macOS 27.0.1).

## Goal

A `macos/` folder that makes `studio/` runnable on macOS through a
compatibility layer (`compat.py`, mirroring `linux/compat.py`) — without
changing `studio/`. The end goal is a second pull request following the same
pattern as PR #3.

## Non-goals

- No shared platform-neutral core with `linux/` in this iteration. Reason:
  Hassan has so far only seen and approved the "one folder per platform"
  pattern; extracting a shared core now would be extra risk for a PR that
  hasn't even been opened yet. The replacement table below already shows
  fairly different mechanisms between Linux and macOS (gio vs. osascript,
  AppIndicator vs. PyObjC, systemd vs. launchd). If strong overlap shows up
  later, extracting a shared core is a separate, deliberate step.
- No app-bundle distribution (.app, code signing, notarization) — a later
  topic, not part of this port.

## Structure

```
macos/
  compat.py           # mirrors linux/compat.py
  run.py               # entry point, mirrors linux/run.py
  setup.sh             # setup, mirrors linux/setup.sh
  build-llama.sh       # fallback: build llama.cpp from source with -DGGML_METAL=ON
  build-whisper.sh     # fallback: build whisper.cpp from source (possibly reused from linux/)
  test_smoke.py        # mirrors linux/test_smoke.py
  README.md
  ARCHITECTURE.md
```

## Replacement table (Windows part → macOS)

| Part in `studio/` | macOS replacement |
|---|---|
| Data folder | `~/Library/Application Support/Fatima Voice Studio` |
| Audio folder | `~/Music/Fatima Voice Studio` |
| Engine `llama-tts` | Homebrew `llama.cpp` (Metal is enabled by default on Apple Silicon) or fallback: build from source with `-DGGML_METAL=ON` |
| `whisper-cli` | Homebrew `whisper.cpp` or fallback: `build-whisper.sh` (as on Linux) |
| ffmpeg | system ffmpeg (Homebrew), same patch pattern as `linux/compat.py::_patch_tools` |
| Hardware (`hardware.py`) | `sysctl -n machdep.cpu.brand_string` (CPU), `sysctl hw.memsize` (RAM), `pmset -g batt` (battery), `system_profiler SPDisplaysDataType` (GPU name) |
| VRAM | unified memory: GPU memory = RAM, no separate value |
| Trash | `osascript -e 'tell application "Finder" to delete (POSIX file "…")'` |
| Folder picker | `osascript -e 'POSIX path of (choose folder)'` |
| `os.startfile` | `open` |
| Clipboard | `pbcopy` / `pbpaste` |
| Autostart (tray toggle) | `~/Library/LaunchAgents/*.plist` with `RunAtLoad` |
| `--service` (persistent background run) | its own LaunchAgent plist with `KeepAlive` (kept separate from the autostart plist — the same two concepts as on Linux: login start vs. persistent service) |
| Engine dies with the app (`setpriv --pdeathsig`) | no kernel equivalent on macOS. Approach: launch `llama-tts`/`whisper-cli` through a small watcher shell wrapper that polls `kill -0 $PPID` and kills the child once the parent is gone (also works when the app is killed with `kill -9`) |
| Tray (`pystray`) | `darwin` backend via PyObjC. **Important finding:** `studio/__main__.py` already calls `tray.run()` on the main thread (the server runs in a background thread) — that's exactly what PyObjC/`NSApplication` needs. No restructuring of `run.py` required, only `patch_tray()` with a macOS clipboard (`_copy` → `pbcopy`) and notify implementation (`osascript -e 'display notification'` or pystray's own `notify()` — to be checked) |
| Wording (Linux/Windows text in `studio/web/`) | same pattern as `linux/compat.py` (`TEXTS`/`JS_PATCHES`), hints pointing to `brew install …` instead of `pacman`/`apt` |

## Open technical questions (resolved during implementation, not in this design)

These can only be answered by actually installing and testing on this Mac, not
by further analysis. They become the first implementation task:

1. Does the Homebrew bottle of `llama.cpp` (currently `v0.6.0`) build a
   `llama-tts` binary at all? If not, or if Qwen3-TTS support is missing
   (needs build b10270+): fall back to building from source with
   `-DGGML_METAL=ON`.
2. Does Homebrew's `whisper.cpp` (1.9.5) provide a usable `whisper-cli` with
   Metal/CoreML, or does it need its own build script like on Linux?
3. Speech synthesis speed on Apple M6 (reference points: the Windows app
   advertises ~2.2x realtime on an RTX 5060; Linux reaches 3-4x on an
   RTX 4070 Ti SUPER).
4. Notifications: does pystray's `darwin` backend support `icon.notify()`
   natively, or does it need `osascript -e 'display notification'` the way
   Linux needs `notify-send`?
5. Whether the maintainer accepts a second platform layer in the same
   pattern (very likely after PR #3, but not guaranteed).

## Testing

Same approach as Linux: first a smoke test (`macos/test_smoke.py` — import +
compatibility layer + patched functions present), then real functional tests
on this Mac (TTS, Whisper batch, voice cloning, WAV/MP3/SRT, pause/resume,
`kill -9` recovery, video/M4A, tray, LaunchAgent autostart, `--service`).
`studio/` must stay untouched throughout, verified the same way as on Linux
via `git diff` against `origin/main`.

## Outcome for README/issue

Once done: a new GitHub issue following the pattern of issue #1 ("macOS
support"), then a PR with the `macos/` folder — no changes to `studio/`, same
flow as PR #3.
