# Fatima Voice Studio on Linux

Upstream, Fatima Voice Studio is a Windows-only app. This folder holds everything needed to run it on Linux.
**The `studio/` folder is not modified**: a compatibility layer (`compat.py`) replaces the Windows-specific parts at
startup, so upstream changes can be picked up with a plain `git pull`.

## Tested status

Honest overview of what has and hasn't been verified. "Re-run pending" means it worked before the latest changes
(rebase onto upstream 0.2.4 and the fixes from the PR review) and still has to be repeated on the GPU machine.

| Area | Status |
|---|---|
| `test_smoke.py` (static + runtime + web checks), `setup.sh` syntax, generated `.desktop`/`.service` files incl. install paths with spaces | **Tested** after the latest changes (Debian 13, no GPU) |
| No Windows ffmpeg/Whisper download is offered or started; system ffmpeg wins over a stray `ffmpeg.exe`; no Download button for the System engine | **Tested** by the smoke test (HTTP-level, no real download) |
| Whisper build (`build-whisper.sh`), transcription, subtitle timing, `[pause]` scripts, language auto-detection | **Tested** on CPU, Debian 13 (before the latest changes) |
| Full TTS run, voice cloning, English and German batch with `[pause]`, WAV + MP3 + SRT, abort and resume, `kill -9` cleanup | **Tested** on CachyOS (Arch), RTX 4070 Ti SUPER, `llama.cpp-cuda` b10689 (2026-10-08). Batch part, pause/resume, `kill -9` cleanup with resume, and voice cloning re-run after the rebase, see the next rows |
| Full TTS + Whisper batch in one go: 3 scripts (German with two voices, English), `[pause]`, Q8 model, Whisper `small`, WAV + MP3 + SRT, −16 LUFS | **Tested** on CachyOS (Arch), RTX 4070 Ti SUPER, `llama.cpp-cuda` b10689 (2026-10-09, after the rebase and the review fixes). All scripts finished without errors, subtitles match the script (Whisper match 0.93–1.0) |
| Video/M4A/WebM inside a real batch: voices created from an M4A, an MP4 (video with audio) and a WebM (Opus) upload, then one batch with all three voices (WAV + MP3 + SRT, Whisper match 0.91 / 1.0 / 1.0), with a deliberately broken `engine/ffmpeg/ffmpeg.exe` present | **Tested** on CachyOS (Arch), 2026-10-09. The fake `ffmpeg.exe` was never run, `/api/tools` reports the system ffmpeg as ready, the ffmpeg download request returns 409 |
| MP4 and M4A decoded through the system ffmpeg (`media.decode`, `to_wav16k`) with a stray `ffmpeg.exe` present | **Tested** (generated test clips, Debian 13, no GPU) |
| Pause and resume of a running batch (24 segments, 550 s); `kill -9` on the app in the middle of generation, restart, batch continues with the finished segments | **Tested** on CachyOS (Arch), RTX 4070 Ti SUPER, 2026-10-09. Pause finishes the current segment and stops (`llama-tts` idle), resume continues at the next one; `kill -9` ended `llama-tts` within 1.5 s, the restarted app resumed at segment 7 of 24 without redoing the finished ones, WAV/MP3/SRT complete, −16.1 LUFS |
| Voice cloning: new voice from a 6 s WAV (`POST /api/voices`), used in an 8- and a 24-segment batch | **Tested** (it runs and the output is normal; whether it sounds like the reference was not judged by ear) |
| Transcription (`POST /api/transcripts`, the backend of the `/transcribe` page) with WAV, M4A and MP4 input, language auto-detection, TXT/SRT/VTT/JSON output; Whisper `medium` (q5_0) re-run of the batch above | **Tested** on CachyOS (Arch), 2026-10-09 (Whisper on the CPU, about real time). The `/transcribe` page itself in a browser: not tested |
| Tray icon visibility in the KDE panel, Browse dialog (zenity/kdialog), `xdg-open` buttons | Not tested (needs a screen) |
| systemd user service (`./setup.sh --service`) at runtime: install, start, health check, a speech request through it, `llama-tts` inside the service's cgroup, `systemctl stop`, `kill -9` on the main process during generation | **Tested** on CachyOS (Arch), 2026-10-09. `stop` ends the app and `llama-tts`; after `kill -9` the unit restarted by itself after about 5 s (`Restart=on-failure`) and answered `/v1/health`. Not tested: starting at a real login or reboot, `loginctl enable-linger` |
| `--desktop` menu entry | Generated file passes `desktop-file-validate`; launching it in the KDE session (tray, browser tab) not tested. The unit and desktop files were also launched from an install path with spaces on Debian 13 |
| Voice-clip upload with the voice separator (`separate=1`, `uvr-vocals` model) from an MP4; the new voice then spoke a sentence | **Tested** (2026-10-09, CachyOS, about 6 s for a 9 s clip; separation quality not judged by ear) |
| Voice-clip upload with the plain noise-removal switch (`denoise=1`) | Not tested |
| German audio through Whisper `small` (inside the batch above) | **Tested** |
| Model download through the app (Whisper `medium` 540 MB and `large-v3` 1.1 GB, started via the API) | **Tested** (both finished and were used). Q8 and `small` were already on disk; `turbo` not tried |
| Whisper `large-v3` (q5_0): the 3-script batch (WAV + MP3 + SRT, match 0.96 / 1.0 / 1.0) and transcription of WAV, M4A, MP4 and a WAV with added noise | **Tested** on CachyOS (Arch), 2026-10-09. Whisper runs on the CPU: about 1.7x the audio length for `large` (20 s for 11 s), 4 s for `small`. The noise was mild, so it did not show a difference between `small` and `large` |

