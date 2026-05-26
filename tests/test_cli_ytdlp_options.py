import importlib.util
from pathlib import Path


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
