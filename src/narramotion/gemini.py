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
    """
    Analyze only the end portion of an audio file and locate where the
    actual narration/scripture ends.

    Gemini timestamps are relative to the tail preview clip.
    This function converts them back to absolute timestamps in the
    original audio file.
    """

    client = _client()

    # ------------------------------------------------------------
    # 1. Get original audio duration
    # ------------------------------------------------------------

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    output = result.stdout.strip()

    if not output:
        raise RuntimeError(
            f"Could not determine duration of {audio_path.name}"
        )

    total_duration = float(output)

    # ------------------------------------------------------------
    # 2. Calculate tail preview range
    # ------------------------------------------------------------

    preview_duration = min(
        float(window_sec),
        total_duration,
    )

    tail_start = max(
        0.0,
        total_duration - preview_duration,
    )

    # ------------------------------------------------------------
    # 3. Extract tail preview
    # ------------------------------------------------------------

    with tempfile.TemporaryDirectory(
        prefix="narramotion-end-"
    ) as td:
        preview = Path(td) / "tail.mp3"

        run([
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-ss",
            f"{tail_start:.3f}",
            "-i",
            str(audio_path),
            "-t",
            f"{preview_duration:.3f}",
            "-vn",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "4",
            str(preview),
        ])

        uploaded = client.files.upload(
            file=str(preview)
        )

        # --------------------------------------------------------
        # 4. Ask Gemini for a timestamp RELATIVE TO THIS CLIP
        # --------------------------------------------------------

        prompt = f"""
You are analyzing ONLY the final {preview_duration:.3f} seconds of a narration audio file.

IMPORTANT TIMESTAMP RULE:

The audio clip provided to you starts at 0.000 seconds.

ALL timestamps you return MUST be relative to THIS PROVIDED CLIP.

Do NOT return a timestamp from the original full audio file.

Your valid timestamp range is:

0.000 to {preview_duration:.3f} seconds

The end of the audio may contain spoken material such as:

- "End of Chapter 1"
- "End of Chapter 1 to 3"
- chapter announcements
- narrator or reader credits
- recording credits
- publisher information
- copyright notices
- website or organization names
- closing metadata
- other non-narrative closing material

Your task is to locate the END OF THE ACTUAL NARRATION CONTENT.

For Bible audiobook material, identify the point immediately after the
final spoken word of the actual Scripture text and BEFORE any closing
announcement such as "End of Chapter".

For example:

"... Grace be with you. Amen.
End of Chapter 1."

The returned timestamp should point immediately after "Amen" and before
"End of Chapter 1".

If there is no spoken closing metadata, return the end of the actual
narration.

Return ONLY JSON with exactly these keys:

{{
  "reading_end_sec": number,
  "closing_words": string,
  "confidence": number from 0 to 1,
  "reason": string
}}

"reading_end_sec" MUST be measured from the beginning of THIS PROVIDED
CLIP, where the clip begins at 0.000 seconds.

Do not use markdown.
""".strip()

        response = client.models.generate_content(
            model=model,
            contents=[
                uploaded,
                prompt,
            ],
            config=types.GenerateContentConfig(
                temperature=0,
            ),
        )

        data = _extract_json(
            response.text or ""
        )

    # ------------------------------------------------------------
    # 5. Read Gemini's CLIP-RELATIVE timestamp
    # ------------------------------------------------------------

    relative_end = float(
        data["reading_end_sec"]
    )

    # Small tolerance for model rounding.
    tolerance = 1.0

    if (
        relative_end < 0
        or relative_end > preview_duration + tolerance
    ):
        raise RuntimeError(
            f"Gemini returned invalid end timestamp "
            f"{relative_end:.3f}s for {audio_path.name}. "
            f"Tail preview duration is "
            f"{preview_duration:.3f}s."
        )

    # Clamp tiny rounding overshoot.
    relative_end = min(
        relative_end,
        preview_duration,
    )

    # ------------------------------------------------------------
    # 6. Convert preview-relative time -> original-file time
    # ------------------------------------------------------------

    absolute_end = (
        tail_start
        + relative_end
    )

    absolute_end = min(
        absolute_end,
        total_duration,
    )

    # ------------------------------------------------------------
    # 7. Return ORIGINAL AUDIO timestamp
    # ------------------------------------------------------------

    return {
        "reading_end_sec": absolute_end,
        "closing_words": data.get(
            "closing_words",
            "",
        ),
        "confidence": float(
            data.get(
                "confidence",
                0,
            )
        ),
        "reason": data.get(
            "reason",
            "",
        ),

        # Helpful debugging metadata
        "tail_start_sec": tail_start,
        "relative_end_sec": relative_end,
        "source_duration_sec": total_duration,
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
