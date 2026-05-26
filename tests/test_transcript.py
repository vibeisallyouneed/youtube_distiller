from youtube_distiller.transcript import parse_srt, parse_vtt, render_markdown_summary_shell


def test_parse_vtt_deduplicates_youtube_caption_overlap():
    vtt = """WEBVTT

00:00:01.000 --> 00:00:03.000
Today we're talking about risk management

00:00:02.000 --> 00:00:04.000
risk management for day trading

00:00:10.000 --> 00:00:12.000
Always prove profitability in a simulator first.
"""

    segments = parse_vtt(vtt)

    assert [s.text for s in segments] == [
        "Today we're talking about risk management",
        "risk management for day trading",
        "Always prove profitability in a simulator first.",
    ]
    assert segments[0].start_sec == 1.0
    assert segments[-1].start_sec == 10.0


def test_parse_srt_preserves_timestamps():
    srt = """1
00:00:01,000 --> 00:00:03,500
Use a trading simulator before risking real money.

2
00:00:04,000 --> 00:00:06,000
Write down your entry, exit, and risk.
"""

    segments = parse_srt(srt)

    assert [s.text for s in segments] == [
        "Use a trading simulator before risking real money.",
        "Write down your entry, exit, and risk.",
    ]
    assert segments[0].start_sec == 1.0
    assert segments[0].end_sec == 3.5


def test_markdown_shell_marks_source_and_requires_grounding():
    segments = parse_vtt(
        """WEBVTT

00:00:01.000 --> 00:00:05.000
Use a trading simulator before risking real money.
"""
    )

    markdown = render_markdown_summary_shell(
        title="How To Start Day Trading in 2026 (full training)",
        url="https://www.youtube.com/watch?v=oKlhUSSHe2Q",
        transcript_source="auto_captions",
        segments=segments,
    )

    assert "Transcript source: auto_captions" in markdown
    assert "Do not finalize strategy rules without timestamped evidence" in markdown
    assert "00:00:01" in markdown


def test_markdown_shell_marks_partial_when_required_visual_evidence_is_missing():
    segments = parse_vtt(
        """WEBVTT

00:00:01.000 --> 00:00:05.000
Look here at this chart setup.
"""
    )

    markdown = render_markdown_summary_shell(
        title="Chart Strategy",
        url="https://www.youtube.com/watch?v=abc",
        transcript_source="manual_captions",
        segments=segments,
        visual_required=True,
        visual_manifest=None,
    )

    assert "Distillation status: partial_missing_required_visual_evidence" in markdown
    assert "Do not present this as a complete video distillation" in markdown
    assert "Visual evidence: missing_required" in markdown


def test_markdown_shell_marks_complete_when_required_visual_evidence_exists():
    segments = parse_vtt(
        """WEBVTT

00:00:01.000 --> 00:00:05.000
Look here at this chart setup.
"""
    )

    markdown = render_markdown_summary_shell(
        title="Chart Strategy",
        url="https://www.youtube.com/watch?v=abc",
        transcript_source="manual_captions",
        segments=segments,
        visual_required=True,
        visual_manifest={
            "frames": [
                {
                    "timestamp_sec": 1,
                    "path": "frames/frame_000001.jpg",
                }
            ]
        },
    )

    assert "Distillation status: complete_with_visual_evidence" in markdown
    assert "Visual evidence: available" in markdown
