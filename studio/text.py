"""Turning a script into segments the engine speaks one at a time.

A script is split at paragraphs (blank lines) and [pause] tags, then each paragraph's sentences are packed into
segments of up to `max_chars` characters. Segments never cross a paragraph or a pause, so the silence between
them is always ours (and the right length), and a segment can be regenerated on its own.

Pause tags: [pause] (1 second), [pause 2], [pause 2s], [pause 1.5 s], [pause 500ms].
"""
import re

PAUSE_TAG = re.compile(r"\[\s*pause(?:\s+(\d+(?:[.,]\d+)?)\s*(ms|s|sec|seconds?)?)?\s*\]", re.I)
SENTENCE_END = re.compile(r"(?<=[.!?…。！？])[\"'”’»)\]]*\s+")
CLAUSE_END = re.compile(r"(?<=[,;:—–])\s+")
MIN_SEGMENT = 40  # characters: shorter sentences are joined to their neighbour when they fit


def _pause_seconds(m: re.Match) -> float:
    if not m.group(1):
        return 1.0
    value = float(m.group(1).replace(",", "."))
    return value / 1000 if (m.group(2) or "").lower() == "ms" else value


def clean(text: str) -> str:
    """Normalise spacing and characters the engine reads badly."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*\n\s*", "\n\n", text)  # paragraph breaks
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)  # single line breaks are just wrapping
    return text.strip()


def _split_long(sentence: str, limit: int) -> list[str]:
    """A sentence longer than the limit: split at commas/semicolons, else between words."""
    if len(sentence) <= limit:
        return [sentence]
    out, cur = [], ""
    for part in CLAUSE_END.split(sentence):
        if len(part) > limit:  # no punctuation to split at: cut between words
            words = part.split(" ")
            for w in words:
                if cur and len(cur) + 1 + len(w) > limit:
                    out.append(cur)
                    cur = w
                else:
                    cur = f"{cur} {w}".strip()
            continue
        if cur and len(cur) + 1 + len(part) > limit:
            out.append(cur)
            cur = part
        else:
            cur = f"{cur} {part}".strip()
    if cur:
        out.append(cur)
    return out


def sentences(paragraph: str) -> list[str]:
    return [s.strip() for s in SENTENCE_END.split(paragraph) if s.strip()]


def _pack(paragraph: str, limit: int) -> list[str]:
    """Pack a paragraph's sentences into chunks of at most `limit` characters, balanced in size."""
    parts = [p for s in sentences(paragraph) for p in _split_long(s, limit)]
    if not parts:
        return []
    total = sum(len(p) + 1 for p in parts)
    # Aim for evenly sized chunks rather than full ones followed by a stub.
    target = min(limit, max(MIN_SEGMENT, total / max(1, -(-total // limit))))
    out, cur = [], ""
    for p in parts:
        if cur and (len(cur) + 1 + len(p) > limit or len(cur) >= target):
            out.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        if out and len(cur) < MIN_SEGMENT and len(out[-1]) + 1 + len(cur) <= limit:
            out[-1] = f"{out[-1]} {cur}"
        else:
            out.append(cur)
    return out


def split(text: str, *, max_chars: int = 600, pause_segment: float = 0.25,
          pause_paragraph: float = 0.7) -> list[dict]:
    """[{"text", "pause_after" (seconds of silence after it), "paragraph" (0-based)}]"""
    text = clean(text)
    segments: list[dict] = []
    paragraph = 0
    for block in text.split("\n\n"):
        start, ended_by_tag = len(segments), False
        pos = 0
        for m in [*PAUSE_TAG.finditer(block), None]:
            chunk = block[pos:m.start() if m else len(block)].strip()
            for t in _pack(chunk, max_chars):
                segments.append({"text": t, "pause_after": pause_segment, "paragraph": paragraph})
            ended_by_tag = bool(m) and not block[m.end():].strip()
            if m:
                if len(segments) > start:  # a tag before any text in this paragraph has nothing to follow
                    segments[-1]["pause_after"] = _pause_seconds(m)
                pos = m.end()
        if len(segments) > start:
            if not ended_by_tag:
                segments[-1]["pause_after"] = pause_paragraph
            paragraph += 1
    if segments:
        segments[-1]["pause_after"] = 0.0
    return segments


def title_of(text: str, words: int = 6) -> str:
    """A short title from the start of a script (for file names and lists)."""
    first = re.sub(PAUSE_TAG, " ", clean(text)).split("\n")[0]
    w = re.findall(r"[\w'’-]+", first)
    return " ".join(w[:words]) or "Untitled"


def estimate_seconds(text: str) -> float:
    """Rough speaking time: about 14 characters per second across our languages."""
    return len(re.sub(PAUSE_TAG, "", text)) / 14.0
