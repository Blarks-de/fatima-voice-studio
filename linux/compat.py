"""Linux compatibility layer for Fatima Voice Studio.

The upstream app is Windows-only (registry, ctypes.windll, PowerShell, Recycle Bin, job objects, .exe engines).
Instead of editing studio/, this module is applied *before* studio is imported and replaces exactly those parts.
Call `apply()` first, then import/run `studio` as usual (see run.py).

What it does:
  * paths      user data lives in $FVS_HOME (default ~/.local/share/fatima-voice-studio), audio in ~/Music
  * engine     one engine called "system": the llama-tts / whisper-cli found on PATH (or FVS_LLAMA_TTS / FVS_WHISPER_CLI)
  * hardware   GPU / RAM / CPU / battery from nvidia-smi, lspci, /sys and /proc instead of the registry
  * trash      gio trash / trash-put instead of the Recycle Bin
  * dialogs    zenity / kdialog folder picker instead of the Windows one
  * autostart  ~/.config/autostart/*.desktop instead of Startup-folder .lnk files
  * updater    switched off (Windows installer updates); update with `git pull`
  * engine     llama-tts dies with the app (setpriv --pdeathsig), like the Windows job object
  * wording    visible "Windows" texts in the web page are rewritten (Start at login, Trash …)
  * misc       os.startfile -> xdg-open, clipboard -> wl-copy / xclip / xsel
"""
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

LINUX_DIR = Path(__file__).resolve().parent
REPO = LINUX_DIR.parent
SYSTEM_ENGINE = "system"

_applied = False


def fvs_home() -> Path:
    return Path(os.environ.get("FVS_HOME") or Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
                / "fatima-voice-studio")


def music_dir() -> Path:
    return Path(os.environ.get("XDG_MUSIC_DIR") or Path.home() / "Music") / "Fatima Voice Studio"


def find_tool(env: str, name: str) -> str | None:
    """A tool path from an environment variable, else from PATH."""
    given = os.environ.get(env)
    if given:
        return given if Path(given).exists() else None
    local = LINUX_DIR / "bin" / name  # built by build-whisper.sh
    return str(local) if local.exists() else shutil.which(name)


def _run(args: list[str], timeout: float = 10) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


# ---- paths and the "system" engine ---------------------------------------------------------------------------

def _patch_config() -> None:
    from studio import config

    home = fvs_home()
    config.HOME = home
    config.DATA = home / "data"
    config.CONFIG_FILE = config.DATA / "config.json"
    config.VOICES = home / "voices"
    music = music_dir()
    config.MUSIC = music
    d = config.DEFAULTS
    d["batches_dir"] = str(music / "Batches")
    d["exports_dir"] = str(music / "Exports")
    d["models_dir"] = str(home / "models")
    d["engine"] = SYSTEM_ENGINE
    d["check_updates"] = False

    config.ENGINE_EXE = "llama-tts"
    config.WHISPER_EXE = "whisper-cli"
    config.ENGINES.clear()
    config.ENGINES[SYSTEM_ENGINE] = {
        "label": "System · llama.cpp",
        "about": "The llama-tts installed on this PC (CUDA, Vulkan or CPU, whatever that build was made for). "
                 "Nothing to download here.",
        "zips": [], "gpu": True}

    def engine_dir(cfg: dict, key: str | None = None) -> Path:
        return home / "engine" / (key or cfg["engine"])

    def installed_engines(cfg: dict) -> list[str]:
        _link_tools()
        return [k for k in config.ENGINES if (engine_dir(cfg, k) / config.ENGINE_EXE).exists()]

    config.engine_dir = engine_dir
    config.installed_engines = installed_engines
    config.whisper_dir = lambda: home / "engine" / "whisper"
    config.tool_dir = lambda key: home / "engine" / key


def _link(target: str | None, link: Path) -> None:
    """Keep link -> target in step with what is installed (the app expects <engine dir>/<exe>)."""
    try:
        if target is None:
            if link.is_symlink():
                link.unlink()
            return
        if link.is_symlink() and os.readlink(link) == target:
            return
        link.parent.mkdir(parents=True, exist_ok=True)
        link.unlink(missing_ok=True)
        link.symlink_to(target)
    except OSError:
        pass


def _link_tools() -> None:
    home = fvs_home()
    _link(find_tool("FVS_LLAMA_TTS", "llama-tts"), home / "engine" / SYSTEM_ENGINE / "llama-tts")
    _link(find_tool("FVS_WHISPER_CLI", "whisper-cli"), home / "engine" / "whisper" / "whisper-cli")


# ---- hardware ---------------------------------------------------------------------------------------------

