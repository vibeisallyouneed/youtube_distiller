from youtube_distiller.source_policy import (
    acquisition_plan,
    choose_next_source_step,
    is_media_file,
)


def test_source_policy_tries_captions_before_audio():
    assert choose_next_source_step([]) == "manual_captions"
    assert choose_next_source_step(["manual_captions"]) == "auto_captions"
    assert choose_next_source_step(["manual_captions", "auto_captions"]) == "audio_download"
    assert (
        choose_next_source_step(["manual_captions", "auto_captions", "audio_download"])
        == "video_download"
    )


def test_source_policy_requests_user_artifact_after_all_automatic_sources_fail():
    assert (
        choose_next_source_step(
            ["manual_captions", "auto_captions", "audio_download", "video_download"]
        )
        == "user_artifact"
    )


def test_media_file_detection_covers_audio_and_video_inputs():
    assert is_media_file("lesson.mp3")
    assert is_media_file("chart_walkthrough.mp4")
    assert not is_media_file("captions.vtt")


def test_acquisition_plan_gathers_all_possible_video_sources_before_distillation():
    assert acquisition_plan(visual_required=True) == [
        "manual_captions",
        "auto_captions",
        "audio_download",
        "video_download",
    ]
    assert acquisition_plan(visual_required=False) == [
        "manual_captions",
        "auto_captions",
        "audio_download",
    ]
