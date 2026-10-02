"""Contract tests for ScreenCaptureResult — every OS/PIL/mss/vision boundary is mocked.

No real screen, camera, window manager, or Gemini session is touched.
"""

import io

import pytest


@pytest.fixture()
def sp():
    import actions.screen_processor as sp_module

    return sp_module


def test_capture_success_returns_valid_jpeg_with_consistent_dims(sp, monkeypatch):
    import PIL.Image
    import PIL.ImageGrab

    assert sp._PIL_OK, "Pillow required for the JPEG contract path"
    fake = PIL.Image.new("RGB", (1600, 900), (200, 30, 30))
    monkeypatch.setattr(PIL.ImageGrab, "grab", lambda **kwargs: fake)

    result = sp._capture_screenshot()

    assert result.ok is True
    assert result.error == ""
    assert result.image[:2] == b"\xff\xd8"
    decoded = PIL.Image.open(io.BytesIO(result.image))
    assert decoded.format == "JPEG"
    assert (decoded.width, decoded.height) == (result.width, result.height)


def test_capture_result_is_not_tuple_unpackable(sp, monkeypatch):
    import PIL.Image
    import PIL.ImageGrab

    monkeypatch.setattr(PIL.ImageGrab, "grab", lambda **kwargs: PIL.Image.new("RGB", (640, 360)))

    result = sp._capture_screenshot()

    with pytest.raises(TypeError):
        _img, _mime = result


def test_capture_failure_is_structured_without_traceback(sp, monkeypatch):
    import PIL.ImageGrab

    def _boom(*args, **kwargs):
        raise RuntimeError("capture exploded")

    monkeypatch.setattr(PIL.ImageGrab, "grab", _boom)
    monkeypatch.setattr(sp.mss, "mss", _boom)

    result = sp._capture_screenshot()

    assert result.ok is False
    assert result.error == "screen_capture_failed"
    assert "Traceback" not in result.message
    assert result.error_response() == {
        "success": False,
        "error": "screen_capture_failed",
        "message": result.message,
    }


def test_screen_process_consumes_capture_result(sp, monkeypatch):
    class _FakeLive:
        def __init__(self):
            self.called = None

        def is_ready(self):
            return True

        def analyze(self, image_bytes, mime_type, user_text):
            self.called = (image_bytes, mime_type, user_text)

    live = _FakeLive()
    monkeypatch.setattr(sp, "_ensure_started", lambda player=None: None)
    monkeypatch.setattr(sp, "_live", live)
    monkeypatch.setattr(
        sp,
        "_capture_screenshot",
        lambda: sp.ScreenCaptureResult(
            ok=True, image=b"\xff\xd8FAKE\xffd9", mime_type="image/jpeg", width=640, height=360
        ),
    )
    monkeypatch.setattr("core.perception.get_active_window", lambda: None)

    ok = sp.screen_process({"angle": "screen", "text": "What is on screen?"}, player=None)

    assert ok is True
    image_bytes, mime_type, user_text = live.called
    assert image_bytes.startswith(b"\xff\xd8")
    assert mime_type == "image/jpeg"
    assert "What is on screen?" in user_text


def test_screen_process_capture_failure_returns_false(sp, monkeypatch):
    monkeypatch.setattr(sp, "_ensure_started", lambda player=None: None)
    monkeypatch.setattr(
        sp,
        "_capture_screenshot",
        lambda: sp.ScreenCaptureResult(
            ok=False, error="screen_capture_failed", message="Screen capture failed. Please check permissions."
        ),
    )

    ok = sp.screen_process({"angle": "screen", "text": "What do you see?"}, player=None)

    assert ok is False
