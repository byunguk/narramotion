from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


def run(cmd: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    return (result.stdout or "").strip()


def require_binary(name: str) -> None:
    try:
        subprocess.run([name, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"Required executable not found: {name}") from exc

def prefer_ffmpeg_full() -> None:
    import os
    import shutil
    import subprocess
    from pathlib import Path

    # Homebrew installation available?
    brew = shutil.which("brew")

    if not brew:
        return

    try:
        result = subprocess.run(
            [brew, "--prefix", "ffmpeg-full"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return

    prefix = result.stdout.strip()

    if not prefix:
        return

    bin_dir = Path(prefix) / "bin"
    ffmpeg = bin_dir / "ffmpeg"
    ffprobe = bin_dir / "ffprobe"

    if not ffmpeg.exists() or not ffprobe.exists():
        return

    current_path = os.environ.get("PATH", "")

    os.environ["PATH"] = (
        f"{bin_dir}{os.pathsep}{current_path}"
    )

def require_ffmpeg_subtitles() -> None:
    import subprocess

    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-filters",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    if " subtitles " not in result.stdout:
        raise RuntimeError(
            "FFmpeg does not include the subtitles filter. "
            "Narramotion requires ffmpeg-full with libass support."
        )


def ffprobe_duration(path: Path) -> float:
    out = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ], capture=True)
    return float(out)


def file_fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    stat = path.stat()
    h.update(str(path.resolve()).encode())
    h.update(str(stat.st_size).encode())
    h.update(str(stat.st_mtime_ns).encode())
    with path.open("rb") as f:
        h.update(f.read(1024 * 1024))
    return h.hexdigest()[:20]


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_offset(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)s", s)
    if m:
        return float(m.group(1))
    try:
        return float(s)
    except ValueError as exc:
        raise ValueError(f"Unsupported timestamp offset: {value!r}") from exc


def srt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    ms = round(seconds * 1000)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"