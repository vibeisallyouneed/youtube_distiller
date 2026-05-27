# YouTube Distiller

Evidence-grounded YouTube and local video distillation for agents. This project
turns a YouTube URL or local video/audio/transcript into a Markdown evidence
shell that an agent can use to summarize, answer questions, extract topics,
produce tutorials, extract trading strategies, or build structured downstream
outputs.

The bundled installable skill is in `skills/youtube-distiller`.

The CLI output is an evidence packet for an agent. The installable skill uses
that packet to write the final requested Markdown output, such as a summary,
Q&A answer, topic extraction, or trading-strategy distillation.

Source provenance matters. If an output uses extra files, repository docs,
NotebookLM exports, or other non-video material, label it as `video-plus-docs`
or another explicit source scope and separate video-derived claims from
document-derived claims.

## Source Policy

The distiller treats metadata as identification/debug data only. For YouTube
URLs it attempts acquisition in this order:

1. manual captions
2. auto captions
3. audio download plus Whisper transcription
4. video download plus dense, transcript-aligned, and scene-change sampled
   frames when visual understanding is needed

If those fail, it writes a `source_unavailable` report instead of summarizing
from metadata.

When visual evidence is required but video frames cannot be acquired, the output
is marked `partial_missing_required_visual_evidence`. Treat that as transcript-
grounded interim evidence, not a complete video distillation.

When frames are acquired but no visual notes have been extracted, the output is
marked `visual_sources_acquired_pending_interpretation`. OCR-only output is
marked `visual_ocr_extracted_pending_vision_review`, because OCR is a rough text
helper rather than full visual understanding. Frame paths alone are not treated
as extracted information.

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
  --requirement "Extract the trading strategy and identify missing backtest rules" \
  --output data/summaries/VIDEO_ID.md
```

By default, the CLI tries unauthenticated `yt-dlp` first, then common browser
cookie sources: Chrome, Safari, Firefox, Edge, Brave, and Chromium. Use
`--cookies-from-browser none` to disable browser-cookie fallback, or pass a
specific browser such as `--cookies-from-browser chrome`. The default caption
language selector is `--sub-langs "en.*,zh.*"`.

For media downloads, the CLI also retries public-video acquisition with
`youtube:player_client=android` without browser cookies after normal cookie
paths fail. This handles current YouTube web-client 403/SABR behavior while
still preserving cookie-based attempts for captions and restricted videos.

Visual extraction uses dense frame sampling, transcript segment boundaries,
visual cue neighborhoods, and ffmpeg scene-change detection. It also builds
contact sheets for Codex/Claude multimodal review. If Tesseract is installed,
OCR text from sampled frames is included as secondary evidence. The default
dense interval is five seconds and can be lowered with `--frame-interval-sec`.
OCR runs in parallel and can be tuned with `--ocr-workers`.

After multimodal review, add the contact-sheet or frame-level vision notes to
the generated `visual_manifest.json`, then render the final evidence shell with:

```bash
python3 scripts/summarize_video.py \
  --input data/raw/VIDEO_ID.vtt \
  --source-url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --visual-manifest data/frames/VIDEO_ID/visual_manifest.json \
  --requirement "Extract the implementation-ready strategy rules" \
  --output data/summaries/VIDEO_ID.reviewed.md
```

This second pass marks visual-dependent output complete only when OCR/frame
paths are accompanied by actual vision notes.

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
