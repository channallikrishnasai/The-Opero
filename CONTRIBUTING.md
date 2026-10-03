# Contributing to Opero

Thank you for your interest in contributing to Opero! This guide will help you get started.

## Architecture Overview

```
opero/
├── main.py              # Entry point, OperaLive session manager, live Gemini session + tool dispatch
├── ui/                  # PyQt6 UI package: window.py (MainWindow), widgets.py, overlays.py, theme.py, proxy.py (OperaUI); ui.py is a legacy re-export shim, shadowed by the package
├── core/
│   ├── gemini.py        # One-shot Gemini calls (used by file-processing actions)
│   ├── llm_client.py    # Local LLM support (Ollama, OpenAI-compatible) — ORPHANED, not imported
│   ├── action_loader.py # Discovers actions/*.py and dispatches their handlers
│   ├── echo.py          # Content-based echo cancellation
│   ├── viseme.py        # Lip-sync viseme generation
│   ├── tts.py           # Multi-engine TTS (EdgeTTS, Kokoro, ElevenLabs) — ORPHANED; runtime speech is Gemini-native
│   ├── stt.py           # Multi-engine STT (Whisper, Vosk) — ORPHANED; runtime STT is Gemini-native + AssemblyAI
│   ├── wake_word.py     # Local "Hey opero" wake word detection
│   ├── confirm.py       # Human confirmation gate for destructive actions
│   ├── validator.py     # Input validation for tool parameters — ORPHANED (test-only)
│   ├── logger.py        # Centralized logging configuration
│   ├── installer.py     # Auto-dependency installer
│   ├── avatar.py        # Avatar rendering (holographic orb)
│   └── prompt.txt       # AI behavior specification
├── actions/             # Self-registering tool modules (TOOL dict pattern)
│   ├── browser_control.py
│   ├── send_message.py
│   ├── screen_processor.py
│   └── ...              # 52 modules; 37 expose a TOOL dict → 37 active discovered actions
├── memory/
│   ├── config_manager.py   # Settings persistence (JSON + AES encryption)
│   └── memory_manager.py   # Long-term memory with search
├── dashboard/
│   └── server.py        # Local HTTP dashboard (FastAPI + WebSocket)
├── plugins/             # Hot-loadable plugin system
├── config/              # Runtime config (gitignored)
├── tests/               # Test suite (pytest)
└── pyproject.toml       # Modern Python packaging
```

## Key Design Patterns

### Tool Registration
Every action module exposes a module-level `TOOL` dict — the loader rejects the file if any required key is missing:
```python
def execute(params: dict) -> str:
    # params arrive from Gemini's function call; validate what matters to you
    ...

TOOL = {
    "name": "my_action",
    "description": "What this tool does",                              # what Gemini reads to route
    "parameters": {"type": "OBJECT", "properties": { ... }},           # Gemini function-declaration schema
    "handler": execute,                                                # required callable
}
```

### Logging
Use `core.logger` everywhere — never raw `print()`:
```python
from core.logger import get_logger
log = get_logger(__name__)
log.info("Something happened")
log.error("Something failed", exc_info=True)
```

### Error Handling
Never use bare `except: pass`. Always catch specific exceptions:
```python
try:
    result = api_call()
except ConnectionError:
    log.warning("API unreachable")
except TimeoutError:
    log.warning("API timed out")
except Exception as e:
    log.error("Unexpected error: %s", e, exc_info=True)
```

## Development Setup

```bash
# Clone and install
git clone https://github.com/yourusername/opero.git
cd opero
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Lint and type-check
ruff check . --select F821   # the enforced CI gate — must stay clean
ruff check .                 # full run: known debt (~1,844 findings), not CI-enforced
mypy .
```

## Adding a New Action

1. Create `actions/my_action.py`
2. Define the `TOOL` dict (`name`, `description`, `parameters`, `handler`)
3. Implement the handler function referenced by `TOOL["handler"]`
4. Add tests in `tests/test_my_action.py`
5. The action is auto-discovered on next startup

## Code Style

- Line length: 120 characters max
- Use type hints on all public functions
- Docstrings for all public classes and functions
- `snake_case` for functions/variables, `CamelCase` for classes
- Use `core.logger` for all output

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=term-missing

# Run specific test file
python -m pytest tests/test_validator.py -v
```

## Pull Request Checklist

- [ ] Code compiles (`python -m py_compile <changed_files>`)
- [ ] Tests pass (`python -m pytest tests/ -v`)
- [ ] No new bare `except: pass` blocks
- [ ] Uses `core.logger` instead of `print()`
- [ ] Input validation added for new tool parameters
- [ ] Type hints on new public functions