def _drm_vram(vendor_id: str) -> dict[str, float]:
    """PCI address -> VRAM in GB, for cards that report it in sysfs (amdgpu does)."""
    out = {}
    for card in Path("/sys/class/drm").glob("card[0-9]"):
        dev = card / "device"
        try:
            if (dev / "vendor").read_text().strip() != vendor_id:
                continue
            out[dev.resolve().name.removeprefix("0000:")] = int((dev / "mem_info_vram_total").read_text()) / 1024**3
        except (OSError, ValueError):
            continue
    return out


def _lspci_gpus() -> list[dict]:
    from studio import hardware
    amd_vram = _drm_vram("0x1002")
    gpus = []
    for line in _run(["lspci", "-mm"]).splitlines():
        parts = [p for p in line.replace('" "', "\x00").replace('"', "").split("\x00")]
        if len(parts) < 4 or not any(c in parts[1] for c in ("VGA", "3D controller", "Display controller")):
            continue
        slot, vendor_name, device = parts[0].split()[0], parts[2], parts[3]
        name = f"{vendor_name} {device}"
        if "[" in device and "]" in device:  # "Navi 31 [Radeon RX 7900 XTX]" -> the marketing name
            name = device[device.rindex("[") + 1:device.rindex("]")]
        v = hardware._vendor(vendor_name + " " + name)
        vram = round(amd_vram.get(slot, amd_vram.get("0000:" + slot, 0.0)), 1)
        gpus.append({"name": name, "vendor": v, "vram_gb": vram, "driver": None,
                     "integrated": vram < 2 or (v == "intel" and "arc" not in name.lower())})
    return gpus


def _ram_gb() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            return round(int(line.split()[1]) / 1024**2, 1)
    return 0.0


def _cpu() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "Unknown CPU"


def _on_battery() -> bool | None:
    supplies = Path("/sys/class/power_supply")
    try:
        if not any((p / "type").read_text().strip() == "Battery" for p in supplies.iterdir()):
            return None
        for p in supplies.iterdir():
            if (p / "type").read_text().strip() == "Mains":
                return (p / "online").read_text().strip() == "0"
    except OSError:
        pass
    return None


def _patch_hardware() -> None:
    # studio/hardware.py does `import winreg`. The stub exists only for that import: left in sys.modules it makes
    # the standard library (mimetypes) believe it is on Windows and crash on every static file.
    import mimetypes  # noqa: F401  (loaded before the stub, so it never sees it)
    sys.modules["winreg"] = types.ModuleType("winreg")
    try:
        from studio import hardware
    finally:
        del sys.modules["winreg"]
    hardware._registry_gpus = _lspci_gpus
    hardware._ram_gb = _ram_gb
    hardware._cpu = _cpu
    hardware.on_battery = _on_battery
    hardware.recommended_engine = lambda hw: SYSTEM_ENGINE


# ---- trash, dialogs, opening things, clipboard -------------------------------------------------------------

def _to_trash(path: Path) -> None:
    path = Path(path).resolve()
    detail = ""
    for cmd in (["gio", "trash"], ["trash-put"], ["kioclient", "move"]):
        if not shutil.which(cmd[0]):
            continue
        args = cmd + [str(path)] + (["trash:/"] if cmd[0] == "kioclient" else [])
        p = subprocess.run(args, capture_output=True, text=True)
        if p.returncode == 0:
            return
        lines = (p.stderr or p.stdout).strip().splitlines()
        detail = lines[-1] if lines else ""
    raise OSError("Couldn't move it to the trash" + (f": {detail}" if detail else " (install glib2 for `gio trash`, or trash-cli)")
                  + ". The data folder has to be on the same drive as your home folder (see README, FVS_HOME).")


def _pick_folder(start: str = "") -> str | None:
    start_dir = start if start and Path(start).is_dir() else str(Path.home())
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    order = ["kdialog", "zenity"] if "kde" in desktop else ["zenity", "kdialog"]
    for tool in order:
        if not shutil.which(tool):
            continue
        args = ([tool, "--getexistingdirectory", start_dir] if tool == "kdialog"
                else [tool, "--file-selection", "--directory", "--title=Choose a folder", f"--filename={start_dir}/"])
        p = subprocess.run(args, capture_output=True, text=True)
        chosen = p.stdout.strip()
        return str(Path(chosen)) if p.returncode == 0 and chosen else None
    return None  # no dialog tool installed: type the path instead


