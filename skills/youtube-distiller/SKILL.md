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
4. video download + dense, transcript-aligned, and scene-change sampled frames
   when visual understanding is needed

Captions are not a stopping condition. The skill must continue to attempt audio
and video acquisition even after captions are found, then report the full
acquisition manifest. Only after the applicable sources fail should the skill
produce a failure report asking for a local video/audio/transcript file or an
explicitly labeled indexed transcript fallback.

If the requested output depends on visuals, charts, slides, code, UI actions, or
on-screen text, visual evidence is required. If frames are unavailable, say so
and do not claim visual understanding. Mark the result
`partial_missing_required_visual_evidence`; do not present it as a complete
video distillation.

Frame paths alone are not enough. If frames were acquired but no vision notes
were extracted, mark the result
`visual_sources_acquired_pending_interpretation`. If OCR exists but no
multimodal vision notes exist, mark the result
`visual_ocr_extracted_pending_vision_review`. OCR is secondary text evidence,
not complete visual understanding. Inspect the contact sheets or key frames with
Codex/Claude multimodality and add vision notes before finalizing
visual-dependent answers.

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
- `--source-url "<youtube-url>"` when rendering from cached local files and you
  want the output to cite the original URL without re-acquiring YouTube.
- `--cookies-from-browser auto|chrome|safari|firefox|edge|brave|chromium|none`.
  Default `auto` tries unauthenticated access first, then common browser-cookie
  sources.
- `--sub-langs "en.*,zh.*"` to control caption languages.
- `--no-video-understanding` only when visuals are irrelevant.
- `--frame-interval-sec 5` controls dense frame sampling. Lower values reduce
  missed visual changes at the cost of more frames.
- `--scene-threshold 0.3` adds frames at detected scene changes.
- `--ocr-lang "eng+chi_sim+chi_tra"` controls optional Tesseract OCR language
  selection. Use `--no-ocr` to skip OCR.
- `--ocr-workers 4` controls parallel Tesseract workers.
- `--contact-sheet-frames 20` controls how many sampled frames are grouped into
  each contact sheet for multimodal review.
- `--visual-manifest data/frames/<video_id>/visual_manifest.json` renders a
  post-review pass from an existing manifest after Codex/Claude vision notes
  have been added.

Media downloads retry normal cookie/no-cookie paths first, then retry public
videos with the YouTube Android client without browser cookies. This is
required for some current YouTube web-client 403/SABR failures.

## Output Flow

The CLI creates an evidence packet. It does not replace the agent's final
distillation step. When the user asks for a summary, strategy, answer, claims
list, or other output, the skill must write the final requested Markdown output
after the evidence packet is complete.

1. Attempt all applicable caption, audio, and video sources.
2. Transcribe any acquired audio/video with Whisper.
3. Acquire visual frames when needed. The script samples dense intervals,
   transcript segment boundaries, visual cue neighborhoods, and scene changes
   with `ffmpeg`, then writes `data/frames/<video_id>/visual_manifest.json`.
4. Build contact sheets from sampled frames for Codex/Claude multimodal review.
5. Run OCR on sampled frames when Tesseract is available. Treat OCR as
   secondary evidence.
6. Inspect contact sheets or key frames with multimodality and add
   `contact_sheet_notes` or frame-level `vision_notes` to the visual manifest
   before final visual-dependent extraction.
7. Re-run the renderer with `--visual-manifest` so the final artifact includes
   the reviewed visual notes as source evidence.
8. Use transcript, OCR text, vision notes, and sampled frame paths as extraction
   context.
9. Write the final requested output as Markdown. Do not leave the user with only
   the evidence packet.
10. Refine the final answer to match the user's `--requirement`.
11. Include every source acquired, every source unavailable, and missing evidence.
12. If `Distillation status` is `partial_missing_required_visual_evidence`, only
   produce transcript-grounded interim notes and keep the missing visual source
   as a blocker for complete distillation.
13. If `Distillation status` is
   `visual_sources_acquired_pending_interpretation`, inspect/annotate the
   sampled frames before producing final visual-dependent extraction.
14. If `Distillation status` is
   `visual_ocr_extracted_pending_vision_review`, use OCR as rough text evidence
   only and inspect/annotate the contact sheets with multimodality before
   producing final visual-dependent extraction.

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

Never invent missing rules. Record missing thresholds explicitly. Do not mark a
strategy as `backable` from transcript text alone when the video shows chart
rules, parameter values, code, tables, or examples on screen.

## References

Use `references/output-contract.md` when creating structured JSON for websites,
ranking systems, or downstream backtesting.
