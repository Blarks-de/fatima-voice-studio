"""macOS compatibility layer for Fatima Voice Studio.

The upstream app is Windows-only (registry, ctypes.windll, PowerShell, Recycle Bin, job objects, .exe engines).
Instead of editing studio/, this module is applied *before* studio is imported and replaces exactly those parts.
Call `apply()` first, then import/run `studio` as usual (see run.py). Mirrors linux/compat.py; see
docs/superpowers/specs/2026-10-10-macos-port-design.md for why this stays a separate module instead of a shared core.

What it does:
  * paths      user data lives in $FVS_HOME (default ~/Library/Application Support/Fatima Voice Studio),
               audio in ~/Music/Fatima Voice Studio
  * engine     one engine called "system": the llama-tts / whisper-cli found on PATH (or FVS_LLAMA_TTS / FVS_WHISPER_CLI)
  * hardware   CPU / RAM / battery from sysctl and pmset; GPU is unified memory (vram_gb == ram_gb), not the registry
  * trash      osascript (Finder) instead of the Recycle Bin
  * dialogs    osascript "choose folder" instead of the Windows one
  * autostart  a LaunchAgent plist instead of Startup-folder .lnk files
  * updater    switched off (Windows installer updates); update with `git pull`
  * tools      ffmpeg and whisper-cli come from Homebrew / build-*.sh; the Windows downloads are never offered
  * engine     llama-tts dies with the app (pdeath-wrap.sh polls the app's pid; macOS has no pdeathsig)
  * wording    visible "Windows" texts in the web page are rewritten (Start at login, Trash …)
  * misc       os.startfile -> open, clipboard -> pbcopy
"""
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

MACOS_DIR = Path(__file__).resolve().parent
REPO = MACOS_DIR.parent
SYSTEM_ENGINE = "system"
PDEATH_WRAP = MACOS_DIR / "pdeath-wrap.sh"

_applied = False


def fvs_home() -> Path:
    return Path(os.environ.get("FVS_HOME") or Path.home() / "Library" / "Application Support" / "Fatima Voice Studio")


def music_dir() -> Path:
    return Path(os.environ.get("FVS_MUSIC_DIR") or Path.home() / "Music") / "Fatima Voice Studio"


def find_tool(env: str, name: str) -> str | None:
    """A tool path from an environment variable, else from PATH, else the local fallback build."""
    import shutil
    given = os.environ.get(env)
    if given:
        return given if Path(given).exists() else None
    on_path = shutil.which(name)
    if on_path:
        return on_path
    local = MACOS_DIR / "bin" / name  # built by build-llama.sh / build-whisper.sh
    return str(local) if local.exists() else None


def _run(args: list[str], timeout: float = 10) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def llama_build() -> str | None:
    """The build of the installed llama-tts as "b10689", or None. `--version` prints "version: 0.3.0-dev (build 10689,
    commit ...)" (newer builds) or "version: 10689 (commit)" (older ones), on stderr or stdout."""
    tool = find_tool("FVS_LLAMA_TTS", "llama-tts")
    if not tool:
        return None
    try:
        r = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"^version: .*\(build (\d+)", r.stdout + r.stderr, re.M) \
        or re.search(r"^version: b?(\d+) \(", r.stdout + r.stderr, re.M)
    return f"b{m.group(1)}" if m else None


# ---- entry ----------------------------------------------------------------------------------------------

def apply() -> None:
    global _applied
    if _applied:
        return
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise RuntimeError("macos/compat.py is for Apple Silicon Macs only.")
    sys.path.insert(0, str(REPO))
    _applied = True
