# What's new

The app shows the entries for versions newer than yours on Settings → Updates. Keep each line short and plain.

## 0.2.6
- Fixed: a part could refuse to play ("no supported sources") after the batch page refreshed while a batch was running. Players now load again by themselves, and a part's audio only loads when you play it, so long batches open faster.

## 0.2.5
- Whisper runs on your graphics card, like the voice: subtitles and transcripts about 9× faster (a 26-minute script in about 40 seconds instead of 6½ minutes). NVIDIA, AMD and Intel cards; it sets itself up after the update with a small one-time download, and uses the processor if the card can't.
- On the processor, Whisper now runs at low priority with half the threads, so the PC stays usable.
- The top bar shows the subtitle step's progress, and whether it's on the graphics card or the processor.

## 0.2.4
- Tidier top bar: Create, Batches, Voices and Transcribe as tabs; Help (?) and a menu on the right with Settings, Pronunciation, Models, Setup, Connect and About.
- New About page: version, licences of your models, credits, and your PC's details to copy into a problem report.
- Dark mode: pick Light, Dark or Same as Windows in Settings → App.
- New audio players everywhere: a waveform you can click or drag to jump around, and only one plays at a time.
- Tidier voice cards: initials badge, buttons on one line (Make default is now a star), and a note under Add voice saying what's still needed.
- Parts show their state as a coloured strip (green done, amber to check, red failed), and the text lights up while a part plays.
- Create: script boxes grow as you type, and the queue shows how much audio you made today, this week and in all.
- Batch page: details as small labels, and the Whisper score in green, amber or red so scripts to check stand out.
- The top bar shows a filling ring while speaking (hover the line under it for the full text).
- Friendlier empty pages, grey placeholders while pages load, a quicker Settings page, and messages with an icon.
- Help is now built in: step-by-step guides for every part of the app, with search and a Help link on every page. Works offline.
- Works on a fresh Windows install: the app now brings the Microsoft Visual C++ Runtime the engines need, and says clearly when an engine can't start.
- Tidier Settings page: the cards sit in three even columns, Output is split into Speech and Files, and each folder has an Open button.
- Settings now shows the real MP3 quality (192 kbps by default), and offers 192 and 256.

## 0.2.3
- Clearer Updates panel in Settings: what's new, the download size, and what each button does.
- Ready-made English and Spanish pronunciation lists to import (in the dictionaries folder on GitHub).
- A pronunciation word that ends in a full stop (etc., p.m.) no longer swallows the sentence's own full stop.

## 0.2.2
- Windows now shows the right version number (in Installed apps and the program's details) after a Quick update.

## 0.2.1
- Pronunciation: import and export your word list (CSV, JSON or a plain text file).
- Update notices: a dot on Settings, a one-time message, and a Windows notification.

## 0.2.0
- Pronunciation dictionary: tell the voice how to say names, acronyms and abbreviations.
- Numbers, money, percentages, times and years are read as words.
- Speed control (0.85× to 1.2×) without changing the voice's pitch.
- Channel presets: save a voice and its settings, and pick them in one click.
- Transcribe page: turn audio or video into text or subtitles.
- Clean a voice clip taken from a video or song: the music and background are removed.

## 0.1.1
- Every Whisper size for subtitles, and a setting to choose which one is used.

## 0.1.0
- First release.
