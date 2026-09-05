from __future__ import annotations

import shutil
from pathlib import Path

from .audio import audio_files, concat_audio, duration, trim_audio
from .config import Config
from .gemini import detect_reading_start, detect_reading_end, transcribe_words
from .subtitles import offset_cues, words_to_cues, write_srt
from .utils import file_fingerprint, load_json, require_binary, require_ffmpeg_subtitles, save_json
from .video import build_music_bed, concat_video_clips, image_files, music_files, mux, render_image_clips


def process(
    cfg: Config,
    *,
    force: bool = False,
    audio_only: bool = False,
) -> Path:
    require_binary("ffmpeg")
    require_binary("ffprobe")
    if not audio_only:
        require_ffmpeg_subtitles()
    cfg.work_dir.mkdir(parents=True, exist_ok=True)

    if not cfg.audio_dir.is_dir():
        raise RuntimeError(
            f"Audio directory not found: {cfg.audio_dir}"
        )

    sources = audio_files(cfg.audio_dir)

    if not sources:
        raise RuntimeError(
            f"No audio files found in {cfg.audio_dir}"
        )

    images: list[Path] = []

    if not audio_only:
        if not cfg.image_dir.is_dir():
            raise RuntimeError(
                f"Image directory not found: {cfg.image_dir}"
            )

        images = image_files(cfg.image_dir)

        if not images:
            raise RuntimeError(
                f"No images found in {cfg.image_dir}"
            )

    trimmed_dir = cfg.work_dir / "trimmed"
    detect_dir = cfg.work_dir / "detections"
    transcript_dir = cfg.work_dir / "transcripts"

    trimmed_dir.mkdir(parents=True, exist_ok=True)
    detect_dir.mkdir(parents=True, exist_ok=True)
    transcript_dir.mkdir(parents=True, exist_ok=True)

    review: list[dict] = []
    all_cues: list[dict] = []
    trimmed_files: list[Path] = []

    timeline_offset = 0.0

    for index, src in enumerate(sources, 1):
        fingerprint = file_fingerprint(src)
        key = f"{index:04d}-{src.stem}-{fingerprint}"

        detection_path = detect_dir / f"{key}.json"

        print(f"[{index}/{len(sources)}] Processing {src.name}...")

        # ------------------------------------------------------------
        # 1. Detect beginning AND end of actual Scripture
        # ------------------------------------------------------------

        if detection_path.exists() and not force:
            detection = load_json(detection_path)

            # Older cache files may contain start-only detection data.
            # Rebuild them so process() always has both boundaries.
            if (
                "reading_start_sec" in detection
                and "reading_end_sec" in detection
            ):
                print("    detection: cached")
            else:
                detection = None
        else:
            detection = None

        if detection is None:
            print("    detecting start...")

            start_detection = detect_reading_start(
                src,
                cfg.detection_window_sec,
                cfg.detection_model,
            )

            print(
                f"    start: "
                f"{float(start_detection['reading_start_sec']):.2f}s"
            )

            print("    detecting end...")

            end_detection = detect_reading_end(
                src,
                cfg.detection_window_sec,
                cfg.detection_model,
            )

            print(
                f"    end: "
                f"{float(end_detection['reading_end_sec']):.2f}s"
            )

            detection = {
                "reading_start_sec": float(
                    start_detection["reading_start_sec"]
                ),
                "reading_end_sec": float(
                    end_detection["reading_end_sec"]
                ),
                "detected_book": start_detection.get(
                    "detected_book"
                ),
                "detected_chapter": start_detection.get(
                    "detected_chapter"
                ),
                "opening_words": start_detection.get(
                    "opening_words"
                ),
                "closing_words": end_detection.get(
                    "closing_words"
                ),
                "start_confidence": float(
                    start_detection.get("confidence", 0)
                ),
                "end_confidence": float(
                    end_detection.get("confidence", 0)
                ),
                "start_reason": start_detection.get(
                    "reason"
                ),
                "end_reason": end_detection.get(
                    "reason"
                ),
            }

            save_json(detection_path, detection)

        # ------------------------------------------------------------
        # 2. Calculate actual trim boundaries
        # ------------------------------------------------------------

        reading_start = float(
            detection["reading_start_sec"]
        )

        reading_end = float(
            detection["reading_end_sec"]
        )

        start = max(
            0.0,
            reading_start - cfg.trim_preroll_sec,
        )

        # Give the final Scripture word a tiny amount of breathing room.
        #
        # IMPORTANT:
        # Don't make this too large because "End of Chapter..."
        # can begin shortly after the Scripture ends.
        end_postroll_sec = 0.20

        source_duration = duration(src)

        end = min(
            source_duration,
            reading_end + end_postroll_sec,
        )

        if end <= start:
            raise RuntimeError(
                f"Invalid reading boundaries for {src.name}: "
                f"start={start:.3f}, end={end:.3f}"
            )

        start_confidence = float(
            detection.get(
                "start_confidence",
                detection.get("confidence", 0),
            )
        )

        end_confidence = float(
            detection.get(
                "end_confidence",
                detection.get("confidence", 0),
            )
        )

        print(
            f"    trim: "
            f"{start:.2f}s -> {end:.2f}s "
            f"({end - start:.2f}s)"
        )

        # ------------------------------------------------------------
        # 3. Add uncertain detection to review report
        # ------------------------------------------------------------

        if (
            start_confidence < cfg.confidence_threshold
            or end_confidence < cfg.confidence_threshold
        ):
            review.append({
                "file": src.name,
                "reading_start_sec": reading_start,
                "reading_end_sec": reading_end,
                "trim_start_sec": start,
                "trim_end_sec": end,
                "start_confidence": start_confidence,
                "end_confidence": end_confidence,
                "opening_words": detection.get(
                    "opening_words"
                ),
                "closing_words": detection.get(
                    "closing_words"
                ),
                "start_reason": detection.get(
                    "start_reason"
                ),
                "end_reason": detection.get(
                    "end_reason"
                ),
            })

        # ------------------------------------------------------------
        # 4. Trim audio
        #
        # Use the fingerprint-based key in the filename.
        # This prevents stale trimmed files from being reused when
        # the source MP3 changes.
        # ------------------------------------------------------------

        trimmed = trimmed_dir / f"{key}.mp3"

        if not trimmed.exists() or force:
            print("    trimming audio...")

            trim_audio(
                src,
                trimmed,
                start,
                end,
            )

        else:
            print("    trim: cached")

        trimmed_files.append(trimmed)

        # ------------------------------------------------------------
        # 5. Gemini transcription
        # ------------------------------------------------------------

        transcript_cache = (
            transcript_dir / f"{key}.json"
        )

        if transcript_cache.exists() and not force:
            payload = load_json(transcript_cache)
            words = payload["words"]

            print("    transcription: cached")

        else:
            print("    transcribing...")

            transcript_text, words = transcribe_words(
                trimmed,
                cfg.transcribe_model,
                cfg.language_code,
            )

            save_json(
                transcript_cache,
                {
                    "text": transcript_text,
                    "words": words,
                },
            )

        # ------------------------------------------------------------
        # 6. Convert word timestamps -> subtitle cues
        # ------------------------------------------------------------

        cues = words_to_cues(
            words,
            cfg.subtitle_max_words,
            cfg.subtitle_max_sec,
        )

        all_cues.extend(
            offset_cues(
                cues,
                timeline_offset,
            )
        )

        trimmed_duration = duration(trimmed)

        timeline_offset += trimmed_duration

        print(
            f"    final duration: "
            f"{trimmed_duration:.2f}s"
        )

    # ------------------------------------------------------------
    # 7. Save review report
    # ------------------------------------------------------------

    review_path = cfg.work_dir / "review-needed.json"

    save_json(
        review_path,
        review,
    )

    # ------------------------------------------------------------
    # 8. Build final SRT
    # ------------------------------------------------------------

    final_srt = cfg.work_dir / "final.srt"

    write_srt(
        all_cues,
        final_srt,
    )

    print(
        f"Subtitles: {final_srt}"
    )

    # ------------------------------------------------------------
    # 9. Concatenate all trimmed narration
    # ------------------------------------------------------------

    narration = cfg.work_dir / "narration.mp3"

    print("Concatenating narration...")

    concat_audio(
        trimmed_files,
        narration,
        cfg.work_dir,
    )

    print(
        f"Narration: {narration}"
    )

    # ------------------------------------------------------------
    # 10. Copy user-facing audio/subtitle outputs
    # ------------------------------------------------------------

    output_dir = cfg.output.parent

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_narration = output_dir / "narration.mp3"
    output_subtitles = output_dir / "subtitles.srt"

    shutil.copy2(
        narration,
        output_narration,
    )

    shutil.copy2(
        final_srt,
        output_subtitles,
    )

    print(
        f"Output narration: {output_narration}"
    )

    print(
        f"Output subtitles: {output_subtitles}"
    )

    # ------------------------------------------------------------
    # 11. Stop here for --audio-only
    # ------------------------------------------------------------

    if audio_only:
        print()
        print("Audio-only processing complete.")
        print(f"Narration: {output_narration}")
        print(f"Subtitles: {output_subtitles}")
        print(f"Review: {review_path}")

        return output_narration

    # ------------------------------------------------------------
    # 12. Video rendering
    # ------------------------------------------------------------

    total_duration = duration(narration)

    clips = render_image_clips(
        images,
        total_duration,
        cfg.work_dir,
        width=cfg.width,
        height=cfg.height,
        fps=cfg.fps,
        per_image=cfg.image_duration_sec,
        overscan=cfg.overscan,
        codec=cfg.video_codec,
        crf=cfg.crf,
        preset=cfg.preset,
    )

    # ------------------------------------------------------------
    # 11. Concatenate rendered image clips
    # ------------------------------------------------------------

    silent_video = (
        cfg.work_dir / "silent-video.mp4"
    )

    concat_video_clips(
        clips,
        silent_video,
        cfg.work_dir,
    )

    # ------------------------------------------------------------
    # 12. Background music
    # ------------------------------------------------------------

    music = (
        music_files(cfg.music_dir)
        if cfg.music_dir.exists()
        else []
    )

    music_bed = build_music_bed(
        music,
        total_duration,
        cfg.work_dir / "music-bed.m4a",
        cfg.work_dir,
    )

    # ------------------------------------------------------------
    # 13. Final mux + subtitle burn-in
    # ------------------------------------------------------------

    mux(
        silent_video,
        narration,
        final_srt,
        cfg.output,
        music=music_bed,
        music_volume=cfg.music_volume,
        narration_volume=cfg.narration_volume,
        video_codec=cfg.video_codec,
        crf=cfg.crf,
        preset=cfg.preset,
    )

    return cfg.output

