"""The second voice engine: Fish Audio S2 Pro through s2.cpp's HTTP server.

The server is started once with the model and stays loaded (the start costs about 5 s), so each part is one
POST /generate: the text, the voice's clip and its transcript (s2.cpp clones a voice from both), a seed and a length
cap. The transcript is made once with Whisper and kept in the voice's voice.json. The server is stopped after a few
idle minutes, before Qwen3-TTS runs (both won't fit on an 8 GB card), and when the app closes.
"""
import contextlib
import http.client
import json
import logging
import os
import re
import socket
import subprocess
import threading
import time
import uuid
from pathlib import Path

from . import config, hardware, runtime, subtitles, text as textmod

log = logging.getLogger("studio.s2engine")

FRAME_RATE = 44100 / 2048  # S2 Pro's codec frames per second of audio
IDLE_STOP_S = 300          # free the graphics card after this long without a part
SHARE_GB = 12              # below this much graphics memory, S2 Pro and Whisper take turns on the card
START_TIMEOUT_S = 240
PROGRESS = re.compile(r"\[Generate\]\s+(\d+)\s*/\s*(\d+)\s+tokens")
VK_DEVICE = re.compile(r"ggml_vulkan: (\d+) = .*?\| uma: (\d)")  # uma 1 = built into the processor
CRLF = bytes([13, 10])  # multipart line break


class S2Error(Exception):
    pass