## Quick start

```bash
cd ~/fatima-voice-studio/linux
./setup.sh                  # venv + dependencies + a check of the tools
./build-whisper.sh          # only for subtitles/transcripts: builds whisper-cli into linux/bin/ (~1 min)
./fatima-voice-studio       # starts and opens http://127.0.0.1:9830/
```

On the first start, open **Setup** in the app and download the voice model (Qwen3-TTS Q8, 2.3 GB, or Q4, 1 GB)
and, for subtitles, a Whisper model (small, 190 MB). Downloads run inside the app (resumable, SHA-256 checked).
Then create a voice under **Voices** (upload a clip or "Find a new voice") and start on **Create**.

Three programs are **never downloaded** by the app on Linux; install them on the system instead:

| Program | How |
|---|---|
| `llama-tts` (the speech engine) | install llama.cpp (see Requirements). The Setup page shows the "System" engine without a Download button |
| `whisper-cli` (subtitles, transcripts) | `./build-whisper.sh`. Downloading a Whisper *model* in the app works as usual; the Setup page warns until `whisper-cli` exists |
| `ffmpeg` (video files, M4A/AAC input) | your package manager (`sudo pacman -S ffmpeg`, `sudo apt install ffmpeg`). The Models page (Tools) shows "Not found on this PC" until it is installed |

The upstream app would fetch Windows builds of these (`ffmpeg.exe`, `whisper-bin-x64.zip`), which cannot run here.
`compat.py` switches that off. An `ffmpeg.exe` left in `engine/ffmpeg/` by an earlier download is ignored.

## Starting and stopping

| Command | Effect |
|---|---|
| `./fatima-voice-studio` | starts with a **tray icon** (right-click → Quit) and opens the browser; Ctrl+C in the terminal also quits |
| `./fatima-voice-studio --no-tray` | without a tray icon (for servers, systemd) |
| `./fatima-voice-studio --stop` | stops a running instance, however it was started |
| `./fatima-voice-studio --no-browser` | don't open the browser (can be combined) |

The tray icon uses AppIndicator (KDE; GNOME with an extension). That needs `pygobject` in the venv, which `setup.sh`
installs (it builds from source and needs `gobject-introspection`, `cairo`, `pkgconf`). Without `pygobject` the app
starts without a tray icon and says so; quit it with Ctrl+C or `--stop`.

