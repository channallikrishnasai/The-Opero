"""
Animated gradient orb for the OPERO HUD centrepiece.

Pure QPainter implementation — no OpenGL, no external dependencies.
Draws concentric glowing rings with colour gradients that breathe,
rotate, and react to the live audio level.

Usage:
    from core.gradient_orb import GradientOrb
    orb = GradientOrb()
    orb.step(dt, amp)          # once per tick
    orb.paint(p, cx, cy, r)   # once per frame
"""
from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QLinearGradient,
    QPainter, QPen, QRadialGradient,
)


def _qcol(r: int, g: int, b: int, a: int = 255) -> QColor:
    return QColor(max(0, min(255, r)),
                  max(0, min(255, g)),
                  max(0, min(255, b)),
                  max(0, min(255, a)))


def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(c1.red()   + (c2.red()   - c1.red())   * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue()  + (c2.blue()  - c1.blue())  * t),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )


class GradientOrb:
    """Animated gradient orb centrepiece.

    Lifecycle:
        orb = GradientOrb()
        orb.step(dt, amp)          # advance animation state
        orb.paint(p, cx, cy, r)   # draw at centre (cx, cy) with radius r
    """

    def __init__(self) -> None:
        self._t = 0.0            # accumulated time
        self._phase = 0.0        # rotation phase for conical gradient
        self._breath = 0.0       # breathing scale offset
        self._breath_tgt = 0.0
        self._glow = 0.0         # smoothed audio glow
        self._pulse = 0.0        # inner pulse ring phase
        self._hue_shift = 0.0    # slow hue drift
        self._spark_t = 0.0      # time until next spark
        self._sparks: list[tuple[float, float, float, float]] = []
        self._amp = 0.0

    def step(self, dt: float, amp: float) -> None:
        """Advance animation by dt seconds; amp is 0..1 audio level."""
        self._t += dt
        self._amp = amp
        self._phase += dt * (0.4 + amp * 1.2)
        self._hue_shift += dt * 8.0
        self._pulse += dt * (1.8 + amp * 2.5)

        # Breathing — smooth target with audio lift
        self._breath_tgt = 0.02 * math.sin(self._t * 1.2) + amp * 0.08
        self._breath += (self._breath_tgt - self._breath) * 0.12

        # Glow smoothing
        self._glow += (amp - self._glow) * 0.35

        # Spark particles — brief bright dots that orbit the orb
        self._spark_t -= dt
        if self._spark_t <= 0 and amp > 0.03:
            angle = random.uniform(0, math.tau)
            speed = random.uniform(0.8, 2.0)
            life = random.uniform(0.3, 0.8)
            self._sparks.append((angle, speed, life, life))
            self._spark_t = random.uniform(0.05, 0.25)
        alive = []
        for ang, spd, life, mx in self._sparks:
            new_life = life - dt
            if new_life > 0:
                alive.append((ang + spd * dt, spd, new_life, mx))
        self._sparks = alive

    def paint(self, p: QPainter, cx: float, cy: float, r: float,
              primary: QColor | None = None, accent: QColor | None = None,
              bg: QColor | None = None, amp: float | None = None) -> None:
        """Draw the orb centred at (cx, cy) with radius r.

        primary/accent/bg override the default palette.
        amp overrides the internal smoothed level.
        """
        if primary is None:
            primary = _qcol(0, 212, 255)      # C.PRI cyan
        if accent is None:
            accent = _qcol(255, 107, 0)       # C.ACC orange
        if bg is None:
            bg = _qcol(0, 6, 10)              # C.BG
        a = amp if amp is not None else self._glow

        sc = 1.0 + self._breath
        rr = r * sc

        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)

        # ── outer aura ──────────────────────────────────────────────────
        ar = rr * 2.2
        aura = QRadialGradient(cx, cy, ar)
        aura.setColorAt(0.00, _lerp_color(bg, primary, 0.15 + 0.15 * a))
        aura.setColorAt(0.40, _lerp_color(bg, primary, 0.06 + 0.08 * a))
        aura.setColorAt(1.00, QColor(bg.red(), bg.green(), bg.blue(), 0))
        p.setBrush(QBrush(aura))
        p.drawEllipse(QRectF(cx - ar, cy - ar, ar * 2, ar * 2))

        # ── main orb body ───────────────────────────────────────────────
        grad = QRadialGradient(cx - rr * 0.15, cy - rr * 0.2, rr * 1.1)
        # Colour stops shift with hue
        h = self._hue_shift % 360
        c1 = QColor(primary)
        c1.setHsv((c1.hue() + int(h)) % 360, min(255, c1.saturation() + 30), min(255, c1.value() + 20))
        c2 = QColor(accent)
        c2.setHsv((c2.hue() + int(h * 0.7)) % 360, c2.saturation(), min(255, c2.value() + 10))

        grad.setColorAt(0.00, _lerp_color(c1, _qcol(255, 255, 255), 0.35 + 0.15 * a))
        grad.setColorAt(0.25, _lerp_color(c1, _qcol(255, 255, 255), 0.10))
        grad.setColorAt(0.55, c1)
        grad.setColorAt(0.80, _lerp_color(c1, c2, 0.35))
        grad.setColorAt(1.00, _lerp_color(c2, bg, 0.30))
        p.setBrush(QBrush(grad))
        p.drawEllipse(QRectF(cx - rr, cy - rr, rr * 2, rr * 2))

        # ── inner bright core ───────────────────────────────────────────
        ir = rr * (0.18 + 0.06 * math.sin(self._pulse))
        ig = QRadialGradient(cx, cy, ir)
        ig.setColorAt(0.0, _lerp_color(_qcol(255, 255, 255), primary, 0.20 + 0.10 * a))
        ig.setColorAt(0.5, _lerp_color(primary, _qcol(255, 255, 255), 0.25))
        ig.setColorAt(1.0, QColor(primary.red(), primary.green(), primary.blue(), 0))
        p.setBrush(QBrush(ig))
        p.drawEllipse(QRectF(cx - ir, cy - ir, ir * 2, ir * 2))

        # ── rotating ring ───────────────────────────────────────────────
        ring_r = rr * 0.72
        ring_w = max(1.0, rr * 0.04 + a * rr * 0.03)
        cg = QConicalGradient(cx, cy, -math.degrees(self._phase) % 360)
        cg.setColorAt(0.00, QColor(primary.red(), primary.green(), primary.blue(), int(180 + 75 * a)))
        cg.setColorAt(0.25, QColor(accent.red(), accent.green(), accent.blue(), int(60 + 40 * a)))
        cg.setColorAt(0.50, QColor(primary.red(), primary.green(), primary.blue(), int(40 + 30 * a)))
        cg.setColorAt(0.75, QColor(accent.red(), accent.green(), accent.blue(), int(80 + 50 * a)))
        cg.setColorAt(1.00, QColor(primary.red(), primary.green(), primary.blue(), int(180 + 75 * a)))
        p.setPen(QPen(QBrush(cg), ring_w))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2))

        # ── second ring (counter-rotating) ──────────────────────────────
        ring2_r = rr * 0.88
        cg2 = QConicalGradient(cx, cy, math.degrees(self._phase * 0.6) % 360)
        cg2.setColorAt(0.00, QColor(accent.red(), accent.green(), accent.blue(), int(100 + 55 * a)))
        cg2.setColorAt(0.33, QColor(primary.red(), primary.green(), primary.blue(), int(30 + 20 * a)))
        cg2.setColorAt(0.66, QColor(accent.red(), accent.green(), accent.blue(), int(70 + 40 * a)))
        cg2.setColorAt(1.00, QColor(accent.red(), accent.green(), accent.blue(), int(100 + 55 * a)))
        p.setPen(QPen(QBrush(cg2), ring_w * 0.6))
        p.drawEllipse(QRectF(cx - ring2_r, cy - ring2_r, ring2_r * 2, ring2_r * 2))

        # ── spark particles ─────────────────────────────────────────────
        if self._sparks:
            p.setPen(Qt.PenStyle.NoPen)
            for ang, _spd, life, mx in self._sparks:
                frac = life / mx
                dist = rr * (0.5 + 0.5 * (1.0 - frac))
                sx = cx + math.cos(ang) * dist
                sy = cy + math.sin(ang) * dist
                sz = max(1.0, rr * 0.025 * frac)
                sa = int(220 * frac * frac)
                p.setBrush(QBrush(_qcol(255, 255, 255, sa)))
                p.drawEllipse(QPointF(sx, sy), sz, sz)

        # ── outer glow halo ─────────────────────────────────────────────
        halo_r = rr * (1.3 + 0.15 * a)
        hg = QRadialGradient(cx, cy, halo_r)
        hg.setColorAt(0.00, QColor(primary.red(), primary.green(), primary.blue(), int(20 + 25 * a)))
        hg.setColorAt(0.50, QColor(primary.red(), primary.green(), primary.blue(), int(8 + 10 * a)))
        hg.setColorAt(1.00, QColor(primary.red(), primary.green(), primary.blue(), 0))
        p.setBrush(QBrush(hg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - halo_r, cy - halo_r, halo_r * 2, halo_r * 2))
