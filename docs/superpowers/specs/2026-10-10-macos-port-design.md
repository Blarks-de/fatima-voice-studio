# macOS-Port von Fatima Voice Studio — Design

Stand: 2026-10-10

## Kontext

Fatima Voice Studio ist ein Windows-orientiertes Programm zur Sprachsynthese und
zum Klonen von Stimmen (Upstream: https://github.com/hassanxs/fatima-voice-studio,
MIT-Lizenz). Der Linux-Port (`linux/`) ist fertig, PR #3 wurde von Hassan Latif in
`main` gemergt, Issue #1 ist geschlossen, Linux ist offiziell community-supported.
Details und Testprotokoll: `Agenten/fatima-voice-studio.md`, `linux/SESSION.md`.

Hassan hat für den Linux-Port ausdrücklich dieses Muster gebilligt:
- ein Add-on-Ordner pro Plattform (`linux/`)
- `studio/` bleibt unangetastet
- keine `sys.platform`-Weichen direkt im Windows-Code

Dieses Dokument beschreibt den gleichen Ansatz für macOS, auf dem Mac mini
(Apple M6, 32 GB Unified Memory, macOS 27.0.1, dieser Rechner), auf dem auch
entwickelt und getestet wird.

## Ziel

Ein `macos/`-Ordner, der `studio/` über eine Kompatibilitätsschicht (`compat.py`,
analog zu `linux/compat.py`) für macOS lauffähig macht — ohne `studio/` zu ändern.
Endziel ist ein zweiter Pull Request nach dem gleichen Muster wie PR #3.

## Nicht-Ziel

- Kein gemeinsamer plattformneutraler Kern mit `linux/` in dieser Iteration.
  Begründung: Hassan hat bisher nur das Muster "ein Ordner pro Plattform" gesehen
  und gebilligt; eine Abstraktion vorab wäre zusätzliches Risiko für einen PR, der
  noch gar nicht gestellt ist. Die Tabelle der Ersetzungen (unten) zeigt ohnehin
  recht unterschiedliche Mechanismen zwischen Linux und macOS (gio vs. osascript,
  AppIndicator vs. pyobjc, systemd vs. launchd). Falls sich später doch starke
  Überlappung zeigt, ist eine Extraktion ein separater, bewusster Schritt.
- Keine App-Bundle-Distribution (.app, Code-Signing, Notarization) — das ist ein
  späteres Thema, nicht Teil dieses Ports.

## Struktur

```
macos/
  compat.py          # analog zu linux/compat.py
  run.py              # Einstiegspunkt, analog zu linux/run.py
  setup.sh            # Einrichtung, analog zu linux/setup.sh
  build-llama.sh      # Fallback: llama.cpp selbst bauen mit -DGGML_METAL=ON
  build-whisper.sh     # Fallback: whisper.cpp selbst bauen (ggf. vom linux/-Skript übernommen)
  test_smoke.py        # analog zu linux/test_smoke.py
  README.md
  ARCHITECTURE.md
```

## Ersetzungstabelle (Windows-Teil → macOS)