def _startfile(path) -> None:
    subprocess.Popen(["xdg-open", str(path)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def _copy(text: str) -> None:
    for args in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
        if shutil.which(args[0]):
            subprocess.run(args, input=text.encode(), check=False)
            return


def _patch_misc() -> None:
    os.startfile = _startfile  # type: ignore[attr-defined]
    trash = types.ModuleType("studio.trash")
    trash.to_recycle_bin = _to_trash
    sys.modules["studio.trash"] = trash
    winui = types.ModuleType("studio.winui")
    winui.pick_folder = _pick_folder
    sys.modules["studio.winui"] = winui


# ---- autostart and updater ---------------------------------------------------------------------------------

AUTOSTART_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart" / "fatima-voice-studio.desktop"


def desktop_entry(extra_args: str = "") -> str:
    return ("[Desktop Entry]\nType=Application\nName=Fatima Voice Studio\n"
            "Comment=Voiceovers and voice cloning on this PC\n"
            f"Exec={LINUX_DIR / 'fatima-voice-studio'} {extra_args}".rstrip() + "\n"
            "Terminal=false\nCategories=AudioVideo;Audio;\nIcon=audio-input-microphone\n")


def _patch_autostart() -> None:
    from studio import autostart
    autostart.enabled = lambda: AUTOSTART_FILE.exists()

    def set_enabled(on: bool) -> None:
        if on:
            AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
            AUTOSTART_FILE.write_text(desktop_entry("--no-browser"), encoding="utf-8")
        else:
            AUTOSTART_FILE.unlink(missing_ok=True)

    autostart.set_enabled = set_enabled
    autostart.python_console = lambda: sys.executable
    autostart.install_launchers = lambda: None


def _patch_updater() -> None:
    from studio import updater
    msg = "Updates aren't offered on Linux. Update with `git pull` in the project folder."

    class LinuxUpdater(updater.Updater):
        async def watch(self) -> None:
            return None

        async def check(self) -> dict:
            self.state.update(status="error", error=msg)
            return self.state

        def start(self, kind: str) -> None:
            raise ValueError(msg)

    updater.Updater = LinuxUpdater


def _patch_engine() -> None:
    """Windows ties llama-tts to the app with a job object. Here setpriv makes the kernel kill it if the app dies."""
    if not shutil.which("setpriv"):
        return
    from studio import engine

    class Popen(subprocess.Popen):
        def __init__(self, args, *a, **kw):
            super().__init__(["setpriv", "--pdeathsig", "SIGKILL", *args], *a, **kw)  # setpriv execs: same pid

    engine.subprocess = types.SimpleNamespace(**{**vars(subprocess), "Popen": Popen})


def _notify(message: str, title: str | None = None) -> None:
    """AppIndicator has no notifications; use the desktop's own."""
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "Fatima Voice Studio", title or "Fatima Voice Studio", message],
                       capture_output=True)


def patch_tray() -> None:
    """Only needed for --tray (importing studio.tray pulls in pystray)."""
    import pystray
    from studio import tray
    tray.copy = _copy

    real_item = pystray.MenuItem
    pystray.MenuItem = lambda text, *a, **kw: real_item(_linux_text(text), *a, **kw)

    real_init = tray.Tray.__init__

    def init(self, *a, **kw):
        real_init(self, *a, **kw)
        self.icon.notify = _notify  # type: ignore[method-assign]

    tray.Tray.__init__ = init


# ---- wording --------------------------------------------------------------------------------------------

# The web page is upstream's and mentions Windows in a few visible texts. They are rewritten on the way out,
# so studio/web/ stays untouched.
TEXTS = [
    ("Start with Windows (in the tray)", "Start at login (in the tray)"),
    ("Start with Windows", "Start at login"),
    ("Windows notification when a batch finishes", "Desktop notification when a batch finishes"),
    ("Recycle Bin", "Trash"),
]


def _linux_text(text: str) -> str:
    for old, new in TEXTS:
        text = text.replace(old, new)
    return text


def _patch_web() -> None:
    from fastapi import Response
    from studio import app as studio_app

    create_app = studio_app.create_app

    def create(cfg: dict):
        app = create_app(cfg)

        @app.middleware("http")
        async def linux_wording(request, call_next):
            if request.url.path != "/app.js":
                return await call_next(request)
            # a "not modified" answer would keep serving the browser's old, unrewritten copy
            request.scope["headers"] = [(k, v) for k, v in request.scope["headers"]
                                        if k not in (b"if-none-match", b"if-modified-since")]
            resp = await call_next(request)
            body = b"".join([chunk async for chunk in resp.body_iterator])
            skip = {"content-length", "etag", "last-modified"}
            headers = {k: v for k, v in resp.headers.items() if k.lower() not in skip}
            return Response(_linux_text(body.decode("utf-8")), status_code=resp.status_code, headers=headers)

        return app

    studio_app.create_app = create


# ---- entry ----------------------------------------------------------------------------------------------

def apply() -> None:
    global _applied
    if _applied:
        return
    if not sys.platform.startswith("linux"):
        raise RuntimeError("linux/compat.py is for Linux only.")
    sys.path.insert(0, str(REPO))
    _patch_config()
    _patch_misc()
    _patch_hardware()
    _patch_autostart()
    _patch_updater()
    _patch_engine()
    _link_tools()
    _patch_web()
    _applied = True
