"""Backward-compatible coordinator — imports everything from the ui/ package.

All functionality lives in the sub-modules under ui/:
  ui/theme.py      — C class, palette management, colour helpers
  ui/widgets.py    — HudCanvas, MetricBar, LogWidget, FileDropZone, etc.
  ui/overlays.py   — SetupOverlay, CustomizeOverlay, AudioDeviceOverlay, etc.
  ui/window.py     — MainWindow class
  ui/proxy.py      — OperaUI wrapper
"""
from ui import *
from ui.theme import (
    C, qcol, DEFAULT_UI_COLOR,
    apply_theme_mode, apply_ui_accent, current_palette, current_theme_mode,
    retheme_all_widgets,
)
from ui.widgets import (
    HudCanvas, MetricBar, LogWidget, FileDropZone, _CameraPreview,
    ClipboardPanel, AutomationCanvas, _metrics,
    file_category, fmt_size, _FILE_ICONS,
    _nvml_gpu_windows, _SysMetrics,
)
from ui.overlays import (
    SetupOverlay, CustomizeOverlay, HueWheel, PluginManagerOverlay,
    _HudOverlay, ConfirmBanner, IncomingCallBanner,
    WhatsAppPairingOverlay, AutomationStudioOverlay,
    AudioDeviceOverlay, MemoryOverlay, PluginSettingsOverlay,
    RemoteKeyOverlay, APIKeysOverlay, MiniModeWidget,
    BASE_DIR, CONFIG_DIR, API_FILE,
)
from ui.window import (
    MainWindow,
    APP_VERSION, APP_PROTOCOL,
    _DEFAULT_W, _DEFAULT_H, _MIN_W, _MIN_H,
    _LEFT_W, _RIGHT_W,
)
from ui.proxy import OperaUI
