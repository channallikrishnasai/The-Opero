from pathlib import Path

from actions import website_builder


def test_website_builder_creates_standalone_site(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(website_builder, "ROOT", tmp_path)
    outcome = website_builder.execute({"name": "demo-site", "title": "Demo", "summary": "A demo site"})
    page = (tmp_path / "demo-site" / "index.html").read_text(encoding="utf-8")
    assert "Website created" in outcome
    assert "Demo" in page


def test_website_builder_refuses_existing_folder(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(website_builder, "ROOT", tmp_path)
    (tmp_path / "demo").mkdir()
    assert "will not overwrite" in website_builder.execute({"name": "demo"})
