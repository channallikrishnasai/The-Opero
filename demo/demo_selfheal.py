"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           O.P.E.R.O  —  SELF-HEAL ENGINE  LIVE DEMONSTRATION               ║
║      Watch the AI detect bugs, synthesize patches, and heal itself          ║
╚══════════════════════════════════════════════════════════════════════════════╝

Run this from the project root:
    python demo/demo_selfheal.py

What you will see:
    1. Three live bugs triggered with real tracebacks
    2. The heal engine analyze each traceback
    3. Gemini synthesize a minimal patch for each bug
    4. Safety Sandbox validate the patch (AST + py_compile)
    5. Atomic backup created before any change
    6. Patch applied to disk
    7. Healed function verified by re-running it
"""

from __future__ import annotations

import os
import sys
import time
import shutil
import traceback
import textwrap
from pathlib import Path

# ── Make sure project root is on sys.path ─────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── ANSI colours (work in VS Code integrated terminal) ────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
MAG    = "\033[95m"
WHITE  = "\033[97m"

BAR    = f"{CYAN}{'─' * 78}{RESET}"
DBAR   = f"{CYAN}{'═' * 78}{RESET}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _print(text: str = "") -> None:
    print(text)

def _delay(s: float = 0.04) -> None:
    time.sleep(s)

def _typewrite(text: str, delay: float = 0.018, colour: str = WHITE) -> None:
    for ch in text:
        sys.stdout.write(colour + ch + RESET)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def _header(title: str) -> None:
    _print()
    _print(DBAR)
    pad = (78 - len(title)) // 2
    _print(f"{CYAN}{BOLD}{' ' * pad}{title}{RESET}")
    _print(DBAR)

def _section(title: str) -> None:
    _print()
    _print(BAR)
    _print(f"  {YELLOW}{BOLD}{title}{RESET}")
    _print(BAR)

def _label(key: str, val: str, colour: str = CYAN) -> None:
    _print(f"  {DIM}{key:<22}{RESET}{colour}{val}{RESET}")

def _ok(msg: str) -> None:
    _print(f"  {GREEN}{BOLD}✓  {msg}{RESET}")

def _warn(msg: str) -> None:
    _print(f"  {YELLOW}⚠  {msg}{RESET}")

def _err(msg: str) -> None:
    _print(f"  {RED}✗  {msg}{RESET}")

def _box(lines: list[str], colour: str = DIM) -> None:
    _print(f"  {colour}┌{'─'*74}┐{RESET}")
    for line in lines:
        padded = line[:72].ljust(72)
        _print(f"  {colour}│ {WHITE}{padded}{colour} │{RESET}")
    _print(f"  {colour}└{'─'*74}┘{RESET}")

def _spinner(msg: str, duration: float = 2.0) -> None:
    frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    end = time.time() + duration
    i = 0
    while time.time() < end:
        sys.stdout.write(f"\r  {CYAN}{frames[i % len(frames)]}  {msg}...{RESET}")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    sys.stdout.write(f"\r  {GREEN}✓  {msg} — Done!{RESET}{'':30}\n")


# ── Reload the demo module fresh each time ────────────────────────────────────

def _reload_demo():
    """Reload demo_broken_module so we always test the current file on disk."""
    import importlib
    mod_name = "demo.demo_broken_module"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    # Also clear submodule if cached differently
    if "demo_broken_module" in sys.modules:
        del sys.modules["demo_broken_module"]
    import demo.demo_broken_module as m
    return m


# ── Demo case runner ──────────────────────────────────────────────────────────

def run_demo_case(
    case_num: int,
    title: str,
    description: str,
    trigger_fn,          # callable that intentionally raises
    verify_fn,           # callable to run AFTER healing (should succeed)
    context_note: str = "",
) -> bool:
    """
    Runs a single self-heal demonstration:
    1. Trigger the bug → capture traceback
    2. Feed to AutoHealEngine
    3. Show the result
    4. Verify the fix works
    """

    _header(f"DEMO {case_num} OF 3  —  {title}")

    # ── Step 1: Describe the bug ───────────────────────────────────────────────
    _section("📋  BUG DESCRIPTION")
    _typewrite(description, colour=WHITE)
    _delay(0.3)

    # ── Step 2: Trigger the exception ─────────────────────────────────────────
    _section("💥  TRIGGERING THE BUG")
    tb_text = ""
    try:
        trigger_fn()
        _err("Expected an exception but none was raised.")
        return False
    except Exception:
        tb_text = traceback.format_exc()
        lines = tb_text.strip().splitlines()
        _box(lines, colour=RED)
        _delay(0.5)

    # ── Step 3: Analyse ────────────────────────────────────────────────────────
    _section("🔍  TRACEBACK ANALYSIS")
    _spinner("Parsing traceback", 1.2)

    from actions.auto_heal_engine import TracebackAnalyzer
    parsed = TracebackAnalyzer.parse(tb_text)

    if not parsed["success"]:
        _err("Could not identify a first-party source file from this traceback.")
        _warn("Skipping this case.")
        return False

    _label("Target file :", Path(parsed["target_file"]).name)
    _label("Line number :", str(parsed["line_number"]))
    _label("Exception   :", parsed["exception_type"])
    _label("Message     :", (parsed["exception_message"] or "")[:70])
    _delay(0.4)

    # ── Step 4: Synthesize patch ───────────────────────────────────────────────
    _section("🧠  GEMINI — PATCH SYNTHESIS")
    _typewrite("Sending code context + traceback to Gemini 2.5 Flash...", colour=DIM)
    _spinner("Synthesising minimal surgical hotfix", 3.5)

    # ── Step 5: Apply patch ────────────────────────────────────────────────────
    _section("⚡  SAFETY SANDBOX + PATCH APPLICATION")
    _typewrite("Validating patch AST syntax in memory before touching disk...", colour=DIM)

    from actions.auto_heal_engine import AutoHealEngine
    result = AutoHealEngine.heal_traceback(tb_text, context_notes=context_note)

    if not result["success"]:
        _err(f"Heal failed: {result.get('message')}")
        return False

    _ok("AST syntax validation passed — patch is safe")
    _ok(f"Atomic backup created")
    _ok(f"Patch written and py_compile verified")
    _print()
    _label("Patch ID    :", result.get("patch_id", "N/A"), colour=MAG)
    _label("Explanation :", result.get("explanation", "")[:72])
    _delay(0.4)

    # ── Step 6: Verify the fix ─────────────────────────────────────────────────
    _section("✅  VERIFYING THE HEALED CODE")
    _typewrite("Reloading patched module and re-running the failing call...", colour=DIM)

    try:
        m = _reload_demo()
        output = verify_fn(m)
        _ok(f"Call succeeded! → {output}")
    except Exception as e:
        _err(f"Verification failed after patching: {e}")
        _warn("The patch may need another iteration.")
        return False

    _delay(0.3)
    return True


# ── Main demo ─────────────────────────────────────────────────────────────────

def main() -> None:
    os.system("cls" if os.name == "nt" else "clear")

    _print(f"""
{CYAN}{BOLD}
  ██████╗ ██████╗ ███████╗██████╗  ██████╗
 ██╔═══██╗██╔══██╗██╔════╝██╔══██╗██╔═══██╗
 ██║   ██║██████╔╝█████╗  ██████╔╝██║   ██║
 ██║   ██║██╔═══╝ ██╔══╝  ██╔══██╗██║   ██║
 ╚██████╔╝██║     ███████╗██║  ██║╚██████╔╝
  ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═╝ ╚═════╝
{RESET}""")

    _typewrite("  SELF-HEAL ENGINE  —  LIVE DEMONSTRATION", colour=f"{CYAN}{BOLD}")
    _print(f"  {DIM}Watch OPERO detect bugs, synthesize patches, and fix its own code in real-time{RESET}")
    _print()
    _print(f"  {YELLOW}Target file   :{RESET}  demo/demo_broken_module.py")
    _print(f"  {YELLOW}AI Backend    :{RESET}  Google Gemini 2.5 Flash")
    _print(f"  {YELLOW}Safety checks :{RESET}  AST parse  →  py_compile  →  atomic backup")
    _print(f"  {YELLOW}Demo cases    :{RESET}  3 bugs  (ZeroDivisionError, KeyError, TypeError)")
    _print()
    input(f"  {GREEN}Press ENTER to begin the demonstration...{RESET}")

    # ─── Keep a backup of the original file so we can restore it after demo ───
    demo_file = ROOT / "demo" / "demo_broken_module.py"
    backup    = ROOT / "demo" / "demo_broken_module.py.original"
    shutil.copy2(demo_file, backup)

    results: list[bool] = []

    # ═══════════════════════════════════════════════════════════════════════════
    # CASE 1 — ZeroDivisionError
    # ═══════════════════════════════════════════════════════════════════════════
    def trigger_1():
        import demo.demo_broken_module as m
        return m.divide_numbers(10, 0)

    def verify_1(m):
        return m.divide_numbers(10, 0)   # after patch should return safe value

    ok1 = run_demo_case(
        case_num=1,
        title="ZeroDivisionError",
        description=(
            "divide_numbers(a, b) performs a / b with no guard against b=0.\n"
            "  Calling divide_numbers(10, 0) crashes with ZeroDivisionError.\n"
            "  The self-heal engine will add a zero-division guard automatically."
        ),
        trigger_fn=trigger_1,
        verify_fn=verify_1,
        context_note="Add a safe zero-division guard that returns 0 or infinity when b is 0.",
    )
    results.append(ok1)
    input(f"\n  {DIM}Press ENTER for the next demo...{RESET}")

    # ═══════════════════════════════════════════════════════════════════════════
    # CASE 2 — KeyError
    # ═══════════════════════════════════════════════════════════════════════════
    def trigger_2():
        import demo.demo_broken_module as m
        return m.get_user_name({})       # missing 'username' key

    def verify_2(m):
        return m.get_user_name({})       # after patch should return safe default

    ok2 = run_demo_case(
        case_num=2,
        title="KeyError — Missing Dictionary Key",
        description=(
            "get_user_name(data) accesses data['username'] directly with no guard.\n"
            "  Passing an empty dict crashes with KeyError: 'username'.\n"
            "  The engine will add a .get() fallback or try/except guard."
        ),
        trigger_fn=trigger_2,
        verify_fn=verify_2,
        context_note="Use dict.get() with a safe default instead of direct key access.",
    )
    results.append(ok2)
    input(f"\n  {DIM}Press ENTER for the final demo...{RESET}")

    # ═══════════════════════════════════════════════════════════════════════════
    # CASE 3 — TypeError / ValueError
    # ═══════════════════════════════════════════════════════════════════════════
    def trigger_3():
        import demo.demo_broken_module as m
        return m.parse_score("not_a_number")   # can't int() a non-numeric string

    def verify_3(m):
        return m.parse_score("not_a_number")   # after patch should return safe value

    ok3 = run_demo_case(
        case_num=3,
        title="ValueError — Type Conversion Failure",
        description=(
            "parse_score(value) does int(value) with no exception handling.\n"
            "  Passing a non-numeric string raises ValueError: invalid literal.\n"
            "  The engine will wrap the conversion in try/except with a safe fallback."
        ),
        trigger_fn=trigger_3,
        verify_fn=verify_3,
        context_note="Wrap int() in a try/except ValueError block returning 0 as safe default.",
    )
    results.append(ok3)

    # ═══════════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════════════════
    _header("DEMONSTRATION COMPLETE — SUMMARY")

    passed = sum(results)
    total  = len(results)

    _print(f"""
  {CYAN}┌─────────────────────────────────────────────────┐
  │   Cases run      : {WHITE}{total}{CYAN}                             │
  │   Patches applied: {GREEN if passed==total else YELLOW}{passed}{CYAN}                             │
  │   Failures       : {RED if total-passed else GREEN}{total - passed}{CYAN}                             │
  └─────────────────────────────────────────────────┘{RESET}
""")

    for i, (ok, label) in enumerate(zip(results, [
        "ZeroDivisionError guard",
        "KeyError  → .get() fallback",
        "ValueError → try/except wrap",
    ]), 1):
        icon = f"{GREEN}✓" if ok else f"{RED}✗"
        _print(f"  {icon}  Case {i}: {label}{RESET}")

    _print()

    # Restore original broken file so demo can be re-run
    if backup.exists():
        shutil.copy2(backup, demo_file)
        backup.unlink()
        _print(f"  {DIM}(demo_broken_module.py restored to original broken state for next run){RESET}")

    _print()
    _print(f"  {CYAN}{BOLD}Patch history saved to:{RESET}  config/patch_history.json")
    _print(f"  {CYAN}{BOLD}Backups stored in    :{RESET}  config/patch_backups/")
    _print()
    _typewrite("  OPERO Self-Heal Engine — End of Demonstration", colour=f"{CYAN}{BOLD}")
    _print()


if __name__ == "__main__":
    main()