class S2Cancelled(Exception):
    pass


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class S2Server:
    def __init__(self, cfg: dict, job=None):
        self.cfg = cfg
        self.job = job              # Windows job object: the server dies with the app
        self.proc: subprocess.Popen | None = None
        self.port = 0
        self.loaded: tuple | None = None  # (model, engine, device) the running server has
        self.frames = 0             # progress of the part being spoken
        self.last_used = 0.0
        self.log_path = config.DATA / "logs" / "s2.log"
        self._ready = threading.Event()
        self._uma: dict[int, bool] = {}
        self._conn: http.client.HTTPConnection | None = None
        self._cancel = False
        self._lock = threading.RLock()  # re-entrant: a part's voice transcript runs Whisper through gpu_turn
        self._held = 0
        threading.Thread(target=self._idle_watch, daemon=True).start()

    # ---- the server process ----

    def running(self) -> bool:
        return bool(self.proc and self.proc.poll() is None)

    def stop(self) -> None:
        proc, self.proc, self.loaded = self.proc, None, None
        if proc and proc.poll() is None:
            log.info("Stopping the S2 Pro server")
            proc.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass

    def _idle_watch(self) -> None:
        while True:
            time.sleep(15)
            if self.running() and not self._held and time.monotonic() - self.last_used > IDLE_STOP_S:
                self.stop()

    @contextlib.contextmanager
    def gpu_turn(self):
        """Whisper's turn on the graphics card. On cards under SHARE_GB, S2 Pro (about 7 GB) and Whisper don't fit
        together: wait for the part being spoken to finish, unload the server, and let the next part load it again
        (about 5 s). Bigger cards run both side by side."""
        gpu = hardware.main_gpu(hardware.detect())
        if not gpu or gpu["vram_gb"] >= SHARE_GB:
            yield
            return
        with self._lock:
            self._held += 1
            try:
                if self.running():
                    log.info("S2 Pro makes room on the graphics card for Whisper")
                    self.stop()
                yield
            finally:
                self._held -= 1

    def _device(self) -> int | None:
        """Vulkan device to use: the one remembered (also found by Whisper: the same order), else let it start on 0
        and move to the dedicated card if 0 turns out to be built into the processor."""
        for key in ("s2_vk_device", "whisper_vk_device"):
            if self.cfg.get(key) is not None:
                return int(self.cfg[key])
        return 0

    def ensure(self, model: str) -> None:
        """A server with this model on the engine in use, started if needed (already locked by speak)."""
        engine = config.s2_engine(self.cfg)
        if not engine:
            raise S2Error("S2 Pro runs on the NVIDIA · CUDA or AMD / Intel · Vulkan engine. Switch to one on Setup.")
        device = self._device() if engine == "vulkan" else 0
        if self.running() and self.loaded == (model, engine, device):
            return
        self.stop()
        for _ in range(2):
            better = self._start(model, engine, device)
            if better is None:
                return
            log.info("S2 Pro started on the built-in graphics; using Vulkan device %s (the graphics card)", better)
            self.cfg["s2_vk_device"] = device = better
            config.save(self.cfg)

    def _start(self, model: str, engine: str, device: int) -> int | None:
        """Start the server; returns a better Vulkan device if it picked a built-in chip (then it's stopped)."""
        folder = config.s2_dir(engine)
        exe = folder / config.S2_EXE
        if not exe.exists():
            raise S2Error("S2 Pro's engine part for this graphics card is missing. Open Models and click Get it.")
        gguf = Path(self.cfg["models_dir"]).resolve() / config.MODELS[model]["files"][0]
        self.port = _free_port()
        args = [str(exe), "--server", "-H", "127.0.0.1", "-P", str(self.port), "--model", str(gguf),
                "--tokenizer", str(folder / "tokenizer.json"), "--gpu-layers", "36", "--log-level", "info"]
        args += ["--cuda", "0"] if engine == "cuda" else ["--vulkan", str(device)]
        env = os.environ.copy()
        if engine == "cuda":  # cuBLAS and cudart come from the voice engine's folder
            env["PATH"] = str(config.engine_dir(self.cfg, "cuda")) + os.pathsep + env.get("PATH", "")
        runtime.prepare(folder)
        self._ready.clear()
        self._uma = {}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log.info("Starting the S2 Pro server (%s, %s)", config.MODELS[model]["label"], engine)
        self.proc = subprocess.Popen(args, cwd=folder, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if self.job:
            self.job.add(self.proc)
        threading.Thread(target=self._pump, args=(self.proc,), daemon=True).start()
        deadline = time.monotonic() + START_TIMEOUT_S
        while time.monotonic() < deadline:
            if self._ready.wait(0.5):
                break
            if self.proc.poll() is not None:
                raise S2Error(self._start_problem())
        else:
            self.stop()
            raise S2Error("S2 Pro took too long to start and was stopped.")
        if engine == "vulkan" and self._uma.get(device) and not all(self._uma.values()):
            self.stop()
            return min(d for d, built_in in self._uma.items() if not built_in)
        while time.monotonic() < deadline:  # "Server starting" comes just before it listens
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                    break
            except OSError:
                if self.proc.poll() is not None:
                    raise S2Error(self._start_problem())
                time.sleep(0.2)
        self.loaded = (model, engine, device)
        return None

    def _pump(self, proc: subprocess.Popen) -> None:
        """The server's output: to s2.log, and the bits the app watches (ready, devices, progress)."""
        with open(self.log_path, "a", encoding="utf-8", errors="replace") as logf:
            for raw in proc.stdout:
                line = raw.decode("utf-8", "replace").rstrip()
                logf.write(line + "\n")
                if "Server starting on" in line:
                    self._ready.set()
                elif m := VK_DEVICE.search(line):
                    self._uma[int(m[1])] = m[2] == "1"
                elif m := PROGRESS.search(line):
                    self.frames = int(m[1])
            logf.flush()

    def _start_problem(self) -> str:
        code = self.proc.returncode if self.proc else None
        try:
            tail = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]
        except OSError:
            tail = []
        if any("ErrorOutOfDeviceMemory" in l or "out of memory" in l.lower() for l in tail):
            return ("S2 Pro didn't fit in the graphics card's memory. Close other programs that use it, or use the "
                    "smaller Q6 model.")
        detail = next((l for l in reversed(tail) if "rror" in l or "ailed" in l), "")
        return runtime.load_problem(code) or f"S2 Pro couldn't start: {detail or f'code {code}'}"

    # ---- speaking ----

    def cancel(self) -> None:
        self._cancel = True
        conn = self._conn
        if conn is not None and conn.sock is not None:
            try:  # cut the request now: the server stops generating when it goes away
                conn.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def _post(self, fields: dict, files: dict, dest: Path) -> None:
        """POST /generate as multipart over a connection this object can cut (http.client: a socket we hold, so
        Stop doesn't wait for the part to finish; the server sends nothing until the audio is ready)."""
        boundary = uuid.uuid4().hex
        body = bytearray()
        for name, value in fields.items():
            body += f'--{boundary}'.encode() + CRLF + f'Content-Disposition: form-data; name="{name}"'.encode() + CRLF * 2
            body += value.encode("utf-8") + CRLF
        for name, (filename, data, ctype) in files.items():
            body += f'--{boundary}'.encode() + CRLF + f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode()
            body += CRLF + f'Content-Type: {ctype}'.encode() + CRLF * 2 + data + CRLF
        body += f'--{boundary}--'.encode() + CRLF
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=float(self.cfg.get("timeout_s") or 900))
        self._conn = conn
        try:
            conn.request("POST", "/generate", body=bytes(body),
                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            r = conn.getresponse()
            if r.status != 200:
                raise S2Error(f"S2 Pro couldn't speak this part: {r.read().decode('utf-8', 'replace')[:300]}")
            with open(dest, "wb") as f:
                while chunk := r.read(1 << 16):
                    f.write(chunk)
        finally:
            self._conn = None
            conn.close()

    def speak(self, model: str, text: str, voice: Path | None, seed: int, out: Path) -> None:
        """Speak `text` into the WAV file `out` (blocking; run it in a thread)."""
        with self._lock:
            self._held += 1
            try:
                self._speak(model, text, voice, seed, out)
            finally:
                self._held -= 1

    def _speak(self, model: str, text: str, voice: Path | None, seed: int, out: Path) -> None:
        self._cancel = False
        ref = (voice, transcript(self.cfg, voice)) if voice else None  # before the server takes the card
        self.ensure(model)
        if self._cancel:
            raise S2Cancelled()
        expected = textmod.estimate_seconds(text) * FRAME_RATE
        params = {"seed": int(seed) % 2**31, "max_new_tokens": int(min(4096, expected * 3 + 150))}
        fields = {"text": text, "params": json.dumps(params)}
        files = {}
        if ref:
            fields["reference_text"] = ref[1]
            files["reference"] = ("voice.wav", Path(ref[0]).read_bytes(), "audio/wav")
        self.frames = 0
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.unlink(missing_ok=True)
        tmp = out.with_name(out.name + ".part")
        try:
            self._post(fields, files, tmp)
            tmp.replace(out)
        except (OSError, http.client.HTTPException) as e:
            tmp.unlink(missing_ok=True)
            if self._cancel:
                raise S2Cancelled()
            try:  # a dropped connection is usually the server going down: give Windows a moment to say so
                self.proc.wait(timeout=3)
            except (subprocess.TimeoutExpired, AttributeError):
                pass
            if not self.running():
                self.stop()
                raise S2Error("S2 Pro stopped while speaking. It starts again for the next part.") from e
            raise S2Error(f"S2 Pro couldn't speak this part: {e}") from e
        finally:
            self.last_used = time.monotonic()
        if self._cancel:
            out.unlink(missing_ok=True)
            raise S2Cancelled()


def transcript(cfg: dict, clip: Path) -> str:
    """What the voice's clip says (s2.cpp needs it to clone the voice): from voice.json, else heard by Whisper once
    and kept there."""
    meta_path = Path(clip).parent / "voice.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    if meta.get("transcript"):
        return meta["transcript"]
    if not subtitles.whisper_available(cfg):
        raise S2Error("S2 Pro needs to know what the voice's clip says: download a Whisper model on Models, or type "
                      "it in the voice's Edit dialog.")
    words = subtitles.transcript(subtitles.run_whisper(cfg, Path(clip), meta.get("language"))).strip()
    if not words:
        raise S2Error("Whisper couldn't hear any words in the voice's clip. Type what it says in the voice's Edit dialog.")
    if meta_path.exists():
        meta["transcript"] = words
        tmp = meta_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(meta_path)
    log.info("Transcribed the clip of %s for S2 Pro", meta.get("name") or clip)
    return words
