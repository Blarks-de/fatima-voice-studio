# Architektur der Linux-Anpassung

Prinzip: `studio/` (Upstream) wird nicht verändert. `run.py` ruft `compat.apply()` auf, **bevor** `studio`
importiert wird; `compat.py` ersetzt zur Laufzeit die Windows-Teile. Danach läuft der normale Einstieg
`studio.__main__.main()`.

```mermaid
flowchart LR
    subgraph Start
        L[fatima-voice-studio<br/>bash] --> R[run.py]
        SD[systemd / .desktop] --> L
        MCPs[mcp_stdio.py] --> C
        R --> C[compat.apply]
    end
    C -->|patcht| S[studio/ Upstream<br/>FastAPI + Worker + Web-UI]
    R -->|danach| M[studio.__main__.main]
    M --> S

    subgraph compat.py ersetzt
        P1[config: Pfade, Engine 'system']
        P2[hardware: lspci, /proc, /sys]
        P3[trash: gio trash]
        P4[winui: zenity / kdialog]
        P5[autostart: ~/.config/autostart]
        P6[updater: aus]
        P7[os.startfile: xdg-open]
        P8[tray.copy: wl-copy / xclip]
        P9[engine: setpriv --pdeathsig]
        P10[web: Windows-Texte umschreiben<br/>tray: notify-send]
    end
    C --- P1 & P2 & P3 & P4 & P5 & P6 & P7 & P8 & P9 & P10

    S -->|Subprozess je Segment| E[llama-tts<br/>System, CUDA/Vulkan]
    S -->|Subprozess| W[whisper-cli<br/>System, CPU]
    S -->|ffmpeg| F[ffmpeg<br/>System]
    E --> GPU[(GPU)]
    S <-->|HTTP :9830| UI[Browser / OpenAI-API / MCP]
    S --> D[(FVS_HOME<br/>data, models, voices)]
    S --> A[(~/Music/…<br/>Batches, Exports)]
    HF[Hugging Face] -->|Modell-Download in der App| D
```

## Ablauf beim Start

1. `run.py` setzt den Importpfad und importiert `compat`.
2. `compat.apply()`:
   1. importiert `studio.config` und biegt Pfade, Standardwerte und Engine-Funktionen um,
   3. ersetzt `studio.trash` und `studio.winui` durch Linux-Module (`sys.modules`),
   4. überschreibt die Hardware-Erkennung (`import winreg` in `studio/hardware.py` wird nur für diesen einen Import
      mit einem Stub bedient; bliebe er in `sys.modules`, hielte `mimetypes` das System für Windows), Autostart-Funktionen und den Updater,
   5. legt die Symlinks `engine/system/llama-tts` und `engine/whisper/whisper-cli` an.
3. `studio.__main__.main()` startet uvicorn wie unter Windows.

Reihenfolge ist wichtig: Module wie `presets`, `voices`, `speech_text` lesen `config.DATA`/`config.VOICES` schon als
Standardargument beim Import. `config` muss deshalb vor allen anderen gepatcht sein.

## Engine „system“

Upstream erwartet `<engine_dir>/<ENGINE_EXE>` und lädt Windows-ZIPs herunter. Unter Linux gibt es eine einzige
Engine `system` ohne Downloads (`zips: []`). `engine_dir()` zeigt auf `FVS_HOME/engine/system`, darin liegt ein
Symlink auf das `llama-tts` aus dem `PATH` (oder `FVS_LLAMA_TTS`). Dasselbe gilt für `whisper-cli`. So bleibt
der Upstream-Code für Start, Fortschritt und Fehlermeldungen unverändert.

## Was nicht ersetzt wurde (und warum es geht)

- `creationflags=CREATE_NO_WINDOW`: Upstream nutzt `getattr(subprocess, …, 0)`, unter Linux also 0.
- `_KillOnCloseJob` (Windows Job Object): nur bei `sys.platform == "win32"`. Unter Linux ersetzt
  `compat._patch_engine` das: `engine.subprocess.Popen` startet `llama-tts` über `setpriv --pdeathsig SIGKILL`,
  der Kernel beendet die Engine also mit der App (`setpriv` ersetzt sich per exec, die PID bleibt gleich).
- ffmpeg: Upstream sucht erst die eigene `ffmpeg.exe`, dann `shutil.which("ffmpeg")`.
