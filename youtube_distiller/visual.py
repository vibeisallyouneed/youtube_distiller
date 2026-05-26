from __future__ import annotations

from pathlib import Path
import re
import subprocess

from youtube_distiller.transcript import TranscriptSegment


VISUAL_CUE_RE = re.compile(
    r"\b("
    r"look|see here|right here|this candle|this chart|this setup|entry|exit|"
    r"stop|stop loss|target|take profit|premarket high|breakout|break down|"
    r"support|resistance|trendline|vwap|ema|moving average|rsi|macd"
    r")\b",
    re.IGNORECASE,
)


def plan_frame_samples(
    *,
    duration_sec: int,
    interval_sec: int = 10,
    transcript: list[TranscriptSegment] | None = None,
) -> list[int]:
    samples = set(range(0, max(duration_sec, 0) + 1, interval_sec))

    for segment in transcript or []:
        if not VISUAL_CUE_RE.search(segment.text):
            continue
        start = max(0, int(segment.start_sec) - 5)
        mid = max(0, int(segment.start_sec))
        after_cue = min(duration_sec, int(segment.start_sec) + 5)
        after_segment = min(duration_sec, int(segment.end_sec) + 5)
        samples.update([start, mid, after_cue, after_segment])

    return sorted(samples)


def build_ffmpeg_frame_command(
    *,
    video: Path,
    output_dir: Path,
    timestamp_sec: int,
) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-ss",
        str(timestamp_sec),
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_dir / f"frame_{timestamp_sec:06d}.jpg"),
    ]


def extract_frames(
    *,
    video: Path,
    output_dir: Path,
    timestamps: list[int],
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    for timestamp_sec in timestamps:
        output_path = output_dir / f"frame_{timestamp_sec:06d}.jpg"
        command = build_ffmpeg_frame_command(
            video=video,
            output_dir=output_dir,
            timestamp_sec=timestamp_sec,
        )
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode == 0 and output_path.exists():
            frames.append(output_path)
    return frames


def timestamp_from_frame_path(path: Path) -> int:
    match = re.search(r"frame_(\d+)\.jpg$", path.name)
    if match is None:
        return 0
    return int(match.group(1))


def render_visual_manifest(
    *,
    video_path: Path,
    frames: list[Path],
    source: str,
) -> dict:
    return {
        "visual_evidence_required": True,
        "source": source,
        "video_path": str(video_path),
        "frames": [
            {
                "timestamp_sec": timestamp_from_frame_path(frame),
                "path": str(frame),
                "ocr_text": None,
                "vision_notes": None,
            }
            for frame in frames
        ],
    }
