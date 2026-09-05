from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from .utils import parse_offset, run

def _load_saved_api_key() -> str | None:
    config_path = (
        Path.home()
        / ".config"
        / "narramotion"
        / "config.json"
    )

    if not config_path.exists():
        return None

    try:
        data = json.loads(
            config_path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return None

    value = data.get("gemini_api_key")

    if not isinstance(value, str):
        return None

    value = value.strip()

    return value or None


def _client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        api_key = _load_saved_api_key()

    if not api_key:
        raise RuntimeError(
            "Gemini API key is not configured. "
            "Run: narramotion init"
        )

    return genai.Client(
        api_key=api_key
    )


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"Gemini did not return JSON: {text[:500]}")
    return json.loads(text[start:end + 1])

def _audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    value = result.stdout.strip()

    if not value:
        raise RuntimeError(
            f"ffprobe returned no duration for {audio_path}"
        )

    return float(value)

def detect_reading_start(audio_path: Path, window_sec: float, model: str) -> dict[str, Any]:
    """Analyze only the beginning of a file and identify where Scripture reading begins."""
    client = _client()
    with tempfile.TemporaryDirectory(prefix="bvm-detect-") as td:
        preview = Path(td) / "preview.mp3"
        run([
            "ffmpeg", "-y", "-v", "error", "-i", str(audio_path),
            "-t", f"{window_sec:.3f}", "-vn", "-c:a", "libmp3lame", "-q:a", "4", str(preview)
        ])
        uploaded = client.files.upload(file=str(preview))
        prompt = """
You are locating the start of the actual Scripture text in a Bible audiobook chapter.

The beginning of the audio may contain any combination of:
- book or chapter announcements
- narrator or reader credits
- "recorded by" statements
- publisher or copyright notices
- website or organization names
- introductions
- other metadata or spoken credits

IMPORTANT:
A book title or chapter announcement is NOT the start of the Scripture text.

For example, audio may sound like:

"Chapter 2 of the Gospel according to St. Matthew.
Recorded by John Smith for ...
Now when Jesus was born in Bethlehem..."

In that example, reading_start_sec must point to:
"Now when Jesus was born in Bethlehem..."

Ignore ALL announcements, credits, recording information, and metadata,
even when they appear AFTER the book/chapter announcement.

Find the timestamp where the first actual verse of Scripture begins.

Use your knowledge of the Bible to distinguish the actual biblical text
from spoken metadata or credits.

Return ONLY JSON with exactly these keys:

{
  "reading_start_sec": number,
  "detected_book": string or null,
  "detected_chapter": integer or null,
  "opening_words": string,
  "confidence": number from 0 to 1,
  "reason": string
}

"opening_words" must contain the first words of the actual Scripture text,
not the chapter announcement or recording credits.

Use seconds from the start of this audio clip.
Do not use markdown.
""".strip()
        response = client.models.generate_content(
            model=model,
            contents=[uploaded, prompt],
            config=types.GenerateContentConfig(temperature=0),
        )
        data = _extract_json(response.text or "")
        data["reading_start_sec"] = float(data["reading_start_sec"])
        data["confidence"] = float(data.get("confidence", 0))
        return data

