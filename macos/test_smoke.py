#!/usr/bin/env python3
"""Smoke test for the macOS compatibility layer (macos/compat.py).

compat.py patches parts of studio/ at runtime. If upstream renames or moves one of them, the patch stops working
without any error message. This test is there to notice that.

  static    every name compat.py replaces or relies on still exists in studio/ (read with ast, nothing is imported)
  runtime   apply() works, and the patched names are the ones the rest of studio/ really uses

It needs the packages from requirements-macos.txt, Apple Silicon macOS, but no GPU and no llama-tts. Everything it
writes goes to a temporary folder, not to your home directory.

  .venv/bin/python macos/test_smoke.py
  .venv/bin/python -m pytest macos/test_smoke.py
"""
import ast
import os
import platform
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parent / "studio"

TARGETS = {
    "config": {"HOME", "DATA", "CONFIG_FILE", "VOICES", "MUSIC", "DEFAULTS", "ENGINES", "ENGINE_EXE", "WHISPER_EXE",
               "engine_dir", "installed_engines", "whisper_dir", "tool_dir"},
    "hardware": {"_vendor", "_registry_gpus", "_ram_gb", "_cpu", "on_battery", "recommended_engine"},
    "autostart": {"enabled", "set_enabled", "python_console", "install_launchers"},
    "updater": {"Updater"},
    "trash": {"to_recycle_bin"},
    "winui": {"pick_folder"},
    "engine": {"subprocess"},
    "tray": {"copy", "Tray"},
    "app": {"create_app", "Updater", "pick_folder"},
    "media": {"ffmpeg_exe", "ffmpeg_source"},
    "downloads": {"Downloads"},
}
CLASS_MEMBERS = {
    ("updater", "Updater"): {"watch", "check", "start"},
    ("tray", "Tray"): {"__init__"},
    ("downloads", "Downloads"): {"tools", "start_tool", "delete_tool", "start_engine", "_whisper_missing"},
}
DEFAULT_KEYS = {"batches_dir", "exports_dir", "models_dir", "engine", "check_updates"}
ENGINE_FLAGS = {"-m", "-mm", "-ngl", "-c", "4096", "-n", "-f", "--tts-lang", "-s", "--output", "--tts-speaker-file"}


def parse(module: str) -> ast.Module:
    return ast.parse((STUDIO / f"{module}.py").read_text(encoding="utf-8"), filename=f"studio/{module}.py")


def top_level_names(tree: ast.Module) -> set[str]:
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(a.asname or a.name for a in node.names)
    return names


