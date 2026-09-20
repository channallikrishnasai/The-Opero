"""
ppt_builder.py — OPERO PowerPoint Presentation Builder

Generates multi-slide PowerPoint .pptx decks from structured inputs.
Supports multiple visual themes: auto, neon, corporate, luxury, academic, sunset.
Adapted from OPERO for the OPERO action-loader format.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ── Project layout ────────────────────────────────────────────────────────────

PROJECT_NAME = "OPERO"
DEFAULT_OUTPUT_DIR = Path.home() / "Documents" / "OPERO Presentations"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sanitize_filename(name: str, default: str = "presentation") -> str:
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "", (name or "").strip())
    safe = re.sub(r"\s+", " ", safe).strip().replace(" ", "_")
    return safe or default


def _resolve_output_path(output_path: str | None, title: str) -> Path:
    if output_path:
        path = Path(output_path).expanduser()
        if not path.is_absolute():
            head = path.parts[0].lower() if path.parts else ""
            tail = Path(*path.parts[1:]) if len(path.parts) > 1 else Path(path.name)
            if head in {"downloads", "download"}:
                path = Path.home() / "Downloads" / tail
            elif head == "desktop":
                path = Path.home() / "Desktop" / tail
            else:
                path = Path.cwd() / path
        if path.suffix.lower() != ".pptx":
            path = path.with_suffix(".pptx")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_OUTPUT_DIR / f"{_sanitize_filename(title)}.pptx"


def _open_file(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def _parse_json_arg(value, fallback):
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            return fallback
        try:
            return json.loads(txt)
        except Exception:
            return fallback
    return fallback


def _import_pptx():
    try:
        from pptx import Presentation
        from pptx.dml.color import RGBColor
        from pptx.util import Inches, Pt
        return Presentation, RGBColor, Inches, Pt
    except Exception as e:
        raise RuntimeError("python-pptx is required: pip install python-pptx") from e


# ── Theme library ─────────────────────────────────────────────────────────────

_THEMES = {
    "auto": {
        "bg": "07131C", "panel": "0E2230", "accent": "00D4FF",
        "accent2": "FF8A3D", "text": "F1FAFF", "muted": "8DB7C8", "line": "23485E",
    },
    "neon": {
        "bg": "05070C", "panel": "111827", "accent": "21E6C1",
        "accent2": "7C5CFF", "text": "F6FAFF", "muted": "98A9C0", "line": "253245",
    },
    "corporate": {
        "bg": "081018", "panel": "102130", "accent": "F97316",
        "accent2": "22C55E", "text": "F8FAFC", "muted": "94A3B8", "line": "2B4057",
    },
    "luxury": {
        "bg": "0A0910", "panel": "161320", "accent": "D4AF37",
        "accent2": "F3E8C7", "text": "FFFDF7", "muted": "C9C1B2", "line": "3B314E",
    },
    "academic": {
        "bg": "0D1117", "panel": "141A22", "accent": "60A5FA",
        "accent2": "F59E0B", "text": "F8FAFC", "muted": "94A3B8", "line": "263445",
    },
    "sunset": {
        "bg": "1A0F14", "panel": "25141A", "accent": "FB7185",
        "accent2": "FDBA74", "text": "FFF7F8", "muted": "E5B7C0", "line": "402430",
    },
}


def _select_theme(theme_hint: str | None, title: str = "", subtitle: str = "") -> dict:
    text = f"{theme_hint or ''} {title} {subtitle}".lower()
    if any(w in text for w in ["neon", "futur", "tech", "cyber", "ai", "startup"]):
        return _THEMES["neon"]
    if any(w in text for w in ["luxury", "premium", "gold", "fashion", "brand"]):
        return _THEMES["luxury"]
    if any(w in text for w in ["finance", "corp", "board", "enterprise", "business"]):
        return _THEMES["corporate"]
    if any(w in text for w in ["academic", "research", "science", "education", "study"]):
        return _THEMES["academic"]
    if any(w in text for w in ["sunset", "creative", "marketing", "campaign"]):
        return _THEMES["sunset"]
    return _THEMES["auto"]


def _hex_to_rgb(hex_str: str):
    h = hex_str.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# ── Core presentation builder ─────────────────────────────────────────────────

def _build_presentation(
    title: str,
    subtitle: str,
    slides: list[dict],
    theme: dict,
    output_path: Path,
) -> Path:
    Presentation, RGBColor, Inches, Pt = _import_pptx()

    from pptx.util import Emu
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6]  # Blank

    def hex_rgb(h: str):
        r, g, b = _hex_to_rgb(h)
        return RGBColor(r, g, b)

    def add_bg(slide):
        from pptx.util import Emu
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = hex_rgb(theme["bg"])

    def add_text_box(slide, text, left, top, width, height, font_size, bold=False, color=None, align="left"):
        from pptx.util import Emu
        from pptx.enum.text import PP_ALIGN
        txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = text
        if align == "center":
            p.alignment = PP_ALIGN.CENTER
        run = p.runs[0]
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.name = "Segoe UI"
        run.font.color.rgb = hex_rgb(color or theme["text"])

    def add_rect(slide, left, top, width, height, color, alpha=None):
        from pptx.util import Emu
        shape = slide.shapes.add_shape(
            1,  # MSO_SHAPE_TYPE.RECTANGLE
            Inches(left), Inches(top), Inches(width), Inches(height)
        )
        shape.fill.solid()
        r, g, b = _hex_to_rgb(color)
        shape.fill.fore_color.rgb = RGBColor(r, g, b)
        shape.line.color.rgb = hex_rgb(theme["line"])
        shape.line.width = Pt(0.5)
        return shape

    # ── Title slide ──────────────────────────────────────────────────────────
    slide = prs.slides.add_slide(blank_layout)
    add_bg(slide)
    add_rect(slide, 0, 5.8, 13.33, 0.05, theme["accent"])
    add_text_box(slide, "OPERO", 0.5, 0.3, 4, 0.5, 9, bold=True, color=theme["accent"])
    add_text_box(slide, title, 0.5, 1.8, 12, 2.5, 44, bold=True, color=theme["text"])
    add_text_box(slide, subtitle or "", 0.5, 4.5, 10, 1, 22, color=theme["muted"])
    add_text_box(slide, "Generated by OPERO", 0.5, 6.5, 6, 0.5, 9, color=theme["muted"])

    # ── Content slides ────────────────────────────────────────────────────────
    for i, slide_data in enumerate(slides):
        slide = prs.slides.add_slide(blank_layout)
        add_bg(slide)
        add_rect(slide, 0, 0, 13.33, 0.08, theme["accent"])
        add_rect(slide, 0, 6.9, 13.33, 0.05, theme["line"])

        slide_title = str(slide_data.get("title", f"Slide {i+1}"))
        kicker = str(slide_data.get("kicker", ""))
        bullets = slide_data.get("bullets") or []
        if isinstance(bullets, str):
            bullets = [b.strip() for b in bullets.split("\n") if b.strip()]
        notes = str(slide_data.get("notes", ""))

        if kicker:
            add_text_box(slide, kicker.upper(), 0.5, 0.2, 10, 0.4, 9, bold=True, color=theme["accent"])

        add_text_box(slide, slide_title, 0.5, 0.7, 12, 1.2, 30, bold=True, color=theme["text"])
        add_rect(slide, 0.5, 1.95, 1.2, 0.04, theme["accent"])

        bullet_text = "\n".join(f"• {b}" for b in bullets) if bullets else ""
        if bullet_text:
            txBox = slide.shapes.add_textbox(Inches(0.5), Inches(2.15), Inches(12.3), Inches(4.5))
            tf = txBox.text_frame
            tf.word_wrap = True
            from pptx.util import Pt as _Pt
            for j, bullet in enumerate(bullets):
                p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
                run = p.add_run()
                run.text = f"• {bullet}"
                run.font.size = _Pt(18)
                run.font.name = "Segoe UI"
                r2, g2, b2 = _hex_to_rgb(theme["text"])
                run.font.color.rgb = RGBColor(r2, g2, b2)

        # Footer
        slide_num_text = f"{str(i+2).zfill(2)} / {str(len(slides)+1).zfill(2)}"
        add_text_box(slide, slide_num_text, 11.5, 7.0, 1.5, 0.4, 9, color=theme["muted"])
        add_text_box(slide, "OPERO", 0.4, 7.0, 3, 0.4, 9, bold=True, color=theme["accent"])

        if notes:
            slide.notes_slide.notes_text_frame.text = notes

    prs.save(str(output_path))
    return output_path


# ── Public action entry point ─────────────────────────────────────────────────

def execute(parameters: dict) -> str:
    title = str(parameters.get("title") or "Untitled Presentation").strip()[:120]
    subtitle = str(parameters.get("subtitle") or "").strip()[:200]
    theme_hint = str(parameters.get("theme") or "").strip()
    output_path_str = parameters.get("output_path") or None
    open_after = bool(parameters.get("open_after", True))

    raw_slides = _parse_json_arg(parameters.get("slides"), [])
    if not isinstance(raw_slides, list):
        raw_slides = []

    if not raw_slides:
        raw_slides = [
            {"title": "Introduction", "kicker": "Overview", "bullets": ["Welcome to this presentation", "Agenda follows"]},
            {"title": "Main Points", "kicker": "Key Content", "bullets": ["First key point", "Second key point", "Third key point"]},
            {"title": "Summary", "kicker": "Conclusion", "bullets": ["Recap of main points", "Next steps", "Questions?"]},
        ]

    theme = _select_theme(theme_hint, title, subtitle)
    output_path = _resolve_output_path(output_path_str, title)

    try:
        path = _build_presentation(title, subtitle, raw_slides, theme, output_path)
        if open_after:
            _open_file(path)
        return (
            f"✅ Presentation created: {path}\n"
            f"   Slides: {len(raw_slides) + 1} (title + {len(raw_slides)} content)\n"
            f"   Theme: {theme_hint or 'auto'}"
        )
    except RuntimeError as e:
        return f"❌ {e}"
    except Exception as e:
        return f"❌ Failed to create presentation: {e}"


# ── OPERO tool registration ───────────────────────────────────────────────────

TOOL = {
    "name": "ppt_builder",
    "description": (
        "Creates a polished PowerPoint (.pptx) presentation from a title, optional subtitle, "
        "and a list of slides. Each slide supports: title, kicker (eyebrow label), bullets (list of strings), "
        "and notes. Supports themes: auto, neon, corporate, luxury, academic, sunset. "
        "Use when the user asks to create a presentation, slideshow, deck, or PowerPoint."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "title": {"type": "STRING", "description": "Presentation title"},
            "subtitle": {"type": "STRING", "description": "Optional subtitle shown on the title slide"},
            "theme": {
                "type": "STRING",
                "description": "Visual theme: auto, neon, corporate, luxury, academic, sunset",
            },
            "slides": {
                "type": "STRING",
                "description": (
                    "JSON array of slide objects. Each object: "
                    "{\"title\": str, \"kicker\": str, \"bullets\": [str, ...], \"notes\": str}"
                ),
            },
            "output_path": {
                "type": "STRING",
                "description": "Optional output path. Defaults to ~/Documents/OPERO Presentations/",
            },
            "open_after": {
                "type": "BOOLEAN",
                "description": "Open the file in PowerPoint when done (default true)",
            },
        },
        "required": ["title"],
    },
    "handler": execute,
}
