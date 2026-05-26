from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
import shutil
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
        start = max(0, int(segment.start_sec))
        midpoint = max(0, int((segment.start_sec + segment.end_sec) / 2))
        end = min(duration_sec, int(segment.end_sec))
        samples.update([start, midpoint, end])

        if not VISUAL_CUE_RE.search(segment.text):
            continue
        start = max(0, int(segment.start_sec) - 5)
        mid = max(0, int(segment.start_sec))
        after_cue = min(duration_sec, int(segment.start_sec) + 5)
        after_segment = min(duration_sec, int(segment.end_sec) + 5)
        samples.update([start, mid, after_cue, after_segment])

    return sorted(samples)


def build_ffmpeg_scene_detect_command(
    *,
    video: Path,
    threshold: float = 0.3,
) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(video),
        "-vf",
        f"select='gt(scene,{threshold})',showinfo",
        "-f",
        "null",
        "-",
    ]


def parse_scene_change_timestamps(output: str, max_scenes: int = 500) -> list[int]:
    timestamps = []
    seen = set()
    for match in re.finditer(r"pts_time:(?P<timestamp>\d+(?:\.\d+)?)", output):
        timestamp = int(float(match.group("timestamp")))
        if timestamp in seen:
            continue
        timestamps.append(timestamp)
        seen.add(timestamp)
        if len(timestamps) >= max_scenes:
            break
    return sorted(timestamps)


def detect_scene_change_timestamps(
    *,
    video: Path,
    threshold: float = 0.3,
    max_scenes: int = 500,
) -> list[int]:
    command = build_ffmpeg_scene_detect_command(video=video, threshold=threshold)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []
    return parse_scene_change_timestamps(result.stderr, max_scenes=max_scenes)


def frame_reason_map(
    *,
    timestamps: list[int],
    interval_sec: int,
    transcript: list[TranscriptSegment] | None,
    scene_timestamps: list[int],
) -> dict[int, list[str]]:
    reasons = {timestamp: [] for timestamp in timestamps}

    for timestamp in timestamps:
        if interval_sec > 0 and timestamp % interval_sec == 0:
            reasons[timestamp].append("dense_interval")
        if timestamp in scene_timestamps:
            reasons[timestamp].append("scene_change")

    for segment in transcript or []:
        boundary_points = {
            max(0, int(segment.start_sec)),
            max(0, int((segment.start_sec + segment.end_sec) / 2)),
            int(segment.end_sec),
        }
        cue_points = set()
        if VISUAL_CUE_RE.search(segment.text):
            cue_points.update(
                {
                    max(0, int(segment.start_sec) - 5),
                    max(0, int(segment.start_sec)),
                    int(segment.start_sec) + 5,
                    int(segment.end_sec) + 5,
                }
            )
        for timestamp in timestamps:
            if timestamp in boundary_points:
                reasons[timestamp].append("transcript_boundary")
            if timestamp in cue_points:
                reasons[timestamp].append("visual_cue")

    return {
        timestamp: sorted(set(reason_list)) or ["selected"]
        for timestamp, reason_list in reasons.items()
    }


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


def ocr_engine_available() -> bool:
    return shutil.which("tesseract") is not None


def extract_text_from_frame(
    *,
    frame: Path,
    languages: str = "eng+chi_sim+chi_tra",
) -> str | None:
    if not ocr_engine_available():
        return None

    language_candidates = [languages]
    if languages != "eng":
        language_candidates.append("eng")

    for language in language_candidates:
        result = subprocess.run(
            ["tesseract", str(frame), "stdout", "-l", language, "--psm", "6"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            continue
        text = re.sub(r"\s+", " ", result.stdout).strip()
        if text:
            return text
    return None


def extract_ocr_text(
    *,
    frames: list[Path],
    languages: str = "eng+chi_sim+chi_tra",
    workers: int = 4,
) -> dict[Path, str]:
    ocr_text: dict[Path, str] = {}
    if workers <= 1:
        for frame in frames:
            text = extract_text_from_frame(frame=frame, languages=languages)
            if text:
                ocr_text[frame] = text
        return ocr_text

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(extract_text_from_frame, frame=frame, languages=languages): frame
            for frame in frames
        }
        for future in as_completed(futures):
            frame = futures[future]
            text = future.result()
            if text:
                ocr_text[frame] = text
    return ocr_text


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
    frame_reasons: dict[Path, list[str]] | None = None,
    ocr_text_by_frame: dict[Path, str] | None = None,
) -> dict:
    return {
        "visual_evidence_required": True,
        "source": source,
        "video_path": str(video_path),
        "frames": [
            {
                "timestamp_sec": timestamp_from_frame_path(frame),
                "path": str(frame),
                "reasons": (frame_reasons or {}).get(frame, []),
                "ocr_text": (ocr_text_by_frame or {}).get(frame),
                "vision_notes": None,
            }
            for frame in frames
        ],
    }
