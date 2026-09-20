"""All overlay/panel classes: setup, customization, audio devices, memory, etc."""
from __future__ import annotations

import json
import math
import platform
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import (
    QEasingCurve, QLineF, QPointF, QPropertyAnimation, QRect, QRectF, QSize,
    Qt, QTimer, QUrl, pyqtSignal, pyqtSlot,
)
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QDesktopServices, QFont, QPainter, QPen, QPixmap,
    QPolygonF,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget, QMenu,
)

from core.logger import get_logger
from ui.theme import C, qcol, DEFAULT_UI_COLOR
from ui.widgets import AutomationCanvas

log = get_logger(__name__)

_OS = platform.system()

import sys as _sys

def _base_dir() -> Path:
    if getattr(_sys, 'frozen', False):
        return Path(_sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / 'config'
API_FILE   = CONFIG_DIR / 'api_keys.json'


class SetupOverlay(QWidget):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: {C.BG};
                border: 1px solid {C.BORDER};
                border-radius: 10px;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(10)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Segoe UI", font_size,
                            QFont.Weight.DemiBold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("INITIALISATION REQUIRED", 14, True))
        layout.addWidget(_lbl("Configure O.P.E.R.O. before first boot.", 9, color=C.PRI_DIM))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("Gemini API Key", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont("Segoe UI", 10))
        self._key_input.setFixedHeight(34)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: {C.PANEL}; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 6px; padding: 6px 10px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        layout.addWidget(self._key_input)
        layout.addSpacing(8)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("Operating System", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 8, color=C.ACC2,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","⊞  Windows"),("mac","  macOS"),("linux","🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            btn.setFixedHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(10)

        init_btn = QPushButton("  INITIALISE SYSTEMS")
        init_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        init_btn.setFixedHeight(38)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO}; border: 1px solid {C.PRI};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows":(C.PRI,"#001a22"),"mac":(C.ACC2,"#1a1400"),"linux":(C.GREEN,"#001a0d")}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {fg}; color: {bg};
                        border: none; border-radius: 6px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PANEL}; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 6px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() +
                f" QLineEdit {{ border: 1px solid {C.RED}; }}"
            )
            return
        self.done.emit(key, self._sel_os)


class HueWheel(QWidget):
    """
    Circular colour picker. The user drags the handle (small white circle)
    around the wheel to choose from ALL hues. The filled circle in the centre
    is a live preview of the selected colour.
    """

    hue_picked    = pyqtSignal(str)   # while dragging (live)
    hue_committed = pyqtSignal(str)   # when the handle is released

    _RING = 16   # ring thickness (px)

    def __init__(self, initial_hex: str = DEFAULT_UI_COLOR, parent=None):
        super().__init__(parent)
        self.setFixedSize(148, 148)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hue  = 0.53
        self._drag = False
        self.set_color(initial_hex)

    # ── API ──────────────────────────────────────────────────────────────────
    def color(self) -> str:
        return QColor.fromHsvF(self._hue, 1.0, 1.0).name()

    def set_color(self, hex_str: str):
        c = QColor((hex_str or "").strip())
        if c.isValid() and c.hsvHueF() >= 0:
            self._hue = c.hsvHueF()
            self.update()

    # ── geometry helpers ─────────────────────────────────────────────────────
    def _ring_rect(self) -> QRectF:
        m = self._RING / 2 + 3
        return QRectF(self.rect()).adjusted(m, m, -m, -m)

    def _hue_from_pos(self, pos: QPointF) -> float:
        c  = QRectF(self.rect()).center()
        dx = pos.x() - c.x()
        dy = c.y() - pos.y()          # screen y goes down — flip to math axis
        ang = math.atan2(dy, dx)      # [-π, π], counter-clockwise
        return (ang / (2 * math.pi)) % 1.0

    # ── drawing ──────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect   = self._ring_rect()
        center = rect.center()

        grad = QConicalGradient(center, 0)
        for i in range(0, 361, 20):
            grad.setColorAt(i / 360.0, QColor.fromHsvF((i % 360) / 360.0, 1.0, 1.0))
        p.setPen(QPen(QBrush(grad), self._RING))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)

        # centre preview circle
        preview = QColor.fromHsvF(self._hue, 1.0, 1.0)
        inner   = rect.adjusted(30, 30, -30, -30)
        p.setPen(QPen(qcol(C.BORDER_B), 1))
        p.setBrush(QBrush(preview))
        p.drawEllipse(inner)

        # draggable handle
        r   = rect.width() / 2
        ang = self._hue * 2 * math.pi
        hx  = center.x() + r * math.cos(ang)
        hy  = center.y() - r * math.sin(ang)
        p.setPen(QPen(QColor("#00060a"), 2))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(QPointF(hx, hy), 7.5, 7.5)
        p.end()

    # ── fare ─────────────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        self._drag = True
        self._hue  = self._hue_from_pos(e.position())
        self.update()
        self.hue_picked.emit(self.color())

    def mouseMoveEvent(self, e):
        if self._drag:
            self._hue = self._hue_from_pos(e.position())
            self.update()
            self.hue_picked.emit(self.color())

    def mouseReleaseEvent(self, e):
        if self._drag:
            self._drag = False
            self.hue_committed.emit(self.color())


