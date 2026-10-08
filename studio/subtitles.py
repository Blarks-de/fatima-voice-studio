"""SRT subtitles for a finished script, and transcripts (whisper.cpp).

The cue text always comes from the script itself (so names and spelling are yours); Whisper only supplies the
timing. Script words are matched to the words Whisper heard, and words it heard differently ("42" for
"forty-two") get times interpolated from their neighbours. Without a Whisper model, cues are timed from the
known segment boundaries, spreading each segment's time over its text.
"""
import difflib
import json
import logging
import os
import re
import subprocess
import unicodedata
import uuid
from pathlib import Path

from . import config, text as textmod

log = logging.getLogger("studio.subtitles")

MAX_LINE = 42      # characters per subtitle line
MAX_CUE_CHARS = 84  # two lines
MAX_CUE_SECONDS = 7.0
MIN_CUE_SECONDS = 0.8


class WhisperError(Exception):
    pass


def _norm(word: str) -> str:
    w = unicodedata.normalize("NFKC", word.lower()).replace("’", "'")
    return re.sub(r"[^\w']", "", w)


def whisper_available(cfg: dict) -> bool:
    return bool(config.subtitles_model(cfg)) and (config.whisper_dir() / config.WHISPER_EXE).exists()


def run_whisper(cfg: dict, wav: Path, language: str | None, model: str | None = None) -> dict:
    """Run whisper-cli; returns its full JSON (segments with token timings)."""
    model = model or config.subtitles_model(cfg)
    exe = config.whisper_dir() / config.WHISPER_EXE
    if not model or not exe.exists():
        raise WhisperError("No subtitles model installed. Download Whisper on the Models page.")
    tmp = config.DATA / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    stem = tmp / f"w{uuid.uuid4().hex[:10]}"
    threads = max(2, min(16, (os.cpu_count() or 4) - 2))
    args = [str(exe), "-m", str(Path(cfg["models_dir"]).resolve() / config.MODELS[model]["files"][0]),
            "-f", str(Path(wav).resolve()), "-l", language or "auto", "-t", str(threads), "-ojf", "-of", str(stem), "-np"]
    try:  # the limit grows with the audio (large models on the CPU run near real time); a stuck run can't block the queue
        import soundfile as sf
        seconds = sf.info(str(wav)).duration
    except Exception:
        seconds = 600
    try:
        p = subprocess.run(args, cwd=exe.parent, capture_output=True, timeout=120 + seconds * 2,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        stem.with_suffix(".json").unlink(missing_ok=True)
        raise WhisperError("Whisper took far longer than this audio needs and was stopped.")
    out = stem.with_suffix(".json")
    if p.returncode or not out.exists():
        err = (p.stderr or p.stdout or b"").decode("utf-8", "replace").strip().splitlines()
        raise WhisperError("Whisper failed: " + (err[-1] if err else f"code {p.returncode}"))
    try:
        return json.loads(out.read_text(encoding="utf-8", errors="replace"))
    finally:
        out.unlink(missing_ok=True)


def whisper_words(result: dict) -> list[tuple[str, float, float]]:
    """Words with start/end seconds, built from Whisper's tokens (a token starting with a space starts a word)."""
    words: list[list] = []
    for seg in result.get("transcription", []):
        for tok in seg.get("tokens", []):
            t = tok.get("text", "")
            if t.startswith("[_") or not t.strip():
                continue
            start, end = tok["offsets"]["from"] / 1000, tok["offsets"]["to"] / 1000
            if t.startswith(" ") or not words:
                words.append([t.strip(), start, end])
            else:
                words[-1][0] += t
                words[-1][2] = end
    return [(w, s, e) for w, s, e in words if _norm(w)]


def transcript(result: dict) -> str:
    return " ".join(seg.get("text", "").strip() for seg in result.get("transcription", [])).strip()


# ---- cues ------------------------------------------------------------------------

def _script_units(script: str) -> list[list[str]]:
    """The script as subtitle-sized pieces of words: sentences, split further when too long."""
    units = []
    clean = textmod.PAUSE_TAG.sub(" ", textmod.clean(script))
    for paragraph in clean.split("\n\n"):
        for sentence in textmod.sentences(paragraph):
            words = sentence.split()
            if len(sentence) <= MAX_CUE_CHARS:
                units.append(words)
                continue
            # Split long sentences at commas where possible, else between words, into <= MAX_CUE_CHARS pieces.
            cur: list[str] = []
            for w in words:
                if cur and len(" ".join(cur + [w])) > MAX_CUE_CHARS:
                    units.append(cur)
                    cur = []
                cur.append(w)
                if re.search(r"[,;:]$", w) and len(" ".join(cur)) > MAX_CUE_CHARS * 0.45:
                    units.append(cur)
                    cur = []
            if cur:
                units.append(cur)
    return [u for u in units if u]


def _word_times(script_words: list[str], heard: list[tuple[str, float, float]]) -> list[tuple[float, float]]:
    """Time for every script word: matched to Whisper's words, gaps interpolated."""
    a = [_norm(w) for w in script_words]
    b = [_norm(w) for w, _, _ in heard]
    times: list[tuple[float, float] | None] = [None] * len(a)
    for block in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(block.size):
            _, s, e = heard[block.b + k]
            times[block.a + k] = (s, e)
    # Interpolate unmatched runs between known neighbours, in proportion to their characters.
    i = 0
    total_end = heard[-1][2] if heard else 0.0
    while i < len(a):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(a) and times[j] is None:
            j += 1
        t0 = times[i - 1][1] if i > 0 else 0.0
        t1 = times[j][0] if j < len(a) else total_end
        if t1 < t0:
            t1 = t0
        chars = [max(1, len(script_words[k])) for k in range(i, j)]
        span, acc = t1 - t0, 0
        for k, c in zip(range(i, j), chars):
            s = t0 + span * acc / sum(chars)
            acc += c
            times[k] = (s, t0 + span * acc / sum(chars))
        i = j
    return [t for t in times]  # type: ignore[misc]


def _wrap(words: list[str]) -> str:
    text = " ".join(words)
    if len(text) <= MAX_LINE:
        return text
    # Two balanced lines, broken between words.
    best, best_score = text, 1e9
    for k in range(1, len(words)):
        l1, l2 = " ".join(words[:k]), " ".join(words[k:])
        if len(l1) <= MAX_LINE + 6 and len(l2) <= MAX_LINE + 6:
            score = abs(len(l1) - len(l2))
            if score < best_score:
                best, best_score = f"{l1}\n{l2}", score
    return best


def build_cues(units: list[list[str]], times: list[tuple[float, float]], track_end: float) -> list[tuple[float, float, str]]:
    cues, k = [], 0
    for words in units:
        span = times[k:k + len(words)]
        k += len(words)
        start, end = span[0][0], span[-1][1]
        # Too long on screen: split the unit in two at the middle word.
        if end - start > MAX_CUE_SECONDS and len(words) > 3:
            mid = len(words) // 2
            cues.append([start, span[mid - 1][1], words[:mid]])
            cues.append([span[mid][0], end, words[mid:]])
        else:
            cues.append([start, end, words])
    for i, c in enumerate(cues):  # minimum display time, never overlapping the next cue
        nxt = cues[i + 1][0] if i + 1 < len(cues) else track_end
        if c[1] - c[0] < MIN_CUE_SECONDS:
            c[1] = min(c[0] + MIN_CUE_SECONDS, max(nxt - 0.05, c[1]))
        c[1] = min(c[1], nxt - 0.02) if i + 1 < len(cues) else min(c[1] + 0.2, track_end)
    return [(max(0.0, s), max(s, e), _wrap(w)) for s, e, w in cues]


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: list[tuple[float, float, str]]) -> str:
    return "".join(f"{i}\n{_ts(s)} --> {_ts(e)}\n{t}\n\n" for i, (s, e, t) in enumerate(cues, 1))


