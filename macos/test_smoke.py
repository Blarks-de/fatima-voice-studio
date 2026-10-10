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
