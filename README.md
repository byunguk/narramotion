# Narramotion

Narramotion is a batch CLI for turning narration audio, images, and optional background music into a subtitled slideshow video.

It is designed for long-form narration workflows where many audio files need to be:

- detected and trimmed
- transcribed
- combined into one timeline
- subtitled
- rendered with low-memory image motion
- mixed with background music
- exported as a final MP4

Narramotion also supports audio-only processing when you want to inspect the combined narration and subtitles before rendering video.

---

## Features

- Batch-processes narration files in filename order
- Uses Gemini to detect the useful spoken content boundaries
- Removes non-content intro and outro material
- Supports configurable start/end detection windows
- Trims audio with FFmpeg
- Transcribes with `gemini-3.5-transcribe`
- Uses word-level timestamps for subtitle timing
- Combines many audio files into one continuous narration
- Generates a single SRT timeline across all files
- Renders images in low-memory 10-second clips
- Avoids FFmpeg `zoompan`
- Uses fixed overscan + moving crop for image motion
- Rotates background music tracks
- Mixes narration and BGM
- Burns subtitles into the final video
- Caches Gemini detection and transcription results
- Supports `--audio-only`
- Supports `--detect-only`
- Supports optional per-project `project.yaml`
- Uses built-in defaults when no project config exists

---

## Requirements

- macOS or Linux
- Python 3.11+
- Gemini API key
- FFmpeg
- FFprobe

For final video rendering with burned subtitles, Narramotion requires an FFmpeg build with the `subtitles` filter provided by `libass`.

On macOS, the recommended installation is:

```bash
brew install ffmpeg-full
```

`ffmpeg-full` is keg-only, so Narramotion prefers the Homebrew `ffmpeg-full` installation automatically when available.

You can verify subtitle support with:

```bash
$(brew --prefix ffmpeg-full)/bin/ffmpeg -hide_banner -filters | grep subtitles
```

Expected output includes something similar to:

```text
subtitles         V->V       Render text subtitles onto input video using the libass library.
```

---

## Development installation

```bash
git clone https://github.com/YOUR_GITHUB_USER/narramotion.git
cd narramotion

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e '.[dev]'
```

Verify the CLI:

```bash
narramotion --help
```

---

## Gemini API key

Narramotion reads the Gemini API key from:

```text
GEMINI_API_KEY
```

For the current terminal session:

```bash
export GEMINI_API_KEY='YOUR_API_KEY'
```

Verify that it is set without printing the key:

```bash
if [ -n "$GEMINI_API_KEY" ]; then
  echo "Gemini API key is set"
else
  echo "Gemini API key is NOT set"
fi
```

Do not commit API keys to Git.

---

## Project structure

A project can use the default layout:

```text
my-project/
├── audio/
├── images/
├── music/
├── .narramotion/
└── output/
```

You only need to create the input folders you actually use.

For example:

```bash
mkdir -p projects/1timothy/audio
mkdir -p projects/1timothy/images
mkdir -p projects/1timothy/music
```

`.narramotion/` and `output/` are created automatically.

---

## Running a project

The preferred usage is to pass the project directory:

```bash
narramotion projects/1timothy
```

Narramotion automatically looks for:

```text
projects/1timothy/project.yaml
```

or:

```text
projects/1timothy/project.yml
```

If neither exists, built-in defaults are used.

The legacy form is also supported:

```bash
narramotion projects/1timothy/project.yaml
```

---

## Built-in defaults

When no `project.yaml` exists, Narramotion uses defaults equivalent to:

```yaml
dirs:
  audio: ./audio
  images: ./images
  music: ./music
  work: ./.narramotion
  output: ./output/final.mp4

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

---

## Optional project configuration

`project.yaml` is optional.

Use it only when you want to override one or more defaults.

Example:

```yaml
music:
  volume: 0.05

images:
  duration_sec: 15
```

All other settings continue using built-in defaults.

Another example:

```yaml
dirs:
  audio: ./narration
  output: ./renders/movie.mp4