def detect_reading_end(
    audio_path: Path,
    window_sec: float,
    model: str,
) -> dict[str, Any]:
    client = _client()

    total_duration = _audio_duration(audio_path)
    tail_start = max(0.0, total_duration - window_sec)

    with tempfile.TemporaryDirectory(
        prefix="narramotion-end-detect-"
    ) as td:
        preview = Path(td) / "tail.mp3"

        run([
            "ffmpeg",
            "-y",
            "-v", "error",
            "-ss", f"{tail_start:.3f}",
            "-i", str(audio_path),
            "-t", f"{window_sec:.3f}",
            "-vn",
            "-c:a", "libmp3lame",
            "-q:a", "4",
            str(preview),
        ])

        uploaded = client.files.upload(file=str(preview))

        prompt = """
You are given an audio clip containing the FINAL portion of a narrated Bible reading.

IMPORTANT TIMESTAMP RULE:

The supplied audio clip starts at timestamp 0.000 seconds.

Ignore any timestamp or timing from the original source recording.

All timestamps you return MUST be relative to THIS supplied audio clip.

Therefore:

- the first sound in this supplied clip = 0.000 seconds
- reading_end_sec MUST be >= 0
- reading_end_sec MUST NOT exceed the duration of this supplied clip

Your task is to determine where the actual Scripture reading ends.

The audio may contain spoken closing material after the Scripture, for example:

"End of Chapter 1 to 3"

or:

"End of Chapter 4"

It may also contain other closing announcements, credits, narrator information,
publisher information, website names, copyright information, or metadata.

These closing statements are NOT part of the Scripture.

Find the LAST spoken word that belongs to the actual Scripture text.

Set reading_end_sec to the point immediately AFTER that final Scripture word
and BEFORE the first word of any closing announcement or metadata.

Example:

If this supplied clip contains:

[0:00 ...]
"... grace be with thee. Amen.
End of Chapter 1 to 3."

and "Amen" finishes at 84.2 seconds while "End" begins at 85.0 seconds,

return approximately:

{
  "reading_end_sec": 84.2,
  "closing_words": "grace be with thee. Amen.",
  "following_words": "End of Chapter 1 to 3",
  "confidence": 0.99,
  "reason": "The Scripture reading ends after Amen; the following phrase is a closing announcement."
}

Do NOT return the timestamp where the closing announcement finishes.

Do NOT return a timestamp from the original recording.

Do NOT include "End of..." or any other closing announcement in the Scripture.

If there is silence between the final Scripture word and the closing announcement,
reading_end_sec should be at the END OF THE FINAL SCRIPTURE WORD,
not at the end of the silence.

Return ONLY valid JSON with exactly these keys:

{
  "reading_end_sec": number,
  "closing_words": string,
  "following_words": string,
  "confidence": number,
  "reason": string
}

No markdown.
No code fences.
""".strip()

        response = client.models.generate_content(
            model=model,
            contents=[uploaded, prompt],
            config=types.GenerateContentConfig(
                temperature=0
            ),
        )

        data = _extract_json(response.text or "")

        relative_end = float(data["reading_end_sec"])

        if relative_end < 0 or relative_end > window_sec + 2:
            raise RuntimeError(
                f"Gemini returned invalid end timestamp "
                f"{relative_end:.3f}s for {audio_path.name}"
            )

        absolute_end = tail_start + relative_end

        # Never allow an end timestamp beyond the source file.
        absolute_end = min(
            absolute_end,
            total_duration,
        )

        return {
            "reading_end_sec": absolute_end,
            "relative_end_sec": relative_end,
            "tail_start_sec": tail_start,
            "audio_duration_sec": total_duration,
            "closing_words": data.get("closing_words"),
            "confidence": float(
                data.get("confidence", 0)
            ),
            "reason": data.get("reason"),
        }

def transcribe_words(
    audio_path: Path,
    model: str,
    language_code: str,
) -> tuple[str, list[dict[str, Any]]]:
    client = _client()
    uploaded = client.files.upload(file=str(audio_path))

    cfg = types.GenerateContentConfig(
        audio_transcription_config=types.AudioTranscriptionConfig(
            language_codes=[language_code] if language_code else [],
            word_timestamp=True,
            mode="VERBATIM",
        )
    )

    max_attempts = 10

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[uploaded],
                config=cfg,
            )
            break

        except Exception as exc:
            message = str(exc)

            is_rate_limit = (
                "429" in message
                or "RESOURCE_EXHAUSTED" in message
            )

            if not is_rate_limit:
                raise

            if attempt >= max_attempts:
                raise

            # Gemini usually returns:
            # "Please retry in 6.519218129s."
            match = re.search(
                r"retry in\s+([0-9.]+)s",
                message,
                re.IGNORECASE,
            )

            if match:
                wait_sec = float(match.group(1)) + 2.0
            else:
                # fallback when retry delay cannot be parsed
                wait_sec = 30.0

            print(
                f"Gemini rate limit reached. "
                f"Waiting {wait_sec:.1f}s "
                f"before retry ({attempt}/{max_attempts})..."
            )

            time.sleep(wait_sec)

    else:
        raise RuntimeError(
            f"Gemini transcription failed after {max_attempts} attempts"
        )

    words: list[dict[str, Any]] = []

    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)

        for part in getattr(content, "parts", []) or []:
            transcription = getattr(
                part,
                "audio_transcription",
                None,
            )

            if not transcription:
                continue

            for wi in getattr(transcription, "words", []) or []:
                word = str(
                    getattr(wi, "word", "") or ""
                ).strip()

                if not word:
                    continue

                words.append({
                    "word": word,
                    "start": parse_offset(
                        getattr(wi, "start_offset", 0)
                    ),
                    "end": parse_offset(
                        getattr(wi, "end_offset", 0)
                    ),
                })

    return response.text or "", words
