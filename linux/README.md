# Fatima Voice Studio unter Linux

Fatima Voice Studio ist upstream eine reine Windows-App. Dieser Ordner enthält alles, was nötig ist, um sie unter
Linux zu betreiben. **Der Ordner `studio/` bleibt unverändert**; eine Kompatibilitätsschicht (`compat.py`) ersetzt
beim Start die Windows-Teile. So lassen sich Upstream-Änderungen per `git pull` übernehmen.

Getestet auf CachyOS (Arch), Python 3.13, RTX 4070 Ti SUPER, `llama.cpp-cuda` b10689 (Stand 2026-10-08).

## Schnellstart

```bash
cd ~/fatima-voice-studio/linux
./setup.sh                  # venv + Abhängigkeiten + Check der Werkzeuge
./build-whisper.sh          # nur für Untertitel/Transkripte: baut whisper-cli nach linux/bin/ (~1 Min)
./fatima-voice-studio       # startet und öffnet http://127.0.0.1:9830/
```

Beim ersten Start in der App: **Setup** öffnen, Sprachmodell herunterladen (Qwen3-TTS Q8, 2,3 GB, oder Q4,
1 GB) und für Untertitel ein Whisper-Modell (small, 190 MB). Die Downloads laufen über die App selbst
(fortsetzbar, SHA-256-geprüft). Danach unter **Voices** eine Stimme anlegen (Clip hochladen oder
„Find a new voice“) und unter **Create** loslegen.

Für die Engine muss nichts heruntergeladen werden: Die App nutzt das `llama-tts` aus dem System.

## Starten und Beenden

| Befehl | Wirkung |
|---|---|
| `./fatima-voice-studio` | startet mit **Tray-Icon** (Rechtsklick → Quit) und öffnet den Browser; Strg+C im Terminal beendet auch |
| `./fatima-voice-studio --no-tray` | ohne Tray-Icon (für Server, systemd) |
| `./fatima-voice-studio --stop` | beendet eine laufende Instanz, egal wie sie gestartet wurde |
| `./fatima-voice-studio --no-browser` | Browser nicht öffnen (kombinierbar) |

Das Tray-Icon nutzt AppIndicator (KDE, GNOME mit Erweiterung). Dafür braucht das venv `pygobject`, das `setup.sh`
installiert (baut aus dem Quellcode: `gobject-introspection`, `cairo`, `pkgconf`). Fehlt `pygobject`, startet die App ohne Tray und weist darauf hin; beenden dann mit Strg+C oder `--stop`.

## Voraussetzungen

| Was | Wofür | Arch-Paket |
|---|---|---|
| `uv` | venv mit Python 3.13 | `uv` |
| `gobject-introspection`, `cairo`, `pkgconf` | baut `pygobject` für das Tray-Icon (optional) | gleichnamig |
| `llama-tts` | Sprachausgabe (Qwen3-TTS) | `llama.cpp-cuda` (NVIDIA) oder `llama.cpp-vulkan` (AMD/Intel) |
| `whisper-cli` | Untertitel, Transkripte | `./build-whisper.sh` (das Arch-Paket `whisper-cpp` kollidiert mit `llama.cpp-cuda`, beide bringen `ggml` mit) |
| `ffmpeg` | Video-Dateien, M4A/AAC einlesen | `ffmpeg` |
| `setpriv` (util-linux) | Engine endet mit der App | `util-linux` |
| `gio` oder `trash-cli` | Löschen in den Papierkorb | `glib2` / `trash-cli` |
| `zenity` oder `kdialog` | „Browse“-Knopf in den Einstellungen | `zenity` / `kdialog` |
| `notify-send` | Benachrichtigung, wenn ein Batch fertig ist | `libnotify` |
| `wl-copy`/`xclip`/`xsel` | Zwischenablage im Tray-Menü | `wl-clipboard` / `xclip` |

Das `llama-tts` muss Qwen3-TTS können: mindestens **b10270** (4. Aug 2026), ältere Builds haben eine andere
Kommandozeile. Geprüft ist b10689; die Windows-Version der App ist auf b11476 gepinnt. `setup.sh` warnt, wenn das
`llama-tts` älter ist (`LLAMA_MIN_BUILD` am Anfang des Skripts). Läuft ein Modell nicht, zuerst `llama-tts` aktualisieren.

Python 3.14 geht nicht (für `sherpa-onnx`/`lameenc` gibt es noch keine Wheels), deshalb legt `setup.sh` das venv
mit 3.13 an.

## Dateien in diesem Ordner

| Datei | Zweck |
|---|---|
| `build-whisper.sh` | baut `whisper-cli` (CPU, statisch) nach `bin/` |
| `setup.sh` | Einrichtung; `--service` (systemd), `--desktop` (Menüeintrag) |
| `fatima-voice-studio` | Startskript (Tray ist Standard; `--no-tray`, `--stop`, `--no-browser`, `--check`) |
| `run.py` | Einstieg: lädt `compat.py`, dann das normale `studio.__main__` |
| `compat.py` | Die Kompatibilitätsschicht (siehe `ARCHITECTURE.md`) |
| `mcp_stdio.py` | stdio-MCP-Start für Agenten (Claude Code …) |
| `requirements-linux.txt` | Abhängigkeiten ohne `pywin32` |
| `systemd/`, `desktop/` | Vorlagen für Dienst und Menüeintrag |
| `.venv/` | Python-Umgebung (nicht in git) |
| `ARCHITECTURE.md` | Aufbau und Datenfluss mit Diagramm |

## Wo liegen die Daten?

Nichts im Repo. Standard:

