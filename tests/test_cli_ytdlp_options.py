import importlib.util
from pathlib import Path
import subprocess


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "summarize_video.py"
SPEC = importlib.util.spec_from_file_location("summarize_video", SCRIPT_PATH)
summarize_video = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(summarize_video)


def test_ytdlp_invocation_can_include_browser_cookies(monkeypatch):
    monkeypatch.setattr(summarize_video, "ytdlp_command", lambda: ["yt-dlp"])

    command = summarize_video.build_ytdlp_invocation(
        ["--dump-json", "--skip-download", "https://youtube.test/watch?v=abc"],
        cookies_from_browser="chrome",
    )

    assert command == [
        "yt-dlp",
        "--cookies-from-browser",
        "chrome",
        "--dump-json",
        "--skip-download",
        "https://youtube.test/watch?v=abc",
    ]


def test_caption_command_defaults_to_english_and_chinese_subtitles(monkeypatch, tmp_path):
    monkeypatch.setattr(summarize_video, "ytdlp_command", lambda: ["yt-dlp"])

    command = summarize_video.build_caption_command(
        url="https://youtube.test/watch?v=abc",
        raw_dir=tmp_path,
        auto=True,
        sub_langs=summarize_video.DEFAULT_SUB_LANGS,
        cookies_from_browser="chrome",
    )

    assert "--write-auto-subs" in command
    assert command[command.index("--sub-langs") + 1] == "en.*,zh.*"
    assert command[1:3] == ["--cookies-from-browser", "chrome"]


def test_default_cookie_candidates_try_no_cookies_then_common_browsers():
    assert summarize_video.cookie_candidates("auto") == [
        None,
        "chrome",
        "safari",
        "firefox",
        "edge",
        "brave",
        "chromium",
    ]


def test_caption_acquisition_retries_with_browser_cookies(monkeypatch, tmp_path):
    monkeypatch.setattr(summarize_video, "ytdlp_command", lambda: ["yt-dlp"])
    calls = []

    def fake_run(command):
        calls.append(command)
        if "--cookies-from-browser" in command:
            output = tmp_path / "abc.zh.vtt"
            output.write_text("WEBVTT\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "blocked")

    monkeypatch.setattr(summarize_video, "run", fake_run)

    result = summarize_video.try_ytdlp_captions(
        "https://youtube.test/watch?v=abc",
        tmp_path,
        auto=False,
        sub_langs=summarize_video.DEFAULT_SUB_LANGS,
        cookie_sources=[None, "chrome"],
    )

    assert result == (tmp_path / "abc.zh.vtt", "via_chrome_cookies")
    assert "--cookies-from-browser" not in calls[0]
    assert calls[1][1:3] == ["--cookies-from-browser", "chrome"]


def test_unavailable_report_does_not_make_sufficiency_claims(tmp_path):
    output = tmp_path / "summary.md"
    summarize_video.write_unavailable(
        json_output=tmp_path / "summary.source_unavailable.json",
        markdown_output=output,
        url="https://youtube.test/watch?v=abc",
        attempted=["manual_captions", "auto_captions", "audio_download", "video_download"],
        requirement="Summarize accurately.",
        output_kind="summary",
        question=None,
        topic=None,
        source_manifest=[],
    )

    text = output.read_text(encoding="utf-8").lower()
    assert ("en" + "ough") not in text
    assert "could not acquire a transcript, audio, or video source" in text
