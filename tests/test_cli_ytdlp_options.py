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


def test_ytdlp_invocation_can_include_youtube_player_client(monkeypatch):
    monkeypatch.setattr(summarize_video, "ytdlp_command", lambda: ["yt-dlp"])

    command = summarize_video.build_ytdlp_invocation(
        ["-f", "18", "https://youtube.test/watch?v=abc"],
        player_client="android",
    )

    assert command == [
        "yt-dlp",
        "--extractor-args",
        "youtube:player_client=android",
        "-f",
        "18",
        "https://youtube.test/watch?v=abc",
    ]


def test_media_attempts_try_cookie_paths_then_android_without_cookies():
    assert summarize_video.media_attempt_candidates([None, "chrome"]) == [
        (None, None),
        ("chrome", None),
        (None, "android"),
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


def test_video_download_falls_back_to_android_client_without_cookies(monkeypatch, tmp_path):
    monkeypatch.setattr(summarize_video, "ytdlp_command", lambda: ["yt-dlp"])
    calls = []

    def fake_run(command):
        calls.append(command)
        if "youtube:player_client=android" in command:
            output = tmp_path / "abc.mp4"
            output.write_text("video", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "HTTP Error 403: Forbidden")

    monkeypatch.setattr(summarize_video, "run", fake_run)

    result = summarize_video.try_ytdlp_video(
        "https://youtube.test/watch?v=abc",
        tmp_path,
        cookie_sources=[None, "chrome"],
    )

    assert result == (tmp_path / "abc.mp4", "via_android_client_without_browser_cookies")
    assert "--cookies-from-browser" not in calls[0]
    assert calls[1][1:3] == ["--cookies-from-browser", "chrome"]
    assert "--cookies-from-browser" not in calls[2]
    assert calls[2][1:3] == ["--extractor-args", "youtube:player_client=android"]


def test_audio_download_uses_same_android_client_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(summarize_video, "ytdlp_command", lambda: ["yt-dlp"])
    calls = []

    def fake_run(command):
        calls.append(command)
        if "youtube:player_client=android" in command:
            output = tmp_path / "abc.mp3"
            output.write_text("audio", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "HTTP Error 403: Forbidden")

    monkeypatch.setattr(summarize_video, "run", fake_run)

    result = summarize_video.try_ytdlp_audio(
        "https://youtube.test/watch?v=abc",
        tmp_path,
        cookie_sources=["chrome"],
    )

    assert result == (tmp_path / "abc.mp3", "via_android_client_without_browser_cookies")
    assert calls[0][1:3] == ["--cookies-from-browser", "chrome"]
    assert "--cookies-from-browser" not in calls[1]
    assert calls[1][1:3] == ["--extractor-args", "youtube:player_client=android"]


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
