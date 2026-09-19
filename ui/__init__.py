"""OPERO UI package — re-exports for backward compatibility."""
from __future__ import annotations

from ui.theme import (
    C, qcol, DEFAULT_UI_COLOR,
    apply_theme_mode, apply_ui_accent, current_palette, current_theme_mode,
    retheme_all_widgets,
)
from ui.widgets import (
    HudCanvas, MetricBar, LogWidget, FileDropZone, _CameraPreview,
    ClipboardPanel, AutomationCanvas, _metrics,
    file_category, fmt_size, _FILE_ICONS,
)
from ui.overlays import (
    SetupOverlay, CustomizeOverlay, HueWheel, PluginManagerOverlay,
    _HudOverlay, ConfirmBanner, IncomingCallBanner,
    WhatsAppPairingOverlay, AutomationStudioOverlay,
    AudioDeviceOverlay, MemoryOverlay, PluginSettingsOverlay,
    RemoteKeyOverlay, APIKeysOverlay, MiniModeWidget,
    BASE_DIR, CONFIG_DIR, API_FILE,
)
from ui.window import MainWindow
from ui.proxy import OperaUI

__all__ = [
    "C", "qcol", "DEFAULT_UI_COLOR",
    "apply_theme_mode", "apply_ui_accent", "current_palette",
    "current_theme_mode", "retheme_all_widgets",
    "HudCanvas", "MetricBar", "LogWidget", "FileDropZone",
    "_CameraPreview", "ClipboardPanel", "AutomationCanvas", "_metrics",
    "file_category", "fmt_size", "_FILE_ICONS",
    "SetupOverlay", "CustomizeOverlay", "HueWheel",
    "PluginManagerOverlay", "_HudOverlay", "ConfirmBanner",
    "IncomingCallBanner", "WhatsAppPairingOverlay",
    "AutomationStudioOverlay", "AudioDeviceOverlay", "MemoryOverlay",
    "PluginSettingsOverlay", "RemoteKeyOverlay", "APIKeysOverlay",
    "MiniModeWidget", "BASE_DIR", "CONFIG_DIR", "API_FILE",
    "MainWindow", "OperaUI",
]
