#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import shutil

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from youtube_distiller.source_policy import (
    acquisition_plan,
    choose_next_source_step,
    is_media_file,
)
from youtube_distiller.transcript import (
    TranscriptSegment,
    parse_plain_text,
    parse_srt,
    parse_vtt,
    render_markdown_summary_shell,
)
from youtube_distiller.visual import extract_frames, plan_frame_samples, render_visual_manifest


VIDEO_ID_REPLACEMENTS = str.maketrans({"?": "_", "&": "_", "=": "_", "/": "_", ":": "_"})
DEFAULT_SUB_LANGS = "en.*,zh.*"
DEFAULT_COOKIE_SOURCES = ("chrome", "safari", "firefox", "edge", "brave", "chromium")


def run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def ytdlp_command() -> list[str]:
    binary = shutil.which("yt-dlp")
    if binary:
        return [binary]
    return [sys.executable, "-m", "yt_dlp"]


def cookie_candidates(cookies_from_browser: str | None) -> list[str | None]:
    if cookies_from_browser is None or cookies_from_browser == "auto":
        return [None, *DEFAULT_COOKIE_SOURCES]
    if cookies_from_browser.lower() in {"none", "off", "false", "no"}:
        return [None]
    return [cookies_from_browser]


def cookie_status(source: str | None) -> str:
    if source is None:
        return "without_browser_cookies"
    return f"via_{source}_cookies"


def build_ytdlp_invocation(
    args: list[str],
    *,
    cookies_from_browser: str | None = None,
) -> list[str]:
    command = [*ytdlp_command()]
    if cookies_from_browser:
        command.extend(["--cookies-from-browser", cookies_from_browser])
    command.extend(args)
    return command


def fetch_metadata(url: str, cookie_sources: list[str | None]) -> dict | None:
    for cookie_source in cookie_sources:
        result = run(
            build_ytdlp_invocation(
                ["--dump-json", "--skip-download", url],
                cookies_from_browser=cookie_source,
            )
        )
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def metadata_video_url(metadata: dict, fallback_url: str) -> str:
    return metadata.get("webpage_url") or fallback_url


def metadata_title(metadata: dict, fallback_title: str) -> str:
    if fallback_title != "Untitled YouTube Video":
        return fallback_title
    return metadata.get("title") or fallback_title


def read_transcript(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".vtt":
        return parse_vtt(text), "caption_file"
    if path.suffix.lower() == ".srt":
        return parse_srt(text), "caption_file"
    return parse_plain_text(text), "transcript_file"


def build_caption_command(
    *,
    url: str,
    raw_dir: Path,
    auto: bool,
    sub_langs: str,
    cookies_from_browser: str | None = None,
) -> list[str]:
    flag = "--write-auto-subs" if auto else "--write-subs"
    return build_ytdlp_invocation(
        [
            "--skip-download",
            flag,
            "--sub-langs",
            sub_langs,
            "--sub-format",
            "vtt",
            "-o",
            str(raw_dir / "%(id)s.%(ext)s"),
            url,
        ],
        cookies_from_browser=cookies_from_browser,
    )


def try_ytdlp_captions(
    url: str,
    raw_dir: Path,
    auto: bool,
    sub_langs: str,
    cookie_sources: list[str | None],
) -> tuple[Path, str] | None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for cookie_source in cookie_sources:
        before = set(raw_dir.glob("*.vtt"))
        result = run(
            build_caption_command(
                url=url,
                raw_dir=raw_dir,
                auto=auto,
                sub_langs=sub_langs,
                cookies_from_browser=cookie_source,
            )
        )
        after = set(raw_dir.glob("*.vtt"))
        new_files = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)
        if result.returncode == 0 and new_files:
            return new_files[0], cookie_status(cookie_source)
    return None


def try_ytdlp_audio(
    url: str,
    audio_dir: Path,
    cookie_sources: list[str | None],
) -> tuple[Path, str] | None:
    audio_dir.mkdir(parents=True, exist_ok=True)
    for cookie_source in cookie_sources:
        before = set(audio_dir.glob("*"))
        result = run(
            build_ytdlp_invocation(
                [
                    "-f",
                    "bestaudio/best",
                    "-x",
                    "--audio-format",
                    "mp3",
                    "-o",
                    str(audio_dir / "%(id)s.%(ext)s"),
                    url,
                ],
                cookies_from_browser=cookie_source,
            )
        )
        after = set(audio_dir.glob("*.mp3"))
        new_files = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)
        if result.returncode == 0 and new_files:
            return new_files[0], cookie_status(cookie_source)
    return None


