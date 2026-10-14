# SESSION – Fatima Voice Studio

Der Stand der Arbeit steht in **`linux/SESSION.md`** (Linux-Port, Git-Stand, Issue #1, offene Punkte, nächste Schritte, macOS-Notizen) und **`macos/SESSION.md`** (macOS-Port, Branch-Stand, Issue #4, PR #5). Zuerst die lesen.

Kurz (2026-10-08): Linux-Version läuft, Branch `linux-support` (1 Commit) liegt im Fork Blarks-de/fatima-voice-studio,
Issue hassanxs/fatima-voice-studio#1 ist offen, kein PR. Nächster Schritt: Whisper-Untertitel-Batch testen.

Update 2026-10-09: Whisper-Teil (Build, Transkription, SRT-Timing) auf dockfish getestet und ok, Details in `linux/SESSION.md`. Kompletter Batch mit TTS steht noch auf der GPU-Maschine aus; Maintainer hat im Issue #1 um den PR gebeten.

Update 2026-10-09 (Piepkiste, GPU-Maschine): Kompletter TTS + Whisper-Batch getestet und ok (Details in `linux/SESSION.md`). README-Tested-Tabelle aktualisiert (Commit 2c9a845).
`linux-support` (5 eigene Commits auf origin/main 0.2.4) per Force-Push im Fork; PR hassanxs/fatima-voice-studio#3 ist offen und mergeable. Kommentar mit Teststand dort gepostet (issuecomment-6084631395).
Permission-Regel für den Force-Push in `.claude/settings.local.json` (git-ignoriert). Nächste Schritte: auf Maintainer-Antwort warten; offen bleiben Whisper ab medium, App-Downloads, /transcribe, systemd/--desktop, Dialoge am Bildschirm, `engine_release b11476` vs. b10689.

Update 2026-10-09 (spät): Pause/Resume, kill -9 mit Fortsetzen und Stimmenklonen auf der Piepkiste getestet, alles ok (Details `linux/SESSION.md`). README-Tabelle angepasst, lokal committet, noch nicht gepusht. Offen: Video/M4A im echten Batch, Voice-Separator, Whisper large/turbo, systemd/--desktop, Bildschirmtests.

Update 2026-10-09 (nachts): Video/M4A/WebM im echten Batch und Voice-Separator getestet, ok (Details `linux/SESSION.md`); `985038f` ist in PR #3 gepusht. Alle Pflichttests aus Hassans Review sind erledigt. Offen: Whisper large/turbo, /transcribe im Browser, systemd/--desktop, Bildschirmtests, denoise=1. README-Änderung dazu ist lokal, nicht committet.

Update 2026-10-09 (nachts): Whisper large-v3 getestet (Batch + Transkription), ok; README-Zeile ergänzt, noch nicht committet/gepusht. Korrektur: `subtitles_model: ""` bevorzugt small per `SUBTITLE_PREFERENCE`, das ist kein Fehler. Offen: turbo, /transcribe im Browser, systemd/--desktop, Bildschirmtests, denoise=1.

Update 2026-10-09 (nachts): systemd-Dienst getestet (Install, Sprechen, stop, kill -9 mit Auto-Neustart), ok; Fehler in der llama.cpp-Versionsprüfung von `setup.sh` (meldete b0) behoben. 2 neue Commits lokal, noch nicht gepusht. Offen: turbo, /transcribe im Browser, Start bei echtem Login, Bildschirmtests, denoise=1.

Update 2026-10-09 (nachts): Whisper turbo getestet, ok; README-Commit lokal, noch nicht gepusht. Offen: /transcribe im Browser, Start bei echtem Login, Bildschirmtests, denoise=1.

Update 2026-10-09 (nachts): /transcribe im Browser getestet (Upload MP4/M4A, Fortschritt, Read, TXT/SRT/VTT), ok. README-Commit lokal, noch nicht gepusht. Offen: Start bei echtem Login, Tray/Browse-Dialog/xdg-open am Bildschirm, denoise=1, engine_release b11476.

Update 2026-10-09 (nachts): denoise getestet (ok) und engine_release geklärt: die About-Seite zeigte die Windows-Pin-Version b11476 statt der installierten b10689 und „Windows <Kernel>“; in `linux/compat.py` behoben (+2 Smoke-Tests, 25 ok). 2 Commits lokal, noch nicht gepusht. Offen: Start bei echtem Login/Reboot, Tray/Browse-Dialog/xdg-open am Bildschirm.

Update 2026-10-10 (AgentM6, Mac mini Apple M6): macOS-Port umgesetzt und komplett manuell verifiziert (Details in `macos/SESSION.md`). 13-Task-Plan, finales Review (2 Critical + 8 Important, alle gefixt bis auf 3 bewusst zurückgestellte), dabei ein echter Tray-Absturz (SIGTRAP, Hauptthread-Verstoß gegen AppKit) gefunden und in `macos/compat.py` behoben. Branch auf inzwischen weitergezogenes `origin/main` (0.2.4 → 0.2.6) rebased, ohne Codeänderung, 39/39 Tests weiterhin grün. Issue hassanxs/fatima-voice-studio#4 und PR #5 eröffnet (gleiches Muster wie Issue #1/PR #3). Branches: `macos-support` (volle Historie, Fork) und `macos-port-pr` (saubere 19 Commits, nur `macos/`, Basis für den PR). Nächster Schritt: auf Hassans Rückmeldung warten.

Update 2026-10-11: Hassans drei Review-Punkte zu PR #5 umgesetzt (LaunchAgent-Namen auf `io.github.hassanxs.*`, Dangling-Referenz auf das nicht im PR enthaltene Design-Doc sowie interne Review-Labels entfernt, `build-llama.sh` auf llama.cpp-Tag `b11476` gepinnt). Details, genaue Commit-IDs und Testergebnisse in `macos/SESSION.md`. Commit auf `macos-support` (`a4c7b06`) und per Cherry-Pick auf `macos-port-pr` (`60d8f39`) — beide zum Fork gepusht, PR #5 zeigt `60d8f39` als Head-Commit. Nächster Schritt: auf Hassans Rückmeldung warten.

Update 2026-10-14: S2 Pro (Fish Audio) über Metal umgesetzt und auf diesem Mac vollständig getestet. Upstream war inzwischen auf 0.3.3 weitergezogen und hatte S2 Pro für Windows/Linux eingeführt; `macos-support` dafür per `git rebase origin/main` aktualisiert (konfliktfrei). 5 Tasks (TDD, 50 Smoke-Tests grün): `studio/config.py`/`studio/s2engine.py` um die `"metal"`-Engine ergänzt, neues `macos/build-s2.sh` (Quellbau, kein Homebrew-Formula für s2.cpp), `macos/compat.py`s neue `_patch_s2()`. Echter Build + Download (Q6, 4,5 GB) über die laufende App bestätigt; dabei ein echter Downloads.start()-Bug gefunden und gefixt (Größe-0-Markierung blockierte jeden S2-Pro-Download dauerhaft — derselbe Fehler steckt unverändert in `linux/compat.py`). Frisches Opus-Review fand einen Critical-Fund: `--metal` allein stürzte bei jeder echten Sprachausgabe ab (`unsupported op 'PAD'`, fehlende Metal-Codec-Op im gepinnten s2.cpp-Commit); behoben durch zusätzliches `--codec-cpu` (Codec auf CPU, Transformer bleibt auf Metal) — danach echte Sprachausgabe bestätigt: Englisch, Hindi, Emotionstag `[excited]`, Whisper-Untertitel auf einer S2-Pro-Stimme, Abbruch mitten im Batch, sauberes Prozessende mit der App. Details in `macos/SESSION.md`. Keine Commits (auf Wunsch des Nutzers nicht erstellt).
