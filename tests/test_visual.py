from pathlib import Path

from youtube_distiller.transcript import TranscriptSegment
from youtube_distiller.visual import (
    build_ffmpeg_frame_command,
    build_ffmpeg_scene_detect_command,
    parse_scene_change_timestamps,
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


def test_plan_frame_samples_covers_transcript_boundaries_without_keyword_cues():
    segments = [
        TranscriptSegment(13, 18, "The rule is shown on screen now."),
        TranscriptSegment(41, 46, "Then change the risk parameter to two percent."),
    ]

    samples = plan_frame_samples(duration_sec=60, interval_sec=30, transcript=segments)

    assert 13 in samples
    assert 15 in samples
    assert 18 in samples
    assert 41 in samples
    assert 43 in samples
    assert 46 in samples


def test_build_ffmpeg_frame_command_maps_timestamps_to_output_names():
    command = build_ffmpeg_frame_command(
        video=Path("video.mp4"),
        output_dir=Path("frames"),
        timestamp_sec=67,
    )

    assert command[:4] == ["ffmpeg", "-y", "-ss", "67"]
    assert command[-1] == "frames/frame_000067.jpg"


def test_build_ffmpeg_scene_detect_command_uses_showinfo():
    command = build_ffmpeg_scene_detect_command(
        video=Path("video.mp4"),
        threshold=0.32,
    )

    assert command[:3] == ["ffmpeg", "-hide_banner", "-i"]
    assert "select='gt(scene,0.32)',showinfo" in command
    assert command[-2:] == ["null", "-"]


def test_parse_scene_change_timestamps_deduplicates_to_seconds():
    output = """
    [Parsed_showinfo_1 @ 0x1] n:1 pts:13000 pts_time:13.000 pos:0
    [Parsed_showinfo_1 @ 0x1] n:2 pts:13300 pts_time:13.300 pos:0
    [Parsed_showinfo_1 @ 0x1] n:3 pts:41200 pts_time:41.200 pos:0
    """

    assert parse_scene_change_timestamps(output) == [13, 41]


def test_render_visual_manifest_marks_required_visual_evidence():
    manifest = render_visual_manifest(
        video_path=Path("data/video/oKlhUSSHe2Q.mp4"),
        frames=[Path("data/frames/oKlhUSSHe2Q/frame_000067.jpg")],
        source="downloaded_video",
        frame_reasons={
            Path("data/frames/oKlhUSSHe2Q/frame_000067.jpg"): ["scene_change", "transcript_boundary"],
        },
        ocr_text_by_frame={
            Path("data/frames/oKlhUSSHe2Q/frame_000067.jpg"): "Entry above VWAP; stop below low.",
        },
    )

    assert manifest["visual_evidence_required"] is True
    assert manifest["source"] == "downloaded_video"
    assert manifest["frames"][0]["timestamp_sec"] == 67
    assert manifest["frames"][0]["reasons"] == ["scene_change", "transcript_boundary"]
    assert manifest["frames"][0]["ocr_text"] == "Entry above VWAP; stop below low."