video:
  crf: 18
```

Only those values are overridden.

---

## Input files

### Audio

Place narration files in:

```text
audio/
```

Supported audio files are processed in lexical filename order.

Using zero-padded numbering is recommended:

```text
chapter_01.mp3
chapter_02.mp3
chapter_03.mp3
...
chapter_10.mp3
```

Random descriptive filenames are also allowed, but filename order determines processing order.

### Images

Place images in:

```text
images/
```

Supported image filenames can be arbitrary.

Example:

```text
sunset.jpg
IMG_4821.png
scene-final.webp
```

### Background music

Place optional music files in:

```text
music/
```

Music filenames can also be arbitrary.

If the folder is empty or missing, Narramotion renders without background music.

---

## Detection only

Use:

```bash
narramotion projects/1timothy --detect-only
```

This performs content-boundary detection only.

It does not:

- trim audio
- transcribe the full audio
- build subtitles
- concatenate narration
- render images
- mix music
- render video

Detection results are cached under:

```text
.narramotion/detections/
```

A summary is written to:

```text
.narramotion/detections-summary.json
```

Low-confidence results are written to:

```text
.narramotion/review-needed.json
```

To ignore cached detections and run detection again:

```bash
narramotion projects/1timothy --detect-only --force
```

---

## Audio-only processing

Use:

```bash
narramotion projects/1timothy --audio-only
```

This performs:

1. detection
2. trimming
3. Gemini transcription
4. SRT generation
5. narration concatenation

It stops before image/video rendering.

User-facing outputs are written to:

```text
output/narration.mp3
output/subtitles.srt
```

Internal build copies remain under:

```text
.narramotion/narration.mp3
.narramotion/final.srt
```

This is useful for reviewing the narration and subtitles before rendering a long video.

---

## Full video rendering

Run:

```bash
narramotion projects/1timothy
```

The pipeline performs:

```text
audio files
    ↓
content-boundary detection
    ↓
trim
    ↓
Gemini transcription
    ↓
word timestamps
    ↓
SRT generation
    ↓
narration concat
    ↓
image motion rendering
    ↓
background music bed
    ↓
subtitle burn-in
    ↓
output/final.mp4
```

Final user-facing outputs are:

```text
output/
├── narration.mp3
├── subtitles.srt
└── final.mp4
```

---

## Audio boundary detection

Narramotion can remove spoken material that does not belong to the actual narration content.

Examples include:

- chapter or book announcements
- narrator credits
- "recorded by" statements
- publisher information
- copyright notices
- website names
- closing announcements
- "End of Chapter..." messages

Detection operates on configurable portions near the beginning and end of each source file rather than requiring the entire file to be sent for boundary analysis.

The detected start timestamp receives a small preroll margin to avoid clipping the first spoken sound.

---

## Gemini rate limits

Gemini transcription can return:

```text
429 RESOURCE_EXHAUSTED
```

when the current per-minute quota is exceeded.

Narramotion retries rate-limited transcription requests automatically after the retry delay reported by Gemini.

Successful transcript results are cached, so restarting the command normally does not retranscribe files that already completed successfully.

Do not use `--force` unless you intentionally want to rebuild cached AI/intermediate stages.

---

## Subtitle timing

Each audio file is transcribed independently.

For every file:

```text
word timestamps start at 0
```

Narramotion calculates the duration of the trimmed audio and offsets the subtitle cues of subsequent files.

Example:

```text
chapter 1 duration = 300 sec
chapter 2 local subtitle = 12 sec
```

The final subtitle timestamp becomes:

```text
312 sec
```

This creates one continuous SRT timeline for the concatenated narration.

---

## Low-memory image rendering

Narramotion intentionally avoids FFmpeg `zoompan`.

Instead, each image is rendered as its own short video clip using:

```text
fixed overscan
+
smooth moving crop
```

The default image duration is:

```text
10 seconds
```

and the default overscan is:

```text
1.06
```

This approach keeps FFmpeg filter graphs smaller and avoids the memory usage associated with very large intermediate image scaling.

Rendered image clips are stored in the work directory and concatenated into the silent video.

---

## Background music

Background music is optional.

Current behavior:

- music files are read from the configured music directory
- tracks are concatenated/rotated to cover the narration duration
- the music bed is trimmed to narration length
- narration and BGM are mixed during final muxing

Default BGM volume:

```yaml
music:
  volume: 0.10