class StaticChecks(unittest.TestCase):
    """Does what compat.py patches still exist upstream? Runs anywhere, imports nothing."""

    def test_patch_targets_exist(self):
        for module, wanted in TARGETS.items():
            with self.subTest(module=module):
                self.assertTrue((STUDIO / f"{module}.py").exists(), f"studio/{module}.py is gone")
                missing = wanted - top_level_names(parse(module))
                self.assertFalse(missing, f"studio/{module}.py no longer has {sorted(missing)}; compat.py patches them")

    def test_patched_class_members_exist(self):
        for (module, cls), wanted in CLASS_MEMBERS.items():
            with self.subTest(cls=f"{module}.{cls}"):
                node = next(n for n in parse(module).body if isinstance(n, ast.ClassDef) and n.name == cls)
                members = {n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
                self.assertFalse(wanted - members, f"{module}.{cls} no longer has {sorted(wanted - members)}")

    def test_config_defaults_keys_exist(self):
        for node in parse("config").body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "DEFAULTS" for t in node.targets):
                keys = {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
                self.assertFalse(DEFAULT_KEYS - keys, f"config.DEFAULTS lost {sorted(DEFAULT_KEYS - keys)}")
                return
        self.fail("config.DEFAULTS not found")

    def test_engine_command_line(self):
        used = {n.value for n in ast.walk(parse("engine")) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        self.assertFalse(ENGINE_FLAGS - used,
                         f"engine.py no longer passes {sorted(ENGINE_FLAGS - used)} to llama-tts. "
                         "Check LLAMA_MIN_BUILD in setup.sh and the llama.cpp version in the README.")

    def test_shell_scripts_are_syntactically_valid(self):
        for name in ("build-llama.sh", "build-whisper.sh"):
            with self.subTest(script=name):
                r = subprocess.run(["bash", "-n", str(HERE / name)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)


@unittest.skipUnless(sys.platform == "darwin" and platform.machine() == "arm64", "the compatibility layer is for Apple Silicon Macs")
class RuntimeChecks(unittest.TestCase):
    """apply() the patches, then check what the app really ends up using."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        root = Path(cls.tmp.name)
        os.environ.update(FVS_HOME=str(root / "home"), FVS_MUSIC_DIR=str(root / "music"),
                          FVS_LAUNCH_AGENTS_DIR=str(root / "launchagents"))
        sys.path.insert(0, str(HERE))
        import compat
        compat.apply()
        cls.compat = compat

    def test_apply_twice_is_harmless(self):
        self.compat.apply()

    def test_fvs_home_and_music_dir_use_the_overrides(self):
        root = Path(self.tmp.name)
        self.assertEqual(self.compat.fvs_home(), root / "home")
        self.assertEqual(self.compat.music_dir(), root / "music" / "Fatima Voice Studio")

    def test_llama_build_is_read_from_every_known_version_format(self):
        script = Path(self.tmp.name) / "fake-llama-tts"
        old = os.environ.get("FVS_LLAMA_TTS")
        try:
            os.environ["FVS_LLAMA_TTS"] = str(script)
            for line, want in [("version: 0.3.0-dev (build 10689, commit c13e6fe)", "b10689"),
                               ("version: 10689 (c13e6fe)", "b10689"), ("version: b9000 (abc)", "b9000"),
                               ("no version here", None)]:
                script.write_text(f"#!/bin/sh\necho '{line}' >&2\n")
                script.chmod(0o755)
                self.assertEqual(self.compat.llama_build(), want, line)
            os.environ["FVS_LLAMA_TTS"] = str(script) + "-missing"
            self.assertIsNone(self.compat.llama_build())
        finally:
            if old is None:
                os.environ.pop("FVS_LLAMA_TTS", None)
            else:
                os.environ["FVS_LLAMA_TTS"] = old

    def test_paths_and_engine(self):
        home = Path(os.environ["FVS_HOME"])
        from studio import config as c
        self.assertEqual(c.ENGINE_EXE, "llama-tts")
        self.assertEqual(c.WHISPER_EXE, "whisper-cli")
        self.assertEqual(list(c.ENGINES), ["system"])
        self.assertEqual(c.DEFAULTS["engine"], "system")
        self.assertFalse(c.DEFAULTS["check_updates"])
        self.assertEqual(c.engine_dir({"engine": "system"}), home / "engine" / "system")
        self.assertEqual(c.DATA, home / "data")
        self.assertIsInstance(c.installed_engines({"engine": "system"}), list)

    def test_about_page_does_not_show_the_windows_engine_pin(self):
        from studio import config as c
        self.assertEqual(c.ENGINE_RELEASE, self.compat.llama_build() or "not found")

    def _client(self):
        from fastapi.testclient import TestClient
        from studio import config, app
        return TestClient(app.create_app(config.load()), headers={"X-Studio": "1"})

    def test_ffmpeg_is_the_system_one_never_a_windows_exe(self):
        from studio import media, config
        fake_exe = config.tool_dir("ffmpeg") / "ffmpeg.exe"
        fake_exe.parent.mkdir(parents=True, exist_ok=True)
        fake_exe.write_text("MZ not a macOS program")
        self.addCleanup(fake_exe.unlink, missing_ok=True)
        with tempfile.TemporaryDirectory() as bindir:
            real = Path(bindir) / "ffmpeg"
            real.write_text("#!/bin/sh\n")
            real.chmod(0o755)
            old_path = os.environ["PATH"]
            os.environ["PATH"] = bindir
            try:
                self.assertEqual(media.ffmpeg_exe(), str(real), "ffmpeg.exe must not win over the system ffmpeg")
                self.assertEqual(media.ffmpeg_source(), "system")
            finally:
                os.environ["PATH"] = old_path
            os.environ["PATH"] = bindir + "/nothing-here"
            try:
                self.assertIsNone(media.ffmpeg_exe(), "ffmpeg.exe must not be used when there is no system ffmpeg")
                self.assertIsNone(media.ffmpeg_source())
            finally:
                os.environ["PATH"] = old_path

    def test_no_windows_ffmpeg_download_is_offered_or_started(self):
        from studio import config
        c = self._client()
        tools = c.get("/api/tools").json()
        self.assertEqual([t["key"] for t in tools], ["ffmpeg"])
        self.assertTrue(tools[0]["system_only"])
        self.assertEqual(tools[0]["size"], 0)
        r = c.post("/api/tools/ffmpeg/download")
        self.assertEqual(r.status_code, 409)
        self.assertIn("ffmpeg", r.json()["detail"])
        self.assertFalse((config.tool_dir("ffmpeg") / "ffmpeg.exe").exists())

    def test_system_engine_has_no_download(self):
        c = self._client()
        eng = next(e for e in c.get("/api/setup").json()["engines"] if e["key"] == "system")
        self.assertEqual(eng["size"], 0)
        r = c.post("/api/setup/engines/system/download")
        self.assertEqual(r.status_code, 409)
        self.assertIn("nothing to download", r.json()["detail"])

    def test_whisper_model_download_skips_the_windows_zip(self):
        from studio import downloads, config
        d = downloads.Downloads(config.load())
        self.assertFalse(d._whisper_missing(), "no Windows whisper-bin-x64.zip must ever be requested on macOS")
        for m in d.status():
            if m["kind"] == "subtitles":
                self.assertIn("build-whisper.sh", m["about"])

    def test_missing_whisper_cli_gets_a_clear_warning(self):
        from studio import config, hardware
        cfg = config.load()
        folder = Path(cfg["models_dir"])
        folder.mkdir(parents=True, exist_ok=True)
        model = folder / config.MODELS["whisper-base"]["files"][0]
        model.write_bytes(b"x")
        self.addCleanup(model.unlink, missing_ok=True)
        old = os.environ.get("FVS_WHISPER_CLI")
        os.environ["FVS_WHISPER_CLI"] = "/nonexistent/whisper-cli"
        try:
            hw = hardware.detect(True)
            msgs = [w["message"] for w in hardware.warnings(hw, cfg, "system")]
        finally:
            if old is None:
                del os.environ["FVS_WHISPER_CLI"]
            else:
                os.environ["FVS_WHISPER_CLI"] = old
        self.assertTrue(any("./build-whisper.sh" in m or "brew install whisper-cpp" in m for m in msgs), msgs)

    def test_hardware(self):
        from studio import hardware as h
        self.assertIs(h._registry_gpus, self.compat._apple_gpus)
        self.assertEqual(h.recommended_engine({}), "system")
        gpus = h._registry_gpus()
        self.assertEqual(len(gpus), 1)
        self.assertFalse(gpus[0]["integrated"], "a non-integrated GPU is what main_gpu() picks for model_fit()")
        self.assertGreater(gpus[0]["vram_gb"], 0)
        self.assertEqual(gpus[0]["vram_gb"], h._ram_gb(), "unified memory: GPU memory is RAM")
        self.assertGreater(h._ram_gb(), 0)
        self.assertIsInstance(h._cpu(), str)
        self.assertIn(h.on_battery(), (None, True, False))

    def test_model_fit_uses_the_full_unified_memory(self):
        from studio import hardware as h
        hw = h.detect(True)
        # this Mac has 32 GB unified memory; qwen3-tts-q8 must fit without falling back to Q4/CPU
        self.assertEqual(h.model_fit("qwen3-tts-q8", hw, "system"), "fits")

    def test_applescript_literal_escaping(self):
        c = self.compat
        self.assertEqual(c._as_literal("simple"), '"simple"')
        self.assertEqual(c._as_literal('has "quotes"'), '"has \\"quotes\\""')
        self.assertEqual(c._as_literal("back\\slash"), '"back\\\\slash"')

    def test_patched_names_are_the_ones_in_use(self):
        from studio import store, voices, transcribe, app
        for mod in (store, voices, transcribe):
            self.assertIs(mod.to_recycle_bin, self.compat._to_trash, f"{mod.__name__} still has the Windows trash")
        self.assertIs(app.pick_folder, self.compat._pick_folder)

    def test_trash_reports_a_clear_error_for_a_missing_file(self):
        missing = Path(self.tmp.name) / "does-not-exist"
        with self.assertRaises(OSError):
            self.compat._to_trash(missing)

    def test_autostart(self):
        file = self.compat.AUTOSTART_FILE
        if not str(file).startswith(self.tmp.name):
            self.skipTest("compat was imported before the test set FVS_LAUNCH_AGENTS_DIR; not touching the real one")
        import unittest.mock as mock
        from studio import autostart as a
        self.assertFalse(a.enabled())
        with mock.patch("subprocess.run") as run:
            a.set_enabled(True)
            self.assertEqual(run.call_args.args[0][:2], ["launchctl", "load"])
        self.assertTrue(a.enabled())
        self.assertIn(self.compat.LAUNCH_AGENT_LABEL, file.read_text(encoding="utf-8"))
        with mock.patch("subprocess.run") as run:
            a.set_enabled(False)
            self.assertEqual(run.call_args.args[0][:2], ["launchctl", "unload"])
        self.assertFalse(a.enabled())

    def test_service_plist_has_keepalive(self):
        if not str(self.compat.SERVICE_FILE).startswith(self.tmp.name):
            self.skipTest("compat was imported before the test set FVS_LAUNCH_AGENTS_DIR; not touching the real one")
        self.compat.write_service_plist()
        self.addCleanup(self.compat.SERVICE_FILE.unlink, missing_ok=True)
        xml = self.compat.SERVICE_FILE.read_text(encoding="utf-8")
        self.assertIn(self.compat.SERVICE_LABEL, xml)
        self.assertIn("<key>KeepAlive</key><true/>", xml)
        self.assertIn("--no-tray", xml)

    def test_updater_says_no(self):
        import asyncio
        from studio import app, config
        state = asyncio.run(app.Updater(config.load()).check())
        self.assertEqual(state["status"], "error")
        self.assertIn("git pull", state["error"])
        self.assertEqual(app.Updater.__name__, "MacOSUpdater", "app.py still has the Windows updater")

    def test_wrong_architecture_is_rejected(self):
        self.compat._applied = False
        try:
            with unittest.mock.patch("platform.machine", return_value="x86_64"):
                with self.assertRaises(RuntimeError):
                    self.compat.apply()
        finally:
            self.compat._applied = False
            self.compat.apply()  # restore the patched state for the remaining tests in this class (mock is gone here)


if __name__ == "__main__":
    unittest.main(verbosity=2)