def try_ytdlp_video(
    url: str,
    video_dir: Path,
    cookie_sources: list[str | None],
) -> tuple[Path, str] | None:
    video_dir.mkdir(parents=True, exist_ok=True)
    for cookie_source in cookie_sources:
        before = set(video_dir.glob("*.mp4"))
        result = run(
            build_ytdlp_invocation(
                [
                    "-f",
                    "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
                    "--merge-output-format",
                    "mp4",
                    "-o",
                    str(video_dir / "%(id)s.%(ext)s"),
                    url,
                ],
                cookies_from_browser=cookie_source,
            )
        )
        after = set(video_dir.glob("*.mp4"))
        new_files = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)
        if result.returncode == 0 and new_files:
            return new_files[0], cookie_status(cookie_source)
    return None


def probe_duration_sec(video_path: Path) -> int | None:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
    )
    if result.returncode != 0:
        return None
    try:
        return int(float(result.stdout.strip()))
    except ValueError:
        return None


def transcribe_audio(audio_path: Path, transcript_path: Path, model_name: str) -> Path | None:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(audio_path), vad_filter=True)
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for segment in segments:
        text = " ".join(segment.text.split())
        if not text:
            continue
        lines.append(
            {
                "start_sec": float(segment.start),
                "end_sec": float(segment.end),
                "text": text,
            }
        )
    transcript_path.write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n",
        encoding="utf-8",
    )
    return transcript_path


def record_source(manifest: list[dict], name: str, status: str, path: Path | None = None) -> None:
    manifest.append(
        {
            "name": name,
            "status": status,
            "path": str(path) if path else None,
        }
    )


def choose_primary_transcript(candidates: list[tuple[str, Path]]) -> tuple[str, Path] | None:
    priority = {
        "manual_captions": 0,
        "auto_captions": 1,
        "whisper_audio": 2,
        "whisper_video": 3,
        "user_provided": 4,
    }
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: priority.get(item[0], 99))[0]


def read_jsonl_transcript(path: Path) -> list[TranscriptSegment]:
    segments = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        segments.append(
            TranscriptSegment(
                start_sec=float(row["start_sec"]),
                end_sec=float(row["end_sec"]),
                text=str(row["text"]),
            )
        )
    return segments


def video_id_from_audio(audio_path: Path) -> str:
    return audio_path.stem


def write_unavailable(
    *,
    json_output: Path,
    markdown_output: Path,
    url: str,
    attempted: list[str],
    requirement: str,
    output_kind: str,
    question: str | None,
    topic: str | None,
    metadata: dict | None = None,
    source_manifest: list[dict] | None = None,
) -> None:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "url": url,
        "status": "source_unavailable",
        "attempted": attempted,
        "next_step": choose_next_source_step(attempted),
        "requirement": requirement,
        "output_kind": output_kind,
        "question": question,
        "topic": topic,
        "metadata": compact_metadata(metadata) if metadata else None,
        "source_manifest": source_manifest or [],
        "message": "Provide transcript/audio/video file or use an indexed public transcript/summary fallback.",
    }
    json_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    metadata_section = render_metadata_section(metadata) if metadata else ""
    source_lines = render_source_manifest(source_manifest or [])
    result_text = (
        "I could not acquire a transcript, audio, or video source for this request. "
        "Metadata may be shown below for identification and debugging, but metadata "
        "alone is not a video source and must not be used to summarize, answer questions, or extract rules from "
        "the video."
    )
    next_steps = (
        "- Provide a local video, audio, `.vtt`, `.srt`, or `.txt` file.\n"
        "- Try a public indexed transcript/summary fallback and clearly mark it as such.\n"
        "- Re-run in an environment where YouTube media/caption access is available."
    )
    markdown_output.write_text(
        f"""# Video Distillation: Source Unavailable

## Source

- URL: {url}
- Status: source_unavailable
- Attempted: {", ".join(attempted) if attempted else "none"}

## User Request

- Output kind: {output_kind}
- Requirement: {requirement}
{f"- Question: {question}" if question else ""}
{f"- Topic: {topic}" if topic else ""}

## Acquisition Manifest

{source_lines}

## Result

{result_text}

{metadata_section}

## Next Steps

{next_steps}
""",
        encoding="utf-8",
    )


