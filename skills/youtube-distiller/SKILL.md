---
name: youtube-distiller
description: Use when a user provides a YouTube URL or local video/audio/transcript and asks to summarize, distill, answer questions from, extract a topic, create notes, produce action items, or extract domain-specific outputs such as trading strategies, tutorials, workflows, reviews, or claims.
---

# YouTube Distiller

## Purpose

Distill a YouTube or local video into the output the user asks for, grounded in
timestamped evidence. The user may request a broad summary, a topic-specific
answer, a tutorial, claims, action items, or a domain-specific extraction such
as trading strategy rules.

## Core Rule

Do not pretend source access succeeded. Metadata is useful for identifying and
debugging a video, but metadata is not a transcript, audio stream, or visual
source.

Always attempt every applicable source before summarizing or extracting:

1. manual captions
2. auto captions
3. audio download + Whisper transcription
4. video download + sampled frames when visual understanding is needed

Captions are not a stopping condition. The skill must continue to attempt audio
and video acquisition even after captions are found, then report the full
acquisition manifest. Only after the applicable sources fail should the skill
produce a failure report asking for a local video/audio/transcript file or an
explicitly labeled indexed transcript fallback.

If the requested output depends on visuals, charts, slides, code, UI actions, or
on-screen text, visual evidence is required. If frames are unavailable, say so
and do not claim visual understanding.

## Run

From the skill directory:

```bash
python3 scripts/summarize_video.py \
  --url "<youtube-url>" \
  --title "<title if known>" \
  --requirement "Extract the trading strategy and say whether it is backtestable" \
  --output data/summaries/<video_id>.md
```

Local files:

```bash
python3 scripts/summarize_video.py \
  --input /path/to/video.mp4 \
  --requirement "Answer: what does the speaker say about risk management?" \
  --output data/summaries/result.md
```

Useful flags:

- `--output-kind summary|qa|topic|tutorial|strategy|claims|notes|custom`
- `--question "specific question"` for Q&A.
- `--topic "specific topic"` for topic extraction.
- `--cookies-from-browser auto|chrome|safari|firefox|edge|brave|chromium|none`.
  Default `auto` tries unauthenticated access first, then common browser-cookie
  sources.
- `--sub-langs "en.*,zh.*"` to control caption languages.
- `--no-video-understanding` only when visuals are irrelevant.

## Output Flow

1. Attempt all applicable caption, audio, and video sources.
2. Transcribe any acquired audio/video with Whisper.
3. Acquire visual frames when needed. The script samples frames with `ffmpeg`
   and writes `data/frames/<video_id>/visual_manifest.json`.
4. Use the generated Markdown shell as evidence context.
5. Refine the final answer to match the user's `--requirement`.
6. Include every source acquired, every source unavailable, and missing evidence.

## Output Kinds

- `summary`: executive summary, main topics, takeaways, caveats.
- `qa`: answer only the user question, cite timestamps when available.
- `topic`: extract only the requested topic and ignore unrelated material.
- `tutorial`: convert the video into executable steps.
- `strategy`: extract deterministic strategy rules and missing backtest fields.
- `claims`: list claims, evidence, uncertainty, and checks needed.
- `notes`: concise study notes or meeting-style notes.
- `custom`: follow the user requirement exactly.

## Domain-Specific Rule: Trading

When extracting trading strategies, classify each candidate:

- `backable`: instrument universe, timeframe, entry, exit, stop, sizing, and
  execution timing are explicit.
- `partially_backable_needs_visual_verification`: the rule shape exists but
  chart levels, indicator settings, thresholds, or examples need frames.
- `not_backable`: the video gives concepts, opinions, or examples but not
  deterministic rules.

Never invent missing rules. Record missing thresholds explicitly.

## References

Use `references/output-contract.md` when creating structured JSON for websites,
ranking systems, or downstream backtesting.
