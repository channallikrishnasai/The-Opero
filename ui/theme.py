"""Theme constants, palette management, and colour helpers."""
from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

from core.logger import get_logger
log = get_logger(__name__)

class C:
    BG        = "#00060a"
    PANEL     = "#010d14"
    PANEL2    = "#010f18"
    BORDER    = "#0d3347"
    BORDER_B  = "#1a5c7a"
    BORDER_A  = "#0f4060"
    PRI       = "#00d4ff"
    PRI_DIM   = "#007a99"
    PRI_GHO   = "#001f2e"
    ACC       = "#ff6b00"
    ACC2      = "#ffcc00"
    GREEN     = "#00ff88"
    GREEN_D   = "#00aa55"
    RED       = "#ff3355"
    MUTED_C   = "#ff3366"
    TEXT      = "#8ffcff"
    TEXT_DIM  = "#3a8a9a"
    TEXT_MED  = "#5ab8cc"
    WHITE     = "#d8f8ff"
    DARK      = "#000d14"
    BAR_BG    = "#011520"


# Keys tied to the accent colour — status colours (ACC, GREEN, RED…) stay fixed
_HUE_LINKED = (
    "BG", "PANEL", "PANEL2", "BORDER", "BORDER_B", "BORDER_A",
    "PRI", "PRI_DIM", "PRI_GHO", "TEXT", "TEXT_DIM", "TEXT_MED",
    "WHITE", "DARK", "BAR_BG",
)
_PALETTE_DEFAULTS: dict[str, str] = {k: getattr(C, k) for k in _HUE_LINKED}

DEFAULT_UI_COLOR = _PALETTE_DEFAULTS["PRI"]

# ── Light mode palette ────────────────────────────────────────────────────────
_PALETTE_LIGHT: dict[str, str] = {
    "BG":       "#f0f2f5",
    "PANEL":    "#ffffff",
    "PANEL2":   "#f7f8fa",
    "BORDER":   "#c0c8d0",
    "BORDER_B": "#90a0b0",
    "BORDER_A": "#a8b8c8",
    "PRI":      "#0077aa",
    "PRI_DIM":  "#005580",
    "PRI_GHO":  "#d0e8f5",
    "TEXT":     "#1a3a4a",
    "TEXT_DIM": "#6a8090",
    "TEXT_MED": "#3a6070",
    "WHITE":    "#102030",
    "DARK":     "#e8ecf0",
    "BAR_BG":   "#e4e8ec",
}

_theme_mode: str = "dark"   # module-level; toggled by apply_theme_mode()


def apply_theme_mode(mode: str) -> bool:
    """Switch between 'dark' and 'light' themes.

    Sets the base palette on class C for the requested mode.
    Any active accent hue should be re-applied on top by the caller.
    Returns True if the mode actually changed.
    """
    global _theme_mode
    mode = (mode or "dark").strip().lower()
    if mode not in ("dark", "light"):
        mode = "dark"
    if mode == _theme_mode:
        return False

    # Set the base palette for the requested mode
    src = _PALETTE_LIGHT if mode == "light" else _PALETTE_DEFAULTS
    for key, hex0 in src.items():
        setattr(C, key, hex0)

    _theme_mode = mode
    return True


def current_theme_mode() -> str:
    """Return the active theme mode ('dark' or 'light')."""
    return _theme_mode


def apply_ui_accent(accent_hex: str) -> bool:
    """
    Re-derives the whole teal-family palette from the chosen accent colour
    (hue shift — brightness/saturation ratios are preserved, design stays intact).
    Painted elements (HUD, waveform, metrics) pick up the new colour on the next
    frame; stylesheet-based panels pick it up when they are rebuilt.
    """
    import colorsys

    accent_hex = (accent_hex or "").strip().lower()
    if not (accent_hex.startswith("#") and len(accent_hex) == 7):
        return False
    try:
        int(accent_hex[1:], 16)
    except ValueError:
        return False

    def _hsv(h: str) -> tuple[float, float, float]:
        r = int(h[1:3], 16) / 255
        g = int(h[3:5], 16) / 255
        b = int(h[5:7], 16) / 255
        return colorsys.rgb_to_hsv(r, g, b)

    base_h            = _hsv(_PALETTE_DEFAULTS["PRI"])[0]
    acc_h, acc_s, _av = _hsv(accent_hex)
    dh   = acc_h - base_h
    grey = acc_s < 0.08   # near-grey accent → the whole theme is desaturated

    # Pick the right source palette for the current theme mode
    _src = _PALETTE_LIGHT if _theme_mode == "light" else _PALETTE_DEFAULTS
    for key, hex0 in _src.items():
        h, s, v = _hsv(hex0)
        if grey:
            s *= 0.15
        r, g, b = colorsys.hsv_to_rgb((h + dh) % 1.0, s, v)
        setattr(C, key, "#{:02x}{:02x}{:02x}".format(
            int(r * 255 + 0.5), int(g * 255 + 0.5), int(b * 255 + 0.5)))
    return True


def current_palette() -> dict[str, str]:
    """A snapshot of the accent-linked colours currently on class C."""
    return {k: getattr(C, k) for k in _HUE_LINKED}


def retheme_all_widgets(old: dict[str, str], new: dict[str, str]) -> None:
    """
    LIVE full theme change. Replaces the old palette colours with the new ones
    in EVERY widget's stylesheet across the app and repaints them. This way the
    colour change applies INSTANTLY across the whole interface — panels, buttons,
    borders included — not just the painted elements. No restart needed.
    """
    mapping = {old[k].lower(): new[k].lower()
               for k in old if old[k].lower() != new.get(k, old[k]).lower()}
    if not mapping:
        return
    app = QApplication.instance()
    if app is None:
        return
    for w in app.allWidgets():
        try:
            ss = w.styleSheet()
            if ss:
                s2 = ss
                for o, n in mapping.items():
                    if o in s2:
                        s2 = s2.replace(o, n)
                if s2 != ss:
                    w.setStyleSheet(s2)
            w.update()
        except Exception:
            pass


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c
