from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .config import load_config
from .utils import prefer_ffmpeg_full


def _get_version() -> str:
    try:
        return version("narramotion")
    except PackageNotFoundError:
        return "0.0.0-dev"


def _config_file() -> Path:
    return (
        Path.home()
        / ".config"
        / "narramotion"
        / "config.json"
    )


def _save_gemini_api_key(api_key: str) -> Path:
    config_path = _config_file()

    config_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "gemini_api_key": api_key,
    }

    config_path.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # API key should only be readable/writable by the current user.
    try:
        os.chmod(
            config_path,
            0o600,
        )
    except OSError:
        pass

    return config_path


def run_init() -> None:
    print("Narramotion setup")
    print()

    api_key = getpass.getpass(
        "Gemini API key: "
    ).strip()

    if not api_key:
        raise RuntimeError(
            "Gemini API key cannot be empty."
        )

    config_path = _save_gemini_api_key(
        api_key
    )

    print()
    print("Gemini API key saved.")
    print(f"Config: {config_path}")
    print()
    print("Setup complete.")


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
            "Project directory, project.yaml path, "
            "or 'init'"
        ),
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
        version=f"%(prog)s {_get_version()}",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # ------------------------------------------------------------
    # init
    # ------------------------------------------------------------

    if args.project == "init":
        if (
            args.detect_only
            or args.audio_only
            or args.force
        ):
            parser.error(
                "init cannot be combined with "
                "--detect-only, --audio-only, or --force"
            )

        try:
            run_init()
            return

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

    # ------------------------------------------------------------
    # Normal project processing
    # ------------------------------------------------------------

    if not args.project:
        parser.error(
            "a project directory is required"
        )

    if args.detect_only and args.audio_only:
        parser.error(
            "--detect-only and --audio-only "
            "cannot be used together"
        )

    try:
        # Keep --help and --version fast.
        # FFmpeg and heavy processing modules are initialized
        # only when actual project work begins.
        prefer_ffmpeg_full()

        from .pipeline import (
            detect_only,
            process,
        )

        cfg = load_config(
            Path(args.project)
        )

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