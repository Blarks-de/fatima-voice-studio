"""Downloads models and engine builds (resumable, SHA-256 checked), reports progress, and removes them again."""
import asyncio
import hashlib
import logging
import shutil
import zipfile
from pathlib import Path

import httpx

from . import config

log = logging.getLogger("studio.downloads")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 22):
            h.update(chunk)
    return h.hexdigest()


class Downloads:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.jobs: dict[str, dict] = {}  # key -> {status, done, total, error}
        self._tasks: dict[str, asyncio.Task] = {}

    @property
    def folder(self) -> Path:
        return Path(self.cfg["models_dir"])

    def missing(self, key: str) -> list[str]:
        return [f for f in config.model_files(key) if not (self.folder / f).exists()]

    def _whisper_missing(self) -> bool:
        return not (config.whisper_dir() / config.WHISPER_EXE).exists()

    def status(self) -> list[dict]:
        installed = config.installed_models(self.cfg)
        out = []
        for key, m in config.MODELS.items():
            extra = config.WHISPER_ZIP[1] if m["kind"] == "subtitles" and self._whisper_missing() else 0
            out.append({
                "key": key, "kind": m["kind"], "label": m["label"], "short": m["short"], "about": m["about"],
                "license": m["license"], "noncommercial": bool(m.get("noncommercial")), "page": m["page"],
                "installed": key in installed and not (m["kind"] == "subtitles" and self._whisper_missing()),
                "size": sum(config.FILES[f][1] for f in config.model_files(key)),
                "to_download": sum(config.FILES[f][1] for f in self.missing(key)) + extra,
                "partial": self.partial_bytes(key),
                "shared": [f for f in config.model_files(key)
                           if sum(f in config.model_files(k) for k in config.MODELS) > 1],
                "job": self.jobs.get(key),
            })
        return out

    def partial_bytes(self, key: str) -> int:
        parts = (self.folder / (f + ".part") for f in self.missing(key))
        return sum(p.stat().st_size for p in parts if p.exists())

    def start(self, key: str) -> None:
        if key not in config.MODELS:
            raise ValueError("Unknown model")
        self._launch(key, self._run(key))

    def _launch(self, key: str, coro) -> None:
        if key in self._tasks and not self._tasks[key].done():
            coro.close()
            return
        self.jobs[key] = {"status": "downloading", "done": 0, "total": 0, "error": None}
        self._tasks[key] = asyncio.create_task(coro)

    def busy(self, key: str) -> bool:
        t = self._tasks.get(key)
        return bool(t and not t.done())

    def cancel(self, key: str) -> None:
        task = self._tasks.get(key)
        if task and not task.done():
            task.cancel()

    async def _run(self, key: str) -> None:
        job = self.jobs[key]
        files = self.missing(key)
        need_whisper = config.MODELS[key]["kind"] == "subtitles" and self._whisper_missing()
        job["total"] = sum(config.FILES[f][1] for f in files) + (config.WHISPER_ZIP[1] if need_whisper else 0)
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(30, read=300)) as client:
                for name in files:
                    url, size, sha = config.FILES[name]
                    await self._fetch(client, url, size, sha, self.folder / name, job)
                if need_whisper:
                    await self._install_zips(client, [config.WHISPER_ZIP], config.whisper_dir(), config.WHISPER_EXE, job)
            job["status"] = "done"
            log.info("Downloaded %s", key)
            m = config.MODELS[key]
            if m["kind"] == "voice" and self.cfg["default_model"] not in config.installed_models(self.cfg):
                self.cfg["default_model"] = key  # first voice model: make it the default
                config.save(self.cfg)
        except asyncio.CancelledError:
            job["status"] = "cancelled"  # the .part file stays, so the next download resumes
        except Exception as e:
            log.exception("Download of %s failed", key)
            job.update(status="failed", error=str(e) or e.__class__.__name__)

    def _headers(self, url: str) -> dict:
        t = (self.cfg.get("hf_token") or "").strip()
        return {"Authorization": f"Bearer {t}"} if t and url.startswith("https://huggingface.co/") else {}

    async def _fetch(self, client: httpx.AsyncClient, url: str, size: int, sha: str, final: Path, job: dict) -> None:
        part = final.with_name(final.name + ".part")
        have = part.stat().st_size if part.exists() else 0
        if have > size:
            part.unlink()
            have = 0
        if have < size:
            headers = ({"Range": f"bytes={have}-"} if have else {}) | self._headers(url)
            async with client.stream("GET", url, headers=headers) as r:
                r.raise_for_status()
                if have and r.status_code != 206:  # server ignored the range; start over
                    have = 0
                job["done"] += have
                with open(part, "ab" if have else "wb") as f:
                    async for chunk in r.aiter_bytes(1 << 20):
                        f.write(chunk)
                        job["done"] += len(chunk)
        else:
            job["done"] += have
        if part.stat().st_size != size:
            raise IOError(f"{final.name} is incomplete ({part.stat().st_size} of {size} bytes); try again.")
        job["status"] = "checking"
        digest = await asyncio.to_thread(_sha256, part)
        if digest != sha:
            part.unlink()
            raise IOError(f"{final.name} didn't match its published checksum, so it was deleted. Download it again.")
        job["status"] = "downloading"
        part.replace(final)

    async def _install_zips(self, client, zips: list[tuple[str, int, str]], target: Path, exe: str, job: dict) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        paths = []
        for url, size, sha in zips:
            path = target.parent / url.rsplit("/", 1)[1]
            if path.exists():
                job["done"] += size
            else:
                await self._fetch(client, url, size, sha, path, job)
            paths.append(path)
        job["status"] = "installing"
        await asyncio.to_thread(self._unpack, paths, target, exe)

    @staticmethod
    def _unpack(zips: list[Path], target: Path, exe: str) -> None:
        staging = target.with_name(target.name + ".new")
        shutil.rmtree(staging, ignore_errors=True)
        for z in zips:
            with zipfile.ZipFile(z) as f:
                f.extractall(staging)
        found = next(staging.rglob(exe), None)  # some builds keep their files in a subfolder (Release/)
        if not found:
            raise IOError(f"The download doesn't contain {exe}")
        if found.parent != staging:
            inner = found.parent
            for item in inner.iterdir():
                shutil.move(str(item), staging / item.name)
        if target.exists():
            shutil.rmtree(target)
        staging.replace(target)
        for z in zips:
            z.unlink()

    # ---- engine builds (job key "engine:<id>") ----

    def engine_zips(self, key: str) -> list[tuple[str, int, Path]]:
        root = config.engine_dir(self.cfg, key).parent
        return [(url, size, root / url.rsplit("/", 1)[1]) for url, size, _ in config.ENGINES[key]["zips"]]

    def engine_partial(self, key: str) -> int:
        parts = (z.with_name(z.name + ".part") for _, _, z in self.engine_zips(key))
        return sum(p.stat().st_size for p in parts if p.exists())

    def start_engine(self, key: str) -> None:
        if key not in config.ENGINES:
            raise ValueError("Unknown engine")
        self._launch("engine:" + key, self._run_engine(key))

    async def _run_engine(self, key: str) -> None:
        job = self.jobs["engine:" + key]
        zips = config.ENGINES[key]["zips"]
        job["total"] = sum(size for _, size, _ in zips)
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(30, read=300)) as client:
                await self._install_zips(client, zips, config.engine_dir(self.cfg, key), config.ENGINE_EXE, job)
            job["status"] = "done"
            log.info("Installed engine %s", key)
            if self.cfg["engine"] not in config.installed_engines(self.cfg):  # first engine: use it
                self.cfg["engine"] = key
                config.save(self.cfg)
        except asyncio.CancelledError:
            job["status"] = "cancelled"
        except Exception as e:
            log.exception("Engine %s download failed", key)
            job.update(status="failed", error=str(e) or e.__class__.__name__)

    def discard_engine(self, key: str) -> None:
        if self.busy("engine:" + key):
            raise RuntimeError("That engine is downloading right now. Cancel it first.")
        for _, _, z in self.engine_zips(key):
            for p in (z, z.with_name(z.name + ".part")):
                p.unlink(missing_ok=True)
        self.jobs.pop("engine:" + key, None)

    def delete_engine(self, key: str) -> None:
        self.discard_engine(key)
        shutil.rmtree(config.engine_dir(self.cfg, key), ignore_errors=True)

    # ---- removing models ----

    def discard(self, key: str) -> list[str]:
        """Abandon a paused download: delete its unfinished .part files."""
        busy = {f for k, t in self._tasks.items() if not t.done() and k in config.MODELS for f in config.model_files(k)}
        if any(name in busy for name in self.missing(key)):
            raise RuntimeError("Another download is using this file right now. Cancel it first.")
        removed = []
        for name in self.missing(key):
            part = self.folder / (name + ".part")
            if part.exists():
                part.unlink()
                removed.append(part.name)
        self.jobs.pop(key, None)
        return removed

    def delete(self, key: str) -> list[str]:
        """Remove a model's files, keeping any another installed model still uses."""
        others = {f for k in config.installed_models(self.cfg) if k != key for f in config.model_files(k)}
        removed = []
        for name in config.model_files(key):
            if name in others:
                continue
            for path in (self.folder / name, self.folder / (name + ".part")):
                if path.exists():
                    path.unlink()
                    removed.append(path.name)
        self.jobs.pop(key, None)
        return removed