| Was | Ort |
|---|---|
| Einstellungen, API-Key, Logs | `~/.local/share/fatima-voice-studio/data/` |
| Modelle | `~/.local/share/fatima-voice-studio/models/` |
| Stimmen-Bibliothek | `~/.local/share/fatima-voice-studio/voices/` |
| Engine-Links (`llama-tts`, `whisper-cli`) | `~/.local/share/fatima-voice-studio/engine/` |
| Batches, Exporte (Audio) | `~/Music/Fatima Voice Studio/{Batches,Exports}` |

Umgebungsvariablen:

| Variable | Wirkung |
|---|---|
| `FVS_HOME` | anderer Datenordner. Er muss auf demselben Laufwerk wie `~` liegen, sonst klappt der Papierkorb nicht |
| `XDG_MUSIC_DIR` | Basis für Batches/Exporte |
| `FVS_LLAMA_TTS` | Pfad zu einem anderen `llama-tts` (z. B. selbst gebaut) |
| `FVS_WHISPER_CLI` | Pfad zu einem anderen `whisper-cli` (sonst: `linux/bin/`, dann `PATH`) |

Die Links in `engine/` legt `compat.py` bei jedem Start neu an, ein Update von `llama.cpp` braucht also nichts weiter.

## Autostart

- **systemd (empfohlen):** `./setup.sh --service`, danach `systemctl --user status fatima-voice-studio`,
  Logs mit `journalctl --user -u fatima-voice-studio`. Läuft mit `--no-tray --no-browser`.
- **Desktop-Autostart:** Der Schalter „Start with Windows“ in den Einstellungen legt
  `~/.config/autostart/fatima-voice-studio.desktop` an (die Beschriftung ist Upstream-Text).
- **Menüeintrag:** `./setup.sh --desktop`.

## Agenten / MCP

Der MCP-Endpunkt hängt direkt am laufenden Server: `http://127.0.0.1:9830/mcp`, Header
`Authorization: Bearer <API-Key>` (Key: Einstellungen oder `data/config.json`). Für Claude Code:

```bash
claude mcp add --transport http fatima http://127.0.0.1:9830/mcp --header "Authorization: Bearer <API-Key>"
```

Alternativ per stdio (die App muss laufen):
`~/fatima-voice-studio/linux/.venv/bin/python ~/fatima-voice-studio/linux/mcp_stdio.py`.

## Unterschiede zu Windows

- Es gibt eine einzige Engine „System“; die Windows-Downloads (CUDA/Vulkan/CPU-ZIPs) entfallen. Ob GPU oder
  CPU gerechnet wird, hängt vom installierten `llama.cpp` ab.
- Updates: aus (`git pull` im Projekt). Die Update-Seite zeigt dazu einen Hinweis.
- Stirbt die App hart, beendet der Kernel auch `llama-tts` (`setpriv --pdeathsig`, wie das Job Object unter Windows).
- Das Tray-Icon ist Standard und nur da, wenn der Desktop AppIndicator kann (KDE: ja, GNOME: Erweiterung). 
  Benachrichtigungen („Batch fertig“) laufen über `notify-send`.
- Sichtbare „Windows“-Texte der Oberfläche („Start with Windows“, „Recycle Bin“ …) werden beim Ausliefern umgeschrieben
  („Start at login“, „Trash“). Die Liste steht in `compat.py` (`TEXTS`); `studio/web/` bleibt unverändert.

## Fehlersuche

| Symptom | Ursache / Abhilfe |
|---|---|
| `tensor … not within the file bounds` | Modell-Download unvollständig. In der App neu laden (setzt fort) |
| „No voice: pass a voice name …“ | Zuerst eine Stimme anlegen (Voices) oder eine Standardstimme setzen |
| Setup zeigt „No engine installed“ | `llama-tts` nicht im `PATH`. `which llama-tts` oder `FVS_LLAMA_TTS` setzen |
| Keine Untertitel | `whisper-cli` fehlt (`./build-whisper.sh`) oder kein Whisper-Modell geladen |
| Löschen schlägt fehl („Papierkorb … Einhängepunkte“) | `FVS_HOME` liegt nicht auf demselben Laufwerk wie `~` |
| Port belegt | In den Einstellungen `port` ändern (Neustart nötig) |
| Engine-Fehler im Detail | `~/.local/share/fatima-voice-studio/data/logs/engine.log` und `studio.log` |

## Update und Wartung

```bash
cd ~/fatima-voice-studio && git pull        # Upstream übernehmen
linux/setup.sh                              # falls sich requirements.txt geändert hat
```

Nach einem Upstream-Update prüfen: `linux/fatima-voice-studio --check` und den Smoke-Test:

```bash
.venv/bin/python linux/test_smoke.py        # oder: .venv/bin/python -m pytest linux/test_smoke.py
```

Die Schicht hängt an diesen Namen in `studio/`: `config` (HOME, DATA, DEFAULTS, ENGINES …), `hardware`
(`_registry_gpus`, `_ram_gb`, `_cpu`, `on_battery`), `autostart`, `updater.Updater`, `studio.trash`, `studio.winui`,
`tray.copy`. Der Test prüft, dass es sie noch gibt und dass `compat.py` sie tatsächlich ersetzt (auch dort, wo
`app.py`, `store.py` & Co. sie per `from … import` binden), außerdem die `llama-tts`-Kommandozeile aus `engine.py`
und den Wortlaut der Weboberfläche. Er braucht weder GPU noch `llama-tts` noch Display (der Tray-Test wird ohne
Display übersprungen) und schreibt nur in einen temporären Ordner. Schlägt er an, muss `compat.py` angepasst
werden, oder Upstream baut einen Hook.