```

---

## FFmpeg subtitle requirement

Burning SRT subtitles requires FFmpeg's `subtitles` filter.

Narramotion checks this before performing full video rendering.

On macOS, install:

```bash
brew install ffmpeg-full
```

Narramotion prefers:

```text
$(brew --prefix ffmpeg-full)/bin/ffmpeg
```

when available.

Audio-only processing does not require the subtitle video filter.

---

## Work and cache layout

Narramotion uses `.narramotion/` as its internal build/cache directory:

```text
.narramotion/
├── detections/
├── transcripts/
├── trimmed/
├── image-clips/
├── final.srt
├── narration.mp3
├── music-bed.m4a
├── silent-video.mp4
└── review-needed.json
```

This directory can be deleted if you want a completely clean rebuild.

Normally you should keep it so that expensive AI processing can be reused.

---

## Output layout

User-facing artifacts are written to:

```text
output/
├── narration.mp3
├── subtitles.srt
└── final.mp4
```

`.narramotion/` should be treated as internal build data.

`output/` contains the files intended for the user.

---

## Force rebuilding

To ignore caches:

```bash
narramotion projects/1timothy --force
```

Be careful: this may cause Gemini detection and transcription requests to run again.

For detection-only rebuilding:

```bash
narramotion projects/1timothy --detect-only --force
```

---

## Recommended `.gitignore`

Projects commonly contain large audio, image, music, cache, and generated files.

Recommended exclusions:

```gitignore
.venv/
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/

.env
.env.*
!.env.example

.DS_Store

.narramotion/
output/

audio/
images/
music/
audio-test/

projects/

project.yaml
```

Keep source code, tests, release scripts, Homebrew files, and `project.example.yaml` in Git.

---

## Testing

Run syntax validation:

```bash
python -m compileall -q src/narramotion
```

Run tests:

```bash
pytest
```

Before committing, old package-name references can also be checked with:

```bash
grep -RIn \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude-dir=.narramotion \
  "bible_video_maker\|bible-video" . || true
```

---

## Building a standalone macOS CLI

Build:

```bash
./scripts/build_macos.sh
```

Expected output:

```text
dist/narramotion
```

Package the release artifact with:

```bash
./scripts/package_release.sh
```

The standalone Narramotion executable still relies on FFmpeg being available on the target machine.

---

## Homebrew Cask

The repository includes Homebrew Cask scaffolding for distributing the standalone macOS binary.

The Cask should depend on:

```ruby
depends_on formula: "ffmpeg-full"
```

because Narramotion requires FFmpeg with `libass` subtitle support for final video rendering.

After publishing a versioned GitHub Release:

1. update the Cask version
2. update the release URL
3. update the SHA-256
4. publish the Cask in your Homebrew tap

Example installation:

```bash
brew install --cask YOUR_GITHUB_USER/tap/narramotion
```

---

## Current limitations

- Image transitions are currently hard cuts
- Background music does not yet crossfade
- Automatic ducking is not yet implemented
- Subtitle styling currently relies on FFmpeg/libass defaults
- Detection is AI-based and low-confidence results should be reviewed
- File processing order is currently filename order
- `--force` rebuilds multiple stages rather than targeting individual stages

Potential future CLI options include:

```text
--force-detect
--force-transcribe
--force-render
--render-only
```

---

## License

Narramotion is licensed under the MIT License. See [LICENSE](LICENSE) for details.