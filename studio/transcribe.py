"""Transcripts of any audio or video file (the Transcribe page): Whisper on the CPU, one job at a time, with
progress. Each transcript is a folder in data/transcripts with .txt, .srt, .vtt and Whisper's .json."""
import asyncio
import datetime as dt
import json
import logging
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from . import config, media, runtime, subtitles
from .trash import to_recycle_bin

log = logging.getLogger("studio.transcribe")
PROGRESS = re.compile(r"progress\s*=\s*(\d+)%")


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


class Transcripts:
    def __init__(self, cfg: dict, root: Path = config.DATA / "transcripts"):
        self.cfg, self.root = cfg, root
        self.root.mkdir(parents=True, exist_ok=True)
        self.items: dict[str, dict] = {}
        self._wake = asyncio.Event()
        self._proc: subprocess.Popen | None = None
        for meta in self.root.glob("*/meta.json"):
            try:
                t = json.loads(meta.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if t["status"] in ("converting", "running"):  # the app stopped mid-job
                t["status"] = "queued" if (meta.parent / "source").exists() or any(meta.parent.glob("source.*")) else "failed"
                if t["status"] == "failed":
                    t["error"] = "The app stopped before this finished. Add the file again."
            self.items[t["id"]] = t

    def folder(self, t: dict) -> Path:
        return self.root / t["id"]

    def save(self, t: dict) -> None:
        p = self.folder(t) / "meta.json"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(t, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)

    def list(self) -> list[dict]:
        return sorted(self.items.values(), key=lambda t: t["created"], reverse=True)

    def add(self, src: Path, filename: str, *, model: str | None, language: str | None, translate: bool) -> dict:
        tid = uuid.uuid4().hex[:10]
        folder = self.root / tid
        folder.mkdir(parents=True)
        shutil.move(str(src), folder / f"source{Path(filename).suffix.lower()[:6]}")
        t = {"id": tid, "name": Path(filename).name, "created": _now(), "status": "queued", "progress": 0,
             "model": model or config.subtitles_model(self.cfg), "language": language or "auto", "translate": translate,
             "error": None, "seconds": None, "took": None, "detected_language": None, "words": None, "files": {}}
        self.items[tid] = t
        self.save(t)
        self._wake.set()
        return t

    def delete(self, tid: str) -> None:
        t = self.items.get(tid)
        if not t:
            raise KeyError(tid)
        if t["status"] in ("converting", "running"):
            if self._proc and self._proc.poll() is None:
                self._proc.kill()
        to_recycle_bin(self.folder(t))
        self.items.pop(tid, None)

    async def run(self) -> None:
        while True:
            self._wake.clear()
            nxt = next((t for t in sorted(self.items.values(), key=lambda t: t["created"]) if t["status"] == "queued"), None)
            if not nxt:
                await self._wake.wait()
                continue
            started = asyncio.get_running_loop().time()
            try:
                await asyncio.to_thread(self._process, nxt)
                nxt["status"] = "done"
            except Exception as e:
                if nxt["id"] not in self.items:
                    continue  # deleted while running
                log.exception("Transcript %s failed", nxt["name"])
                nxt.update(status="failed", error=str(e) or e.__class__.__name__)
            nxt["took"] = round(asyncio.get_running_loop().time() - started, 1)
            if nxt["id"] in self.items:
                self.save(nxt)

    def _process(self, t: dict) -> None:
        folder = self.folder(t)
        src = next(folder.glob("source*"))
        wav = folder / "audio16k.wav"
        t.update(status="converting", progress=0)
        self.save(t)
        t["seconds"] = round(media.to_wav16k(src, wav), 1)
        model = t["model"] if t["model"] in config.installed_models(self.cfg) else config.subtitles_model(self.cfg)
        if not model or not subtitles.whisper_available(self.cfg):
            raise subtitles.WhisperError("No Whisper model is downloaded. Get one on the Models page.")
        t.update(status="running", model=model)
        self.save(t)
        exe = config.whisper_dir() / config.WHISPER_EXE
        threads = max(2, min(16, (os.cpu_count() or 4) - 2))
        stem = folder / "whisper"
        args = [str(exe), "-m", str(Path(self.cfg["models_dir"]).resolve() / config.MODELS[model]["files"][0]),
                "-f", str(wav), "-l", t["language"] or "auto", "-t", str(threads), "-ojf", "-of", str(stem), "-pp"]
        if t["translate"]:
            args.append("-tr")
        runtime.prepare(exe.parent)
        self._proc = subprocess.Popen(args, cwd=exe.parent, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                      creationflags=media.NO_WINDOW)
        tail = []
        for raw in self._proc.stderr:
            line = raw.decode("utf-8", "replace")
            if m := PROGRESS.search(line):
                t["progress"] = int(m[1])
            tail = (tail + [line.strip()])[-5:]
        code = self._proc.wait()
        self._proc = None
        result_file = stem.with_suffix(".json")
        if code or not result_file.exists():
            raise subtitles.WhisperError(runtime.load_problem(code)
                                         or "Whisper failed: " + (tail[-1] if tail else f"code {code}"))
        result = json.loads(result_file.read_text(encoding="utf-8", errors="replace"))
        text = subtitles.transcript(result)
        heard = subtitles.whisper_words(result)
        srt = subtitles.from_whisper(text, heard, t["seconds"]) if heard else ""
        name = re.sub(r"[^\w\- ]+", "", Path(t["name"]).stem).strip() or "transcript"
        files = {"txt": f"{name}.txt", "srt": f"{name}.srt", "vtt": f"{name}.vtt", "json": f"{name}.json"}
        (folder / files["txt"]).write_text(_paragraphs(result) + "\n", encoding="utf-8")
        (folder / files["srt"]).write_text(srt, encoding="utf-8")
        (folder / files["vtt"]).write_text("WEBVTT\n\n" + re.sub(r"(\d\d:\d\d:\d\d),(\d\d\d)", r"\1.\2", srt), encoding="utf-8")
        result_file.replace(folder / files["json"])
        wav.unlink(missing_ok=True)
        src.unlink(missing_ok=True)  # the transcript is kept, not the (possibly large) source file
        t.update(files=files, progress=100, words=len(text.split()),
                 detected_language=(result.get("result") or {}).get("language"))


def _paragraphs(result: dict) -> str:
    """Whisper's segments joined into readable paragraphs: a new one after a pause of over 1.5 s."""
    out, cur, last_end = [], [], None
    for seg in result.get("transcription", []):
        start, end = seg["offsets"]["from"] / 1000, seg["offsets"]["to"] / 1000
        if cur and last_end is not None and start - last_end > 1.5:
            out.append(" ".join(cur))
            cur = []
        cur.append(seg.get("text", "").strip())
        last_end = end
    if cur:
        out.append(" ".join(cur))
    return "\n\n".join(p for p in out if p)
