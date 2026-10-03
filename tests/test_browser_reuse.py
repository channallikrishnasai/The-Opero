"""Phase 7B: browser reuse-before-create and stale-target recovery helpers."""
from actions.browser_control import (
    _looks_stale, _norm_url, _recover_stale, _reuse_tab, _url_matches,
)


class _FakeMCP:
    def __init__(self, listing="", select_result="Selected.", close_error=False,
                 evaluate_result="A page"):
        self.listing = listing
        self.select_result = select_result
        self.evaluate_result = evaluate_result
        self.close_error = close_error
        self.selected = []
        self.closed = False

    def tabs(self, action="", index=None, **_):
        if action == "list":
            return self.listing
        if action == "select":
            self.selected.append(index)
            return self.select_result
        return ""

    def close(self):
        self.closed = True
        if self.close_error:
            raise RuntimeError("already dead")

    def evaluate(self, _expr):
        if isinstance(self.evaluate_result, Exception):
            raise self.evaluate_result
        return self.evaluate_result


# ── staleness detection ──────────────────────────────────────────────────────

def test_stale_markers_are_detected():
    assert _looks_stale("Target page, context or browser has been closed")
    assert _looks_stale("Error: Target closed")
    assert _looks_stale("browser error: Browser closed unexpectedly")
    assert _looks_stale("Page crashed while loading")


def test_long_page_content_never_reads_as_stale():
    content = "Target page, context or browser " * 60        # > 600 chars
    assert not _looks_stale(content)


def test_ordinary_text_without_error_prefix_is_not_stale():
    assert not _looks_stale("the target closed the deal yesterday")
    assert not _looks_stale("")

def test_error_prefix_rule_requires_target_and_closed():
    assert not _looks_stale("Failed: element not found")     # no 'target'
    assert _looks_stale("Failed to reach target: crashed")


# ── URL comparison ───────────────────────────────────────────────────────────

def test_norm_url_ignores_scheme_www_and_slash():
    assert _norm_url("https://www.Example.com/Path/") == "example.com/path"
    assert _norm_url("http://example.com") == "example.com"
    assert _norm_url("") == ""


def test_url_matches_tolerates_noise_but_not_other_hosts():
    assert _url_matches("https://example.com/docs", "www.example.com/docs/")
    assert _url_matches("example.com", "example.com/anything")
    assert _url_matches("example.com/anything", "example.com")
    assert not _url_matches("other.com", "example.com")
    assert not _url_matches("", "example.com")


# ── reuse before create ──────────────────────────────────────────────────────

# Real MCP listing shape, captured live from mcp.tabs(action="list"):
#   ### Result
#   - 0: [](about:blank)
#   - 1: (current) [Example Domain](https://example.com/)
_LISTING = ("### Result\n"
            "- 0: [](about:blank)\n"
            "- 1: [Example Domain](https://example.com/)\n"
            "- 2: (current) [Python Docs](https://docs.python.org/3/)\n"
            "- 3: [Example (again)](http://www.example.com)")


def test_reuse_tab_selects_the_open_tab_instead_of_creating_one():
    mcp = _FakeMCP(listing=_LISTING)
    out = _reuse_tab(mcp, "https://example.com")
    assert out and out.startswith("Reused the already-open tab 1")
    assert "no new tab created" in out
    assert mcp.selected == [1]


def test_reuse_tab_returns_none_when_url_is_not_open():
    mcp = _FakeMCP(listing=_LISTING)
    assert _reuse_tab(mcp, "https://openai.com") is None
    assert mcp.selected == []                 # never even tried a select


def test_reuse_tab_tolerates_scheme_www_and_slash_drift():
    mcp = _FakeMCP(listing=_LISTING)
    out = _reuse_tab(mcp, "www.example.com/")     # matches tab 1 by host+path
    assert out and "tab 1" in out


def test_reuse_tab_gives_up_on_stale_listings_and_selects():
    stale = _FakeMCP(listing="Target page, context or browser has been closed")
    assert _reuse_tab(stale, "https://example.com") is None

    bad_select = _FakeMCP(listing=_LISTING,
                          select_result="Error: Target closed")
    assert _reuse_tab(bad_select, "https://example.com") is None

    missing = _FakeMCP(listing=_LISTING, select_result="index does not exist")
    assert _reuse_tab(missing, "https://example.com") is None


def test_reuse_tab_survives_a_broken_tab_listing():
    class _Broken:
        def tabs(self, **_):
            raise RuntimeError("transport down")

    assert _reuse_tab(_Broken(), "https://example.com") is None


def test_reuse_tab_ignores_empty_urls():
    mcp = _FakeMCP(listing=_LISTING)
    assert _reuse_tab(mcp, "") is None


# ── stale recovery ───────────────────────────────────────────────────────────

def test_recover_stale_restarts_and_proves_liveness():
    mcp = _FakeMCP(evaluate_result="A page")
    assert _recover_stale(mcp) is True
    assert mcp.closed is True                 # server was shut down once


def test_recover_stale_fails_honestly_when_probe_stays_stale():
    mcp = _FakeMCP(evaluate_result="Target page, context or browser has been closed")
    assert _recover_stale(mcp) is False


def test_recover_stale_fails_honestly_on_transport_error():
    mcp = _FakeMCP(close_error=True)
    assert _recover_stale(mcp) is False
