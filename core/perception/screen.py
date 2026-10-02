"""Explicit one-shot screen capture — observation only.

Captures happen only when :func:`capture_screen` is called; nothing here polls,
caches, or forwards images. The image bytes never enter a perception context
or its serialization — only metadata does.
"""

import io
import time
from dataclasses import dataclass
from typing import Any

from PIL import Image

from .errors import PerceptionError, PerceptionUnavailableError


@dataclass(frozen=True)
class ScreenCapture:
    png: bytes
    width: int
    height: int
    monitor: int
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        """Capture metadata only — deliberately excludes the image bytes."""
        return {
            "width": self.width,
            "height": self.height,
            "monitor": self.monitor,
            "timestamp": self.timestamp,
            "size_bytes": len(self.png),
        }


def capture_screen(monitor: int = 0) -> ScreenCapture:
    """Capture one frame of *monitor* (0 = full virtual screen) as PNG."""
    if not isinstance(monitor, int) or monitor < 0:
        raise PerceptionError(f"monitor must be a non-negative int, got {monitor!r}")
    try:
        import mss
    except ImportError as exc:
        raise PerceptionUnavailableError("screen capture requires the 'mss' package") from exc
    try:
        with mss.mss() as session:
            shot = session.grab(session.monitors[monitor])
            width, height = shot.size
            rgb = shot.rgb
    except Exception as exc:
        raise PerceptionUnavailableError(f"screen capture failed: {exc}") from exc
    buffer = io.BytesIO()
    Image.frombytes("RGB", (width, height), rgb).save(buffer, format="PNG")
    return ScreenCapture(
        png=buffer.getvalue(),
        width=width,
        height=height,
        monitor=monitor,
        timestamp=time.time(),
    )
