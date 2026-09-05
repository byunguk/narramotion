from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .utils import prefer_ffmpeg_full


VERSION = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="narramotion",
        description=(
            "Create narrated slideshow videos "
            "from audio, images, and music."
        ),
    )

    parser.add_argument(
        "project",
        nargs="?",
        help="Project directory or project.yaml path",
    )

    parser.add_argument(
        "--detect-only",
        action="store_true",
        help=(
            "Detect narration content boundaries only, "
            "without trimming, transcription, or rendering."
        ),
    )

    parser.add_argument(
        "--audio-only",
        action="store_true",
        help=(
            "Process narration and subtitles "
            "without rendering video."
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cached processing results.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.project:
        parser.error("a project directory is required")

    if args.detect_only and args.audio_only:
        parser.error(
            "--detect-only and --audio-only cannot be used together"
        )

    try:
        # Do not initialize FFmpeg or import the heavy processing
        # pipeline for --help / --version.
        prefer_ffmpeg_full()

        from .pipeline import detect_only, process

        cfg = load_config(Path(args.project))

        if args.detect_only:
            output = detect_only(
                cfg,
                force=args.force,
            )
        else:
            output = process(
                cfg,
                force=args.force,
                audio_only=args.audio_only,
            )

        print()
        print(f"Done: {output}")

    except KeyboardInterrupt:
        print(
            "\nCancelled.",
            file=sys.stderr,
        )
        raise SystemExit(130)

    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()