## Requirements

| What | Used for | Arch package |
|---|---|---|
| `uv` | venv with Python 3.13 | `uv` |
| `gobject-introspection`, `cairo`, `pkgconf` | builds `pygobject` for the tray icon (optional) | same names |
| `llama-tts` | speech output (Qwen3-TTS) | `llama.cpp-cuda` (NVIDIA) or `llama.cpp-vulkan` (AMD/Intel) |
| `whisper-cli` | subtitles, transcripts | `./build-whisper.sh` (the Arch package `whisper-cpp` conflicts with `llama.cpp-cuda`, both ship `ggml`) |
| `ffmpeg` | reading video files and M4A/AAC | `ffmpeg` |
| `setpriv` (util-linux) | the engine ends with the app | `util-linux` |
| `gio` or `trash-cli` | deleting to the trash | `glib2` / `trash-cli` |
| `zenity` or `kdialog` | "Browse" button in Settings | `zenity` / `kdialog` |
| `notify-send` | notification when a batch is done | `libnotify` |
| `wl-copy`/`xclip`/`xsel` | clipboard in the tray menu | `wl-clipboard` / `xclip` |

`llama-tts` has to support Qwen3-TTS: at least **b10270** (4 Aug 2026); older builds have a different command line.
Verified with b10689; the Windows version of the app pins b11476. `setup.sh` warns if `llama-tts` is older
(`LLAMA_MIN_BUILD` at the top of the script). If a model won't run, update `llama-tts` first.

Python 3.14 doesn't work (no wheels for `sherpa-onnx`/`lameenc` yet), which is why `setup.sh` creates the venv with 3.13.

## Files in this folder

| File | Purpose |
|---|---|
| `build-whisper.sh` | builds `whisper-cli` (CPU, static) into `bin/` |
| `setup.sh` | setup; `--service` (systemd), `--desktop` (menu entry). Both work from an install path with spaces |
| `fatima-voice-studio` | launcher (tray is the default; `--no-tray`, `--stop`, `--no-browser`, `--check`) |
| `run.py` | entry point: loads `compat.py`, then the normal `studio.__main__` |
| `compat.py` | the compatibility layer (see `ARCHITECTURE.md`) |
| `test_smoke.py` | checks that the layer still fits `studio/` (see "Update and maintenance") |
| `mcp_stdio.py` | stdio MCP launcher for agents (Claude Code …) |
| `requirements-linux.txt` | dependencies without `pywin32` |
| `systemd/`, `desktop/` | templates for the service and the menu entry (`@EXEC@` is replaced by the quoted launcher path) |
| `.venv/` | Python environment (not in git) |
| `ARCHITECTURE.md` | structure and data flow with a diagram |

## Where is the data?

Nothing in the repo. Defaults:

| What | Location |
|---|---|
| Settings, API key, logs | `~/.local/share/fatima-voice-studio/data/` |
| Models | `~/.local/share/fatima-voice-studio/models/` |
| Voice library | `~/.local/share/fatima-voice-studio/voices/` |
| Engine links (`llama-tts`, `whisper-cli`) | `~/.local/share/fatima-voice-studio/engine/` |
| Batches, exports (audio) | `~/Music/Fatima Voice Studio/{Batches,Exports}` |

Environment variables:

| Variable | Effect |
|---|---|
| `FVS_HOME` | different data folder. It has to be on the same drive as `~`, otherwise moving to the trash fails |
| `XDG_MUSIC_DIR` | base for batches/exports |
| `FVS_LLAMA_TTS` | path to a different `llama-tts` (e.g. self-built) |
| `FVS_WHISPER_CLI` | path to a different `whisper-cli` (otherwise: `linux/bin/`, then `PATH`) |

`compat.py` recreates the links in `engine/` on every start, so updating `llama.cpp` needs nothing else.

## Autostart

- **systemd (recommended):** `./setup.sh --service`, then `systemctl --user status fatima-voice-studio`, logs with
  `journalctl --user -u fatima-voice-studio`. Runs with `--no-tray --no-browser`.
