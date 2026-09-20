from pathlib import Path


def test_netlify_configuration_publishes_original_landing_page():
    root = Path(__file__).resolve().parent.parent
    config = (root / "netlify.toml").read_text(encoding="utf-8")
    page = (root / "site" / "index.html").read_text(encoding="utf-8")
    assert 'publish = "site"' in config
    assert "X-Frame-Options" in config
    assert "<title>OPERO" in page
    assert "Brahma" not in page