def compact_metadata(metadata: dict | None) -> dict:
    if not metadata:
        return {}
    return {
        "id": metadata.get("id"),
        "title": metadata.get("title"),
        "channel": metadata.get("channel") or metadata.get("uploader"),
        "duration": metadata.get("duration"),
        "upload_date": metadata.get("upload_date"),
        "webpage_url": metadata.get("webpage_url"),
        "chapters": metadata.get("chapters") or [],
        "description": metadata.get("description"),
    }


def render_metadata_section(metadata: dict | None) -> str:
    if not metadata:
        return ""
    title = metadata.get("title") or "Unknown"
    channel = metadata.get("channel") or metadata.get("uploader") or "Unknown"
    duration = metadata.get("duration")
    upload_date = metadata.get("upload_date") or "Unknown"
    description = (metadata.get("description") or "").strip()
    chapters = metadata.get("chapters") or []
    tags = metadata.get("tags") or []

    chapter_lines = "\n".join(
        f"- `{seconds_to_hhmmss(chapter.get('start_time', 0))}` {chapter.get('title', '').strip()}"
        for chapter in chapters[:30]
        if chapter.get("title")
    )
    if not chapter_lines:
        chapter_lines = "- No chapters found in metadata."

    tag_line = ", ".join(tags[:20]) if tags else "None found"
    description_excerpt = description[:3000] if description else "No description found."

    return f"""## Metadata-Only Evidence

- Title: {title}
- Channel: {channel}
- Duration: {duration if duration is not None else "unknown"} seconds
- Upload date: {upload_date}
- Tags: {tag_line}

### Description Excerpt

{description_excerpt}

### Chapters

{chapter_lines}

### Diagnostic Note

This metadata is included only so the user can verify the video identity and
debug source acquisition. Do not use it as a substitute for transcript, audio,
or video evidence.
"""


def render_source_manifest(source_manifest: list[dict]) -> str:
    if not source_manifest:
        return "- No acquisition steps were recorded."
    lines = []
    for item in source_manifest:
        path = f" `{item['path']}`" if item.get("path") else ""
        lines.append(f"- {item.get('name', 'unknown')}: {item.get('status', 'unknown')}{path}")
    return "\n".join(lines)


