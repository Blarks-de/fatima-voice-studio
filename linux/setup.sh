#!/usr/bin/env bash
# Sets up Fatima Voice Studio on Linux: virtual environment, dependencies, and a check of the tools it needs.
#   ./setup.sh               venv + dependencies + check
#   ./setup.sh --service     also install and enable a systemd user service (starts at login, no tray)
#   ./setup.sh --desktop     also install an application-menu entry
set -euo pipefail
here="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$here"

service=0; desktop=0
for a in "$@"; do
  case "$a" in
    --service) service=1 ;;
    --desktop) desktop=1 ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *) echo "Unknown option: $a" >&2; exit 2 ;;
  esac
done

ok()   { printf '  \033[32mok\033[0m    %s\n' "$*"; }
warn() { printf '  \033[33mfehlt\033[0m %s\n' "$*"; }

# 1. Python environment (3.11-3.13: sherpa-onnx and lameenc have no wheels for newer versions yet)
if ! command -v uv >/dev/null; then echo "uv is required (pacman -S uv)." >&2; exit 1; fi
if [ ! -x .venv/bin/python ]; then
  echo "Creating the virtual environment (Python 3.13) ..."
  uv venv --python 3.13 .venv
fi
echo "Installing dependencies ..."
# pygobject (tray icon) builds from source and is optional: without it the app still runs, just without a tray
grep -v '^pygobject' requirements-linux.txt > .venv/requirements-core.txt
uv pip install --python .venv/bin/python -r .venv/requirements-core.txt
uv pip install --python .venv/bin/python 'pygobject>=3.50' 2>/dev/null \
  || warn "pygobject (tray icon) not installed: pacman -S gobject-introspection cairo pkgconf, then run setup.sh again"
.venv/bin/python run.py --check && ok "app imports cleanly"

# 2. External tools
echo "Checking tools:"
if command -v llama-tts >/dev/null || [ -n "${FVS_LLAMA_TTS:-}" ]; then ok "llama-tts: $(command -v llama-tts || echo "$FVS_LLAMA_TTS")"
else warn "llama-tts (the speech engine): install llama.cpp with CUDA/Vulkan (Arch: llama.cpp-cuda or llama.cpp-vulkan), or set FVS_LLAMA_TTS"; fi
if [ -x bin/whisper-cli ] || command -v whisper-cli >/dev/null || [ -n "${FVS_WHISPER_CLI:-}" ]; then ok "whisper-cli: $([ -x bin/whisper-cli ] && echo "$here/bin/whisper-cli" || command -v whisper-cli || echo "$FVS_WHISPER_CLI")"
else warn "whisper-cli (subtitles, transcripts): run ./build-whisper.sh (the Arch package whisper-cpp conflicts with llama.cpp-cuda). Without it speech works, subtitles don't."; fi
if command -v ffmpeg >/dev/null; then ok "ffmpeg"; else warn "ffmpeg (video files, MP3/M4A input): sudo pacman -S ffmpeg"; fi
if command -v gio >/dev/null || command -v trash-put >/dev/null; then ok "trash (gio / trash-put)"; else warn "gio or trash-cli (deleting batches uses the trash)"; fi
if command -v zenity >/dev/null || command -v kdialog >/dev/null; then ok "folder dialog (zenity / kdialog)"; else warn "zenity or kdialog (Browse button in Settings; otherwise type the path)"; fi
if command -v nvidia-smi >/dev/null; then ok "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"; else warn "nvidia-smi (GPU detection for NVIDIA; other cards are read from lspci)"; fi

# 3. Optional integration
if [ "$service" = 1 ]; then
  mkdir -p ~/.config/systemd/user
  sed "s|@DIR@|$here|g" systemd/fatima-voice-studio.service > ~/.config/systemd/user/fatima-voice-studio.service
  systemctl --user daemon-reload
  systemctl --user enable --now fatima-voice-studio.service
  ok "systemd user service enabled (journalctl --user -u fatima-voice-studio)"
fi
if [ "$desktop" = 1 ]; then
  mkdir -p ~/.local/share/applications
  sed "s|@DIR@|$here|g" desktop/fatima-voice-studio.desktop > ~/.local/share/applications/fatima-voice-studio.desktop
  ok "menu entry installed"
fi

echo
echo "Start:  $here/fatima-voice-studio        (opens http://127.0.0.1:9830/)"
echo "Then open Setup in the app and download the voice model (and a Whisper model for subtitles)."
