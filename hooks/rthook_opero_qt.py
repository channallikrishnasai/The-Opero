import os
import sys

if sys.platform.startswith("win") and hasattr(sys, "_MEIPASS"):
    _qt_bin = os.path.join(sys._MEIPASS, "PyQt6", "Qt6", "bin")
    if os.path.isdir(_qt_bin):
        try:
            os.add_dll_directory(_qt_bin)
        except (AttributeError, OSError):
            pass
        _path = os.environ.get("PATH", "")
        if _qt_bin not in _path.split(os.pathsep):
            os.environ["PATH"] = _qt_bin + os.pathsep + _path
        os.environ.setdefault(
            "QT_PLUGIN_PATH",
            os.path.join(sys._MEIPASS, "PyQt6", "Qt6", "plugins"),
        )
