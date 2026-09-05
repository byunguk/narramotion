from __future__ import annotations

import math
from pathlib import Path

from .utils import run

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MUSIC_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".flac"}


def image_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def music_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in MUSIC_EXTS)


def _motion_filter(width: int, height: int, fps: int, duration: float, overscan: float, pattern: int) -> str:
    # Low-memory Ken Burns alternative: fixed small overscan + moving crop. No zoompan.
    ow = max(width + 2, int(round(width * overscan / 2) * 2))
    oh = max(height + 2, int(round(height * overscan / 2) * 2))
    p = "min(max(t/{:.6f},0),1)".format(max(duration, 0.001))
    ease = f"({p})*({p})*(3-2*({p}))"
    dx = "(in_w-out_w)"
    dy = "(in_h-out_h)"
    patterns = [
        (f"{dx}*{ease}", f"{dy}/2"),
        (f"{dx}*(1-{ease})", f"{dy}/2"),
        (f"{dx}/2", f"{dy}*{ease}"),
        (f"{dx}/2", f"{dy}*(1-{ease})"),
        (f"{dx}*{ease}", f"{dy}*{ease}"),
        (f"{dx}*(1-{ease})", f"{dy}*{ease}"),
    ]
    x, y = patterns[pattern % len(patterns)]
    return (
        f"scale={ow}:{oh}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}:x='{x}':y='{y}',fps={fps},format=yuv420p"
    )


def render_image_clips(images: list[Path], total_duration: float, work_dir: Path, *, width: int, height: int, fps: int, per_image: float, overscan: float, codec: str, crf: int, preset: str) -> list[Path]:
    if not images:
        raise ValueError("No images found")
    clips_dir = work_dir / "image-clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    count = math.ceil(total_duration / per_image)
    clips: list[Path] = []
    for i in range(count):
        remaining = total_duration - i * per_image
        dur = min(per_image, remaining)
        image = images[i % len(images)]
        clip = clips_dir / f"clip-{i:05d}.mp4"
        vf = _motion_filter(width, height, fps, dur, overscan, i)
        run([
            "ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(image),
            "-t", f"{dur:.3f}", "-vf", vf,
            "-an", "-c:v", codec, "-crf", str(crf), "-preset", preset,
            "-pix_fmt", "yuv420p", str(clip)
        ])
        clips.append(clip)
    return clips


def concat_video_clips(clips: list[Path], dst: Path, work_dir: Path) -> None:
    list_file = work_dir / "video-concat.txt"
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in clips), encoding="utf-8")
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(dst)])


def build_music_bed(music: list[Path], total_duration: float, dst: Path, work_dir: Path) -> Path | None:
    if not music:
        return None
    # Repeats tracks sequentially until they exceed narration length, then trims.
    concat_list = work_dir / "music-concat.txt"
    entries = []
    # Repeating the full set 100x is intentionally simple; ffmpeg stops at -t.
    for _ in range(100):
        for p in music:
            entries.append(f"file '{p.resolve()}'")
    concat_list.write_text("\n".join(entries), encoding="utf-8")
    dst.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-t", f"{total_duration:.3f}", "-vn", "-c:a", "aac", "-b:a", "192k", str(dst)
    ])
    return dst


def mux(video: Path, narration: Path, subtitles: Path, output: Path, *, music: Path | None, music_volume: float, narration_volume: float, video_codec: str, crf: int, preset: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    sub = (
        str(subtitles.resolve())
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
    )

    vf = f"subtitles=filename='{sub}'"
    if music:
        cmd = [
            "ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(narration), "-i", str(music),
            "-filter_complex",
            f"[1:a]volume={narration_volume}[n];[2:a]volume={music_volume}[m];[n][m]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v", "-map", "[a]", "-vf", vf,
            "-c:v", video_codec, "-crf", str(crf), "-preset", preset,
            "-c:a", "aac", "-b:a", "192k", "-shortest", str(output)
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(narration),
            "-map", "0:v", "-map", "1:a", "-vf", vf,
            "-c:v", video_codec, "-crf", str(crf), "-preset", preset,
            "-c:a", "aac", "-b:a", "192k", "-shortest", str(output)
        ]
    run(cmd)
