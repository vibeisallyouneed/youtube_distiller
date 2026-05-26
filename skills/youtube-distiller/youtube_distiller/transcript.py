from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import re


@dataclass(frozen=True)
class TranscriptSegment:
    start_sec: float
    end_sec: float
    text: str


TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})"
)
SRT_TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}:\d{2},\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


def timestamp_to_seconds(value: str) -> float:
    value = value.replace(",", ".")
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(".")
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(millis) / 1000
    )


def seconds_to_timestamp(value: float) -> str:
    total = int(value)
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def clean_caption_text(text: str) -> str:
    text = TAG_RE.sub("", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_vtt(text: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
    previous_text = None

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0] == "WEBVTT":
            continue

        timestamp_index = next(
            (idx for idx, line in enumerate(lines) if TIMESTAMP_RE.search(line)),
            None,
        )
        if timestamp_index is None:
            continue

        match = TIMESTAMP_RE.search(lines[timestamp_index])
        if match is None:
            continue

        caption_text = clean_caption_text(" ".join(lines[timestamp_index + 1 :]))
        if not caption_text or caption_text == previous_text:
            continue

        previous_text = caption_text
        segments.append(
            TranscriptSegment(
                start_sec=timestamp_to_seconds(match.group("start")),
                end_sec=timestamp_to_seconds(match.group("end")),
                text=caption_text,
            )
        )

    return segments


def parse_srt(text: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
    previous_text = None

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        timestamp_index = next(
            (idx for idx, line in enumerate(lines) if SRT_TIMESTAMP_RE.search(line)),
            None,
        )
        if timestamp_index is None:
            continue

        match = SRT_TIMESTAMP_RE.search(lines[timestamp_index])
        if match is None:
            continue

        caption_text = clean_caption_text(" ".join(lines[timestamp_index + 1 :]))
        if not caption_text or caption_text == previous_text:
            continue

        previous_text = caption_text
        segments.append(
            TranscriptSegment(
                start_sec=timestamp_to_seconds(match.group("start")),
                end_sec=timestamp_to_seconds(match.group("end")),
                text=caption_text,
            )
        )

    return segments


def parse_plain_text(text: str) -> list[TranscriptSegment]:
    clean = clean_caption_text(text)
    if not clean:
        return []
    return [TranscriptSegment(start_sec=0.0, end_sec=0.0, text=clean)]


def render_markdown_summary_shell(
    *,
    title: str,
    url: str,
    transcript_source: str,
    segments: list[TranscriptSegment],
    visual_manifest: dict | None = None,
    visual_required: bool = True,
    requirement: str = "Summarize the video.",
    output_kind: str = "summary",
    question: str | None = None,
    topic: str | None = None,
    acquisition_manifest: list[dict] | None = None,
) -> str:
    evidence = "\n".join(
        f"- `{seconds_to_timestamp(segment.start_sec)}` {segment.text}"
        for segment in segments
    )
    has_visual_frames = bool(visual_manifest and visual_manifest.get("frames"))
    has_visual_ocr = visual_manifest_has_ocr(visual_manifest)
    has_visual_notes = visual_manifest_has_notes(visual_manifest)
    if visual_manifest and visual_manifest.get("frames"):
        visual_status = "available"
        visual_lines = "\n".join(
            render_visual_frame_line(frame)
            for frame in visual_manifest["frames"]
        )
    elif visual_required:
        visual_status = "missing_required"
        visual_lines = (
            "- Required visual/video evidence was not acquired. This artifact is "
            "a partial transcript/audio distillation only. Do not present this "
            "as a complete video distillation or claim visual understanding."
        )
    else:
        visual_status = "not_required"
        visual_lines = "- Visual evidence was not requested."

    distillation_status = render_distillation_status(
        visual_required=visual_required,
        has_visual_frames=has_visual_frames,
        has_visual_ocr=has_visual_ocr,
        has_visual_notes=has_visual_notes,
    )
    completion_gate = render_completion_gate(
        distillation_status=distillation_status,
        visual_required=visual_required,
        has_visual_frames=has_visual_frames,
        has_visual_ocr=has_visual_ocr,
        has_visual_notes=has_visual_notes,
    )

    focus_lines = [
        f"- Output kind: {output_kind}",
        f"- Requirement: {requirement}",
    ]
    if question:
        focus_lines.append(f"- Question: {question}")
    if topic:
        focus_lines.append(f"- Topic: {topic}")
    focus = "\n".join(focus_lines)

    output_guidance = render_output_guidance(
        output_kind=output_kind,
        requirement=requirement,
        question=question,
        topic=topic,
        visual_required=visual_required,
    )
    acquisition_lines = render_acquisition_manifest(acquisition_manifest or [])
    contact_sheet_lines = render_contact_sheets(visual_manifest)

    return f"""# Video Distillation: {title}

## Source

- URL: {url}
- Transcript source: {transcript_source}
- Evidence segments available: {len(segments)}
- Visual evidence: {visual_status}
- Distillation status: {distillation_status}

## Completion Gate

{completion_gate}

## User Request

{focus}

## Acquisition Manifest

{acquisition_lines}

## Requested Output Draft

{output_guidance}

## Evidence Rules

Do not finalize claims without source evidence. If the requested output depends
on visual content and visual evidence is missing, mark that limitation clearly.
Do not finalize strategy rules without timestamped evidence.

For trading videos, visual evidence is required whenever the speaker references
charts, candles, indicators, levels, on-screen examples, or phrases like
`look here`, `this setup`, `entry`, `stop`, or `target`.

Use extracted visual text and visual notes as source material for the requested
output, not as an appendix. For strategy extraction, reconcile the transcript,
OCR text, and frame notes before deciding whether entry, exit, stop, sizing,
indicator settings, timeframe, and execution timing are explicit.

## Visual Evidence Map

### Contact Sheets

{contact_sheet_lines}

### Frame Notes

{visual_lines}

## Evidence Map

{evidence}
"""


def render_visual_frame_line(frame: dict) -> str:
    timestamp = seconds_to_timestamp(frame.get("timestamp_sec", 0))
    path = frame.get("path", "")
    reasons = frame.get("reasons") or []
    reason_text = f" Reasons: {', '.join(reasons)}." if reasons else ""
    ocr_text = clean_visual_text(frame.get("ocr_text"))
    ocr_part = f" OCR: {ocr_text}" if ocr_text else ""
    notes = clean_visual_text(frame.get("vision_notes"))
    notes_part = f" Visual notes: {notes}" if notes else ""
    return f"- `{timestamp}` {path}.{reason_text}{ocr_part}{notes_part}"


def clean_visual_text(value) -> str:
    if not value:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    if len(text) > 500:
        return f"{text[:497]}..."
    return text


def render_contact_sheets(visual_manifest: dict | None) -> str:
    if not visual_manifest:
        return "- None."
    contact_sheets = visual_manifest.get("contact_sheets") or []
    if not contact_sheets:
        return "- None."
    contact_sheet_notes = visual_manifest.get("contact_sheet_notes") or {}
    lines = []
    for path in contact_sheets:
        note = clean_visual_text(contact_sheet_notes.get(path))
        if note:
            lines.append(f"- {path}: {note}")
        else:
            lines.append(f"- {path}")
    return "\n".join(lines)


def visual_manifest_has_ocr(visual_manifest: dict | None) -> bool:
    if not visual_manifest:
        return False
    for frame in visual_manifest.get("frames", []):
        if clean_visual_text(frame.get("ocr_text")):
            return True
    return False


def visual_manifest_has_notes(visual_manifest: dict | None) -> bool:
    if not visual_manifest:
        return False
    for note in (visual_manifest.get("contact_sheet_notes") or {}).values():
        if clean_visual_text(note):
            return True
    for frame in visual_manifest.get("frames", []):
        if clean_visual_text(frame.get("vision_notes")):
            return True
    return False


def render_output_guidance(
    *,
    output_kind: str,
    requirement: str,
    question: str | None,
    topic: str | None,
    visual_required: bool,
) -> str:
    if output_kind == "qa":
        return (
            f"Answer this question from the video evidence: `{question or requirement}`.\n\n"
            "Use only video-grounded evidence. Say when the video does not answer it."
        )
    if output_kind == "topic":
        return (
            f"Extract only this topic from the video: `{topic or requirement}`.\n\n"
            "Ignore unrelated sections. Include timestamps for relevant evidence."
        )
    if output_kind == "tutorial":
        return (
            "Convert the video into executable steps. Include prerequisites, steps, "
            "decision points, and expected outcomes."
        )
    if output_kind == "strategy":
        return (
            "Extract strategy rules only if deterministic evidence exists. Include "
            "instrument universe, timeframe, entry, exit, stop, sizing, evidence, "
            "missing fields, and backtest readiness."
        )
    if output_kind == "claims":
        return (
            "List the video's major claims, the evidence offered, uncertainty level, "
            "and what external checks would be needed."
        )
    if output_kind == "notes":
        return "Produce concise structured notes with key ideas, definitions, and takeaways."
    if output_kind == "custom":
        return f"Follow this user requirement exactly: `{requirement}`."
    visual_note = (
        " Include visual evidence where relevant."
        if visual_required
        else " Visual evidence was not requested."
    )
    return f"Produce a concise executive summary, main points, takeaways, and caveats.{visual_note}"


def render_distillation_status(
    *,
    visual_required: bool,
    has_visual_frames: bool,
    has_visual_ocr: bool = False,
    has_visual_notes: bool = False,
) -> str:
    if visual_required and not has_visual_frames:
        return "partial_missing_required_visual_evidence"
    if visual_required and has_visual_ocr and not has_visual_notes:
        return "visual_ocr_extracted_pending_vision_review"
    if visual_required and not has_visual_notes:
        return "visual_sources_acquired_pending_interpretation"
    if visual_required:
        return "complete_with_visual_extraction"
    return "complete_transcript_only_visual_not_required"


def render_completion_gate(
    *,
    distillation_status: str,
    visual_required: bool,
    has_visual_frames: bool,
    has_visual_ocr: bool = False,
    has_visual_notes: bool = False,
) -> str:
    if visual_required and not has_visual_frames:
        return (
            "- Status: partial.\n"
            "- Required visual/video evidence is missing.\n"
            "- Do not present this as a complete video distillation.\n"
            "- Do not claim visual understanding, chart verification, UI/code verification, "
            "or complete strategy extraction.\n"
            "- Use this artifact only for transcript-grounded interim notes until video "
            "frames, local video, or another visual source is provided."
        )
    if visual_required and has_visual_ocr and not has_visual_notes:
        return (
            "- Status: OCR extracted, multimodal vision review pending.\n"
            "- Use OCR as rough text evidence only; it can be noisy and incomplete.\n"
            "- Inspect the contact sheets or key frames with multimodal vision and write "
            "`vision_notes` before finalizing visual-dependent extraction.\n"
            "- For trading strategy extraction, do not mark the strategy backable until "
            "visual thresholds, indicator settings, chart examples, and on-screen rules "
            "have been reconciled with the transcript."
        )
    if visual_required and not has_visual_notes:
        return (
            "- Status: visual sources acquired, interpretation pending.\n"
            "- Do not finalize visual-dependent extraction from frame paths alone.\n"
            "- Inspect the sampled frames or run OCR/vision annotation first.\n"
            "- For trading strategy extraction, do not mark the strategy backable until "
            "visual thresholds, indicator settings, chart examples, and on-screen rules "
            "have been reconciled with the transcript."
        )
    return (
        f"- Status: {distillation_status}.\n"
        "- Continue to cite acquired evidence and list any remaining limitations."
    )


def render_acquisition_manifest(acquisition_manifest: list[dict]) -> str:
    if not acquisition_manifest:
        return "- No acquisition steps were recorded."
    lines = []
    for item in acquisition_manifest:
        path = f" `{item['path']}`" if item.get("path") else ""
        lines.append(f"- {item.get('name', 'unknown')}: {item.get('status', 'unknown')}{path}")
    return "\n".join(lines)