def from_whisper(script: str, heard: list[tuple[str, float, float]], track_end: float) -> str:
    units = _script_units(script)
    words = [w for u in units for w in u]
    if not words:
        return ""
    if not heard:
        raise WhisperError("Whisper heard no speech in the audio.")
    return to_srt(build_cues(units, _word_times(words, heard), track_end))


def from_segments(segments: list[tuple[str, float, float]], track_end: float) -> str:
    """No Whisper: time each segment's words by spreading the segment's (start, end) over its characters."""
    units_all, times_all = [], []
    for text, start, end in segments:
        units = _script_units(text)
        words = [w for u in units for w in u]
        chars = [len(w) + 1 for w in words]
        total, acc = sum(chars) or 1, 0
        for c in chars:
            s = start + (end - start) * acc / total
            acc += c
            times_all.append((s, start + (end - start) * acc / total))
        units_all += units
    return to_srt(build_cues(units_all, times_all, track_end)) if units_all else ""


def match_rate(script: str, heard: list[tuple[str, float, float]]) -> float:
    """Share of script words Whisper heard the same way: a quick check that the audio says the script."""
    a = [_norm(w) for w in textmod.PAUSE_TAG.sub(" ", script).split() if _norm(w)]
    b = [_norm(w) for w, _, _ in heard]
    if not a:
        return 1.0
    matched = sum(m.size for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return matched / len(a)
