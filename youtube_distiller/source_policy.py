SOURCE_ORDER = ("manual_captions", "auto_captions", "audio_download", "video_download")
MEDIA_EXTENSIONS = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".mp4", ".mov", ".mkv", ".webm"}


def choose_next_source_step(attempted):
    attempted_set = set(attempted)
    for step in SOURCE_ORDER:
        if step not in attempted_set:
            return step
    return "user_artifact"


def acquisition_plan(visual_required: bool) -> list[str]:
    steps = ["manual_captions", "auto_captions", "audio_download"]
    if visual_required:
        steps.append("video_download")
    return steps


def is_media_file(path_or_name: str) -> bool:
    lower = path_or_name.lower()
    return any(lower.endswith(extension) for extension in MEDIA_EXTENSIONS)