def seconds_to_hhmmss(value) -> str:
    total = int(float(value or 0))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a timestamp-grounded video distillation shell from a YouTube URL or local source."
    )
    parser.add_argument("--url", help="YouTube video URL")
    parser.add_argument("--input", type=Path, help="Local .vtt/.srt/.txt transcript")
    parser.add_argument("--title", default="Untitled YouTube Video")
    parser.add_argument(
        "--requirement",
        default="Summarize the video.",
        help="What the user wants extracted or answered from the video.",
    )
    parser.add_argument(
        "--output-kind",
        choices=["summary", "qa", "topic", "tutorial", "strategy", "claims", "notes", "custom"],
        default="summary",
    )
    parser.add_argument("--question", help="Specific question to answer from the video")
    parser.add_argument("--topic", help="Specific topic to extract from the video")
    parser.add_argument("--output", type=Path, default=Path("data/summaries/summary.md"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--audio-dir", type=Path, default=Path("data/audio"))
    parser.add_argument("--video-dir", type=Path, default=Path("data/video"))
    parser.add_argument("--frames-dir", type=Path, default=Path("data/frames"))
    parser.add_argument("--transcript-dir", type=Path, default=Path("data/transcripts"))
    parser.add_argument(
        "--cookies-from-browser",
        default="auto",
        help=(
            "Browser name for yt-dlp cookies. Defaults to auto, which tries no cookies "
            "then chrome, safari, firefox, edge, brave, and chromium. Use none to disable."
        ),
    )
    parser.add_argument(
        "--sub-langs",
        default=DEFAULT_SUB_LANGS,
        help="yt-dlp subtitle language selector. Defaults to English and Chinese captions.",
    )
    parser.add_argument("--whisper-model", default="small.en")
    parser.add_argument("--force-whisper", action="store_true")
    parser.add_argument("--video-input", type=Path, help="Local video file for visual evidence")
    parser.add_argument("--duration-sec", type=int, help="Video duration if ffprobe is unavailable")
    parser.add_argument("--frame-interval-sec", type=int, default=10)
    parser.add_argument(
        "--no-video-understanding",
        action="store_true",
        help="Allow transcript-only output. Not recommended for trading videos.",
    )
    args = parser.parse_args()

    if not args.url and not args.input and not args.video_input:
        parser.error("Provide --url, --input, or --video-input")

    cookie_sources = cookie_candidates(args.cookies_from_browser)

    metadata = fetch_metadata(args.url, cookie_sources) if args.url else None
    if metadata and args.url:
        args.title = metadata_title(metadata, args.title)
        args.url = metadata_video_url(metadata, args.url)

    attempted: list[str] = []
    source_manifest: list[dict] = []
    transcript_candidates: list[tuple[str, Path]] = []
    transcript_path = None
    transcript_source = "missing"
    segments: list[TranscriptSegment] = []
    visual_required = not args.no_video_understanding
    video_path = args.video_input

    if metadata:
        record_source(source_manifest, "metadata", "available")

    if args.input:
        if is_media_file(str(args.input)):
            record_source(source_manifest, "user_media", "available", args.input)
            media_transcript = transcribe_audio(
                args.input,
                args.transcript_dir / f"{args.input.stem}.jsonl",
                args.whisper_model,
            )
            if media_transcript is not None:
                record_source(source_manifest, "user_media_whisper", "available", media_transcript)
                transcript_candidates.append(("user_provided", media_transcript))
            else:
                record_source(source_manifest, "user_media_whisper", "unavailable")
            if args.input.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"} and video_path is None:
                video_path = args.input
        else:
            record_source(source_manifest, "user_transcript", "available", args.input)
            transcript_candidates.append(("user_provided", args.input))

    if video_path is not None:
        record_source(source_manifest, "user_video", "available", video_path)

    if args.url:
        for step in acquisition_plan(visual_required):
            attempted.append(step)
            if step == "manual_captions":
                if args.force_whisper:
                    record_source(source_manifest, step, "skipped_force_whisper")
                    continue
                manual_path = try_ytdlp_captions(
                    args.url,
                    args.raw_dir,
                    auto=False,
                    sub_langs=args.sub_langs,
                    cookie_sources=cookie_sources,
                )
                if manual_path is not None:
                    path, status = manual_path
                    record_source(source_manifest, step, f"available_{status}", path)
                    transcript_candidates.append(("manual_captions", path))
                else:
                    record_source(source_manifest, step, "unavailable_after_cookie_fallbacks")

            elif step == "auto_captions":
                if args.force_whisper:
                    record_source(source_manifest, step, "skipped_force_whisper")
                    continue
                auto_path = try_ytdlp_captions(
                    args.url,
                    args.raw_dir,
                    auto=True,
                    sub_langs=args.sub_langs,
                    cookie_sources=cookie_sources,
                )
                if auto_path is not None:
                    path, status = auto_path
                    record_source(source_manifest, step, f"available_{status}", path)
                    transcript_candidates.append(("auto_captions", path))
                else:
                    record_source(source_manifest, step, "unavailable_after_cookie_fallbacks")

            elif step == "audio_download":
                audio_path = try_ytdlp_audio(
                    args.url,
                    args.audio_dir,
                    cookie_sources=cookie_sources,
                )
                if audio_path is not None:
                    audio_path, status = audio_path
                    record_source(source_manifest, step, f"available_{status}", audio_path)
                    audio_transcript = transcribe_audio(
                        audio_path,
                        args.transcript_dir / f"{video_id_from_audio(audio_path)}.jsonl",
                        args.whisper_model,
                    )
                    if audio_transcript is not None:
                        record_source(source_manifest, "whisper_audio", "available", audio_transcript)
                        transcript_candidates.append(("whisper_audio", audio_transcript))
                    else:
                        record_source(source_manifest, "whisper_audio", "unavailable")
                else:
                    record_source(source_manifest, step, "unavailable_after_cookie_fallbacks")

            elif step == "video_download":
                video_status = None
                if video_path is None:
                    video_result = try_ytdlp_video(
                        args.url,
                        args.video_dir,
                        cookie_sources=cookie_sources,
                    )
                    if video_result is not None:
                        video_path, video_status = video_result
                    else:
                        video_status = None
                if video_path is not None:
                    record_source(
                        source_manifest,
                        step,
                        f"available_{video_status}" if video_status else "available_user_video",
                        video_path,
                    )
                    if not any(source == "whisper_audio" for source, _ in transcript_candidates):
                        video_transcript = transcribe_audio(
                            video_path,
                            args.transcript_dir / f"{video_path.stem}.jsonl",
                            args.whisper_model,
                        )
                        if video_transcript is not None:
                            record_source(source_manifest, "whisper_video", "available", video_transcript)
                            transcript_candidates.append(("whisper_video", video_transcript))
                        else:
                            record_source(source_manifest, "whisper_video", "unavailable")
                else:
                    record_source(source_manifest, step, "unavailable_after_cookie_fallbacks")

    primary_transcript = choose_primary_transcript(transcript_candidates)
    if primary_transcript is not None:
        transcript_source, transcript_path = primary_transcript

    if args.url and transcript_path is None and video_path is None:
        write_unavailable(
            json_output=args.output.with_suffix(".source_unavailable.json"),
            markdown_output=args.output,
            url=args.url,
            attempted=attempted,
            requirement=args.requirement,
            output_kind=args.output_kind,
            question=args.question,
            topic=args.topic,
            metadata=metadata,
            source_manifest=source_manifest,
        )
        print(
            "No captions/audio/video source was available. Provide a local video, audio, "
            "caption, or transcript file.",
            file=sys.stderr,
        )
        return 2

    if transcript_path is None and video_path is None:
        write_unavailable(
            json_output=args.output.with_suffix(".source_unavailable.json"),
            markdown_output=args.output,
            url=args.url or str(args.input or args.video_input),
            attempted=attempted,
            requirement=args.requirement,
            output_kind=args.output_kind,
            question=args.question,
            topic=args.topic,
            metadata=metadata,
            source_manifest=source_manifest,
        )
        return 2

    if transcript_path is not None:
        if transcript_path.suffix.lower() == ".jsonl":
            segments = read_jsonl_transcript(transcript_path)
            parsed_source = transcript_source
        else:
            segments, parsed_source = read_transcript(transcript_path)
        if transcript_source == "user_provided":
            transcript_source = parsed_source
    else:
        transcript_source = "missing"

    visual_manifest = None
    if video_path is not None and visual_required:
        duration_sec = args.duration_sec or probe_duration_sec(video_path)
        if duration_sec is None and segments:
            duration_sec = int(max(segment.end_sec for segment in segments))
        if duration_sec is not None:
            timestamps = plan_frame_samples(
                duration_sec=duration_sec,
                interval_sec=args.frame_interval_sec,
                transcript=segments,
            )
            frame_root = args.frames_dir / video_path.stem
            frames = extract_frames(
                video=video_path,
                output_dir=frame_root,
                timestamps=timestamps,
            )
            record_source(source_manifest, "sampled_frames", "available" if frames else "unavailable", frame_root)
            visual_manifest = render_visual_manifest(
                video_path=video_path,
                frames=frames,
                source="local_video" if args.video_input else "downloaded_video",
            )
            manifest_path = frame_root / "visual_manifest.json"
            manifest_path.write_text(
                json.dumps(visual_manifest, indent=2) + "\n",
                encoding="utf-8",
            )

    markdown = render_markdown_summary_shell(
        title=args.title,
        url=args.url or str(args.input),
        transcript_source=transcript_source,
        segments=segments,
        visual_manifest=visual_manifest,
        visual_required=visual_required,
        requirement=args.requirement,
        output_kind=args.output_kind,
        question=args.question,
        topic=args.topic,
        acquisition_manifest=source_manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
