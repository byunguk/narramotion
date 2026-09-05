from __future__ import annotations

from pathlib import Path

from .utils import ffprobe_duration, run


AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".flac"}


def audio_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTS)


def trim_audio(
    src: Path,
    dst: Path,
    start_sec: float,
    end_sec: float,
) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)

    start = max(0.0, float(start_sec))
    end = float(end_sec)

    if end <= start:
        raise ValueError(
            f"Invalid trim range for {src.name}: "
            f"start={start:.3f}, end={end:.3f}"
        )

    duration_sec = end - start

    run([
        "ffmpeg",
        "-y",
        "-v", "error",
        "-ss", f"{start:.3f}",
        "-i", str(src),
        "-t", f"{duration_sec:.3f}",
        "-vn",
        "-c:a", "libmp3lame",
        "-q:a", "2",
        str(dst),
    ])


def concat_audio(files: list[Path], dst: Path, work_dir: Path) -> None:
    if not files:
        raise ValueError("No audio files to concatenate")
    work_dir.mkdir(parents=True, exist_ok=True)
    list_file = work_dir / "audio-concat.txt"
    list_file.write_text("\n".join(f"file '{str(p.resolve()).replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'" for p in files), encoding="utf-8")
    dst.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(dst)
    ])


def duration(path: Path) -> float:
    return ffprobe_duration(path)
