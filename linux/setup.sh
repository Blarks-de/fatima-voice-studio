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

# Oldest llama.cpp build with Qwen3-TTS support (4 Aug 2026). Older llama-tts builds take a different command line.
# Keep in step with the flags engine.py passes (linux/test_smoke.py lists them).
LLAMA_MIN_BUILD=10270

ok()   { printf '  \033[32mok\033[0m    %s\n' "$*"; }
warn() { printf '  \033[33mmissing\033[0m %s\n' "$*"; }

# Fills @EXEC@ in a template with an already quoted command, without sed: sed would treat \ & and the delimiter in
# an install path as special characters. Usage: render TEMPLATE QUOTED_COMMAND
render() { EXEC_Q="$2" awk '{ while ((i = index($0, "@EXEC@"))) $0 = substr($0, 1, i - 1) ENVIRON["EXEC_Q"] substr($0, i + 6) } 1' "$1"; }
# The launcher path as one argument of a systemd ExecStart= line (quotes for spaces; \ " % $ are special there).
unit_quote() { local s=${1//\\/\\\\}; s=${s//\"/\\\"}; s=${s//%/%%}; s=${s//\$/\$\$}; printf '"%s"' "$s"; }

# Finds llama-tts the way compat.py does (FVS_LLAMA_TTS first, then PATH) and checks that it is new enough.
check_llama_tts() {
  local tts="${FVS_LLAMA_TTS:-$(command -v llama-tts || true)}" build
  if [ -z "$tts" ]; then
    warn "llama-tts (the speech engine): install llama.cpp with CUDA/Vulkan (Arch: llama.cpp-cuda or llama.cpp-vulkan), or set FVS_LLAMA_TTS"
    return 0
  fi
  ok "llama-tts: $tts"
  # "llama-tts --version" prints "version: <build> (<commit>)" among other lines
  build="$("$tts" --version 2>&1 | sed -n 's/^version: b\{0,1\}\([0-9][0-9]*\).*/\1/p' | head -n 1 || true)"
  if [ -z "$build" ]; then
    warn "llama-tts: couldn't read the build number from '$tts --version'. The app needs llama.cpp b$LLAMA_MIN_BUILD or newer."
  elif [ "$build" -lt "$LLAMA_MIN_BUILD" ]; then
    warn "llama-tts is llama.cpp b$build, but the app needs b$LLAMA_MIN_BUILD or newer (older builds take a different command line). Update llama.cpp."
  else
    ok "llama.cpp b$build (b$LLAMA_MIN_BUILD or newer needed)"
  fi
}

# 1. Python environment (3.11-3.13: sherpa-onnx and lameenc have no wheels for newer versions yet)
if ! command -v uv >/dev/null; then echo "uv is required (Arch: pacman -S uv; other distributions: https://docs.astral.sh/uv/)." >&2; exit 1; fi
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
check_llama_tts
if [ -x bin/whisper-cli ] || command -v whisper-cli >/dev/null || [ -n "${FVS_WHISPER_CLI:-}" ]; then ok "whisper-cli: $([ -x bin/whisper-cli ] && echo "$here/bin/whisper-cli" || command -v whisper-cli || echo "$FVS_WHISPER_CLI")"
else warn "whisper-cli (subtitles, transcripts): run ./build-whisper.sh (the Arch package whisper-cpp conflicts with llama.cpp-cuda). Without it speech works, subtitles don't."; fi
if command -v ffmpeg >/dev/null; then ok "ffmpeg"; else warn "ffmpeg (video files, M4A input; the app never downloads it on Linux): sudo pacman -S ffmpeg / sudo apt install ffmpeg"; fi
if command -v gio >/dev/null || command -v trash-put >/dev/null; then ok "trash (gio / trash-put)"; else warn "gio or trash-cli (deleting batches uses the trash)"; fi
if command -v zenity >/dev/null || command -v kdialog >/dev/null; then ok "folder dialog (zenity / kdialog)"; else warn "zenity or kdialog (Browse button in Settings; otherwise type the path)"; fi
if command -v nvidia-smi >/dev/null; then ok "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"; else warn "nvidia-smi (GPU detection for NVIDIA; other cards are read from lspci)"; fi

# 3. Optional integration
if [ "$service" = 1 ]; then
  mkdir -p ~/.config/systemd/user
  render systemd/fatima-voice-studio.service "$(unit_quote "$here/fatima-voice-studio")" > ~/.config/systemd/user/fatima-voice-studio.service
  systemctl --user daemon-reload
  systemctl --user enable --now fatima-voice-studio.service
  ok "systemd user service enabled (journalctl --user -u fatima-voice-studio)"
fi
if [ "$desktop" = 1 ]; then
  mkdir -p ~/.local/share/applications
  # the quoting rules of an Exec= line live in compat.exec_quote (one implementation, also used for the autostart entry)
  render desktop/fatima-voice-studio.desktop "$(.venv/bin/python -c 'import sys; sys.path.insert(0, "."); import compat; print(compat.exec_quote(sys.argv[1]))' "$here/fatima-voice-studio")" \
    > ~/.local/share/applications/fatima-voice-studio.desktop
  ok "menu entry installed"
fi

echo
echo "Start:  $here/fatima-voice-studio        (opens http://127.0.0.1:9830/)"
echo "Then open Setup in the app and download the voice model (and a Whisper model for subtitles)."
