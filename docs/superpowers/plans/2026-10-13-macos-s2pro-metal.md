# S2 Pro on macOS (Metal) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Fish Audio S2 Pro run on Apple Silicon Macs through a Metal build of `s2.cpp`, following the same
pattern Windows (`studio/`) and Linux (`linux/compat.py`) already use, without touching Windows or Linux behavior.

**Architecture:** `studio/s2engine.py`'s `S2Server._start()` already branches on `engine in ("cuda", "vulkan")` to
pick the right `s2` CLI flag; this plan adds a third `"metal"` branch. `macos/compat.py` gets a new `_patch_s2()`
(mirroring `linux/compat.py`'s `_patch_s2()`) that tells `studio/` an S2 Pro engine called `"metal"` exists whenever
a Metal-built `s2` binary is present (built by a new `macos/build-s2.sh`, since there is no Homebrew formula for
s2.cpp and no official macOS build — unlike `llama.cpp`/`whisper.cpp`, where Homebrew is tried first). S2 Pro's
model entries keep running on the macOS `"system"` llama-tts engine for the "which engine must be active" gate, the
same way Linux's do.

**Tech Stack:** Python 3 (studio/, macos/compat.py), bash (macos/build-s2.sh), unittest (macos/test_smoke.py),
cmake + s2.cpp (C++/ggml, Metal backend).

**Spec:** `prompt_13.10.2026.md` (repo root) — the user's own task spec for this feature. Also read
`linux/compat.py`'s `_patch_s2()`/`s2_folder()`/`_link_tools()` and `studio/s2engine.py`'s `S2Server._start()`
before touching anything; this plan's code mirrors them closely and the task steps below assume you can see them
side by side.

## Global Constraints

- Repo must be on `origin/main` @ `ddcd77f` (version 0.3.3) or later, rebased in — i.e. `studio/s2engine.py`,
  `studio/config.py`'s S2 Pro entries, `packaging/s2cpp/seed.patch` and `.github/workflows/s2cpp.yml` must already
  exist. (Already done in this session: `macos-support` was rebased onto `origin/main` and now contains all of
  this.)
- Do not change the pinned s2.cpp commit, pull requests, or patch: `2c33261938da1a41d713768b1b391b4d368d7d2c`,
  PRs at `49bb869e2399555ab23be1d6ec4b8aa67c0b6a3c`, `f468f9d70e269855f67c2c7e0080071263edb40b`,
  `68ebea3f66e143ad58e326d11aee2b1817c1ae9c`, and `packaging/s2cpp/seed.patch` — these are exactly what
  `.github/workflows/s2cpp.yml` uses for Windows/Linux, and the spec says not to swap them.
- Windows and Linux must keep working exactly as before — every edit to a shared `studio/` file must be additive
  (a new `"metal"` branch) and must not change the `"cuda"`/`"vulkan"` code paths.
- Apple Silicon only, matching `macos/compat.py`'s existing `apply()` guard (`platform.machine() != "arm64"`).
- No secrets or machine-specific local paths in any committed file.
- Match the existing style of `linux/compat.py` and `macos/compat.py` (small patch functions, lambdas assigned onto
  `studio.config`, `_link()`-based symlinks, `D.start`/`D.start_engine` wrapping the real method).
- **Do not run `git commit` at the end of any task below** (this overrides the writing-plans template's usual
  "Commit" step) — the user commits only on their own explicit request. Leave changes unstaged/uncommitted after
  each task; `git add`/`git status` to show what changed is fine, `git commit` is not.
- Report only test results and measurements you actually ran; if a model file, GPU, or build toolchain is missing,
  say so explicitly instead of marking the step done.

## Review Focus

- **S2 Pro download/activation attempted before `s2.cpp` is built.** Must raise a macOS-specific message pointing
  at `build-s2.sh` (not Windows/Linux wording, not an unhandled exception). Covered in Task 4's
  `test_s2_pro_download_is_blocked_without_s2cpp`.
- **A Mac with little unified memory (e.g. 8 GB) where S2 Pro's existing `on_cpu` fallback triggers.** The new
  `"metal"` branch must not disturb the existing cuda/vulkan `on_cpu`/`vram_gb` logic in `_start()`. Covered in
  Task 2's test (asserts `--cuda`/`--vulkan` are still present, unchanged, alongside `--metal`).
- **Windows/Linux S2 Pro regresses because `studio/s2engine.py` is shared.** The `"cuda"`/`"vulkan"` branches must
  stay byte-for-byte equivalent after the edit. Covered in Task 2's test.
- **S2 Pro models silently never runnable on macOS** because their `"engines"` list doesn't match `cfg["engine"]`
  (`"system"`, not `"metal"` — `"metal"` is only the S2 Pro *backend* key, a separate concept from the main voice
  engine key that `hardware.model_fit()` / `engine.ready_problem()` check). Covered in Task 4's
  `test_s2_pro_models_use_the_system_engine`.
- **The S2 Pro server outlives the app.** `studio/s2engine.py`'s `S2Server` uses `subprocess.Popen` directly; if
  `macos/compat.py` doesn't also point `s2engine.subprocess` at the pdeath-wrapped `Popen` (the way
  `linux/compat.py`'s `_patch_engine()` does), `kill -9`/Quit would leave the S2 Pro server (and its GPU memory)
  running. Covered in Task 4's `test_s2engine_subprocess_is_tied_to_the_app_too`.

---

### Task 1: Remove the macOS-only block that hides S2 Pro models in `studio/config.py`

**Files:**
- Modify: `studio/config.py:4` (drop the now-unused `import sys`), `studio/config.py:281-283` (drop the darwin
  block)
- Test: `macos/test_smoke.py` (`RuntimeChecks`, new method)

**Interfaces:**
- Consumes: nothing new.
- Produces: `config.MODELS` keeps `"s2-pro-q8"` and `"s2-pro-q6"` on macOS (darwin+arm64), same as Windows/Linux.
  Later tasks' `_patch_s2()` relies on these two keys still being in `config.MODELS`.

- [ ] **Step 1: Write the failing test**

  In `macos/test_smoke.py`, inside `class RuntimeChecks`, add (right after `test_about_page_does_not_show_the_windows_engine_pin`
  is a good spot):

  ```python
  def test_s2_pro_models_are_not_hidden_on_macos(self):
      from studio import config as c
      self.assertIn("s2-pro-q8", c.MODELS, "studio/config.py still deletes S2 Pro models on darwin")
      self.assertIn("s2-pro-q6", c.MODELS, "studio/config.py still deletes S2 Pro models on darwin")
  ```

- [ ] **Step 2: Run it to verify it fails**

  Run: `macos/.venv/bin/python -m pytest macos/test_smoke.py -k test_s2_pro_models_are_not_hidden_on_macos -v`
  Expected: FAIL — `s2-pro-q8`/`s2-pro-q6` not in `c.MODELS` (the darwin block in `studio/config.py` deletes them
  at import time on this Mac).

- [ ] **Step 3: Remove the darwin block**

  In `studio/config.py`, delete:

  ```python
  if sys.platform == "darwin":  # no s2.cpp build for macOS yet (Windows: S2_RUNTIME; Linux: linux/compat.py)
      for _k in [k for k, m in MODELS.items() if m.get("runtime") == "s2"]:
          del MODELS[_k]
  ```

  so `MODELS["uvr-vocals"] = {...}` is immediately followed by `SUBTITLE_PREFERENCE = [...]`. Also delete the now
  unused `import sys` (line 4) — nothing else in this file uses `sys`. Verify with:
  `grep -n 'sys\.' studio/config.py` → no hits.

- [ ] **Step 4: Run the test to verify it passes**

  Run: `macos/.venv/bin/python -m pytest macos/test_smoke.py -k test_s2_pro_models_are_not_hidden_on_macos -v`
  Expected: PASS

- [ ] **Step 5: Run the full static+runtime suite once to catch collateral breakage**

  Run: `macos/.venv/bin/python macos/test_smoke.py`
  Expected: same pass count as before this task, plus the one new test (no new failures).

---

### Task 2: Teach `studio/s2engine.py`'s `S2Server._start()` the `"metal"` engine

**Files:**
- Modify: `studio/s2engine.py:154-164` (the `args`/`on_cpu` block inside `_start()`)
- Test: `macos/test_smoke.py` (`StaticChecks`, new method — this is cross-platform source, so keep the test
  platform-independent like the existing `test_engine_command_line`)

**Interfaces:**
- Consumes: `engine: str` parameter already passed into `_start()` (currently `"cuda"` or `"vulkan"`; macOS will
  pass `"metal"`, set up in Task 4 via `config.s2_engine()`).
- Produces: `S2Server._start()` now assembles a valid `s2 --server ... --metal` command line when `engine ==
  "metal"`, on both the `on_cpu` and GPU paths, leaving the `"cuda"`/`"vulkan"` paths unchanged.

- [ ] **Step 1: Write the failing test**

  In `macos/test_smoke.py`, inside `class StaticChecks`, add:

  ```python
  def test_s2engine_has_a_metal_branch(self):
      """s2engine.py's _start() must send s2.cpp --metal for macOS's "metal" S2 engine (config.s2_engine()),
      the same way it already sends --cuda/--vulkan for Windows/Linux, without removing either of those."""
      src = (STUDIO / "s2engine.py").read_text(encoding="utf-8")
      self.assertIn('"metal"', src, "s2engine.py no longer branches on the \"metal\" engine key")
      self.assertIn("--metal", src, "s2engine.py no longer passes --metal to s2.cpp")
      self.assertIn("--cuda", src, "the existing cuda branch must stay (Windows/Linux)")
      self.assertIn("--vulkan", src, "the existing vulkan branch must stay (Windows/Linux)")
  ```

- [ ] **Step 2: Run it to verify it fails**

  Run: `macos/.venv/bin/python -m pytest macos/test_smoke.py -k test_s2engine_has_a_metal_branch -v`
  Expected: FAIL — no `"metal"`/`--metal` in `studio/s2engine.py` yet.

- [ ] **Step 3: Add the metal branch**

  In `studio/s2engine.py`, inside `_start()`, replace:

  ```python
        args = [str(exe), "--server", "-H", "127.0.0.1", "-P", str(self.port), "--model", str(gguf),
                "--tokenizer", str(folder / "tokenizer.json"), "--gpu-layers", "0" if on_cpu else "36",
                "--log-level", "info"]
        if on_cpu:
            args += ["--cuda" if engine == "cuda" else "--vulkan", "-1"]
            log.info("S2 Pro runs on the CPU: the graphics card has %s GB", gpu["vram_gb"])
        else:
            args += ["--cuda", "0"] if engine == "cuda" else ["--vulkan", str(device)]
  ```

  with:

  ```python
        args = [str(exe), "--server", "-H", "127.0.0.1", "-P", str(self.port), "--model", str(gguf),
                "--tokenizer", str(folder / "tokenizer.json"), "--gpu-layers", "0" if on_cpu else "36",
                "--log-level", "info"]
        if on_cpu:
            args += ["--metal"] if engine == "metal" else ["--cuda" if engine == "cuda" else "--vulkan", "-1"]
            log.info("S2 Pro runs on the CPU: the graphics card has %s GB", gpu["vram_gb"])
        else:
            args += (["--metal"] if engine == "metal"
                     else ["--cuda", "0"] if engine == "cuda" else ["--vulkan", str(device)])
  ```

  (Apple Silicon's unified memory means there is no separate Metal device index the way `--vulkan <n>` picks a
  card, so `--metal` takes no argument — this is also exactly what the spec in `prompt_13.10.2026.md` asks for.)
  Leave the `env["PATH"]` cuda-only block right after it untouched — `engine == "metal"` simply doesn't match it,
  which is correct (nothing extra needs to go on `PATH` for Metal).

- [ ] **Step 4: Run the test to verify it passes**

  Run: `macos/.venv/bin/python -m pytest macos/test_smoke.py -k test_s2engine_has_a_metal_branch -v`
  Expected: PASS

- [ ] **Step 5: Run the full static+runtime suite once**

  Run: `macos/.venv/bin/python macos/test_smoke.py` and `linux/.venv/bin/python linux/test_smoke.py` (if a Linux
  checkout/venv is available in this environment; otherwise note it as not run here and rely on Task 5 to run it
  for real, since `studio/s2engine.py` is shared and Linux's own smoke test imports it indirectly via its static
  AST checks, not by executing `_start()`).
  Expected: all green, same counts as before plus the one new test.

---

### Task 3: `macos/build-s2.sh` — build s2.cpp with Metal from the pinned commit

**Files:**
- Create: `macos/build-s2.sh`
- Test: `macos/test_smoke.py` (`StaticChecks`, two additions: a new test method, and one existing list extended)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: when run on an Apple Silicon Mac with Xcode command line tools, cmake and git installed, leaves
  `macos/bin/s2cpp/s2` (executable) and `macos/bin/s2cpp/tokenizer.json` on disk. Task 4's `s2_folder()` looks for
  exactly those two files at exactly that path by default.

- [ ] **Step 1: Write the failing tests**

  In `macos/test_smoke.py`, inside `class StaticChecks`, extend the existing `test_shell_scripts_are_syntactically_valid`'s
  tuple of names:

  ```python
      def test_shell_scripts_are_syntactically_valid(self):
          for name in ("build-llama.sh", "build-whisper.sh", "build-s2.sh", "setup.sh", "fatima-voice-studio"):
  ```

  and add a new method right after it:

  ```python
  S2CPP_REF = "2c33261938da1a41d713768b1b391b4d368d7d2c"
  S2CPP_PRS = ("49bb869e2399555ab23be1d6ec4b8aa67c0b6a3c", "f468f9d70e269855f67c2c7e0080071263edb40b",
               "68ebea3f66e143ad58e326d11aee2b1817c1ae9c")

  def test_build_s2_sh_pins_the_same_commit_and_patches_as_windows_linux(self):
      """build-s2.sh must build exactly what .github/workflows/s2cpp.yml builds for Windows/Linux (same commit,
      same 3 pull requests, same seed.patch) -- the spec says not to swap these, and a silent drift here would
      make macOS's S2 Pro behave differently (or build inconsistently) from the other platforms."""
      script = (HERE / "build-s2.sh").read_text(encoding="utf-8")
      self.assertIn(self.S2CPP_REF, script)
      for sha in self.S2CPP_PRS:
          self.assertIn(sha, script)
      self.assertIn("packaging/s2cpp/seed.patch", script)
      self.assertIn("-DS2_METAL=ON", script)
  ```

  (Place `S2CPP_REF`/`S2CPP_PRS` as class attributes of `StaticChecks`, next to the existing `ENGINE_FLAGS` class
  attribute, or as module-level constants next to `ENGINE_FLAGS` — either is fine, just keep `self.S2CPP_REF` /
  `self.S2CPP_PRS` references consistent with where you put them.)

- [ ] **Step 2: Run it to verify it fails**

  Run: `macos/.venv/bin/python -m pytest macos/test_smoke.py -k "build_s2_sh or shell_scripts_are_syntactically_valid" -v`
  Expected: FAIL — `macos/build-s2.sh` doesn't exist yet (the shell-scripts test fails with "No such file or
  directory" from `bash -n`, the pin-check test fails with `FileNotFoundError`).

- [ ] **Step 3: Write `macos/build-s2.sh`**

  ```bash
  #!/usr/bin/env bash
  # Builds s2.cpp (https://github.com/rodrigomatta/s2.cpp, Fish Audio S2 Pro's engine) with Metal, into
  # macos/bin/s2cpp/. Unlike build-llama.sh/build-whisper.sh (Homebrew fallbacks), this always builds from
  # source: there is no Homebrew formula and no official macOS build of s2.cpp.
  #
  # Pinned to the exact commit, pull requests and patch this project's Windows/Linux s2.cpp builds use
  # (.github/workflows/s2cpp.yml, packaging/s2cpp/seed.patch) -- change those together, not this script alone.
  set -euo pipefail
  here="$(cd "$(dirname "$0")" && pwd)"
  repo="$(cd "$here/.." && pwd)"
  ref="2c33261938da1a41d713768b1b391b4d368d7d2c"
  prs="49bb869e2399555ab23be1d6ec4b8aa67c0b6a3c f468f9d70e269855f67c2c7e0080071263edb40b 68ebea3f66e143ad58e326d11aee2b1817c1ae9c"

  work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
  git clone https://github.com/rodrigomatta/s2.cpp "$work/src"
  cd "$work/src"
  git checkout "$ref"
  git submodule update --init --recursive

  for sha in $prs; do
    git fetch --no-tags --no-recurse-submodules origin "$sha"
    git merge --no-edit "$sha"
  done

  git apply --verbose "$repo/packaging/s2cpp/seed.patch"

  cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DS2_METAL=ON
  cmake --build build -j"$(sysctl -n hw.ncpu)" --target s2

  mkdir -p "$here/bin/s2cpp"
  install -m755 build/s2 "$here/bin/s2cpp/s2"
  cp tokenizer.json "$here/bin/s2cpp/tokenizer.json"
  cp LICENSE.md "$here/bin/s2cpp/LICENSE.md" 2>/dev/null || true

  "$here/bin/s2cpp/s2" --help 2>&1 | grep -E "metal|seed" || { echo "warning: --metal/--seed not found in s2 --help"; exit 1; }
  echo "Built $here/bin/s2cpp/s2 ($ref)"
  ```

- [ ] **Step 4: Run the tests to verify they pass**

  Run: `macos/.venv/bin/python -m pytest macos/test_smoke.py -k "build_s2_sh or shell_scripts_are_syntactically_valid" -v`
  Expected: PASS

- [ ] **Step 5: Run the full static suite once**

  Run: `macos/.venv/bin/python macos/test_smoke.py`
  Expected: all green. (Do not actually run `build-s2.sh` yet in this task — the real build, which takes real
  time and needs a real toolchain, is Task 5.)

---

### Task 4: `macos/compat.py` — `_patch_s2()`, linking, and wiring it into `apply()`

**Files:**
- Modify: `macos/compat.py` (new constants, new `s2_folder()`, extended `_link_tools()`, new `_patch_s2()`,
  extended `_patch_engine()`, extended `apply()`, extended `TEXTS`, extended module docstring)
- Test: `macos/test_smoke.py` (`TARGETS`/`CLASS_MEMBERS` extended; several new `RuntimeChecks` methods)

**Interfaces:**
- Consumes: `config.MODELS["s2-pro-q8"|"s2-pro-q6"]` existing (Task 1), `S2Server._start()`'s `"metal"` branch
  (Task 2), `macos/bin/s2cpp/{s2,tokenizer.json}` as the default build location (Task 3's output path).
- Produces: `config.S2_EXE == "s2"`, `config.S2_RUNTIME == {"metal": ("", 0, "")}`, `config.s2_dir("metal") ==
  <FVS_HOME>/engine/s2-metal`, `config.s2_engine(cfg)` returns `"metal"` or `None`, every `m.get("runtime") ==
  "s2"` model in `config.MODELS` has `m["engines"] == ["system"]`, `downloads.Downloads.start` raises a
  macOS-specific `ValueError` for an S2 Pro model when `s2_folder()` is `None`, `s2engine.subprocess is
  engine.subprocess` after `apply()`.

- [ ] **Step 1: Write the failing tests**

  In `macos/test_smoke.py`, extend the module-level `TARGETS` dict's `"config"` entry and add an `"s2engine"`
  entry:

  ```python
  TARGETS = {
      "config": {"HOME", "DATA", "CONFIG_FILE", "VOICES", "MUSIC", "DEFAULTS", "ENGINES", "ENGINE_EXE", "WHISPER_EXE",
                 "engine_dir", "installed_engines", "whisper_dir", "tool_dir",
                 # _patch_s2: S2 Pro through s2.cpp's Metal build (build-s2.sh)
                 "S2_EXE", "S2_RUNTIME", "s2_dir", "s2_engine", "MODELS"},
      "hardware": {"_vendor", "_registry_gpus", "_ram_gb", "_cpu", "on_battery", "recommended_engine"},
      "autostart": {"enabled", "set_enabled", "python_console", "install_launchers"},
      "updater": {"Updater"},
      "trash": {"to_recycle_bin"},
      "winui": {"pick_folder"},
      "engine": {"subprocess"},
      "s2engine": {"subprocess"},  # the same for the S2 Pro server
      "tray": {"copy", "Tray"},
      "app": {"create_app", "Updater", "pick_folder"},
      "media": {"ffmpeg_exe", "ffmpeg_source"},
      "downloads": {"Downloads"},
  }
  CLASS_MEMBERS = {
      ("updater", "Updater"): {"watch", "check", "start"},
      ("tray", "Tray"): {"__init__"},
      ("downloads", "Downloads"): {"tools", "start_tool", "delete_tool", "start_engine", "_whisper_missing", "start"},
  }
  ```

  Then, in `class RuntimeChecks`, add (e.g. right after `test_about_page_does_not_show_the_windows_engine_pin`,
  or after Task 1's new test if you placed it there):

  ```python
  def test_s2_config_values(self):
      from studio import config as c
      home = Path(os.environ["FVS_HOME"])
      self.assertEqual(c.S2_EXE, "s2")
      self.assertEqual(c.S2_RUNTIME, {"metal": ("", 0, "")})
      self.assertEqual(c.s2_dir("metal"), home / "engine" / "s2-metal")

  def test_s2_pro_models_use_the_system_engine(self):
      """"engines" gates against cfg["engine"] (hardware.model_fit, engine.ready_problem) -- that's "system" on
      macOS, not "metal" (the S2 Pro backend key is a separate concept, config.s2_engine())."""
      from studio import config as c
      for key, m in c.MODELS.items():
          if m.get("runtime") == "s2":
              with self.subTest(model=key):
                  self.assertEqual(m["engines"], ["system"])

  def test_s2_engine_is_none_without_an_s2cpp_build(self):
      from studio import config as c
      with unittest.mock.patch.object(self.compat, "s2_folder", return_value=None):
          self.assertIsNone(c.s2_engine({"engine": "system"}))

  def test_s2_engine_is_metal_once_s2cpp_and_the_system_engine_are_there(self):
      from studio import config as c
      with tempfile.TemporaryDirectory() as d:
          folder = Path(d)
          (folder / "s2").write_text("#!/bin/sh\n")
          (folder / "s2").chmod(0o755)
          (folder / "tokenizer.json").write_text("{}")
          old = os.environ.get("FVS_S2")
          os.environ["FVS_S2"] = str(folder)
          try:
              with unittest.mock.patch.object(c, "installed_engines", return_value=["system"]):
                  self.assertEqual(c.s2_engine({"engine": "system"}), "metal")
          finally:
              if old is None:
                  os.environ.pop("FVS_S2", None)
              else:
                  os.environ["FVS_S2"] = old

  def test_s2_tools_are_linked_into_s2_metal(self):
      home = Path(os.environ["FVS_HOME"])
      with tempfile.TemporaryDirectory() as d:
          folder = Path(d)
          (folder / "s2").write_text("#!/bin/sh\n")
          (folder / "s2").chmod(0o755)
          (folder / "tokenizer.json").write_text("{}")
          old = os.environ.get("FVS_S2")
          os.environ["FVS_S2"] = str(folder)
          try:
              self.compat._link_tools()
              link = home / "engine" / "s2-metal" / "s2"
              self.assertTrue(link.is_symlink())
              self.assertEqual(os.readlink(link), str(folder / "s2"))
              self.assertTrue((home / "engine" / "s2-metal" / "tokenizer.json").is_symlink())
          finally:
              if old is None:
                  os.environ.pop("FVS_S2", None)
              else:
                  os.environ["FVS_S2"] = old

  def test_s2_pro_download_is_blocked_without_s2cpp(self):
      from studio import downloads, config
      d = downloads.Downloads(config.load())
      with unittest.mock.patch.object(self.compat, "s2_folder", return_value=None):
          with self.assertRaises(ValueError) as cm:
              d.start("s2-pro-q6")
      self.assertIn("build-s2.sh", str(cm.exception))

  def test_s2engine_subprocess_is_tied_to_the_app_too(self):
      from studio import s2engine
      self.assertIs(s2engine.subprocess.Popen, self.engine.subprocess.Popen)
  ```

- [ ] **Step 2: Run them to verify they fail**

  Run: `macos/.venv/bin/python -m pytest macos/test_smoke.py -k "s2_config_values or s2_pro_models_use_the_system_engine or s2_engine_is_none or s2_engine_is_metal or s2_tools_are_linked or s2_pro_download_is_blocked or s2engine_subprocess_is_tied" -v`
  Expected: FAIL (`AttributeError: module 'config' has no attribute 'S2_EXE'`, etc. — none of this exists in
  `macos/compat.py` yet) and the static `test_patch_targets_exist`/`test_patched_class_members_exist` also now
  fail until Task 4's edits land.

- [ ] **Step 3: Write `_patch_s2()` and wire it in**

  In `macos/compat.py`, near the top (after `PDEATH_WRAP = MACOS_DIR / "pdeath-wrap.sh"`), add:

  ```python
  S2_EXE = "s2"
  S2_HINT = ("Fish Audio S2 Pro needs its engine part, s2.cpp with Metal. Run ./build-s2.sh in the macos folder "
             "(see macos/README.md): it builds s2.cpp with Metal into macos/bin/s2cpp. Then press Check again.")
  ```

  Near `_link_tools()`, add a helper (mirrors `linux/compat.py`'s `s2_folder()`, but there's only ever one
  backend key, `"metal"`, so there's no per-backend loop):

  ```python
  def s2_folder() -> Path | None:
      """s2.cpp built with Metal (FVS_S2, else macos/bin/s2cpp, built by ./build-s2.sh)."""
      given = os.environ.get("FVS_S2")
      folder = Path(given) if given else MACOS_DIR / "bin" / "s2cpp"
      return folder if (folder / S2_EXE).exists() and (folder / "tokenizer.json").exists() else None
  ```

  Extend `_link_tools()` from:

  ```python
  def _link_tools() -> None:
      home = fvs_home()
      _link(find_tool("FVS_LLAMA_TTS", "llama-tts"), home / "engine" / SYSTEM_ENGINE / "llama-tts")
      _link(find_tool("FVS_WHISPER_CLI", "whisper-cli"), home / "engine" / "whisper" / "whisper-cli")
  ```

  to:

  ```python
  def _link_tools() -> None:
      home = fvs_home()
      _link(find_tool("FVS_LLAMA_TTS", "llama-tts"), home / "engine" / SYSTEM_ENGINE / "llama-tts")
      _link(find_tool("FVS_WHISPER_CLI", "whisper-cli"), home / "engine" / "whisper" / "whisper-cli")
      s2 = s2_folder()
      for name in (S2_EXE, "tokenizer.json"):
          _link(str(s2 / name) if s2 else None, home / "engine" / "s2-metal" / name)
  ```

  Add `_patch_s2()` (mirrors `linux/compat.py`'s `_patch_s2()`, minus the per-backend/`WHISPER_GPU` parts that
  don't apply on macOS), placed after `_patch_tools()` and before `_patch_engine()`:

  ```python
  def _patch_s2() -> None:
      """S2 Pro through s2.cpp's Metal build (build-s2.sh), as the app's "metal" S2 engine. Qwen3-TTS stays on
      the "system" llama-tts engine; S2 Pro runs whenever that engine is installed and s2.cpp is built."""
      from studio import config, downloads

      config.S2_EXE = S2_EXE
      config.S2_RUNTIME = {"metal": ("", 0, "")}  # size 0: nothing for the app to download, build-s2.sh builds it
      config.s2_dir = lambda engine: fvs_home() / "engine" / f"s2-{engine}"
      config.s2_engine = lambda cfg: ("metal" if s2_folder() and SYSTEM_ENGINE in config.installed_engines(cfg)
                                      else None)
      for m in config.MODELS.values():
          if m.get("runtime") == "s2":
              m["engines"] = [SYSTEM_ENGINE]

      D = downloads.Downloads
      real_start = D.start

      def start(self, key: str) -> None:
          if config.MODELS.get(key, {}).get("runtime") == "s2" and not s2_folder():
              raise ValueError(S2_HINT)
          real_start(self, key)

      D.start = start
  ```

  Extend `_patch_engine()` from:

  ```python
      engine.subprocess = types.SimpleNamespace(**{**vars(subprocess), "Popen": Popen})
  ```

  to:

  ```python
      engine.subprocess = types.SimpleNamespace(**{**vars(subprocess), "Popen": Popen})
      from studio import s2engine
      s2engine.subprocess = engine.subprocess  # the S2 Pro server too
  ```

  In `apply()`, insert `_patch_s2()` between `_patch_updater()` and `_patch_engine()`:

  ```python
      _patch_updater()
      _patch_s2()
      _patch_engine()
      _link_tools()
  ```

  Add to the module docstring's "What it does" list (after the `engine` bullet about pdeath-wrap):

  ```
    * S2 Pro     s2.cpp with Metal from macos/bin/s2cpp (build-s2.sh) or FVS_S2, run as the "metal" S2 engine
  ```

  Append to `TEXTS` (same old-text keys as `linux/compat.py`'s S2 Pro wording entries, since the strings being
  matched live in shared `studio/` code — only the replacement text differs):

  ```python
      ("S2 Pro on the NVIDIA · CUDA or AMD / Intel · Vulkan engine.",
       "S2 Pro with s2.cpp for Metal, which build-s2.sh builds."),
      ("Needs the NVIDIA · CUDA or AMD / Intel · Vulkan engine (<a href=\"#setup\">Setup</a>)",
       "Needs s2.cpp with Metal: run ./build-s2.sh in the macos folder"),
      ("Needs the NVIDIA · CUDA or AMD / Intel · Vulkan engine: switch to one on Setup.",
       "Needs s2.cpp with Metal: run ./build-s2.sh in the macos folder, then press Check again on Setup."),
      ("runs on the NVIDIA · CUDA or AMD / Intel · Vulkan engine. Switch to one on Setup.",
       "needs s2.cpp with Metal: run ./build-s2.sh in the macos folder."),
  ```

  (`test_web_script_patches_still_match`, already in the suite, automatically checks every entry you add here
  against `studio/web/app.js` and `studio/*.py` — no separate test needed for the wording itself.)

- [ ] **Step 4: Run the tests to verify they pass**

  Run: `macos/.venv/bin/python -m pytest macos/test_smoke.py -k "s2_config_values or s2_pro_models_use_the_system_engine or s2_engine_is_none or s2_engine_is_metal or s2_tools_are_linked or s2_pro_download_is_blocked or s2engine_subprocess_is_tied or patch_targets_exist or patched_class_members_exist or web_script_patches" -v`
  Expected: PASS

- [ ] **Step 5: Run the full suite once**

  Run: `macos/.venv/bin/python macos/test_smoke.py`
  Expected: all green.

---

### Task 5: Build s2.cpp for real, run the full test matrix, and record what you actually verified

This task has no new production code — it runs what Tasks 1-4 built, on the real Apple Silicon Mac this session
has access to, and only then updates documentation with real results. Do not mark any sub-step "done" without
having actually run it; if something can't run here (missing model file, no GPU, etc.), say so plainly.

- [ ] **Step 1: Static checks**

  Run: `bash -n macos/build-s2.sh` and `bash -n macos/build-llama.sh`
  Expected: both exit 0 (also already covered by `test_shell_scripts_are_syntactically_valid`, but the spec asks
  for them explicitly too).

- [ ] **Step 2: Full smoke test suites**

  Run: `macos/.venv/bin/python macos/test_smoke.py` and `linux/.venv/bin/python linux/test_smoke.py` (the Linux
  one is a static-only check here — this is a Mac, Linux's `RuntimeChecks` class is platform-gated and will
  largely skip; the point is that `linux/test_smoke.py`'s `StaticChecks` still passes against the shared
  `studio/s2engine.py` after Task 2's edit).
  Expected: both suites green. If `linux/.venv` doesn't exist on this machine, run
  `python3 -m pytest linux/test_smoke.py -k StaticChecks` with any Python 3 that has the `linux/requirements`
  (or note plainly that it wasn't run and why).

- [ ] **Step 3: Build s2.cpp with Metal for real**

  Run: `bash macos/build-s2.sh`
  Expected: ends with `Built .../macos/bin/s2cpp/s2 (2c33261938da1a41d713768b1b391b4d368d7d2c)`. If it fails
  (missing cmake, Xcode CLT, network), stop and report the exact failure — do not fake this step.
  Then: `./macos/bin/s2cpp/s2 --help | grep -E "metal|seed"` and confirm both flags are listed.

- [ ] **Step 4: Confirm the app picks it up**

  Run `./macos/fatima-voice-studio --no-tray --no-browser` (or use `run.py --check` / the API directly) against a
  real `FVS_HOME`, and check `GET /api/setup` shows the S2 Pro models with `engine_ok: true` once the "system"
  llama-tts engine is also installed. If `macos/bin/s2cpp` isn't linked yet, `installed_engines()`/`_link_tools()`
  run on every `GET /api/setup`, so a reload after the build should be enough — confirm that, don't assume it.

- [ ] **Step 5: s2.cpp CLI test with a real GGUF model**

  If an S2 Pro GGUF model (Q6 preferred, per the spec) is available on this machine, run exactly:

  ```bash
  ./macos/bin/s2cpp/s2 \
    -m <path-to>/s2-pro-q6_k.gguf \
    -t ./macos/bin/s2cpp/tokenizer.json \
    --metal \
    -ngl 36 \
    --seed 7 \
    -o /tmp/s2.wav \
    -text "For forty years, the lighthouse keeper had never missed a single night."
  ```

  Record whether it produced `/tmp/s2.wav`, and the elapsed time vs. the audio's duration (gen_rtf) if you can
  measure both. If no GGUF model is present (e.g. not yet downloaded through the app, ~4.5-5.6 GB), say so and
  skip to the next step rather than inventing a number.

- [ ] **Step 6: Application-level checks (only as many as the environment allows)**

  Through the running app: S2 Pro Q6/Q8 appear on Models; download and reach "ready"; English generation; one
  S2-only language (Hindi or Urdu) generation; an emotion tag like `[excited]`; a batch alternating Whisper
  subtitles and S2 Pro voices; cancel mid S2-Pro output; confirm the `s2` process exits when the app does (`ps`
  before/after `kill -9` on the app, or Quit). Record actual pass/fail per item; do not claim an item passed
  without having run it in this session.

- [ ] **Step 7: Update docs with only what was actually measured**

  - `macos/README.md`: add S2 Pro / `build-s2.sh` to the Requirements section and the "Tested status" table,
    following the existing convention (one row per area, "done — <what was actually confirmed>" or "not tested
    — <why>").
  - `macos/ARCHITECTURE.md`: add S2 Pro's `"metal"` engine and `build-s2.sh` to the component/data-flow
    description (and the Mermaid diagram, if the diagram enumerates engines/build scripts) alongside the existing
    `"system"` llama-tts engine.
  - Root `SESSION.md` and `macos/SESSION.md`: append a dated entry (today, 2026-10-13) summarizing what was done,
    what was verified with real commands, and what's still open (e.g. no GGUF model / no app-level test if that
    was the case).
  - `/Volumes/blarks/Agenten/fatima-voice-studio.md`: add a short dated section mirroring the SESSION.md entry
    (per this machine's standing instructions to keep that doc in sync with structural/architecture changes).

- [ ] **Step 8: Final report**

  Produce the report the spec asks for: changed files (`git diff --stat`), a short explanation of the Metal
  integration, the tests actually run and their results, measured `gen_rtf`/RAM if any, open blockers, and
  confirmation that `git status`/`git diff` show no unexpected files touched beyond this plan's scope. Do **not**
  `git add`/`git commit` anything — leave the working tree as-is for the user to review and commit themselves.

---

## Self-Review Notes

- **Spec coverage:** §1 (build s2.cpp with Metal) → Task 3 + Task 5 Step 3/5. §2 `studio/config.py` → Task 1.
  §2 `studio/s2engine.py` → Task 2. §2 `macos/compat.py` (all six bullet points: S2_EXE, S2_RUNTIME, s2_engine,
  `["system"]` engines, symlinks, Downloads.start hint, s2engine.subprocess sharing) → Task 4. §2
  `macos/test_smoke.py` → folded into Tasks 1/2/3/4 (TARGETS additions, new TARGETS. Existing tests/paths are
  only added to, never removed. §3 (functional tests) and §4 (application tests) → Task 5. Final report → Task 5
  Step 8.
- **Placeholder scan:** no TBDs; every step has literal code/commands.
- **Type consistency:** `config.s2_engine(cfg) -> str | None` (returns `"metal"` or `None`) used consistently by
  `_patch_s2`'s `D.start` override and by Task 4's tests; `config.s2_dir(engine: str) -> Path` likewise.
- **Review Focus:** see above — each of the five items names the task/test that covers it.