- **Desktop autostart:** the "Start at login" switch in Settings creates `~/.config/autostart/fatima-voice-studio.desktop`.
- **Menu entry:** `./setup.sh --desktop`.

## Agents / MCP

The MCP endpoint is part of the running server: `http://127.0.0.1:9830/mcp`, header
`Authorization: Bearer <API key>` (key: Settings or `data/config.json`). For Claude Code:

```bash
claude mcp add --transport http fatima http://127.0.0.1:9830/mcp --header "Authorization: Bearer <API key>"
```

Alternatively over stdio (the app has to be running):
`~/fatima-voice-studio/linux/.venv/bin/python ~/fatima-voice-studio/linux/mcp_stdio.py`.

## Differences from Windows

- There is a single engine, "System"; the Windows downloads (CUDA/Vulkan/CPU zips) don't apply. Whether the GPU or the
  CPU does the work depends on the installed `llama.cpp`. The Setup page offers no download for it.
- ffmpeg and `whisper-cli` come from the system / `build-whisper.sh`, see "Quick start".
- Updates: off (`git pull` in the project). The Updates page says so.
- If the app dies hard, the kernel also ends `llama-tts` (`setpriv --pdeathsig`, like the job object on Windows).
  `whisper-cli` is not started that way: it is short-lived, so a crash can at worst leave one finished-soon process.
- The tray icon is the default and only appears if the desktop supports AppIndicator (KDE: yes, GNOME: extension).
  Notifications ("batch done") go through `notify-send`.
- Visible "Windows" texts in the interface ("Start with Windows", "Recycle Bin" …) are rewritten on the way out
  ("Start at login", "Trash"). The list is `TEXTS` in `compat.py`; `studio/web/` stays untouched. Some upstream
  wording remains, for example the "Open in File Explorer" tooltip.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `tensor … not within the file bounds` | incomplete model download. Download it again in the app (it resumes) |
| "No voice: pass a voice name …" | create a voice first (Voices) or set a default voice |
| Setup shows "No engine installed" / System engine "Not found on this PC" | `llama-tts` is not on `PATH`. Check `which llama-tts` or set `FVS_LLAMA_TTS`, then press "Check again" |
| No subtitles; Setup warns about `whisper-cli` | run `./build-whisper.sh`, press "Check again". Also needs a Whisper model |
| Video/M4A files can't be read; Tools shows "Not found on this PC" | install `ffmpeg` with your package manager, reload the page |
| Deleting fails ("trash … mount points") | `FVS_HOME` is not on the same drive as `~` |
| Port in use | change `port` in Settings (restart needed) |
| Engine errors in detail | `~/.local/share/fatima-voice-studio/data/logs/engine.log` and `studio.log` |

## Update and maintenance

```bash
cd ~/fatima-voice-studio && git pull        # take over upstream
linux/setup.sh                              # if requirements.txt changed
```

After an upstream update, run `linux/fatima-voice-studio --check` and the smoke test:

```bash
.venv/bin/python linux/test_smoke.py        # or: .venv/bin/python -m pytest linux/test_smoke.py
```

The layer depends on these names in `studio/`: `config` (HOME, DATA, DEFAULTS, ENGINES, TOOLS …), `hardware`
(`_registry_gpus`, `_ram_gb`, `_cpu`, `on_battery`, `warnings`), `autostart`, `updater.Updater`, `media`
(`ffmpeg_exe`, `ffmpeg_source`), `downloads.Downloads` (`tools`, `start_tool`, `delete_tool`, `start_engine`,
`_whisper_missing`), `studio.trash`, `studio.winui`, `tray.copy`, plus a few lines of `studio/web/app.js`. The test
checks that they still exist and that `compat.py` really replaces them (also where `app.py`, `store.py` & co. bind them
with `from … import`), the `llama-tts` command line from `engine.py`, and the wording of the web interface. It needs no
GPU, no `llama-tts` and no display (the tray test is skipped without one) and writes only to a temporary folder. If it
fails, `compat.py` has to be adjusted, or upstream adds a hook.
