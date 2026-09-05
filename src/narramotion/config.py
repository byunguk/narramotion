from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


# ------------------------------------------------------------
# Built-in defaults
# ------------------------------------------------------------

DEFAULT_CONFIG: dict[str, Any] = {
    "dirs": {
        "audio": "./audio",
        "images": "./images",
        "music": "./music",
        "work": "./.narramotion",
        "output": "./output/final.mp4",
    },

    "audio": {
        "detection_window_sec": 90,
        "detection_model": "gemini-3.7-flash",
        "transcribe_model": "gemini-3.5-transcribe",
        "language_code": "en-US",
        "confidence_threshold": 0.90,
        "trim_preroll_sec": 0.30,
        "volume": 1.0,
    },

    "subtitles": {
        "max_words": 9,
        "max_sec": 4.0,
    },

    "images": {
        "duration_sec": 10,
        "overscan": 1.06,
        "transition_sec": 0.0,
    },

    "music": {
        "volume": 0.10,
    },

    "video": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "codec": "libx264",
        "crf": 20,
        "preset": "medium",
    },
}


# ------------------------------------------------------------
# Config object
# ------------------------------------------------------------

@dataclass(frozen=True)
class Config:
    project_dir: Path

    audio_dir: Path
    image_dir: Path
    music_dir: Path
    work_dir: Path
    output: Path

    detection_window_sec: float
    detection_model: str
    transcribe_model: str
    language_code: str
    confidence_threshold: float
    trim_preroll_sec: float
    narration_volume: float

    subtitle_max_words: int
    subtitle_max_sec: float

    image_duration_sec: float
    overscan: float
    transition_sec: float

    music_volume: float

    width: int
    height: int
    fps: int
    video_codec: str
    crf: int
    preset: str


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _deep_merge(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    """
    Recursively merge override into base.

    Example:

    base:
        images:
            duration_sec: 10
            overscan: 1.06

    override:
        images:
            duration_sec: 15

    result:
        images:
            duration_sec: 15
            overscan: 1.06
    """

    result: dict[str, Any] = {}

    for key, value in base.items():
        if isinstance(value, dict):
            result[key] = _deep_merge(
                value,
                {},
            )
        else:
            result[key] = value

    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(
                result[key],
                value,
            )
        else:
            result[key] = value

    return result


def _resolve_path(
    project_dir: Path,
    value: str,
) -> Path:
    """
    Resolve paths relative to the project directory.

    Absolute paths are preserved.
    """

    path = Path(value).expanduser()

    if path.is_absolute():
        return path

    return (project_dir / path).resolve()


# ------------------------------------------------------------
# Config loader
# ------------------------------------------------------------

def load_config(
    project_or_config: str | Path,
) -> Config:
    """
    Load Narramotion configuration.

    Supported inputs:

        narramotion projects/1timothy

    or legacy:

        narramotion projects/1timothy/project.yaml

    Behavior:

    1. Start with built-in defaults.
    2. If project.yaml exists, merge its values.
    3. Missing values continue using defaults.
    """

    input_path = Path(
        project_or_config
    ).expanduser().resolve()

    # --------------------------------------------------------
    # Determine project directory and optional config file
    # --------------------------------------------------------

    if input_path.is_file():
        # Legacy:
        #
        # narramotion project/project.yaml

        config_path = input_path
        project_dir = input_path.parent

    elif (
        input_path.suffix.lower()
        in {".yaml", ".yml"}
        and not input_path.exists()
    ):
        # User explicitly supplied a YAML path,
        # but it does not exist.
        #
        # Do not silently interpret this as a project directory.

        raise FileNotFoundError(
            f"Config file not found: {input_path}"
        )

    else:
        # Preferred:
        #
        # narramotion project/

        project_dir = input_path

        yaml_path = (
            project_dir / "project.yaml"
        )

        yml_path = (
            project_dir / "project.yml"
        )

        if yaml_path.exists():
            config_path = yaml_path

        elif yml_path.exists():
            config_path = yml_path

        else:
            config_path = None

    # --------------------------------------------------------
    # Project directory must exist
    # --------------------------------------------------------

    if not project_dir.exists():
        raise FileNotFoundError(
            f"Project directory not found: "
            f"{project_dir}"
        )

    if not project_dir.is_dir():
        raise NotADirectoryError(
            f"Project path is not a directory: "
            f"{project_dir}"
        )

    # --------------------------------------------------------
    # Load optional YAML overrides
    # --------------------------------------------------------

    override: dict[str, Any] = {}

    if config_path is not None:
        with config_path.open(
            "r",
            encoding="utf-8",
        ) as f:
            loaded = yaml.safe_load(f)

        if loaded is None:
            loaded = {}

        if not isinstance(loaded, dict):
            raise ValueError(
                f"Config must contain a YAML mapping: "
                f"{config_path}"
            )

        override = loaded

        print(
            f"Config: {config_path}"
        )

    else:
        print(
            "Config: built-in defaults"
        )

    # --------------------------------------------------------
    # Merge defaults + project overrides
    # --------------------------------------------------------

    data = _deep_merge(
        DEFAULT_CONFIG,
        override,
    )

    dirs = data["dirs"]
    audio = data["audio"]
    subtitles = data["subtitles"]
    images = data["images"]
    music = data["music"]
    video = data["video"]

    # --------------------------------------------------------
    # Build Config
    # --------------------------------------------------------

    return Config(
        project_dir=project_dir,

        audio_dir=_resolve_path(
            project_dir,
            str(dirs["audio"]),
        ),

        image_dir=_resolve_path(
            project_dir,
            str(dirs["images"]),
        ),

        music_dir=_resolve_path(
            project_dir,
            str(dirs["music"]),
        ),

        work_dir=_resolve_path(
            project_dir,
            str(dirs["work"]),
        ),

        output=_resolve_path(
            project_dir,
            str(dirs["output"]),
        ),

        detection_window_sec=float(
            audio["detection_window_sec"]
        ),

        detection_model=str(
            audio["detection_model"]
        ),

        transcribe_model=str(
            audio["transcribe_model"]
        ),

        language_code=str(
            audio["language_code"]
        ),

        confidence_threshold=float(
            audio["confidence_threshold"]
        ),

        trim_preroll_sec=float(
            audio["trim_preroll_sec"]
        ),

        narration_volume=float(
            audio["volume"]
        ),

        subtitle_max_words=int(
            subtitles["max_words"]
        ),

        subtitle_max_sec=float(
            subtitles["max_sec"]
        ),

        image_duration_sec=float(
            images["duration_sec"]
        ),

        overscan=float(
            images["overscan"]
        ),

        transition_sec=float(
            images["transition_sec"]
        ),

        music_volume=float(
            music["volume"]
        ),

        width=int(
            video["width"]
        ),

        height=int(
            video["height"]
        ),

        fps=int(
            video["fps"]
        ),

        video_codec=str(
            video["codec"]
        ),

        crf=int(
            video["crf"]
        ),

        preset=str(
            video["preset"]
        ),
    )