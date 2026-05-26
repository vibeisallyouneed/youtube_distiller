# YouTube Distiller

Evidence-grounded YouTube and local video distillation for agents. This project
turns a YouTube URL or local video/audio/transcript into a Markdown evidence
shell that an agent can use to summarize, answer questions, extract topics,
produce tutorials, extract trading strategies, or build structured downstream
outputs.

The bundled installable skill is in `skills/youtube-distiller`.

## Source Policy

The distiller does not treat metadata as enough evidence. For YouTube URLs it
attempts acquisition in this order:

1. manual captions
2. auto captions
3. audio download plus Whisper transcription
4. video download plus sampled frames when visual understanding is needed

If those fail, it writes a `source_unavailable` report instead of summarizing
from metadata alone.

## Install

```bash
cd /Users/ping1zzz/projects/youtube_distiller
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
```

The video path requires `ffmpeg` and `ffprobe` on your `PATH`. YouTube download
support depends on `yt-dlp`; transcription depends on `faster-whisper`.

## Run

From the repo root:

```bash
python3 scripts/summarize_video.py \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --cookies-from-browser chrome \
  --requirement "Extract the trading strategy and identify missing backtest rules" \
  --output data/summaries/VIDEO_ID.md
```

Use `--cookies-from-browser chrome|safari|firefox|edge|brave|chromium` when
YouTube hides captions or media behind browser session access. The default
caption language selector is `--sub-langs "en.*,zh.*"`.

For a local transcript:

```bash
python3 scripts/summarize_video.py \
  --input tests/fixtures/sample.vtt \
  --requirement "Summarize the risk-management advice" \
  --no-video-understanding \
  --output data/summaries/sample.md
```

For the installable skill, copy or symlink `skills/youtube-distiller` into
your agent skill directory, such as `~/.agents/skills/` for Codex or
`~/.claude/skills/` for Claude Code.

## Test

```bash
python3 -m pytest
python3 /Users/ping1zzz/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/youtube-distiller
```

## Layout

```text
youtube_distiller/
├── youtube_distiller/              # reusable Python package
├── scripts/summarize_video.py      # repo-level CLI
├── skills/youtube-distiller/       # self-contained installable skill
├── tests/                          # regression tests
└── examples/                       # examples and demos
```
