# Narramotion

Narramotion turns narration audio, images, and background music into
subtitled slideshow videos.

## Installation

### Homebrew

``` bash
brew install --cask byunguk/tap/narramotion
```

Narramotion requires FFmpeg with subtitle support. The Homebrew package
installs the required FFmpeg dependency automatically.

## Setup

Narramotion uses the Gemini API for narration boundary detection and
transcription.

Run the setup command once:

``` bash
narramotion init
```

You will be prompted to enter your Gemini API key:

``` text
Narramotion setup

Gemini API key:

Gemini API key saved.
Config: ~/.config/narramotion/config.json

Setup complete.
```

The API key is stored locally in:

``` text
~/.config/narramotion/config.json
```

The configuration file is created with user-only file permissions.

You can run `narramotion init` again at any time to replace the saved
API key.

### Environment variable

For CI, servers, or temporary use, you can provide the API key through
the `GEMINI_API_KEY` environment variable instead:

``` bash
export GEMINI_API_KEY="your-api-key"
```

The `GEMINI_API_KEY` environment variable takes precedence over the API
key saved by `narramotion init`.

## Quick Start

Create a project directory:

``` text
my-project/
├── audio/
│   ├── 01.mp3
│   └── 02.mp3
├── images/
│   ├── 01.jpg
│   └── 02.jpg
└── music/
    └── background.mp3
```

Then run:

``` bash
narramotion my-project
```

Narramotion uses built-in defaults, so `project.yaml` is optional.

Default project paths:

``` text
audio   -> ./audio
images  -> ./images
music   -> ./music
work    -> ./.narramotion
output  -> ./output/final.mp4
```

## Audio Only

Process narration and generate subtitles without rendering video:

``` bash
narramotion my-project --audio-only
```

Outputs:

``` text
my-project/output/narration.mp3
my-project/output/subtitles.srt
```

Images are not required in audio-only mode.

## Detection Only

Detect narration content boundaries without trimming, transcription, or
video rendering:

``` bash
narramotion my-project --detect-only
```

## Force Reprocessing

Narramotion caches intermediate processing results. To ignore cached
results:

``` bash
narramotion my-project --force
```

## Optional project.yaml

Built-in defaults are used automatically. Create `project.yaml` only
when you want to override them.

``` yaml
audio:
  detection_window_sec: 90
  detection_model: gemini-3.7-flash
  transcribe_model: gemini-3.5-transcribe
  language_code: en-US
  confidence_threshold: 0.90
  trim_preroll_sec: 0.30
  volume: 1.0

subtitles:
  max_words: 9
  max_sec: 4.0

images:
  duration_sec: 10
  overscan: 1.06
  transition_sec: 0.0

music:
  volume: 0.10

video:
  width: 1920
  height: 1080
  fps: 30
  codec: libx264
  crf: 20
  preset: medium
```

Relative paths are resolved from the project directory.

## CLI

``` text
narramotion <project> [options]
narramotion init
narramotion --version
narramotion --help
```

Options:

``` text
--detect-only    Detect narration boundaries only
--audio-only     Process narration and subtitles without rendering video
--force          Ignore cached processing results
--version        Show the installed Narramotion version
-h, --help       Show help
```

## Examples

``` bash
narramotion projects/2timothy
narramotion projects/2timothy --audio-only
narramotion projects/2timothy --detect-only
narramotion projects/2timothy --force
```

## Updating the Gemini API Key

Run `narramotion init` again and enter the new API key. The saved key
will be replaced.

## License

MIT