| Teil in `studio/` | macOS-Ersatz |
|---|---|
| Datenordner | `~/Library/Application Support/Fatima Voice Studio` |
| Audio-Ordner | `~/Music/Fatima Voice Studio` |
| Engine `llama-tts` | Homebrew `llama.cpp` (Metal auf Apple Silicon automatisch aktiv) oder Fallback: selbst bauen mit `-DGGML_METAL=ON` |
| `whisper-cli` | Homebrew `whisper.cpp` oder Fallback: `build-whisper.sh` (wie Linux) |
| ffmpeg | System-ffmpeg (Homebrew), gleiches Patch-Muster wie `linux/compat.py::_patch_tools` |
| Hardware (`hardware.py`) | `sysctl -n machdep.cpu.brand_string` (CPU), `sysctl hw.memsize` (RAM), `pmset -g batt` (Akku), `system_profiler SPDisplaysDataType` (GPU-Name) |
| VRAM | Unified Memory: GPU-Speicher = RAM, kein separater Wert |
| Papierkorb | `osascript -e 'tell application "Finder" to delete (POSIX file "…")'` |
| Ordnerdialog | `osascript -e 'POSIX path of (choose folder)'` |
| `os.startfile` | `open` |
| Zwischenablage | `pbcopy` / `pbpaste` |
| Autostart (Tray-Toggle) | `~/Library/LaunchAgents/*.plist` mit `RunAtLoad` |
| `--service` (Dauerbetrieb) | eigenes LaunchAgent-Plist mit `KeepAlive` (separat vom Autostart-Plist, gleiche zwei Konzepte wie bei Linux: Login-Start vs. Dauerdienst) |
| Engine stirbt mit der App (`setpriv --pdeathsig`) | kein Kernel-Äquivalent auf macOS. Lösung: `llama-tts`/`whisper-cli` über einen kleinen Watcher-Shell-Wrapper starten, der `kill -0 $PPID` pollt und den Child beendet, sobald der Elternprozess weg ist (funktioniert auch bei `kill -9` auf die App) |
| Tray (`pystray`) | `darwin`-Backend über PyObjC. **Wichtig:** `studio/__main__.py` ruft `tray.run()` bereits im Hauptthread auf (Server läuft im Hintergrundthread) — das passt genau zu PyObjC/`NSApplication`-Anforderungen. Keine Umstrukturierung von `run.py` nötig, nur `patch_tray()` mit macOS-Clipboard (`_copy` → `pbcopy`) und -Notify (`osascript display notification` oder natives pystray-`notify`, prüfen) |
| Wording (Linux-/Windows-Texte in `studio/web/`) | gleiches Muster wie `linux/compat.py` (`TEXTS`/`JS_PATCHES`), Hinweistexte auf `brew install …` statt `pacman`/`apt` |

## Offene technische Fragen (zu klären in der Umsetzung, nicht im Design)

Diese Fragen lassen sich nur durch tatsächliches Installieren und Testen auf
diesem Mac beantworten, nicht durch weiteres Nachdenken. Sie werden der erste
Implementierungs-Task:

1. Baut die Homebrew-Bottle von `llama.cpp` (aktuell `v0.6.0`) überhaupt ein
   `llama-tts`-Binary? Falls nein oder falls Qwen3-TTS fehlt (nötig: Build
   b10270+): Fallback auf Selbstbau mit `-DGGML_METAL=ON`.
2. Liefert Homebrews `whisper.cpp` (1.9.5) ein nutzbares `whisper-cli` mit
   Metal/CoreML, oder braucht es wie bei Linux ein eigenes Build-Skript?
3. Geschwindigkeit der Sprachsynthese auf Apple M6 (Vergleichswert: Windows-App
   wirbt mit ~2,2× Echtzeit auf einer RTX 5060; Linux schafft 3–4× auf einer
   RTX 4070 Ti SUPER).
4. Benachrichtigungen: unterstützt pystrays `darwin`-Backend `icon.notify()`
   nativ, oder braucht es `osascript -e 'display notification'` wie bei Linux
   `notify-send`?
5. Ob der Maintainer eine zweite Plattformschicht im gleichen Muster akzeptiert
   (ist nach PR #3 sehr wahrscheinlich, aber nicht zugesichert).

## Testen

Analog zum Linux-Vorgehen: zuerst Smoke-Test (`macos/test_smoke.py`, Import +
Kompatibilitätsschicht + gepatchte Funktionen vorhanden), dann echte
Funktionstests auf diesem Mac (TTS, Whisper-Batch, Stimmenklonen, WAV/MP3/SRT,
Pause/Resume, `kill -9`-Wiederaufnahme, Video/M4A, Tray, LaunchAgent-Autostart,
`--service`). `studio/` bleibt dabei unangetastet, geprüft wie bei Linux per
`git diff` gegen `origin/main`.

## Ergebnis für README/Issue

Nach Abschluss: neues GitHub-Issue nach dem Muster von Issue #1 ("macOS support"),
dann PR mit dem Ordner `macos/` — ändert nichts an `studio/`, gleicher Ablauf wie
bei PR #3.
