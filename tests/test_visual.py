from pathlib import Path

from youtube_distiller.transcript import TranscriptSegment
from youtube_distiller.visual import (
    build_ffmpeg_frame_command,
    plan_frame_samples,
    render_visual_manifest,
)


def test_plan_frame_samples_uses_regular_interval_and_dense_strategy_cues():
    segments = [
        TranscriptSegment(0, 4, "Welcome to the training."),
        TranscriptSegment(62, 70, "Look here at this entry above the premarket high."),
        TranscriptSegment(180, 188, "The stop loss goes under this candle."),
    ]

    samples = plan_frame_samples(duration_sec=240, interval_sec=60, transcript=segments)

    assert 0 in samples
    assert 60 in samples
    assert 120 in samples
    assert 180 in samples
    assert 57 in samples
    assert 62 in samples
    assert 67 in samples
    assert 175 in samples
    assert 180 in samples
    assert 185 in samples


def test_build_ffmpeg_frame_command_maps_timestamps_to_output_names():
    command = build_ffmpeg_frame_command(
        video=Path("video.mp4"),
        output_dir=Path("frames"),
        timestamp_sec=67,
    )

    assert command[:4] == ["ffmpeg", "-y", "-ss", "67"]
    assert command[-1] == "frames/frame_000067.jpg"


def test_render_visual_manifest_marks_required_visual_evidence():
    manifest = render_visual_manifest(
        video_path=Path("data/video/oKlhUSSHe2Q.mp4"),
        frames=[Path("data/frames/oKlhUSSHe2Q/frame_000067.jpg")],
        source="downloaded_video",
    )

    assert manifest["visual_evidence_required"] is True
    assert manifest["source"] == "downloaded_video"
    assert manifest["frames"][0]["timestamp_sec"] == 67
