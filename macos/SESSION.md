# SESSION – macOS-Port von Fatima Voice Studio

Stand: 2026-10-10

## Worum es geht

Fortsetzung des Linux-Ports (siehe `linux/SESSION.md`, Issue #1, PR #3, gemergt). Gleicher Ansatz für macOS
(Apple Silicon): `macos/compat.py` patcht `studio/` zur Laufzeit, `studio/` selbst bleibt unangetastet.
Entwickelt und getestet auf diesem Mac (AgentM6, Mac mini, Apple M6, 32 GB Unified Memory, macOS 27.0.1).

## Ablauf dieser Session

1. **Brainstorming/Spec/Plan** (superpowers-Skills): Design-Spec unter
   `docs/superpowers/specs/2026-10-10-macos-port-design.md`, Umsetzungsplan unter
   `docs/superpowers/plans/2026-10-10-macos-port.md` (13 Tasks, TDD).
2. **Umsetzung** (native, inline, 13 Tasks): `macos/compat.py`, `run.py`, `setup.sh`,
   `requirements-macos.txt`, `fatima-voice-studio` (Launcher), `pdeath-wrap.sh`, `build-llama.sh`,
   `build-whisper.sh`, `test_smoke.py` (39 Tests), `README.md`, `ARCHITECTURE.md`.
3. **Finales Review** (frischer Opus-Subagent, read-only) fand 2 Critical + 8 Important Befunde:
   - **C1**: launchd startet LaunchAgents mit minimalem PATH (kein Homebrew) → Engine/ffmpeg/Whisper wurden
     nicht gefunden, `_link_tools()` löschte den bestehenden Symlink. Fix: `find_tool()`/ffmpeg-Suche mit
     Homebrew-Fallback (`/opt/homebrew/bin`, `/usr/local/bin`), unabhängig von PATH.
   - **C2**: `pdeath-wrap.sh`-Watcher lief weiter, bis die App beendet wurde, nicht bis der gewrappte Befehl
     selbst fertig war → pro Engine-Aufruf (alle ~40s) ein liegengebliebener Watcher-Prozess, der später eine
     möglicherweise wiederverwendete PID mit `kill -9` trifft. Fix: Watcher beendet sich auch, wenn der
     gewrappte Prozess selbst schon weg ist.
   - **I1–I5, I7, I8(a)/(c)**: Autostart-Toggle killte laufende App (`launchctl unload`), kein Tray bei
     Autostart, `--service` startete bei "schon läuft" in Neustart-Schleife, Plist ohne XML-Escaping,
     `setup.sh --service` ließ sich nicht erneut ausführen, `setup.sh`-Check schluckte Fehler, Trash-Fehlertext
     kopiert von Linux (falsch) und folgte Symlinks. Alle gefixt, je mit RED→GREEN-Test.
   - Zurückgestellt (dokumentiert, nicht gefixt): I6 (whisper-cli nicht an pdeath-wrap gebunden, entspricht
     Linux-Verhalten), I8(b) (TCC/Automation-Berechtigung im Headless-Modus bräuchte eine andere, PyObjC-basierte
     Trash-Implementierung), 10 Minor-Funde (M1–M10).
4. **Echter Crash-Fund bei der manuellen Verifikation** (nicht im Review gefunden): `./fatima-voice-studio`
   (Tray per Default) stürzte mit `SIGTRAP` ("zsh: trace trap") ab — reproduzierbar, auch im echten
   interaktiven Terminal des Nutzers, also kein Sandbox-Artefakt. Crash-Report zeigte `EXC_BREAKPOINT` in
   `-[NSStatusItem setMenu:]`, ausgelöst von `studio/tray.py`s Hintergrund-Thread (`_watch()`), der
   `icon.update_menu()`/`.title=`/`.icon=` direkt aufruft. `pystray`s macOS-Backend fasst AppKit
   (`NSStatusItem`/`NSMenu`) ohne Thread-Absicherung an; macOS erzwingt Hauptthread-only für UI-Aufrufe als
   harten Crash. Gefixt in `macos/compat.py::patch_tray()` durch `PyObjCTools.AppHelper.callAfter` — ohne
   `studio/tray.py` anzufassen. Verifiziert: 18+ Sekunden stabil, kein neuer Crash-Report mehr.
5. **Manuelle Verifikation komplett** (echte App auf diesem Mac, teils headless über die API, teils vom Nutzer
   selbst im Terminal):
   - Sprachausgabe (Qwen3-TTS Q8), Whisper-Transkription (Text + SRT-Timing exakt), Stimmenklonen (vom Nutzer
     bestätigt), Tray (Icon erscheint, Quit beendet die App — vom Nutzer im echten Terminal bestätigt)
   - Pause/Resume: Segment wird fertig, Resume setzt korrekt fort (3/3 fertig)
   - `kill -9`: `llama-tts` stirbt binnen 2s mit der App; nach Neustart läuft der unterbrochene Batch von
     selbst weiter (2/2 fertig)
   - Video/M4A: Stimmen aus echter M4A- und MP4-Datei angelegt (echter ffmpeg-Decode-Pfad), erfolgreich
     gesprochen
   - Autostart: Plist-Schreiben/-Löschen über `/api/settings`, `plutil -lint` OK, laufende App bleibt beim
     Deaktivieren unberührt (I1-Fix live bestätigt)
   - `--service`: Installation, Crash-Neustart (`kill -9` → Neustart binnen 1s durch `launchd`), keine
     Neustart-Schleife bei sauberem Exit, wenn die App schon anderweitig läuft (I3-Fix, 20s beobachtet) — nach
     dem Test wieder deinstalliert (`launchctl unload` + Plist gelöscht), auf Wunsch des Nutzers
6. **Rebase auf aktuellen Upstream**: `origin/main` war zwischenzeitlich von 0.2.4 auf **0.2.6** weitergezogen
   (u. a. `studio/tray.py`, `subtitles.py`, `transcribe.py`, `app.py`, `config.py`, `downloads.py`,
   `web/app.js` geändert — genau die Dateien, die `compat.py` patcht/nutzt). `git rebase --onto origin/main
   57aa87b macos-support` — ein trivialer `.gitignore`-Konflikt, sonst keine Konflikte. **Keine
   Code-Änderung in `macos/compat.py` nötig**: 39/39 Tests weiterhin grün, echter App-Lauf gegen 0.2.6
   bestätigt (Version im Health-Check, Sprachausgabe funktioniert).
7. **Issue + PR eröffnet** (nach dem gleichen Muster wie Issue #1 / PR #3 für Linux):
   - Issue: https://github.com/hassanxs/fatima-voice-studio/issues/4
   - PR: https://github.com/hassanxs/fatima-voice-studio/pull/5
   - Für den PR wurde ein separater, **sauberer** Branch `macos-port-pr` von `origin/main` erstellt, auf den
     nur die 19 `macos/`-Commits per Cherry-Pick übernommen wurden (Diff: ausschließlich `macos/`, +1389/−0).
     Die Planungsdokumente (`docs/superpowers/plans/`, `docs/superpowers/specs/`) bleiben auf `macos-support`
     im Fork, sind aber **nicht** Teil des PR-Diffs (auf Wunsch des Nutzers).
   - `gh` war auf diesem Mac nicht installiert (`brew install gh`), `gh auth login` musste interaktiv vom
     Nutzer durchgeführt werden; der SSH-Key dieses Macs (`~/.ssh/github`) war zunächst nicht bei GitHub
     hinterlegt (`git fetch fork` schlug fehl mit "Permission denied (publickey)"), musste erst unter
     https://github.com/settings/keys hinzugefügt werden.

## Git-Stand

- `macos-support` (lokal + `fork/macos-support`): volle Historie inkl. Planungsdocs, rebased auf
  `origin/main` @ `163d9fd` (0.2.6).
- `macos-port-pr` (lokal + `fork/macos-port-pr`): 19 saubere Commits, nur `macos/`, Basis für PR #5.
- `fork` = `git@github.com:Blarks-de/fatima-voice-studio.git`, `origin` = `git@github.com:hassanxs/fatima-voice-studio.git` (SSH, nicht HTTPS).

## Wichtiger Branch-Hygiene-Fehler (für künftige Sessions)

Die macOS-Arbeit wurde zunächst versehentlich direkt auf `linux-support` committet (dem bereits gemergten
Linux-PR-Branch) — der Nutzer hat das zu Recht bemängelt ("Was hat der Linux-Zweig mit dem Mac zu tun?").
Korrigiert durch: neuen Branch `macos-support` am damaligen Stand angelegt, `linux-support` lokal auf den
Commit zurückgesetzt, der exakt `fork/linux-support` entsprach (vorher per `git log fork/linux-support..X`
in beide Richtungen auf Leere geprüft). **Lektion:** Für jedes neue Stück Arbeit einen eigenen, passend
benannten Branch anlegen — nicht einfach auf dem aktuell ausgecheckten Branch weiterarbeiten, nur weil er
nicht `main` ist.

## Offen

- Warten auf Hassans Rückmeldung zu Issue #4 / PR #5.
- Zurückgestellte Punkte aus dem finalen Review (I6, I8b, M1–M10) — siehe Git-Historie (Commit
  "macos: fix pass from final review ...") für Details, falls Hassan dazu Rückfragen hat.
- Intel-Macs werden von `macos/compat.py` bewusst abgelehnt (`apply()` wirft `RuntimeError`) — nicht getestet,
  da kein Intel-Mac zur Verfügung stand.

## Update 2026-10-11: Hassans drei Review-Punkte zu PR #5 umgesetzt

Hassan hat vor dem Merge drei konkrete Änderungen verlangt, alle umgesetzt und committet (`a4c7b06` auf
`macos-support`, per Cherry-Pick identisch als `60d8f39` auf `macos-port-pr`; **beide zum Fork gepusht**,
PR #5 zeigt `60d8f39` als Head-Commit):

1. **LaunchAgent-Namen**: `de.blarks.fatima-voice-studio[.service]` → `io.github.hassanxs.fatima-voice-studio[.service]`
   in `compat.py`, `setup.sh`, `README.md`.
2. **Dangling-Referenzen/interne Labels**: Verweise auf `docs/superpowers/specs/2026-10-10-macos-port-design.md`
   entfernt (die Datei existiert zwar auf `macos-support`, ist aber bewusst nicht Teil des PR-Diffs auf
   `macos-port-pr` — aus Sicht des Reviewers also ein toter Link); technische Begründung blieb im Text
   (`compat.py`-Docstring, `ARCHITECTURE.md`, `README.md`). Interne Labels wie „final review C1/I3/I5/…"
   aus Kommentaren/Docstrings in `compat.py` und `test_smoke.py` entfernt, Erklärung textlich erhalten.
   README-Formulierung „Voice cloning: done — confirmed by the user" → „done — tested on this Mac".
3. **llama.cpp-Pin**: `build-llama.sh` baut jetzt standardmäßig Tag `b11476` (Hassans Vorgabe) statt `master`,
   `LLAMA_TAG` überschreibt weiterhin — analog zu `build-whisper.sh`s `WHISPER_TAG`.

Verifiziert: 39/39 Smoke-Tests grün (mit `macos/.venv/bin/python`, nicht dem System-Python — dem fehlt
`fastapi`), `bash -n` für alle fünf Shell-Skripte ok, keine alten `de.blarks`-/Design-Doc-/Review-Label-Treffer
mehr in `macos/` (außer in dieser SESSION.md selbst, die keine Produktionsdatei ist), `git diff -- studio/`
leer. `docs/superpowers/` wurde bewusst nicht angefasst (kein Teil des PR-Diffs, nicht in Hassans Punkten
genannt).

**Nächster Schritt:** auf Hassans erneute Rückmeldung zu PR #5 warten.

## S2 Pro (Fish Audio) über Metal – Stand 2026-10-14

Plan (geschrieben 2026-10-13, Superpowers writing-plans/executing-plans): `docs/superpowers/plans/2026-10-13-macos-s2pro-metal.md`,
Spec: `prompt_13.10.2026.md` (Repo-Root). Vorher `git fetch` + `git rebase origin/main` auf `macos-support`:
Upstream war zwischenzeitlich von 0.2.6 auf 0.3.3 weitergezogen und hatte S2 Pro (Fish Audio) für Windows und
Linux bereits eingeführt (`studio/s2engine.py`, `packaging/s2cpp/seed.patch`, `linux/compat.py`-Pendant) – ohne
dieses Rebase hätte der ursprüngliche Prompt (der genau diese Dateien referenzierte) nicht gepasst; Rebase lief
konfliktfrei, alte macOS-Commits wurden als bereits gemergt automatisch übersprungen.

### Umgesetzt (5 Tasks, TDD, 50 Smoke-Tests, alle grün)

1. `studio/config.py`: Darwin-Sonderfall entfernt, der S2-Pro-Modelle unter macOS aus `MODELS` löschte.
2. `studio/s2engine.py`: `S2Server._start()` kennt jetzt `engine == "metal"` → `["--metal", "--codec-cpu"]`
   (kein Geräteindex, anders als `--cuda <id>`/`--vulkan <id>` – bestätigt durch den echten `s2 --help`:
   `-M, --metal Use Metal backend (macOS only)`). `--codec-cpu` kam erst in der Review-Fixphase dazu (siehe
   unten) – ohne das Flag stürzt jede S2-Pro-Anfrage ab. CUDA/Vulkan-Zweige unverändert.
3. `macos/build-s2.sh` (neu): baut s2.cpp (Commit `2c33261938da1a41d713768b1b391b4d368d7d2c`, PRs #50/#51/#52,
   `packaging/s2cpp/seed.patch`, `-DS2_METAL=ON`) aus dem Quellcode nach `macos/bin/s2cpp/` – es gibt kein
   Homebrew-Formula für s2.cpp, anders als bei llama.cpp/whisper.cpp.
4. `macos/compat.py`: neue `_patch_s2()` (Vorbild `linux/compat.py`), `s2_folder()`, `_link_tools()` verlinkt
   `s2`/`tokenizer.json` nach `<FVS_HOME>/engine/s2-metal/`, S2-Pro-Modelle laufen weiter über die `"system"`-Engine
   (`engines: ["system"]`, nicht `"metal"` – das ist nur der S2-Backend-Schlüssel), `s2engine.subprocess` hängt am
   selben pdeath-gewrappten `Popen` wie die Haupt-Engine.
   - **Echter Fund beim Live-Test** (nicht von den Unit-Tests erfasst): `Downloads.start()`s eigene Prüfung
     (`not config.S2_RUNTIME[engine][1]`) deutete unsere Größe-0-Markierung ("nichts herunterzuladen") als
     "nicht verfügbar" und hätte jeden S2-Pro-Download dauerhaft blockiert – reproduziert durch einen echten
     `POST /api/models/s2-pro-q6/download` gegen die laufende App (409 "isn't available to download yet"), erst
     danach gefixt (eigener `start()`-Pfad statt Rückfall auf die kaputte Prüfung) und mit RED→GREEN-Test
     abgesichert. Derselbe Fehler steckt unverändert in `linux/compat.py` (dort nicht angefasst, außerhalb des
     Umfangs dieser Session).
5. Echter Build + Verifikation auf diesem Mac, Review durch einen frischen Opus-Subagenten, Fix-Pass (Details
   unten).

### Echte Verifikation auf diesem Mac (Apple M6, 32 GB, macOS 27.0.1)

- `cmake` fehlte (noch nie gebraucht, da llama.cpp/whisper.cpp hier über Homebrew-Bottles laufen) → `brew install
  cmake` (Standard-Build-Tool, reversibel).
- `./macos/build-s2.sh` lief durch, `s2 --help` zeigt `--metal`, `--codec-cpu` und `--seed`.
- Q6-Modell (4,5 GB) über die echte App heruntergeladen (`installed: true`, `engine_ok: true`).
- **Beim ersten Durchlauf gefunden, im Review-Fix behoben**: echte Sprachausgabe über `--metal` allein stürzte
  ab – `ggml_metal_op_encode_impl: error: unsupported op 'PAD'` im Audio-Codec-Decode-Pfad, unabhängig von
  `-ngl`/Text/Sprache. Der frische Opus-Reviewer fand live (CLI und Server-Modus), dass `--codec-cpu` (laut
  `s2 --help`: „Force codec on CPU even when model uses GPU") den Codec auf die CPU zwingt, während der
  Transformer auf Metal bleibt – damit läuft die Generierung durch. Selbst nachgeprüft (CLI und über die echte
  App): echtes, nicht-stilles Audio.
- Mit dem Fix erneut über die laufende App getestet: Englisch (HTTP 200), Hindi als S2-only-Sprache (HTTP 200),
  `[excited]`-Emotionstag (HTTP 200), ein Batch-Skript mit `subtitles: true` auf einer S2-Pro-Stimme (echtes,
  korrekt getimtes `.srt` neben dem `.wav`), Abbruch eines S2-Pro-Skripts mitten im Batch (Status `cancelled`,
  kein Zombie-Prozess), `--stop` beendet App und `s2`-Prozess sauber (normaler, nicht nur Absturz-Fall).
- Gemessen (CLI, `/usr/bin/time -l`, Spec-eigener Testsatz, Q6-Modell): Spitzen-RAM ≈ 5,6 GB; einmaliger
  Lauf 13,79 s für 3,76 s Audio (enthält einmaliges Kompilieren der Metal-Shader-Pipeline). Über die App
  dauerte jede HTTP-Anfrage für ähnlich lange Sätze ~22–28 s – der Server scheint diese Kompilierkosten bei
  jeder Anfrage erneut zu zahlen statt einen warmen Prozess wiederzuverwenden; das ist bestehendes
  `S2Server`-Verhalten, das diese Session nicht verändert hat und hier nicht weiter untersucht wurde.
- 50/50 `macos/test_smoke.py`, 5/5 `linux/test_smoke.py -k StaticChecks` (kein nutzbares `linux/.venv` auf
  diesem Mac – kaputter Symlink von einer anderen Maschine –, daher System-`python3`), `bash -n` für beide
  Build-Skripte.

### Review

Frischer Opus-Subagent (General-Purpose, read-only) über den gesamten Arbeitsbaum-Diff (kein Commit-Bereich
möglich, da auf Wunsch des Nutzers nichts committet wurde – Review-Paket manuell aus `git diff` gebaut).
Verdict: „Ready to merge: With fixes". Ein Critical-Fund (das `--codec-cpu`-Fehlen oben), im selben Durchgang
behoben und verifiziert. Zwei Minor-Funde zurückgestellt (nicht behoben): Windows-Formulierungen lecken auf
`/v1/audio/speech`-Fehlertexten durch (gleiches Muster wie bei Linux), `setup.sh` erwähnt s2.cpp/`build-s2.sh`
gar nicht.

### Offen

- Zwei zurückgestellte Minor-Funde aus dem Review (s. oben) – nicht behoben, auf Wunsch gegen Review-Minors
  nicht automatisch gefixt.
- Warum jede App-Anfrage die Metal-Shader-Pipeline neu kompiliert (~20 s Overhead pro Anfrage) – nicht
  root-cause-untersucht, bestehendes Verhalten.
- Keine Commits erstellt (auf ausdrücklichen Wunsch des Nutzers) – alle Änderungen liegen unstaged/uncommitted
  im Arbeitsbaum von `macos-support`.