class CustomizeOverlay(QWidget):
    """Floating overlay — change assistant name, user name, UI colour, voice and theme."""

    saved = pyqtSignal(str, str, str, str, str)   # assistant_name, user_name, ui_color, voice, theme_mode
    _OW, _OH = 420, 660

    def __init__(self, assistant_name="OPERO", user_name="",
                 ui_color=DEFAULT_UI_COLOR, voice="", theme_mode="dark", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            CustomizeOverlay {{
                background: {C.BG};
                border: 1px solid {C.BORDER};
                border-radius: 10px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(10)

        def _lbl(txt, fs=9, bold=False, color=C.PRI, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt); w.setAlignment(align)
            w.setFont(QFont("Segoe UI", fs,
                            QFont.Weight.DemiBold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        _fs = (f"QLineEdit {{ background: {C.PANEL}; color: {C.TEXT}; "
               f"border: 1px solid {C.BORDER}; border-radius: 6px; padding: 6px 10px; "
               f"font-family: 'Segoe UI'; font-size: 10pt; }}"
               f"QLineEdit:focus {{ border: 1px solid {C.PRI}; }}")

        lay.addWidget(_lbl("⚙  CUSTOMISE ASSISTANT", 13, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        lay.addWidget(sep)

        lay.addWidget(_lbl("Assistant Name", 8, color=C.TEXT_DIM,
                            align=Qt.AlignmentFlag.AlignLeft))
        self._name_input = QLineEdit(assistant_name)
        self._name_input.setFont(QFont("Segoe UI", 10))
        self._name_input.setFixedHeight(34)
        self._name_input.setStyleSheet(_fs)
        lay.addWidget(self._name_input)

        lay.addSpacing(2)
        lay.addWidget(_lbl("Your Name  (leave blank for default)", 8,
                            color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._user_input = QLineEdit(user_name)
        self._user_input.setPlaceholderText("e.g.  Tony   (leave blank for auto)")
        self._user_input.setFont(QFont("Segoe UI", 10))
        self._user_input.setFixedHeight(34)
        self._user_input.setStyleSheet(_fs)
        lay.addWidget(self._user_input)

        from memory.config_manager import AVAILABLE_VOICES, DEFAULT_VOICE
        lay.addSpacing(4)
        lay.addWidget(_lbl("Assistant Voice", 8, color=C.TEXT_DIM,
                            align=Qt.AlignmentFlag.AlignLeft))
        self._sel_voice   = (voice or DEFAULT_VOICE)
        if self._sel_voice not in AVAILABLE_VOICES:
            self._sel_voice = DEFAULT_VOICE
        self._voice_btns: dict[str, QPushButton] = {}
        voice_row = QHBoxLayout(); voice_row.setSpacing(4)
        for _v in AVAILABLE_VOICES:
            b = QPushButton(_v)
            b.setCheckable(True)
            b.setFixedHeight(30)
            b.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, name=_v: self._on_voice_pick(name))
            self._voice_btns[_v] = b
            voice_row.addWidget(b)
        lay.addLayout(voice_row)
        self._refresh_voice_btns()

        self._sel_theme = (theme_mode or "dark").strip().lower()
        if self._sel_theme not in ("dark", "light"):
            self._sel_theme = "dark"
        lay.addSpacing(4)
        lay.addWidget(_lbl("Theme Mode", 8, color=C.TEXT_DIM,
                            align=Qt.AlignmentFlag.AlignLeft))
        theme_row = QHBoxLayout(); theme_row.setSpacing(4)
        self._theme_btns: dict[str, QPushButton] = {}
        for _t in ("dark", "light"):
            b = QPushButton(_t.upper())
            b.setCheckable(True)
            b.setFixedHeight(30)
            b.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, mode=_t: self._on_theme_pick(mode))
            self._theme_btns[_t] = b
            theme_row.addWidget(b)
        lay.addLayout(theme_row)
        self._refresh_theme_btns()

        lay.addSpacing(4)
        clr_hdr = QHBoxLayout()
        clr_hdr.addWidget(_lbl("UI Colour  —  drag the handle", 8,
                               color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        clr_hdr.addStretch()
        df_btn = QPushButton("DEFAULT")
        df_btn.setFixedSize(68, 22)
        df_btn.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
        df_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        df_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 4px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        df_btn.clicked.connect(lambda: self._set_color(DEFAULT_UI_COLOR))
        clr_hdr.addWidget(df_btn)
        lay.addLayout(clr_hdr)

        self._initial_color = (ui_color or DEFAULT_UI_COLOR).strip().lower()
        self._sel_color     = self._initial_color
        self.on_preview     = None   # callable(hex) — live preview; MainWindow wires it

        self._wheel = HueWheel(self._sel_color)
        wheel_row = QHBoxLayout()
        wheel_row.addStretch(); wheel_row.addWidget(self._wheel); wheel_row.addStretch()
        lay.addLayout(wheel_row)
        self._wheel.hue_picked.connect(self._on_wheel_pick)
        self._wheel.hue_committed.connect(self._on_wheel_commit)

        self._hex_input = QLineEdit(self._sel_color)
        self._hex_input.setPlaceholderText("#00d4ff   (custom hex colour)")
        self._hex_input.setFont(QFont("Segoe UI", 10))
        self._hex_input.setFixedHeight(30)
        self._hex_input.setStyleSheet(_fs)
        self._hex_input.textEdited.connect(self._on_hex_edited)
        lay.addWidget(self._hex_input)

        lay.addSpacing(8)
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        save_btn = QPushButton("  APPLY CHANGES")
        save_btn.setFixedHeight(36)
        save_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 6px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setFont(QFont("Segoe UI", 9))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 6px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)

    # ── voice selection ──────────────────────────────────────────────────────
    def _on_voice_pick(self, name: str):
        self._sel_voice = name
        self._refresh_voice_btns()

    def _refresh_voice_btns(self):
        """Highlight the selected voice pill; dim the rest."""
        for name, b in self._voice_btns.items():
            on = (name == self._sel_voice)
            b.setChecked(on)
            if on:
                b.setStyleSheet(f"""
                    QPushButton {{ background: {C.PRI_GHO}; color: {C.PRI};
                        border: 1px solid {C.PRI}; border-radius: 6px; }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{ background: transparent; color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER}; border-radius: 6px; }}
                    QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
                """)

    # ── theme mode selection ───────────────────────────────────────────────────
    def _on_theme_pick(self, mode: str):
        self._sel_theme = mode
        self._refresh_theme_btns()

    def _refresh_theme_btns(self):
        """Highlight the selected theme pill; dim the rest."""
        for name, b in self._theme_btns.items():
            on = (name == self._sel_theme)
            b.setChecked(on)
            if on:
                b.setStyleSheet(f"""
                    QPushButton {{ background: {C.PRI_GHO}; color: {C.PRI};
                        border: 1px solid {C.PRI}; border-radius: 6px; }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{ background: transparent; color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER}; border-radius: 6px; }}
                    QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
                """)

    # ── colour flow ──────────────────────────────────────────────────────────
    def _set_color(self, hx: str, update_wheel: bool = True, preview: bool = True):
        """Updates the selected colour; hex box + wheel stay in sync, theme is live-previewed."""
        self._sel_color = hx.strip().lower()
        self._hex_input.blockSignals(True)
        self._hex_input.setText(self._sel_color)
        self._hex_input.blockSignals(False)
        if update_wheel:
            self._wheel.set_color(self._sel_color)
        if preview and self.on_preview:
            self.on_preview(self._sel_color)

    def _on_wheel_pick(self, hx: str):
        # While dragging: update the hex box, don't apply the theme yet
        self._sel_color = hx
        self._hex_input.blockSignals(True)
        self._hex_input.setText(hx)
        self._hex_input.blockSignals(False)

    def _on_wheel_commit(self, hx: str):
        # Handle released → live-preview the whole interface
        self._set_color(hx, update_wheel=False)

    def _on_hex_edited(self, text: str):
        t = text.strip().lower()
        if t.startswith("#") and len(t) == 7:
            try:
                int(t[1:], 16)
            except ValueError:
                return
            self._set_color(t, update_wheel=True, preview=True)

    def _cancel(self):
        # If a preview was applied, revert to the colour from launch
        if self.on_preview and self._sel_color != self._initial_color:
            self.on_preview(self._initial_color)
        self.hide()

    def _save(self):
        name = self._name_input.text().strip() or "OPERO"
        user = self._user_input.text().strip()
        self.saved.emit(name, user, self._sel_color or DEFAULT_UI_COLOR, self._sel_voice, self._sel_theme)
        self.hide()


class PluginManagerOverlay(QWidget):
    """Floating overlay — lists discovered plugins with per-plugin ON/OFF toggles."""

    _OW = 420

    def __init__(self, plugins: list[dict], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            PluginManagerOverlay {{
                background: {C.BG};
                border: 1px solid {C.BORDER};
                border-radius: 10px;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(8)

        hdr = QLabel("PLUGIN MANAGER")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(hdr)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        lay.addWidget(sep)

        if not plugins:
            empty = QLabel("No plugins found in /plugins.")
            empty.setFont(QFont("Segoe UI", 8))
            empty.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addWidget(empty)

        for p in plugins:
            lay.addLayout(self._build_row(p))

        lay.addSpacing(4)
        close_btn = QPushButton("CLOSE")
        close_btn.setFixedHeight(32)
        close_btn.setFont(QFont("Segoe UI", 9))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 6px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self.hide)
        lay.addWidget(close_btn)
        self.adjustSize()

    def _build_row(self, p: dict) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(8)

        label_text = p["name"] if p["valid"] else f"{p['name']}  (⚠ {p['file']})"
        lbl = QLabel(label_text)
        lbl.setFont(QFont("Segoe UI", 8))
        lbl.setStyleSheet(f"color: {C.TEXT if p['valid'] else C.TEXT_DIM}; background: transparent;")
        lbl.setToolTip(p["description"] if p["valid"] else p["error"])
        lbl.setWordWrap(False)
        row.addWidget(lbl, stretch=1)

        btn = QPushButton()
        btn.setFixedSize(72, 24)
        btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        if not p["valid"]:
            btn.setText("BROKEN")
            btn.setEnabled(False)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 3px;
                }}
            """)
        else:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._style_toggle(btn, p["enabled"])
            btn.clicked.connect(lambda _, name=p["name"], b=btn: self._toggle(name, b))
        row.addWidget(btn)
        return row

    def _style_toggle(self, btn: QPushButton, enabled: bool):
        if enabled:
            btn.setText("ON")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #001a08; color: {C.GREEN};
                    border: 1px solid {C.GREEN_D}; border-radius: 6px;
                }}
                QPushButton:hover {{ background: #002010; }}
            """)
        else:
            btn.setText("OFF")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 6px;
                }}
                QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
            """)

    def _toggle(self, name: str, btn: QPushButton):
        from memory.config_manager import get_plugin_enabled, save_plugin_enabled
        new_val = not get_plugin_enabled(name)
        save_plugin_enabled(name, new_val)
        self._style_toggle(btn, new_val)


class _HudOverlay(QWidget):
    """Base for the floating panels placed by hand over the HUD.

    They are children of the central widget but sit in no layout, so Qt never
    invalidates the region they occupy when they hide or shrink: the HUD keeps
    painting around them and their last frame stays on screen as a ghost. Any
    overlay positioned with _centre_overlay needs this."""

    def hideEvent(self, e):
        p = self.parentWidget()
        if p is not None:
            # Repaint exactly what we were covering, before we stop covering it.
            p.update(self.geometry())
        super().hideEvent(e)

    def closeEvent(self, e):
        p = self.parentWidget()
        if p is not None:
            p.update(self.geometry())
        super().closeEvent(e)

class ConfirmBanner(_HudOverlay):
    """The gate in front of an action that cannot be taken back.

    The old confirmation was a tool parameter the model filled in itself, which
    means it confirmed its own shutdown requests. This is the interface asking,
    and the answer travels from a human finger to core/confirm.py without the
    model in the loop. Nothing blocks while it is up: the assistant keeps
    talking, so this costs no latency — unlike the old gate, which spent two
    tool round trips on every power command."""

    answered = pyqtSignal(bool)
    _OW = 430

    def __init__(self, title: str, detail: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ConfirmBanner {{
                background: rgba(14, 3, 0, 250);
                border: 1px solid {C.ACC};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)

        hdr = QLabel("⚠  CONFIRM")
        hdr.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.ACC}; background: transparent;")
        lay.addWidget(hdr)

        ttl = QLabel(title)
        ttl.setWordWrap(True)
        ttl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        ttl.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        lay.addWidget(ttl)

        if detail:
            dtl = QLabel(detail)
            dtl.setWordWrap(True)
            dtl.setFont(QFont("Courier New", 8))
            dtl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            lay.addWidget(dtl)

        row = QHBoxLayout(); row.setSpacing(8)

        yes = QPushButton("▸  CONFIRM")
        yes.setFixedHeight(32)
        yes.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        yes.setCursor(Qt.CursorShape.PointingHandCursor)
        yes.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.ACC};
                border: 1px solid {C.ACC}; border-radius: 3px; }}
            QPushButton:hover {{ background: rgba(255,107,0,40); }}
        """)
        yes.clicked.connect(lambda: self.answered.emit(True))
        row.addWidget(yes)

        no = QPushButton("CANCEL")
        no.setFixedHeight(32)
        no.setFont(QFont("Courier New", 9))
        no.setCursor(Qt.CursorShape.PointingHandCursor)
        no.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        no.clicked.connect(lambda: self.answered.emit(False))
        row.addWidget(no)
        lay.addLayout(row)

        # Default focus on CANCEL: if someone hits Enter without reading, the
        # safe answer wins.
        no.setDefault(True)
        no.setFocus()

class IncomingCallBanner(_HudOverlay):
    """A prominent, animated decision surface for an incoming WhatsApp call."""

    answered = pyqtSignal(bool)
    _OW = 430

    def __init__(self, caller: str, is_video: bool = False, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(self._OW)
        self.setStyleSheet(f"""
            IncomingCallBanner {{ background: rgba(0, 14, 9, 248);
                border: 1px solid {C.GREEN}; border-radius: 8px; }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 18)
        lay.setSpacing(8)

        hdr = QLabel("●  INCOMING WHATSAPP " + ("VIDEO" if is_video else "VOICE") + " CALL")
        hdr.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        lay.addWidget(hdr)
        who = QLabel(caller or "Unknown caller")
        who.setWordWrap(True)
        who.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        who.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        lay.addWidget(who)
        note = QLabel("Answer opens WhatsApp Desktop. For OPERO to speak into the call, select a virtual microphone (for example VB-CABLE) as WhatsApp's input.")
        note.setWordWrap(True)
        note.setFont(QFont("Courier New", 8))
        note.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(note)
        row = QHBoxLayout(); row.setSpacing(8)
        answer = QPushButton("☎  ANSWER")
        answer.setFixedHeight(34); answer.setCursor(Qt.CursorShape.PointingHandCursor)
        answer.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        answer.setStyleSheet(f"QPushButton {{ color: {C.GREEN}; border: 1px solid {C.GREEN}; border-radius: 3px; background: rgba(0, 90, 35, 35); }} QPushButton:hover {{ background: rgba(0, 180, 70, 60); }}")
        answer.clicked.connect(lambda: self.answered.emit(True))
        row.addWidget(answer)
        decline = QPushButton("DECLINE")
        decline.setFixedHeight(34); decline.setCursor(Qt.CursorShape.PointingHandCursor)
        decline.setFont(QFont("Courier New", 9))
        decline.setStyleSheet(f"QPushButton {{ color: {C.ACC}; border: 1px solid {C.ACC}; border-radius: 3px; background: transparent; }} QPushButton:hover {{ background: rgba(255, 70, 40, 45); }}")
        decline.clicked.connect(lambda: self.answered.emit(False))
        row.addWidget(decline)
        lay.addLayout(row)

class WhatsAppPairingOverlay(_HudOverlay):
    """Displays the bridge QR inside OPERO for one-time WhatsApp linking."""

    _OW = 360

    def __init__(self, qr_payload: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(self._OW)
        self.setStyleSheet(f"""WhatsAppPairingOverlay {{ background: rgba(0, 12, 8, 250);
            border: 1px solid {C.GREEN}; border-radius: 8px; }}""")
        lay = QVBoxLayout(self); lay.setContentsMargins(18, 16, 18, 16); lay.setSpacing(8)
        title = QLabel("▣  LINK WHATSAPP")
        title.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        lay.addWidget(title)
        note = QLabel("WhatsApp → Settings → Linked devices → Link a device, then scan this code.")
        note.setWordWrap(True); note.setFont(QFont("Courier New", 8))
        note.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(note)
        image_label = QLabel(); image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            import io, qrcode
            image = qrcode.make(qr_payload).convert("RGB")
            raw = io.BytesIO(); image.save(raw, format="PNG")
            pixmap = QPixmap(); pixmap.loadFromData(raw.getvalue(), "PNG")
            image_label.setPixmap(pixmap.scaled(260, 260, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation))
        except Exception:
            image_label.setText("QR rendering unavailable. Check the bridge terminal.")
            image_label.setStyleSheet(f"color: {C.ACC}; background: transparent;")
        lay.addWidget(image_label)
        close = QPushButton("HIDE")
        close.setFixedHeight(28); close.clicked.connect(self.hide)
        close.setStyleSheet(f"QPushButton {{ color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px; background: transparent; }} QPushButton:hover {{ color: {C.TEXT}; }}")
        lay.addWidget(close)


# The automations OPERO can walk through, from trigger to result. This is the one
# source of truth: the studio draws it, and the 3D background renders the same
# flows as step chains around the galaxy.
AUTOMATION_FLOWS = {
    "WhatsApp busy reply": [("Trigger", "Incoming WhatsApp call"), ("Condition", "Auto-answer window active"), ("Action", "Answer in Desktop"), ("Voice", "Say busy message")],
    "Internship application": [("Trigger", "Resume uploaded"), ("Research", "Find matching internships"), ("Rank", "Score roles and links"), ("Action", "Fill known form fields"), ("Review", "Wait before submit")],
    "Smart reminder": [("Trigger", "Reminder due"), ("Condition", "User is available"), ("Action", "Speak and show alert")],
    "Desktop command": [("Trigger", "Voice or text command"), ("Plan", "Resolve available tool"), ("Action", "Run desktop task"), ("Result", "Report outcome")],
    "Auto-heal": [("Watch", "Background monitor spots a fault"), ("Diagnose", "Identify the failing component"), ("Repair", "Apply the safe recovery step"), ("Verify", "Confirm the system is healthy")],
    "Daily briefing": [("Trigger", "First wake or scheduled time"), ("Gather", "Calendar, mail and weather"), ("Compose", "Rank what matters today"), ("Voice", "Speak the briefing")],
}


def automation_payload() -> list[dict]:
    """AUTOMATION_FLOWS as compact dicts, for consumers outside Qt."""
    return [
        {"name": name, "steps": [f"{kind}: {label}" for kind, label in steps]}
        for name, steps in AUTOMATION_FLOWS.items()
    ]


class AutomationStudioOverlay(_HudOverlay):
    """Visual workflow map inspired by node-based automation tools."""

    _OW = 820

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(self._OW)
        self.setStyleSheet(f"""AutomationStudioOverlay {{ background: rgba(1, 9, 16, 252);
            border: 1px solid {C.PRI_DIM}; border-radius: 8px; }}""")
        self._flows = AUTOMATION_FLOWS
        lay = QVBoxLayout(self); lay.setContentsMargins(18, 16, 18, 16); lay.setSpacing(9)
        title = QLabel("◈  AUTOMATION STUDIO")
        title.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(title)
        subtitle = QLabel("Visualize how OPERO moves from trigger to result. Sensitive or external steps pause for review.")
        subtitle.setWordWrap(True); subtitle.setFont(QFont("Courier New", 8)); subtitle.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(subtitle)
        self._picker = QComboBox(); self._picker.addItems(list(self._flows))
        self._picker.setFixedHeight(30); self._picker.setFont(QFont("Courier New", 9))
        self._picker.setStyleSheet(f"QComboBox {{ background: #061522; color: {C.TEXT}; border: 1px solid {C.BORDER_B}; border-radius: 3px; padding: 3px 8px; }} QComboBox QAbstractItemView {{ background: #061522; color: {C.TEXT}; }}")
        self._picker.currentTextChanged.connect(self._select_flow); lay.addWidget(self._picker)
        self._canvas = AutomationCanvas(); lay.addWidget(self._canvas)
        self._status = QLabel(); self._status.setFont(QFont("Courier New", 8)); self._status.setStyleSheet(f"color: {C.GREEN}; background: #03140b; border: 1px solid #14623d; border-radius: 3px; padding: 7px;")
        lay.addWidget(self._status)
        close = QPushButton("CLOSE STUDIO"); close.setFixedHeight(30); close.clicked.connect(self.hide)
        close.setStyleSheet(f"QPushButton {{ color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px; background: transparent; }} QPushButton:hover {{ color: {C.TEXT}; border-color: {C.PRI_DIM}; }}")
        lay.addWidget(close)
        self._select_flow(self._picker.currentText())

    def _select_flow(self, name: str):
        self._canvas.set_nodes(self._flows.get(name, []))
        active = "ACTIVE" if name == "WhatsApp busy reply" else "READY"
        self._status.setText(f"● {active}  ·  {len(self._flows.get(name, []))} nodes  ·  OPERO controls the next eligible step")


class AudioDeviceOverlay(_HudOverlay):
    """Choose which microphone OPERO listens to and which speakers it uses.

    Both audio streams used to open with no `device=` at all, so they always
    took the OS default — which on Windows moves by itself the moment a headset
    is plugged in. 'OPERO can't hear me' is usually 'OPERO is listening to the
    webcam'."""

    picked = pyqtSignal()      # emitted after Apply, when something changed
    _OW = 460

    def __init__(self, parent=None):
        super().__init__(parent)
        from core.audio_devices import list_devices, DEFAULT_LABEL
        from memory.config_manager import get_input_device, get_output_device

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            AudioDeviceOverlay {{
                background: {C.BG};
                border: 1px solid {C.BORDER};
                border-radius: 10px;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(8)

        hdr = QLabel("AUDIO DEVICES")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        lay.addWidget(sep)

        _combo_css = (
            f"QComboBox {{ background: {C.PANEL}; color: {C.TEXT}; "
            f"border: 1px solid {C.BORDER}; border-radius: 6px; padding: 6px 10px; "
            f"font-family: 'Segoe UI'; font-size: 9pt; }}"
            f"QComboBox:hover {{ border-color: {C.BORDER_B}; }}"
            f"QComboBox QAbstractItemView {{ background: {C.PANEL}; color: {C.TEXT}; "
            f"selection-background-color: {C.PRI_GHO}; border: 1px solid {C.BORDER}; }}"
        )

        def _row(label: str, kind: str, current: str) -> QComboBox:
            cap = QLabel(label)
            cap.setFont(QFont("Segoe UI", 8))
            cap.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addWidget(cap)

            box = QComboBox()
            box.setFont(QFont("Segoe UI", 9))
            box.setFixedHeight(32)
            box.setStyleSheet(_combo_css)
            box.addItem(DEFAULT_LABEL, "")
            for name in list_devices(kind):
                box.addItem(name, name)
            idx = box.findData(current) if current else 0
            box.setCurrentIndex(idx if idx >= 0 else 0)
            if current and idx < 0:
                box.addItem(f"{current}  (not connected)", current)
                box.setCurrentIndex(box.count() - 1)
            lay.addWidget(box)
            return box

        self._in_box  = _row("MICROPHONE — what OPERO hears you with",
                             "input", get_input_device())
        lay.addSpacing(4)
        self._out_box = _row("SPEAKERS — what OPERO talks through",
                             "output", get_output_device())

        note = QLabel("Applying reconnects the session. Your conversation is kept.")
        note.setWordWrap(True)
        note.setFont(QFont("Segoe UI", 7))
        note.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addSpacing(6)
        lay.addWidget(note)

        row = QHBoxLayout(); row.setSpacing(8)
        ok = QPushButton("  APPLY")
        ok.setFixedHeight(34)
        ok.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 6px; }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
        """)
        ok.clicked.connect(self._apply)
        row.addWidget(ok)

        cancel = QPushButton("CLOSE")
        cancel.setFixedHeight(34)
        cancel.setFont(QFont("Segoe UI", 9))
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 6px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        cancel.clicked.connect(self.hide)
        row.addWidget(cancel)
        lay.addLayout(row)

    def _apply(self):
        from memory.config_manager import (
            get_input_device, get_output_device,
            save_input_device, save_output_device,
        )
        new_in  = self._in_box.currentData()  or ""
        new_out = self._out_box.currentData() or ""
        changed = (new_in != get_input_device()) or (new_out != get_output_device())
        save_input_device(new_in)
        save_output_device(new_out)
        self.hide()
        # Only rebuild the session if something actually moved — a no-op Apply
        # should not cost a reconnect.
        if changed:
            self.picked.emit()

class MemoryOverlay(_HudOverlay):
    """Everything OPERO has stored about you, and when it learned it.

    Memory used to be a 2200-character store that deleted its oldest entries
    when full and mentioned it only on stdout. The cap is gone; this panel is
    the other half of that change — a memory you cannot inspect is a memory you
    cannot trust, and 'delete' has to be something the person can do."""

    _OW = 520

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            MemoryOverlay {{
                background: {C.BG};
                border: 1px solid {C.BORDER};
                border-radius: 10px;
            }}
        """)
        self.setFixedWidth(self._OW)

        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(24, 20, 24, 20)
        self._lay.setSpacing(6)
        self._rebuild()

    def _clear_layout(self):
        """Take every item out of the layout and detach it from the widget tree
        in this call.

        deleteLater() on its own is not enough: it queues destruction for the
        next event-loop pass, and until then the old rows are still children of
        this widget and still paint — which is what drew half of the previous
        panel over the new one. setParent(None) removes them from the tree now;
        deleteLater() then frees them safely."""
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                # hide() stops it painting in this frame; deleteLater() frees it
                # safely afterwards. setParent(None) would also stop the paint,
                # but it turns the widget into a top-level window for the moment
                # between the two calls, which is not something to leave lying
                # around inside a click handler.
                w.hide()
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    si = sub.takeAt(0)
                    sw = si.widget()
                    if sw is not None:
                        sw.hide()
                        sw.deleteLater()
                sub.deleteLater()

    def _settle(self, before):
        """Size the panel to its content, re-centre it, and repaint what the old
        size covered.

        The re-size has to happen here rather than at the end of _rebuild
        because Qt has not polished the freshly-created children at that point,
        so the size hint it would read is the empty-layout one. Measured: a
        first adjustSize() returned 32 px for a panel whose content needed 155,
        and a second call — after the same widgets had been through the event
        loop — returned 155. So this runs twice: once now, once on the next
        turn, from _rebuild.

        The re-centre and the repaint are needed because the overlay is placed
        by hand and is in no layout: shrinking it leaves it off-centre and
        leaves its former pixels on screen, since nothing tells the parent that
        region changed. The repaint has to cover the union of the old and new
        rectangles."""
        self._lay.invalidate()
        self._lay.activate()
        self.updateGeometry()
        self.adjustSize()

        p = self.parentWidget()
        if p is None:
            self.update()
            return
        self.move(max(0, (p.width()  - self.width())  // 2),
                  max(0, (p.height() - self.height()) // 2))
        p.update(before.united(self.geometry()))
        self.update()

    def _rebuild(self):
        before = self.geometry()
        self._clear_layout()

        from memory.memory_manager import all_entries_for_ui

        hdr = QLabel("WHAT OPERO REMEMBERS")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._lay.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        self._lay.addWidget(sep)

        rows = all_entries_for_ui()

        cap = QLabel(f"{len(rows)} stored facts — newest first. "
                     f"Nothing here is sent anywhere; it lives in "
                     f"memory/long_term.json on this machine.")
        cap.setWordWrap(True)
        cap.setFont(QFont("Segoe UI", 7))
        cap.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._lay.addWidget(cap)

        if not rows:
            empty = QLabel("Nothing stored yet.")
            empty.setFont(QFont("Segoe UI", 9))
            empty.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            self._lay.addWidget(empty)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFixedHeight(min(420, 34 * len(rows) + 10))
            scroll.setStyleSheet(
                f"QScrollArea {{ border: 1px solid {C.BORDER}; border-radius: 6px; "
                f"background: transparent; }}"
            )
            inner = QWidget()
            ilay  = QVBoxLayout(inner)
            ilay.setContentsMargins(8, 8, 8, 8)
            ilay.setSpacing(4)

            for r in rows:
                line = QHBoxLayout(); line.setSpacing(8)
                txt = QLabel(f"<b>{r['key'].replace('_', ' ')}</b> "
                             f"<span style='color:{C.TEXT_MED}'>— {r['value']}</span>")
                txt.setWordWrap(True)
                txt.setFont(QFont("Segoe UI", 8))
                txt.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
                line.addWidget(txt, 1)

                meta = QLabel(f"{r['category'][:4]} · {r['updated'] or '—'}")
                meta.setFont(QFont("Segoe UI", 7))
                meta.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
                line.addWidget(meta)

                rm = QPushButton("✕")
                rm.setFixedSize(22, 22)
                rm.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
                rm.setCursor(Qt.CursorShape.PointingHandCursor)
                rm.setToolTip("Forget this")
                rm.setStyleSheet(f"""
                    QPushButton {{ background: transparent; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 4px; }}
                    QPushButton:hover {{ color: {C.RED}; border-color: {C.RED}; }}
                """)
                rm.clicked.connect(
                    lambda _=False, c=r["category"], k=r["key"]: self._forget(c, k))
                line.addWidget(rm)

                holder = QWidget()
                holder.setLayout(line)
                ilay.addWidget(holder)

            ilay.addStretch()
            scroll.setWidget(inner)
            self._lay.addWidget(scroll)

        close = QPushButton("CLOSE")
        close.setFixedHeight(30)
        close.setFont(QFont("Courier New", 9))
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close.clicked.connect(self.hide)
        self._lay.addWidget(close)

        self._settle(before)
        # …and again once Qt has polished the new children, because the size
        # hint is not final until then. Harmless when the first pass already
        # got it right: _settle is idempotent.
        QTimer.singleShot(0, lambda g=before: self._settle(g))

    def _forget(self, category: str, key: str):
        from memory.memory_manager import forget
        forget(key, category)
        # Rebuild on the NEXT event-loop turn, not inside this click handler.
        # The rebuild destroys the very ✕ button that emitted this signal, and
        # Qt is entitled to touch the sender after a slot returns; tearing it
        # down mid-emission is how a widget ends up half-alive on screen.
        QTimer.singleShot(0, self._rebuild)

class PluginSettingsOverlay(QWidget):
    """Floating overlay — renders per-plugin settings forms.

    Fully generic: it iterates the settings schemas a plugin declared via its
    PLUGIN_SETTINGS constant (delivered by PluginRegistry.settings_schemas) and
    builds a form for each. It knows NOTHING about any specific plugin, so the
    core stays clean and plugins remain pure drop-in — install a plugin that
    declares fields (e.g. the 3D-printer suite) and its section appears here;
    install none and this panel simply says there's nothing to configure.
    """

    _test_done = pyqtSignal(str, bool, str)   # namespace, ok, message
    _OW = 460

    def __init__(self, sections: list[dict], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            PluginSettingsOverlay {{
                background: {C.BG};
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)
        self._sections = sections or []
        self._widgets: dict[tuple, object] = {}    # (namespace, key) -> input widget
        self._types:   dict[tuple, str]    = {}     # (namespace, key) -> field type
        self._status_labels: dict[str, QLabel] = {} # namespace -> status QLabel
        self._test_done.connect(self._on_test_done)

        self._fs = (f"QLineEdit {{ background: {C.DARK}; color: {C.TEXT}; "
                    f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px; }}"
                    f"QLineEdit:focus {{ border: 1px solid {C.PRI}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 16)
        root.setSpacing(8)

        root.addWidget(self._lbl("⚙  PLUGIN SETTINGS", 12, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        root.addWidget(sep)

        if not self._sections:
            root.addWidget(self._lbl(
                "No configurable plugins are installed.\nDrop a plugin that needs "
                "settings (like the 3D-printer suite) into the plugins folder and "
                "it will show up here.", 9, color=C.TEXT_DIM))
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("QScrollArea { background: transparent; }")
            inner = QWidget()
            inner.setStyleSheet("background: transparent;")
            form = QVBoxLayout(inner)
            form.setContentsMargins(0, 0, 6, 0)
            form.setSpacing(6)
            for sec in self._sections:
                self._build_section(form, sec)
            form.addStretch(1)
            scroll.setWidget(inner)
            root.addWidget(scroll, 1)

        # ── bottom buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        if self._sections:
            save_btn = QPushButton("▸  SAVE")
            save_btn.setFixedHeight(34)
            save_btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {C.PRI};
                    border: 1px solid {C.PRI_DIM}; border-radius: 3px; }}
                QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
            """)
            save_btn.clicked.connect(self._save_all)
            btn_row.addWidget(save_btn)

        close_btn = QPushButton("CLOSE")
        close_btn.setFixedHeight(34)
        close_btn.setFont(QFont("Courier New", 9))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self.hide)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _lbl(self, txt, fs=9, bold=False, color=C.PRI,
             align=Qt.AlignmentFlag.AlignLeft):
        w = QLabel(txt); w.setAlignment(align); w.setWordWrap(True)
        w.setFont(QFont("Courier New", fs,
                        QFont.Weight.Bold if bold else QFont.Weight.Normal))
        w.setStyleSheet(f"color: {color}; background: transparent;")
        return w

    def _build_section(self, form: QVBoxLayout, sec: dict):
        ns     = sec.get("namespace") or sec.get("plugin") or "plugin"
        title  = sec.get("title") or ns
        fields = sec.get("fields") or []
        values = sec.get("values") or {}

        form.addSpacing(4)
        form.addWidget(self._lbl(title, 10, True, C.PRI))

        for field in fields:
            if not isinstance(field, dict) or not field.get("key"):
                continue
            key   = field["key"]
            ftype = (field.get("type") or "text").lower()
            label = field.get("label") or key
            default = field.get("default")
            stored  = values.get(key, default)

            form.addWidget(self._lbl(label.upper(), 8, color=C.TEXT_DIM))

            if ftype == "choice":
                w = QComboBox()
                w.addItems([str(o) for o in field.get("options", [])])
                w.setFont(QFont("Courier New", 9))
                w.setFixedHeight(30)
                w.setStyleSheet(
                    f"QComboBox {{ background: {C.DARK}; color: {C.TEXT}; "
                    f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 2px 8px; }}"
                    f"QComboBox QAbstractItemView {{ background: {C.DARK}; color: {C.TEXT}; "
                    f"selection-background-color: {C.PRI_GHO}; }}")
                if stored is not None:
                    w.setCurrentText(str(stored))
            elif ftype == "toggle":
                w = QPushButton()
                w.setCheckable(True)
                w.setChecked(bool(stored))
                w.setFixedHeight(28)
                w.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
                w.setCursor(Qt.CursorShape.PointingHandCursor)
                self._style_toggle(w)
                w.toggled.connect(lambda _=False, b=w: self._style_toggle(b))
            else:  # text / password
                w = QLineEdit("" if stored is None else str(stored))
                w.setFont(QFont("Courier New", 10))
                w.setFixedHeight(30)
                w.setStyleSheet(self._fs)
                if field.get("placeholder"):
                    w.setPlaceholderText(str(field["placeholder"]))
                if ftype == "password":
                    w.setEchoMode(QLineEdit.EchoMode.Password)

            self._widgets[(ns, key)] = w
            self._types[(ns, key)]   = ftype
            form.addWidget(w)

        # optional test/connect action button + status line
        action = sec.get("action")
        if isinstance(action, dict) and callable(action.get("run")):
            form.addSpacing(2)
            ab = QPushButton(str(action.get("label") or "TEST"))
            ab.setFixedHeight(30)
            ab.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            ab.setCursor(Qt.CursorShape.PointingHandCursor)
            ab.setStyleSheet(f"""
                QPushButton {{ background: #00091a; color: {C.PRI};
                    border: 1px solid {C.PRI_DIM}; border-radius: 3px; }}
                QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
            """)
            ab.clicked.connect(lambda _=False, n=ns: self._run_action(n))
            form.addWidget(ab)

        status = self._lbl("", 8, color=C.TEXT_DIM)
        self._status_labels[ns] = status
        form.addWidget(status)

        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        form.addWidget(line)

    def _style_toggle(self, btn: QPushButton):
        on = btn.isChecked()
        btn.setText("ON" if on else "OFF")
        if on:
            btn.setStyleSheet(f"QPushButton {{ background: {C.PRI_GHO}; color: {C.PRI}; "
                              f"border: 1px solid {C.PRI}; border-radius: 3px; }}")
        else:
            btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {C.TEXT_MED}; "
                              f"border: 1px solid {C.BORDER}; border-radius: 3px; }}")

    # ── data ──────────────────────────────────────────────────────────────────
    def _gather(self, ns: str) -> dict:
        out = {}
        for (n, key), w in self._widgets.items():
            if n != ns:
                continue
            t = self._types.get((n, key), "text")
            if t == "choice":
                out[key] = w.currentText()
            elif t == "toggle":
                out[key] = w.isChecked()
            else:
                out[key] = w.text().strip()
        return out

    def _save_ns(self, ns: str):
        from memory.config_manager import save_plugin_config
        save_plugin_config(ns, self._gather(ns))

    def _save_all(self):
        for sec in self._sections:
            ns = sec.get("namespace") or sec.get("plugin")
            if ns:
                self._save_ns(ns)
                lbl = self._status_labels.get(ns)
                if lbl:
                    lbl.setText("Saved ✓")
                    lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")

    def _run_action(self, ns: str):
        sec = next((s for s in self._sections
                    if (s.get("namespace") or s.get("plugin")) == ns), None)
        if not sec:
            return
        run_fn = (sec.get("action") or {}).get("run")
        if not callable(run_fn):
            return
        self._save_ns(ns)                 # persist what the user typed before testing
        values = self._gather(ns)
        lbl = self._status_labels.get(ns)
        if lbl:
            lbl.setText("Testing…")
            lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")

        def worker():
            try:
                res = run_fn(values)
                if isinstance(res, tuple) and len(res) == 2:
                    ok, msg = bool(res[0]), str(res[1])
                else:
                    ok, msg = bool(res), str(res)
            except Exception as e:
                ok, msg = False, str(e)
            self._test_done.emit(ns, ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_done(self, ns: str, ok: bool, msg: str):
        lbl = self._status_labels.get(ns)
        if not lbl:
            return
        lbl.setText(msg)
        color = C.PRI if ok else "#ff6b6b"
        lbl.setStyleSheet(f"color: {color}; background: transparent;")


class RemoteKeyOverlay(QWidget):
    """Floating overlay — QR code for instant phone pairing + manual key fallback."""

    closed = pyqtSignal()

    _OW, _OH = 400, 465

    def __init__(self, url: str, key: str, auto_login_url: str = "",
                 manual_url: str = "", expiry_secs: int = 600, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            RemoteKeyOverlay {{
                background: rgba(0, 4, 12, 0.95);
                border: 1px solid {C.BORDER_B};
                border-radius: 14px;
            }}
        """)
        self._expiry          = time.time() + expiry_secs
        self._on_new_key      = None
        self._auto_login_url  = auto_login_url
        self._manual_url      = manual_url or url

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(5)

        def _lbl(txt, fs=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Courier New", fs,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            w.setWordWrap(True)
            return w

        lay.addWidget(_lbl("◈  REMOTE ACCESS", 12, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 1px 0;")
        lay.addWidget(sep)

        # ── QR code ───────────────────────────────────────────────────────────
        self._qr_label = QLabel()
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setFixedSize(176, 176)
        self._qr_label.setStyleSheet(
            "background: white; border-radius: 10px; padding: 4px;"
        )
        qr_row = QHBoxLayout()
        qr_row.addStretch()
        qr_row.addWidget(self._qr_label)
        qr_row.addStretch()
        lay.addLayout(qr_row)

        self._update_qr(auto_login_url)

        lay.addWidget(_lbl("Scan with phone camera to connect instantly", 8, color=C.TEXT_DIM))

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 1px 0;")
        lay.addWidget(sep2)

        lay.addWidget(_lbl("Or enter manually:", 7, color=C.TEXT_DIM,
                           align=Qt.AlignmentFlag.AlignLeft))

        self._url_lbl = QLabel(self._manual_url)
        self._url_lbl.setFont(QFont("Courier New", 8))
        self._url_lbl.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        self._url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._url_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._url_lbl)

        self._key_lbl = QLabel(key)
        self._key_lbl.setFont(QFont("Courier New", 28, QFont.Weight.Bold))
        self._key_lbl.setStyleSheet(f"""
            color: {C.ACC};
            background: {C.PANEL2};
            border: 1px solid {C.BORDER_B};
            border-radius: 8px;
            padding: 6px 4px;
            letter-spacing: 10px;
        """)
        self._key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._key_lbl)

        self._timer_lbl = QLabel()
        self._timer_lbl.setFont(QFont("Courier New", 8))
        self._timer_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._timer_lbl)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        new_btn = QPushButton("NEW KEY")
        new_btn.setFixedHeight(32)
        new_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 5px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        new_btn.clicked.connect(self._refresh_key)
        btn_row.addWidget(new_btn)

        close_btn = QPushButton("DISMISS")
        close_btn.setFixedHeight(32)
        close_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 5px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self._do_close)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self._ctimer = QTimer(self)
        self._ctimer.timeout.connect(self._tick)
        self._ctimer.start(1000)
        self._tick()

    def set_new_key_callback(self, fn) -> None:
        self._on_new_key = fn

    def _update_qr(self, url: str) -> None:
        if not url:
            self._qr_label.setText("—")
            return
        try:
            import qrcode as _qrmod
            from io import BytesIO
            qr = _qrmod.QRCode(
                box_size=5, border=2,
                error_correction=_qrmod.constants.ERROR_CORRECT_M,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap()
            px.loadFromData(buf.getvalue())
            self._qr_label.setPixmap(
                px.scaled(170, 170,
                          Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
            )
        except ImportError:
            self._qr_label.setText("pip install\nqrcode[pil]")
            self._qr_label.setFont(QFont("Courier New", 8))
            self._qr_label.setStyleSheet(
                "color: #888; background: white; border-radius: 10px; padding: 4px;"
            )
        except Exception:
            self._qr_label.setText(url[:28])
            self._qr_label.setFont(QFont("Courier New", 7))
            self._qr_label.setStyleSheet(
                f"color: {C.PRI}; background: white; border-radius: 10px; padding: 4px;"
            )

    def _tick(self):
        remaining = max(0, int(self._expiry - time.time()))
        m, s = divmod(remaining, 60)
        self._timer_lbl.setText(f"Key expires in  {m:02d}:{s:02d}")
        if remaining == 0:
            self._do_close()

    def mark_connected(self) -> None:
        """Call from any thread when a phone successfully connects."""
        self._ctimer.stop()
        self._key_lbl.setText("CONNECTED")
        self._key_lbl.setStyleSheet(f"""
            color: {C.GREEN};
            background: rgba(34,197,94,0.08);
            border: 2px solid rgba(34,197,94,0.4);
            border-radius: 8px;
            padding: 6px 4px;
            letter-spacing: 4px;
        """)
        self._qr_label.setText("✓")
        self._qr_label.setFont(QFont("Courier New", 54, QFont.Weight.Bold))
        self._qr_label.setStyleSheet(
            "color: #00ff88; background: #001a0d; border-radius: 10px;"
        )
        self._timer_lbl.setText("Phone connected — OPERO ready")
        self._timer_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")

    def _refresh_key(self):
        if self._on_new_key:
            result = self._on_new_key()
            if result:
                url    = result[0]
                key    = result[1]
                auto   = result[2] if len(result) >= 3 else ""
                manual = result[3] if len(result) >= 4 else url
                self._manual_url     = manual or url
                self._url_lbl.setText(self._manual_url)
                self._key_lbl.setText(key)
                self._auto_login_url = auto
                self._update_qr(auto or url)
                self._expiry = time.time() + 600
                self._key_lbl.setStyleSheet(f"""
                    color: {C.ACC};
                    background: {C.PANEL2};
                    border: 1px solid {C.BORDER_B};
                    border-radius: 8px;
                    padding: 6px 4px;
                    letter-spacing: 10px;
                """)
                self._timer_lbl.setStyleSheet(
                    f"color: {C.TEXT_MED}; background: transparent;"
                )
                self._ctimer.start(1000)
                self._tick()

    def _do_close(self):
        self._ctimer.stop()
        self.hide()
        self.closed.emit()

class APIKeysOverlay(QWidget):
    """Floating overlay — manage Gemini and AssemblyAI API keys."""

    _saved = pyqtSignal()
    _OW, _OH = 440, 340

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            APIKeysOverlay {{
                background: {C.BG};
                border: 1px solid {C.BORDER};
                border-radius: 10px;
            }}
        """)

        self._fs = (f"QLineEdit {{ background: {C.PANEL}; color: {C.TEXT}; "
                    f"border: 1px solid {C.BORDER}; border-radius: 6px; padding: 6px 10px; "
                    f"font-family: 'Segoe UI'; font-size: 10pt; }}"
                    f"QLineEdit:focus {{ border: 1px solid {C.PRI}; }}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(10)

        def _lbl(txt, fs=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt); w.setAlignment(align)
            w.setFont(QFont("Segoe UI", fs,
                            QFont.Weight.DemiBold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        lay.addWidget(_lbl("API KEYS", 13, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        lay.addWidget(sep)

        lay.addWidget(_lbl("Gemini API Key", 8, color=C.TEXT_DIM,
                            align=Qt.AlignmentFlag.AlignLeft))
        self._gemini_input = QLineEdit()
        self._gemini_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._gemini_input.setPlaceholderText("AIza…")
        self._gemini_input.setFont(QFont("Segoe UI", 10))
        self._gemini_input.setFixedHeight(34)
        self._gemini_input.setStyleSheet(self._fs)
        lay.addWidget(self._gemini_input)

        lay.addWidget(_lbl("AssemblyAI API Key  (for voice engine)", 8, color=C.TEXT_DIM,
                            align=Qt.AlignmentFlag.AlignLeft))
        aai_row = QHBoxLayout(); aai_row.setSpacing(6)
        self._aai_input = QLineEdit()
        self._aai_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._aai_input.setPlaceholderText("…")
        self._aai_input.setFont(QFont("Segoe UI", 10))
        self._aai_input.setFixedHeight(34)
        self._aai_input.setStyleSheet(self._fs)
        aai_row.addWidget(self._aai_input, 1)

        self._test_btn = QPushButton("TEST")
        self._test_btn.setFixedSize(56, 34)
        self._test_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self._test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.PRI_DIM};
                border: 1px solid {C.BORDER}; border-radius: 6px; }}
            QPushButton:hover {{ color: {C.PRI}; border-color: {C.PRI_DIM}; }}
        """)
        self._test_btn.clicked.connect(self._test_aai_key)
        aai_row.addWidget(self._test_btn)
        lay.addLayout(aai_row)

        self._aai_status = QLabel("")
        self._aai_status.setFont(QFont("Segoe UI", 8))
        self._aai_status.setStyleSheet("color: transparent; background: transparent;")
        self._aai_status.setFixedHeight(16)
        lay.addWidget(self._aai_status)

        lay.addStretch(1)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        save_btn = QPushButton("  SAVE")
        save_btn.setFixedHeight(36)
        save_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 6px; }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        close_btn = QPushButton("CLOSE")
        close_btn.setFixedHeight(36)
        close_btn.setFont(QFont("Segoe UI", 9))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 6px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self.hide)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        # Load current keys
        self._load_keys()

    def _load_keys(self):
        """Load current API keys from config."""
        try:
            cfg = json.loads(API_FILE.read_text(encoding="utf-8"))
            self._gemini_input.setText(cfg.get("gemini_api_key", ""))
            self._aai_input.setText(cfg.get("assemblyai_api_key", ""))
        except Exception:
            pass

    def _save(self):
        """Save API keys to config."""
        try:
            cfg = {}
            if API_FILE.exists():
                cfg = json.loads(API_FILE.read_text(encoding="utf-8"))
            cfg["gemini_api_key"] = self._gemini_input.text().strip()
            cfg["assemblyai_api_key"] = self._aai_input.text().strip()
            API_FILE.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
            self._saved.emit()
            self.hide()
        except Exception as e:
            self._aai_status.setText(f"Save failed: {e}")
            self._aai_status.setStyleSheet(f"color: #ff6b6b; background: transparent;")

    def _test_aai_key(self):
        """Test AssemblyAI API key in background thread."""
        key = self._aai_input.text().strip()
        if not key:
            self._aai_status.setText("Enter a key first")
            self._aai_status.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            return

        self._test_btn.setEnabled(False)
        self._test_btn.setText("…")
        self._aai_status.setText("Testing…")
        self._aai_status.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")

        def worker():
            try:
                import assemblyai as aai
                settings = aai.Settings(api_key=key)
                # Try to list transcripts (lightweight API call)
                client = aai.Transcriber(config=settings)
                # A simple test: check if we can authenticate
                # The simplest way is to try to get usage or a dummy transcript
                import urllib.request
                req = urllib.request.Request(
                    "https://api.assemblyai.com/v2/transcript",
                    headers={"Authorization": key, "Content-Type": "application/json"},
                    method="POST"
                )
                # Send empty body to test auth — expect 400 (bad request) not 401
                try:
                    urllib.request.urlopen(req, data=b'{}', timeout=10)
                except urllib.error.HTTPError as e:
                    if e.code == 401:
                        return False, "Invalid key — authentication failed"
                    elif e.code == 400:
                        return True, "Key is valid"
                    else:
                        return False, f"Unexpected response: {e.code}"
                except Exception as e:
                    return False, f"Connection error: {e}"
                return True, "Key is valid"
            except ImportError:
                return False, "assemblyai package not installed"
            except Exception as e:
                return False, f"Error: {e}"

        def on_result(ok, msg):
            self._test_btn.setEnabled(True)
            self._test_btn.setText("TEST")
            self._aai_status.setText(msg)
            color = C.PRI if ok else "#ff6b6b"
            self._aai_status.setStyleSheet(f"color: {color}; background: transparent;")

        import threading
        def run():
            result = worker()
            # Use signal-safe approach
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(self, "_on_test_result",
                                    Qt.ConnectionType.QueuedConnection,
                                    Q_ARG(bool, result[0]),
                                    Q_ARG(str, result[1]))
        threading.Thread(target=run, daemon=True).start()

    @pyqtSlot(bool, str)
    def _on_test_result(self, ok: bool, msg: str):
        """Handle test result on main thread."""
        self._test_btn.setEnabled(True)
        self._test_btn.setText("TEST")
        self._aai_status.setText(msg)
        color = C.PRI if ok else "#ff6b6b"
        self._aai_status.setStyleSheet(f"color: {color}; background: transparent;")


_MINI_STYLES = ["cat", "face", "emoji", "spider"]

_MINI_STYLES = ["cat", "face", "emoji", "spider"]


class MiniModeWidget(QWidget):
    """Small draggable always-on-top widget shown when the main window is
    minimised into 'mini mode'.  Supports multiple animated avatar styles
    driven by the live audio level (0.0-1.0)."""

    restore_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    _SIZE = 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(self._SIZE, self._SIZE)

        self._style = "cat"
        self._audio_level = 0.0
        self._tick = 0
        self._drag_pos = None
        self._emoji_index = 0
        self._emoji_timer = time.time()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(33)  # ~30 fps

    # ── public API ─────────────────────────────────────────────────────────
    def set_style(self, name: str):
        if name in _MINI_STYLES:
            self._style = name

    def set_audio_level(self, level: float):
        try:
            lv = max(0.0, min(1.0, float(level)))
        except (TypeError, ValueError):
            return
        if lv > self._audio_level:
            self._audio_level = lv

    # ── context menu ───────────────────────────────────────────────────────
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {C.DARK}; color: {C.TEXT}; border: 1px solid {C.BORDER};
                     border-radius: 6px; padding: 4px; }}
            QMenu::item:selected {{ background: {C.PRI_GHO}; color: {C.PRI}; }}
        """)
        sub = menu.addMenu("Avatar Style")
        for s in _MINI_STYLES:
            act = sub.addAction(s.upper())
            act.setData(s)
            if s == self._style:
                act.setCheckable(True)
                act.setChecked(True)
        menu.addSeparator()
        menu.addAction("Restore Full Window").triggered.connect(self.restore_requested.emit)
        menu.addAction("Quit").triggered.connect(self.quit_requested.emit)
        chosen = menu.exec(event.globalPos())
        if chosen and chosen.data():
            self.set_style(chosen.data())

    # ── dragging ───────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        self.restore_requested.emit()

    # ── animation tick ─────────────────────────────────────────────────────
    def _step(self):
        self._tick += 1
        # decay audio level
        self._audio_level *= 0.92
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        lv = self._audio_level

        if self._style == "cat":
            self._paint_cat(p, w, h, cx, cy, lv)
        elif self._style == "face":
            self._paint_face(p, w, h, cx, cy, lv)
        elif self._style == "emoji":
            self._paint_emoji(p, w, h, cx, cy, lv)
        elif self._style == "spider":
            self._paint_spider(p, w, h, cx, cy, lv)
        p.end()

    # ── cat ────────────────────────────────────────────────────────────────
    def _paint_cat(self, p, w, h, cx, cy, lv):
        # body
        p.setBrush(QColor("#1a1a2e"))
        p.setPen(QPen(QColor("#e94560"), 2))
        p.drawEllipse(int(cx - 30), int(cy - 20), 60, 50)

        # ears
        ear_pts = [
            (cx - 28, cy - 20), (cx - 18, cy - 42), (cx - 8, cy - 20),
        ]
        ear_pts2 = [
            (cx + 8, cy - 20), (cx + 18, cy - 42), (cx + 28, cy - 20),
        ]
        p.setBrush(QColor("#e94560"))
        p.setPen(Qt.PenStyle.NoPen)
        tri = QPolygonF([QPointF(*ear_pts[0]), QPointF(*ear_pts[1]), QPointF(*ear_pts[2])])
        p.drawPolygon(tri)
        tri2 = QPolygonF([QPointF(*ear_pts2[0]), QPointF(*ear_pts2[1]), QPointF(*ear_pts2[2])])
        p.drawPolygon(tri2)

        # inner ears
        p.setBrush(QColor("#ff6b8a"))
        tri_i = QPolygonF([QPointF(cx - 24, cy - 22), QPointF(cx - 18, cy - 36), QPointF(cx - 12, cy - 22)])
        p.drawPolygon(tri_i)
        tri_i2 = QPolygonF([QPointF(cx + 12, cy - 22), QPointF(cx + 18, cy - 36), QPointF(cx + 24, cy - 22)])
        p.drawPolygon(tri_i2)

        # eyes
        eye_y = cy - 8
        eye_open = 4 + lv * 4
        p.setBrush(QColor("#0f3460"))
        p.setPen(QPen(QColor("#e94560"), 1))
        p.drawEllipse(int(cx - 16), int(eye_y - eye_open / 2), 10, int(eye_open))
        p.drawEllipse(int(cx + 6), int(eye_y - eye_open / 2), 10, int(eye_open))

        # pupils
        p.setBrush(QColor("#e9e9e9"))
        p.setPen(Qt.PenStyle.NoPen)
        px_off = lv * 2
        p.drawEllipse(int(cx - 13 + px_off), int(eye_y - 2), 4, 4)
        p.drawEllipse(int(cx + 9 + px_off), int(eye_y - 2), 4, 4)

        # mouth
        mouth_open = 2 + lv * 8
        p.setPen(QPen(QColor("#e94560"), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        mouth_y = cy + 12
        if lv > 0.15:
            p.drawEllipse(int(cx - 5), int(mouth_y), 10, int(mouth_open))
        else:
            p.drawLine(int(cx - 5), int(mouth_y), int(cx + 5), int(mouth_y))

        # whiskers
        p.setPen(QPen(QColor("#ffffff"), 1))
        for dy in [-3, 0, 3]:
            p.drawLine(int(cx - 20), int(cy + 8 + dy), int(cx - 40), int(cy + 5 + dy))
            p.drawLine(int(cx + 20), int(cy + 8 + dy), int(cx + 40), int(cy + 5 + dy))

        # tail (wavy based on tick)
        import math
        tail_x = cx + 30
        tail_pts = []
        for i in range(12):
            tx = tail_x + i * 3
            ty = cy + 10 + math.sin(self._tick * 0.15 + i * 0.6) * (6 + lv * 8)
            tail_pts.append(QPointF(tx, ty))
        p.setPen(QPen(QColor("#e94560"), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(len(tail_pts) - 1):
            p.drawLine(tail_pts[i], tail_pts[i + 1])

    # ── face with lip sync ─────────────────────────────────────────────────
    def _paint_face(self, p, w, h, cx, cy, lv):
        # head glow
        glow_color = QColor(C.PRI)
        glow_color.setAlpha(int(40 + lv * 80))
        p.setBrush(glow_color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(cx - 34), int(cy - 34), 68, 68)

        # head
        p.setBrush(QColor("#16213e"))
        p.setPen(QPen(QColor(C.PRI), 2))
        p.drawEllipse(int(cx - 30), int(cy - 30), 60, 60)

        # eyes
        eye_y = cy - 8
        blink = (self._tick % 180) < 4
        if blink:
            p.setPen(QPen(QColor("#ffffff"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(int(cx - 14), int(eye_y), int(cx - 6), int(eye_y))
            p.drawLine(int(cx + 6), int(eye_y), int(cx + 14), int(eye_y))
        else:
            eye_h = 6 + lv * 4
            p.setBrush(QColor("#e94560"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(cx - 14), int(eye_y - eye_h / 2), 8, int(eye_h))
            p.drawEllipse(int(cx + 6), int(eye_y - eye_h / 2), 8, int(eye_h))
            # pupil highlight
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(int(cx - 12), int(eye_y - 1), 3, 3)
            p.drawEllipse(int(cx + 8), int(eye_y - 1), 3, 3)

        # mouth — lip sync arc
        mouth_y = cy + 12
        mouth_open = lv * 16
        p.setPen(QPen(QColor(C.PRI), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if lv > 0.1:
            p.drawArc(int(cx - 8), int(mouth_y - mouth_open / 2), 16, int(mouth_open), 0, 180 * 16)
        else:
            p.drawLine(int(cx - 6), int(mouth_y), int(cx + 6), int(mouth_y))

    # ── emoji ──────────────────────────────────────────────────────────────
    def _paint_emoji(self, p, w, h, cx, cy, lv):
        now = time.time()
        if now - self._emoji_timer > 2.0:
            self._emoji_index = (self._emoji_index + 1) % 5
            self._emoji_timer = now

        emojis = ["😀", "😎", "🤔", "😴", "🤩"]
        # draw emoji as large text
        p.setPen(QPen(QColor("#ffffff"), 1))
        font = QFont("Segoe UI Emoji", 48)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, emojis[self._emoji_index])

        # audio-reactive ring
        if lv > 0.05:
            ring_color = QColor(C.ACC)
            ring_color.setAlpha(int(80 + lv * 175))
            p.setPen(QPen(ring_color, 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            r = 40 + lv * 6
            p.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

    # ── spider-man ─────────────────────────────────────────────────────────
    def _paint_spider(self, p, w, h, cx, cy, lv):
        # head
        p.setBrush(QColor("#b71c1c"))
        p.setPen(QPen(QColor("#1a1a1a"), 2))
        p.drawEllipse(int(cx - 28), int(cy - 28), 56, 56)

        # web pattern
        p.setPen(QPen(QColor("#ffffff"), 1))
        import math
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            ex = cx + math.cos(rad) * 26
            ey = cy + math.sin(rad) * 26
            p.drawLine(int(cx), int(cy), int(ex), int(ey))
        # concentric arcs
        for r in [10, 18, 26]:
            p.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        # eyes
        eye_y = cy - 4
        eye_h = 10 + lv * 6
        p.setBrush(QColor("#ffffff"))
        p.setPen(QPen(QColor("#1a1a1a"), 1))
        # left eye
        eye_pts_l = QPolygonF([
            QPointF(cx - 20, eye_y - 2),
            QPointF(cx - 10, eye_y - eye_h / 2),
            QPointF(cx - 6, eye_y),
            QPointF(cx - 10, eye_y + eye_h / 2),
            QPointF(cx - 20, eye_y + 2),
        ])
        p.drawPolygon(eye_pts_l)
        # right eye
        eye_pts_r = QPolygonF([
            QPointF(cx + 20, eye_y - 2),
            QPointF(cx + 10, eye_y - eye_h / 2),
            QPointF(cx + 6, eye_y),
            QPointF(cx + 10, eye_y + eye_h / 2),
            QPointF(cx + 20, eye_y + 2),
        ])
        p.drawPolygon(eye_pts_r)

        # spider legs (animated when speaking)
        p.setPen(QPen(QColor("#1a1a1a"), 2))
        leg_angles_l = [-20, -50, -80, -110]
        leg_angles_r = [200, 230, 260, 290]
        for i, a in enumerate(leg_angles_l):
            import math
            wobble = math.sin(self._tick * 0.2 + i) * (4 + lv * 10)
            rad = math.radians(a + wobble)
            ex = cx + math.cos(rad) * 40
            ey = cy + math.sin(rad) * 40
            mid_x = cx + math.cos(rad) * 28
            mid_y = cy + math.sin(rad) * 28
            p.drawLine(int(cx - 20), int(cy + 10), int(mid_x), int(mid_y - 5))
            p.drawLine(int(mid_x), int(mid_y - 5), int(ex), int(ey))
        for i, a in enumerate(leg_angles_r):
            wobble = math.sin(self._tick * 0.2 + i + 2) * (4 + lv * 10)
            rad = math.radians(a + wobble)
            ex = cx + math.cos(rad) * 40
            ey = cy + math.sin(rad) * 40
            mid_x = cx + math.cos(rad) * 28
            mid_y = cy + math.sin(rad) * 28
            p.drawLine(int(cx + 20), int(cy + 10), int(mid_x), int(mid_y - 5))
            p.drawLine(int(mid_x), int(mid_y - 5), int(ex), int(ey))


class IntegrationOverlay(QWidget):
    """Interactive Link Accounts Overlay — enter credentials directly inside OPERO."""

    _OW = 580
    _status_sig = pyqtSignal(str)   # worker thread -> status label

    def __init__(self, connect_gmail=None, connect_gmail_apppass=None, parent=None):
        super().__init__(parent)
        self._connect_gmail = connect_gmail
        self._connect_gmail_apppass = connect_gmail_apppass
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            IntegrationOverlay {{
                background: #061426;
                border: 1px solid {C.PRI_DIM};
                border-radius: 12px;
            }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        hdr = QHBoxLayout()
        title = QLabel("🔗 LINK ACCOUNTS STUDIO")
        title.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(title); hdr.addStretch()
        close = QPushButton("✕")
        close.setFixedSize(24, 24)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none; font-size: 14px;")
        close.clicked.connect(self.hide)
        hdr.addWidget(close)
        root.addLayout(hdr)

        note = QLabel("Enter your API credentials directly below. OPERO stores them locally in your config folder.")
        note.setWordWrap(True)
        note.setFont(QFont("Segoe UI", 9))
        note.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        root.addWidget(note)

        # ── Gmail Section ──
        g_box = QWidget()
        g_box.setStyleSheet(f"background: #020914; border: 1px solid {C.BORDER}; border-radius: 8px;")
        g_lay = QVBoxLayout(g_box)
        g_lay.setContentsMargins(14, 12, 14, 12); g_lay.setSpacing(8)
        
        g_lbl = QLabel("📧 GMAIL AUTOMATION (OAuth Client ID & Secret)")
        g_lbl.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        g_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        g_lay.addWidget(g_lbl)

        g_link_btn = QPushButton("📖 HOW TO GET GMAIL CLIENT ID & SECRET (OPEN GOOGLE CONSOLE)")
        g_link_btn.setFixedHeight(22)
        g_link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        g_link_btn.setStyleSheet(f"QPushButton {{ color: {C.ACC2}; background: transparent; border: none; text-align: left; font-size: 9px; font-weight: bold; }} QPushButton:hover {{ text-decoration: underline; color: {C.PRI}; }}")
        g_link_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://console.cloud.google.com/apis/credentials/oauthclient")))
        g_lay.addWidget(g_link_btn)

        g_row = QHBoxLayout(); g_row.setSpacing(8)
        self._gmail_id = QLineEdit()
        self._gmail_id.setPlaceholderText("Google Client ID")
        self._gmail_id.setFont(QFont("Segoe UI", 8))
        self._gmail_id.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px;")
        g_row.addWidget(self._gmail_id)

        self._gmail_sec = QLineEdit()
        self._gmail_sec.setEchoMode(QLineEdit.EchoMode.Password)
        self._gmail_sec.setPlaceholderText("Google Client Secret")
        self._gmail_sec.setFont(QFont("Segoe UI", 8))
        self._gmail_sec.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px;")
        g_row.addWidget(self._gmail_sec)
        g_lay.addLayout(g_row)

        g_btn_row = QHBoxLayout()
        save_g = QPushButton("SAVE GMAIL CREDENTIALS")
        save_g.setFixedHeight(28); save_g.setCursor(Qt.CursorShape.PointingHandCursor)
        save_g.setStyleSheet(self._primary_style())
        save_g.clicked.connect(self._save_gmail)
        g_btn_row.addWidget(save_g)

        auth_g = QPushButton("CONNECT & SIGN IN")
        auth_g.setFixedHeight(28); auth_g.setCursor(Qt.CursorShape.PointingHandCursor)
        auth_g.setStyleSheet(self._secondary_style())
        auth_g.clicked.connect(self._run_gmail_connect)
        g_btn_row.addWidget(auth_g)
        g_lay.addLayout(g_btn_row)

        # ── App-password route: the quick path when there is no Google Cloud project ──
        g_sep = QLabel("— OR SIGN IN WITH A GMAIL APP PASSWORD (NO GOOGLE CLOUD PROJECT) —")
        g_sep.setFont(QFont("Courier New", 8))
        g_sep.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        g_lay.addWidget(g_sep)

        g_app_link = QPushButton("📖  GET AN APP PASSWORD  (GOOGLE ACCOUNT → SECURITY → APP PASSWORDS)")
        g_app_link.setFixedHeight(22)
        g_app_link.setCursor(Qt.CursorShape.PointingHandCursor)
        g_app_link.setStyleSheet(f"QPushButton {{ color: {C.ACC2}; background: transparent; border: none; text-align: left; font-size: 9px; font-weight: bold; }} QPushButton:hover {{ text-decoration: underline; color: {C.PRI}; }}")
        g_app_link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://myaccount.google.com/apppasswords")))
        g_lay.addWidget(g_app_link)

        g_app_row = QHBoxLayout(); g_app_row.setSpacing(8)
        self._gmail_addr = QLineEdit()
        self._gmail_addr.setPlaceholderText("you@gmail.com")
        self._gmail_addr.setFont(QFont("Segoe UI", 8))
        self._gmail_addr.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px;")
        g_app_row.addWidget(self._gmail_addr)

        self._gmail_apppw = QLineEdit()
        self._gmail_apppw.setEchoMode(QLineEdit.EchoMode.Password)
        self._gmail_apppw.setPlaceholderText("16-character App Password")
        self._gmail_apppw.setFont(QFont("Segoe UI", 8))
        self._gmail_apppw.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px;")
        self._gmail_apppw.returnPressed.connect(self._connect_apppass)
        g_app_row.addWidget(self._gmail_apppw)
        g_lay.addLayout(g_app_row)

        g_app_btn = QPushButton("🔑  CONNECT WITH APP PASSWORD")
        g_app_btn.setFixedHeight(28); g_app_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        g_app_btn.setStyleSheet(self._primary_style())
        g_app_btn.clicked.connect(self._connect_apppass)
        g_lay.addWidget(g_app_btn)
        root.addWidget(g_box)

        # ── Instagram Section ──
        i_box = QWidget()
        i_box.setStyleSheet(f"background: #020914; border: 1px solid {C.BORDER}; border-radius: 8px;")
        i_lay = QVBoxLayout(i_box)
        i_lay.setContentsMargins(14, 12, 14, 12); i_lay.setSpacing(8)

        i_lbl = QLabel("📸 INSTAGRAM MESSAGING (Meta Token & Account ID)")
        i_lbl.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        i_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        i_lay.addWidget(i_lbl)

        i_link_btn = QPushButton("📖 HOW TO GET META GRAPH TOKEN & INSTAGRAM ID (OPEN GRAPH EXPLORER)")
        i_link_btn.setFixedHeight(22)
        i_link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        i_link_btn.setStyleSheet(f"QPushButton {{ color: {C.ACC2}; background: transparent; border: none; text-align: left; font-size: 9px; font-weight: bold; }} QPushButton:hover {{ text-decoration: underline; color: {C.PRI}; }}")
        i_link_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://developers.facebook.com/tools/explorer/")))
        i_lay.addWidget(i_link_btn)

        i_row = QHBoxLayout(); i_row.setSpacing(8)
        self._insta_acc = QLineEdit()
        self._insta_acc.setPlaceholderText("Instagram Account ID")
        self._insta_acc.setFont(QFont("Segoe UI", 8))
        self._insta_acc.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px;")
        i_row.addWidget(self._insta_acc)

        self._insta_token = QLineEdit()
        self._insta_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._insta_token.setPlaceholderText("Meta Graph Access Token")
        self._insta_token.setFont(QFont("Segoe UI", 8))
        self._insta_token.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 4px 8px;")
        i_row.addWidget(self._insta_token)
        i_lay.addLayout(i_row)

        save_i = QPushButton("SAVE INSTAGRAM CREDENTIALS")
        save_i.setFixedHeight(28); save_i.setCursor(Qt.CursorShape.PointingHandCursor)
        save_i.setStyleSheet(self._primary_style())
        save_i.clicked.connect(self._save_insta)
        i_lay.addWidget(save_i)
        root.addWidget(i_box)

        # Status & Quick links
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(f"color: {C.GREEN}; background: transparent; font-size: 11px;")
        self._status_sig.connect(self._status.setText)
        root.addWidget(self._status)

        # Prefill existing if present
        self._load_existing()

    def _load_existing(self):
        try:
            cfg_dir = BASE_DIR / "config"
            g_file = cfg_dir / "google_oauth_client.json"
            if g_file.exists():
                d = json.loads(g_file.read_text(encoding="utf-8"))
                inst = d.get("installed") or d.get("web") or {}
                if inst.get("client_id"):
                    self._gmail_id.setText(inst.get("client_id"))
            
            wa = cfg_dir / "email_credentials.json"
            if wa.exists():
                d = json.loads(wa.read_text(encoding="utf-8"))
                if d.get("email"):
                    self._gmail_addr.setText(str(d.get("email")))

            i_file = cfg_dir / "instagram.json"
            if i_file.exists():
                d = json.loads(i_file.read_text(encoding="utf-8"))
                if d.get("account_id"):
                    self._insta_acc.setText(d.get("account_id"))
        except Exception:
            pass

    def _connect_apppass(self):
        """Check a Gmail address + App Password off the UI thread.

        The IMAP handshake takes a second or two, so it runs in a worker and
        reports back through a signal rather than freezing the overlay.
        """
        addr = self._gmail_addr.text().strip()
        pw = self._gmail_apppw.text().strip()
        if not addr or not pw:
            self._status.setText("⚠️ Enter both your Gmail address and its App Password.")
            return
        self._status.setText("⏳ Checking the App Password with Gmail…")
        connector = self._connect_gmail_apppass

        def worker():
            try:
                if callable(connector):
                    result = connector(addr, pw)
                else:
                    from actions.gmail import execute
                    result = execute({"action": "connect_app_passcode",
                                      "email": addr, "password": pw})
                self._status_sig.emit(str(result))
            except Exception as exc:
                self._status_sig.emit(f"ERR: {exc}")

        threading.Thread(target=worker, daemon=True, name="gmail-app-password").start()

    def _save_gmail(self):
        cid = self._gmail_id.text().strip()
        csec = self._gmail_sec.text().strip()
        if not cid or not csec:
            self._status.setText("⚠️ Enter both Client ID and Client Secret.")
            return
        try:
            cfg_dir = BASE_DIR / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "installed": {
                    "client_id": cid,
                    "project_id": "opero-assistant",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_secret": csec,
                    "redirect_uris": ["http://localhost"]
                }
            }
            (cfg_dir / "google_oauth_client.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self._status.setText("✓ Gmail Client Credentials Saved! Click 'CONNECT & SIGN IN'.")
        except Exception as e:
            self._status.setText(f"ERR: {e}")

    def _save_insta(self):
        acc = self._insta_acc.text().strip()
        tok = self._insta_token.text().strip()
        if not acc or not tok:
            self._status.setText("⚠️ Enter both Account ID and Access Token.")
            return
        try:
            cfg_dir = BASE_DIR / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "access_token": tok,
                "account_id": acc,
                "api_version": "v25.0",
                "base_url": "https://graph.instagram.com"
            }
            (cfg_dir / "instagram.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self._status.setText("✓ Instagram Credentials Saved successfully!")
        except Exception as e:
            self._status.setText(f"ERR: {e}")

    def _run_gmail_connect(self):
        if not callable(self._connect_gmail):
            self._status.setText("Gmail connect is initializing...")
            return
        self._status.setText("Opening official Google OAuth login window...")
        self._connect_gmail()

    @staticmethod
    def _primary_style() -> str:
        return f"QPushButton {{ color: {C.BG}; background: {C.PRI}; border: 1px solid {C.PRI}; border-radius: 4px; font-weight: bold; font-size: 11px; }} QPushButton:hover {{ background: {C.TEXT}; }}"

    @staticmethod
    def _secondary_style() -> str:
        return f"QPushButton {{ color: {C.PRI}; background: transparent; border: 1px solid {C.PRI_DIM}; border-radius: 4px; font-size: 11px; }} QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}"