def detect_only(cfg: Config, *, force: bool = False) -> Path:
    require_binary("ffmpeg")
    require_binary("ffprobe")
    cfg.work_dir.mkdir(parents=True, exist_ok=True)

    # Validate required inputs before doing expensive AI/audio work.
    if not cfg.audio_dir.is_dir():
        raise RuntimeError(
            f"Audio directory not found: {cfg.audio_dir}"
        )

    sources = audio_files(cfg.audio_dir)

    if not sources:
        raise RuntimeError(
            f"No audio files found in {cfg.audio_dir}"
        )

    detect_dir = cfg.work_dir / "detections"
    detect_dir.mkdir(parents=True, exist_ok=True)

    review: list[dict] = []
    summary: list[dict] = []

    for index, src in enumerate(sources, 1):
        key = f"{index:04d}-{src.stem}-{file_fingerprint(src)}"
        detection_path = detect_dir / f"{key}.json"

        print(f"[{index}/{len(sources)}] Detecting {src.name}...")

        if detection_path.exists() and not force:
            detection = load_json(detection_path)

            # Older cache files may contain start-only detection data.
            # Rebuild them so --detect-only always reports both boundaries.
            if (
                "reading_start_sec" in detection
                and "reading_end_sec" in detection
            ):
                cached = True
            else:
                detection = None
        else:
            detection = None

        if detection is None:
            print("    detecting start...")
            start_detection = detect_reading_start(
                src,
                cfg.detection_window_sec,
                cfg.detection_model,
            )

            print("    detecting end...")
            end_detection = detect_reading_end(
                src,
                cfg.detection_window_sec,
                cfg.detection_model,
            )

            detection = {
                "reading_start_sec": float(
                    start_detection["reading_start_sec"]
                ),
                "reading_end_sec": float(
                    end_detection["reading_end_sec"]
                ),
                "detected_book": start_detection.get("detected_book"),
                "detected_chapter": start_detection.get("detected_chapter"),
                "opening_words": start_detection.get("opening_words"),
                "closing_words": end_detection.get("closing_words"),
                "start_confidence": float(
                    start_detection.get("confidence", 0)
                ),
                "end_confidence": float(
                    end_detection.get("confidence", 0)
                ),
                "start_reason": start_detection.get("reason"),
                "end_reason": end_detection.get("reason"),
            }

            save_json(detection_path, detection)
            cached = False

        reading_start = float(detection["reading_start_sec"])
        reading_end = float(detection["reading_end_sec"])

        start_confidence = float(
            detection.get(
                "start_confidence",
                detection.get("confidence", 0),
            )
        )
        end_confidence = float(
            detection.get(
                "end_confidence",
                detection.get("confidence", 0),
            )
        )

        source_duration = duration(src)
        trim_start = max(
            0.0,
            reading_start - cfg.trim_preroll_sec,
        )
        trim_end = min(
            source_duration,
            reading_end + 0.20,
        )

        item = {
            "file": src.name,
            "reading_start_sec": reading_start,
            "reading_end_sec": reading_end,
            "trim_start_sec": trim_start,
            "trim_end_sec": trim_end,
            "detected_book": detection.get("detected_book"),
            "detected_chapter": detection.get("detected_chapter"),
            "opening_words": detection.get("opening_words"),
            "closing_words": detection.get("closing_words"),
            "start_confidence": start_confidence,
            "end_confidence": end_confidence,
            "start_reason": detection.get("start_reason"),
            "end_reason": detection.get("end_reason"),
            "cached": cached,
        }

        summary.append(item)

        if (
            start_confidence < cfg.confidence_threshold
            or end_confidence < cfg.confidence_threshold
        ):
            review.append(item)

        book = detection.get("detected_book") or "?"
        chapter = detection.get("detected_chapter") or "?"
        cache_label = " cached" if cached else ""

        print(
            f"    {book} {chapter} | "
            f"start={reading_start:.2f}s | "
            f"end={reading_end:.2f}s | "
            f"trim={trim_start:.2f}s->{trim_end:.2f}s | "
            f"confidence={start_confidence:.2f}/{end_confidence:.2f}"
            f"{cache_label}"
        )

    summary_path = cfg.work_dir / "detections-summary.json"
    review_path = cfg.work_dir / "review-needed.json"

    save_json(summary_path, summary)
    save_json(review_path, review)

    print()
    print(f"Detection summary: {summary_path}")
    print(f"Review needed: {len(review)} file(s)")

    return summary_path
