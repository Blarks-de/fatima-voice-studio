"""Runs llama-tts.exe (llama.cpp) once per segment and reports its progress.

llama.cpp has no "stay loaded" mode for speech yet, so every segment starts the engine, loads the model
(about 5 s on an NVIDIA GPU, the files stay in the Windows file cache after the first time), speaks the text and
exits. Segments are about 40 seconds of speech, which keeps that overhead near 10%.
"""
import asyncio
import logging
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from . import config, text as textmod

log = logging.getLogger("studio.engine")

FRAMES = re.compile(r"frames generated: (\d+)")
DONE = re.compile(r"generated (\d+) frames")
FRAME_RATE = 12.5  # Qwen3-TTS 12 Hz codec: frames of audio per second


class EngineError(Exception):
    pass


class Cancelled(Exception):
    pass


class Engine:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.state = "idle"  # idle | busy | error
        self.error: str | None = None
        self.proc: subprocess.Popen | None = None
        self.frames = 0          # progress of the segment being spoken
        self.frames_expected = 0
        self.started = 0.0
        self.log_path = config.DATA / "logs" / "engine.log"
        self.tmp = config.DATA / "tmp"
        self._lock = asyncio.Lock()
        self._cancel = False
        self._job = _KillOnCloseJob() if sys.platform == "win32" else None

    def status(self) -> dict:
        return {"state": self.state, "error": self.error, "engine": self.cfg["engine"],
                "installed": config.installed_engines(self.cfg),
                "frames": self.frames, "frames_expected": self.frames_expected,
                "elapsed": round(time.monotonic() - self.started, 1) if self.state == "busy" else None}

    def ready_problem(self, model: str) -> str | None:
        """Why this model can't run right now (None if it can)."""
        if self.cfg["engine"] not in config.installed_engines(self.cfg):
            return "No engine installed. Open Setup and download one."
        if model not in config.MODELS or config.MODELS[model]["kind"] != "voice":
            return f"Unknown voice model: {model}"
        if model not in config.installed_models(self.cfg):
            return f"{config.MODELS[model]['label']} isn't downloaded. Open Models to download it."
        return None

    def cancel_current(self) -> None:
        self._cancel = True
        proc = self.proc
        if proc and proc.poll() is None:
            proc.kill()

    async def speak(self, model: str, text: str, *, language: str, voice: Path | None, seed: int, out: Path) -> float:
        """Speak `text` into the WAV file `out`; returns the seconds it took."""
        if problem := self.ready_problem(model):
            self.state, self.error = "error", problem
            raise EngineError(problem)
        async with self._lock:
            self._cancel = False
            started = time.monotonic()
            try:
                await asyncio.to_thread(self._run, model, text, language, voice, seed, out)
            except Cancelled:
                self.state = "idle"
                raise
            except EngineError as e:
                self.state, self.error = "error", str(e)
                raise
            self.state, self.error = "idle", None
            return time.monotonic() - started

    def _run(self, model: str, text: str, language: str, voice: Path | None, seed: int, out: Path) -> None:
        m = config.MODELS[model]
        models_dir = Path(self.cfg["models_dir"]).resolve()
        out = Path(out).resolve()  # the engine runs in its own folder
        voice = Path(voice).resolve() if voice else None
        exe = config.engine_dir(self.cfg) / config.ENGINE_EXE
        gpu = config.ENGINES[self.cfg["engine"]]["gpu"]
        self.tmp.mkdir(parents=True, exist_ok=True)
        prompt = self.tmp / f"{uuid.uuid4().hex[:10]}.txt"
        prompt.write_text(text, encoding="utf-8")  # a file, not the command line: keeps accents and quotes intact
        expected = textmod.estimate_seconds(text) * FRAME_RATE
        # Cap the length well above what the text needs: a model that never stops can't run away for minutes.
        cap = int(expected * 3 + 150)
        args = [str(exe), "-m", str(models_dir / m["files"][0]), "-mm", str(models_dir / m["files"][1]),
                "-ngl", "99" if gpu else "0", "-c", "4096", "-n", str(cap),
                "-f", str(prompt), "--tts-lang", language, "-s", str(int(seed) % 2**31),
                "--output", str(out)]
        if voice:
            args += ["--tts-speaker-file", str(voice)]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.unlink(missing_ok=True)
        self.state, self.frames, self.frames_expected, self.started = "busy", 0, int(expected), time.monotonic()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        tail: list[str] = []
        try:
            self.proc = subprocess.Popen(args, cwd=exe.parent, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if self._job:
                self._job.add(self.proc)
            pump = threading.Thread(target=self._pump, args=(self.proc, tail), daemon=True)
            pump.start()
            try:
                code = self.proc.wait(timeout=float(self.cfg.get("timeout_s") or 900))
            except subprocess.TimeoutExpired:
                self.proc.kill()
                raise EngineError("The engine took too long on this segment and was stopped.")
            pump.join(timeout=5)
        finally:
            self.proc = None
            prompt.unlink(missing_ok=True)
        if self._cancel:
            out.unlink(missing_ok=True)
            raise Cancelled()
        if code != 0 or not out.exists():
            detail = next((l for l in reversed(tail) if " E " in l or "error" in l.lower()), tail[-1] if tail else "")
            raise EngineError(_friendly(detail, code))
        if self.frames >= cap - 1:
            log.warning("Segment hit the length cap (%s frames)", cap)

    def _pump(self, proc: subprocess.Popen, tail: list[str]) -> None:
        with open(self.log_path, "a", encoding="utf-8", errors="replace") as logf:
            for raw in proc.stdout:
                line = raw.decode("utf-8", "replace").rstrip()
                if not line:
                    continue
                if m := FRAMES.search(line) or DONE.search(line):
                    self.frames = int(m[1])
                if "print_info" in line or "llama_model_loader" in line or "load_tensors" in line:
                    continue  # model-loading chatter
                logf.write(line + "\n")
                tail.append(line)
                del tail[:-40]


def _friendly(detail: str, code: int) -> str:
    d = detail.lower()
    if "out of memory" in d or "failed to allocate" in d or "cudamalloc" in d:
        return "The graphics card ran out of memory. Close other apps using the GPU, or use the smaller Q4 model."
    if "failed to load" in d or "no such file" in d:
        return "The engine couldn't load the model files. Try downloading the model again on the Models page."
    if "audio" in d and "speaker" in d:
        return "The engine couldn't read the voice clip. Re-add the voice from a WAV or MP3 file."
    return f"The engine stopped (code {code}). {detail.strip()[:200]}".strip()


class _KillOnCloseJob:
    """Windows job object: engine processes die with this process, so they never keep the GPU after a crash."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class Extended(ctypes.Structure):
            _fields_ = [("Basic", Basic), ("Io", ctypes.c_ulonglong * 6),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        self._k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._k32.CreateJobObjectW.restype = wintypes.HANDLE
        self._k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self._k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._handle = self._k32.CreateJobObjectW(None, None)
        info = Extended()
        info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        self._k32.SetInformationJobObject(self._handle, 9, ctypes.byref(info), ctypes.sizeof(info))

    def add(self, proc: subprocess.Popen) -> None:
        self._k32.AssignProcessToJobObject(self._handle, int(proc._handle))
