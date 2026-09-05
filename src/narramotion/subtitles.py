from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import srt_time


def words_to_cues(words: list[dict[str, Any]], max_words: int = 9, max_sec: float = 4.0) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        text = " ".join(w["word"] for w in current)
        cues.append({"start": current[0]["start"], "end": current[-1]["end"], "text": text})
        current = []

    for w in words:
        if current and (len(current) >= max_words or w["end"] - current[0]["start"] > max_sec):
            flush()
        current.append(w)
        if w["word"].endswith((".", "?", "!", ";", ":")) and len(current) >= 3:
            flush()
    flush()
    return cues


def write_srt(cues: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    for idx, cue in enumerate(cues, 1):
        blocks.append(
            f"{idx}\n{srt_time(float(cue['start']))} --> {srt_time(float(cue['end']))}\n{cue['text']}"
        )
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def offset_cues(cues: list[dict[str, Any]], offset: float) -> list[dict[str, Any]]:
    return [
        {"start": float(c["start"]) + offset, "end": float(c["end"]) + offset, "text": c["text"]}
        for c in cues
    ]
