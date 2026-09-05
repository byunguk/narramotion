from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .pipeline import process
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
        help=(
            "Project directory or project.yaml path"
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
        help=(
            "Ignore cached processing results."
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )

    return parser


def main() -> None:
    prefer_ffmpeg_full()
    
    parser = build_parser()
    args = parser.parse_args()

    if not args.project:
        parser.error(
            "a project directory is required"
        )

    try:
        cfg = load_config(
            Path(args.project)
        )

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