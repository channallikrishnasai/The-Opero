"""Generate an original, self-contained static website from a short brief."""
from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path.home() / "Documents" / "OPERO Websites"
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def _safe_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "website").lower()).strip("-")
    if not _NAME.fullmatch(slug):
        raise ValueError("Website name must contain letters, numbers, and hyphens only.")
    return slug


def _render(title: str, summary: str, accent: str) -> str:
    title, summary = html.escape(title), html.escape(summary)
    accent = accent if re.fullmatch(r"#[0-9a-fA-F]{6}", accent) else "#38d9ff"
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>:root{{--accent:{accent};--ink:#07111d;--paper:#eef8fc;--muted:#a5bfce}}*{{box-sizing:border-box}}body{{margin:0;background:var(--ink);color:var(--paper);font:16px/1.6 Inter,system-ui,sans-serif}}main{{max-width:1060px;margin:auto;padding:24px}}nav{{display:flex;justify-content:space-between;padding:15px 0;color:var(--muted)}}.mark{{font-weight:800;letter-spacing:.16em;color:var(--paper)}}.hero{{min-height:550px;display:grid;place-content:center;max-width:740px;background:radial-gradient(circle at 85% 20%,color-mix(in srgb,var(--accent),transparent 75%),transparent 35%)}}.eyebrow{{color:var(--accent);font:700 12px ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase}}h1{{font-size:clamp(48px,8vw,92px);line-height:.96;letter-spacing:-.07em;margin:18px 0}}p{{color:var(--muted);font-size:19px}}a{{display:inline-block;margin-top:18px;padding:12px 17px;border:1px solid var(--accent);border-radius:8px;color:var(--accent);text-decoration:none;font-weight:700}}section{{border-top:1px solid #1a3548;padding:68px 0;display:grid;grid-template-columns:repeat(3,1fr);gap:20px}}article{{padding:22px;border:1px solid #21455b;border-radius:10px;background:#0a1b2b}}article p{{font-size:15px}}@media(max-width:680px){{section{{grid-template-columns:1fr}}}}</style></head>
<body><main><nav><span class="mark">{title.upper()}</span><span>Built with OPERO</span></nav><div class="hero"><span class="eyebrow">Independent digital presence</span><h1>{title}</h1><p>{summary}</p><a href="#learn">Explore more →</a></div><section id="learn"><article><h2>Clear</h2><p>A focused message that introduces what matters.</p></article><article><h2>Useful</h2><p>Structure ready for your content, products, or services.</p></article><article><h2>Yours</h2><p>Plain HTML and CSS you can deploy anywhere.</p></article></section></main></body></html>'''


def execute(parameters: dict) -> str:
    name = _safe_name(parameters.get("name", "website"))
    title = str(parameters.get("title") or name.replace("-", " ").title()).strip()[:100]
    summary = str(parameters.get("summary") or "A website created with OPERO.").strip()[:500]
    folder = ROOT / name
    if folder.exists():
        return f"Website folder already exists: {folder}. Choose a new name; OPERO will not overwrite it."
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "index.html").write_text(_render(title, summary, str(parameters.get("accent", "#38d9ff"))), encoding="utf-8")
    (folder / "README.md").write_text(f"# {title}\n\nOpen index.html locally or deploy this folder to Netlify, GitHub Pages, or any static host.\n", encoding="utf-8")
    return f"Website created at {folder}. Open index.html to preview it."


TOOL = {
    "name": "website_builder",
    "description": "Create an original, deploy-ready static website from a brief in a new OPERO Websites folder.",
    "parameters": {"type": "OBJECT", "properties": {
        "name": {"type": "string", "description": "New URL-safe project name"},
        "title": {"type": "string"}, "summary": {"type": "string"}, "accent": {"type": "string", "description": "Hex color"},
    }, "required": ["name", "title", "summary"]},
    "handler": execute,
}
