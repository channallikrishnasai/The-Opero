"""
MOSS (Measure of Software Similarity) plagiarism checker action.

Uploads source code files to Stanford's MOSS server and returns a URL
with similarity results.  Supports all MOSS languages and directory mode.

Requires: no extra packages (uses stdlib socket).
Config:   moss_user_id and moss_key in config/api_keys.json.
"""
from __future__ import annotations

import glob
import json
import os
import socket
import sys
import time
import tempfile
import zipfile
import base64
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
_CFG  = _BASE / "config" / "api_keys.json"

_MOSS_HOST = "moss.stanford.edu"
_MOSS_PORT = 7690

# Language codes accepted by MOSS
LANGUAGES = {
    "c": "c", "cc": "cc", "cpp": "cc", "c++": "cc",
    "java": "java", "python": "python", "python3": "python",
    "javascript": "javascript", "js": "javascript",
    "haskell": "haskell", "hs": "haskell",
    "lisp": "lisp", "scheme": "scheme", "racket": "scheme",
    "pascal": "pascal", "ml": "ml", "ocaml": "ml",
    "prolog": "prolog", "fortran": "fortran", "ada": "ada",
    "perl": "perl", "ruby": "ruby", "go": "go", "rust": "rust",
    "sql": "sql", "matlab": "matlab", "scala": "scala",
    "swift": "swift", "kotlin": "kotlin", "r": "r",
    "v": "verilog", "verilog": "verilog", "vhdl": "vhdl",
    "assembly": "mips", "mips": "mips", "tcl": "tcl",
    "basic": "basic", "lua": "lua", "php": "php",
    "typescript": "javascript", "ts": "javascript",
    "dart": "dart", "elixir": "elixir", "ex": "elixir",
    "julia": "julia",
}


def _load_config() -> dict:
    try:
        return json.loads(_CFG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _moss_upload(user_id: str, files: list[tuple[str, str]],
                 language: str, base_files: list[tuple[str, str]] | None = None,
                 directory_mode: bool = False, max_matches: int = 10,
                 show: int = 250, comment: str = "") -> str:
    """Upload files to MOSS and return the results URL.

    Parameters
    ----------
    user_id : str
        MOSS user ID (the numeric/string ID from moss.stanford.edu).
    files : list of (filename, contents) tuples
        Source files to compare.
    language : str
        MOSS language code (e.g. "python", "java", "cc").
    base_files : list of (filename, contents), optional
        Base/instructor files to exclude from matches.
    directory_mode : bool
        True = treat each file as part of a directory submission.
    max_matches : int
        Max number of times a passage can appear before ignored.
    show : int
        Number of matching files to show in results.
    comment : str
        Comment string attached to the report.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(60)
    sock.connect((_MOSS_HOST, _MOSS_PORT))

    def send(line: str):
        sock.sendall((line + "\n").encode("ascii"))

    def send_file(file_id: int, name: str, content: str) -> None:
        """Send one source file using the MOSS wire protocol.

        MOSS expects language and byte count in the file header.  The previous
        implementation omitted both, which made valid-looking uploads fail at
        the server before any similarity analysis began.
        """
        payload = (content.encode("utf-8", errors="replace")
                   if isinstance(content, str) else content)
        safe_name = str(name).replace("\n", "_").replace("\r", "_")
        send(f"file {file_id} {language} {len(payload)} {safe_name}")
        sock.sendall(payload)

    # Handshake
    send(f"moss {user_id}")
    time.sleep(0.5)

    # Options
    send(f"directory {1 if directory_mode else 0}")
    send(f"X {language}")
    send(f"maxmatches {max_matches}")
    send(f"show {show}")
    if comment:
        send(f"comment {comment}")

    # Upload base files (if any)
    if base_files:
        for name, content in base_files:
            send_file(0, name, content)

    # Upload source files
    for i, (name, content) in enumerate(files):
        send_file(i + 1, name, content)

    # Submit
    send("end")
    time.sleep(0.5)
    send(f"query {user_id}")
    send("query end")

    # Read response
    response = b""
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if b"\n" in response:
                break
    except socket.timeout:
        pass
    finally:
        sock.close()

    url = response.decode("utf-8", errors="replace").strip()
    return url


def _collect_files(directory: str, extensions: str = "") -> list[tuple[str, str]]:
    """Recursively collect source files from a directory.

    Returns list of (relative_path, contents) tuples.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return []

    exts = set()
    if extensions:
        for e in extensions.split(","):
            e = e.strip().lstrip(".")
            if e:
                exts.add(f".{e}")

    default_exts = {
        ".py", ".java", ".c", ".cc", ".cpp", ".h", ".hpp", ".js", ".ts",
        ".hs", ".lisp", ".scm", ".rkt", ".ml", ".mli", ".pl", ".pm",
        ".rb", ".go", ".rs", ".swift", ".kt", ".scala", ".r", ".m",
        ".v", ".vhd", ".sql", ".lua", ".php", ".dart", ".ex", ".exs",
        ".jl", ".bas", ".pas", ".f", ".f90", ".adb", ".ads", ".tcl",
    }
    if not exts:
        exts = default_exts

    files = []
    for path in sorted(dir_path.rglob("*")):
        if path.is_file() and path.suffix.lower() in exts:
            try:
                rel = str(path.relative_to(dir_path)).replace("\\", "/")
                content = path.read_text(encoding="utf-8", errors="replace")
                files.append((rel, content))
            except Exception:
                continue
    return files


def _detect_language(directory: str) -> str:
    """Auto-detect the dominant language from file extensions."""
    dir_path = Path(directory)
    if not dir_path.exists():
        return "python"

    ext_count: dict[str, int] = {}
    ext_lang = {
        ".py": "python", ".java": "java", ".c": "c", ".cc": "cc",
        ".cpp": "cc", ".h": "c", ".hpp": "cc", ".js": "javascript",
        ".ts": "javascript", ".hs": "haskell", ".lisp": "lisp",
        ".scm": "scheme", ".rkt": "scheme", ".ml": "ml", ".pl": "perl",
        ".rb": "ruby", ".go": "go", ".rs": "rust", ".swift": "swift",
        ".kt": "kotlin", ".scala": "scala", ".r": "r", ".m": "matlab",
        ".v": "verilog", ".vhd": "vhdl", ".sql": "sql", ".lua": "lua",
        ".php": "php", ".dart": "dart", ".jl": "julia",
    }
    for path in dir_path.rglob("*"):
        if path.is_file():
            lang = ext_lang.get(path.suffix.lower())
            if lang:
                ext_count[lang] = ext_count.get(lang, 0) + 1
    if ext_count:
        return max(ext_count, key=ext_count.get)
    return "python"


def _handler(parameters: dict, player=None, speak=None, **kwargs) -> str:
    """MOSS plagiarism check handler.

    Parameters (from Gemini tool call):
        path:      Directory or file(s) to check.
        language:  Source language (auto-detected if omitted).
        base_files: Optional comma-separated base files to exclude.
        comment:   Optional comment for the report.
    """
    target = parameters.get("path", "")
    lang_hint = parameters.get("language", "")
    base_paths = parameters.get("base_files", "")
    comment = parameters.get("comment", "")

    if not target:
        return "Please provide a path to check. For example: check plagiarism in ~/Desktop/myproject"

    target = os.path.expanduser(target)
    if not os.path.exists(target):
        return f"Path not found: {target}"

    # Load config
    cfg = _load_config()
    user_id = cfg.get("moss_user_id", "")
    if not user_id:
        return ("MOSS user ID not configured. "
                "Set 'moss_user_id' in config/api_keys.json. "
                "Register at https://moss.stanford.edu to get your ID.")
    if not str(user_id).strip().isdigit():
        return ("MOSS user ID must be the numeric identifier issued by Stanford MOSS. "
                "Update 'moss_user_id' in config/api_keys.json before submitting code.")

    # Collect files
    if os.path.isfile(target):
        files = [(os.path.basename(target), Path(target).read_text(encoding="utf-8", errors="replace"))]
        directory_mode = False
    else:
        files = _collect_files(target)
        directory_mode = True

    if not files:
        return f"No source files found in {target}"

    # Detect language
    lang = lang_hint.lower().strip() if lang_hint else _detect_language(target)
    lang_code = LANGUAGES.get(lang, lang)

    # Collect base files
    base_files = []
    if base_paths:
        for bp in base_paths.split(","):
            bp = bp.strip()
            if bp and os.path.exists(bp):
                base_files.append((os.path.basename(bp),
                                   Path(bp).read_text(encoding="utf-8", errors="replace")))

    # Submit to MOSS
    try:
        if player:
            player.write_log(f"MOSS: Uploading {len(files)} files (lang={lang_code})…")

        url = _moss_upload(
            user_id=user_id,
            files=files,
            language=lang_code,
            base_files=base_files if base_files else None,
            directory_mode=directory_mode,
            comment=comment,
        )

        if not url or "http" not in url.lower():
            return f"MOSS returned an unexpected response: {url[:200]}"

        return (
            f"MOSS check complete.\n"
            f"Files uploaded: {len(files)}\n"
            f"Language: {lang_code}\n"
            f"Results: {url}\n\n"
            f"Open the link above to see similarity matches between files."
        )
    except socket.timeout:
        return "MOSS server timed out. Try again later."
    except Exception as e:
        return f"MOSS error: {e}"


TOOL = {
    "name": "moss_check",
    "description": (
        "Check code for plagiarism using Stanford MOSS (Measure of Software Similarity). "
        "Uploads source files to Stanford's server and returns a URL with similarity results. "
        "Works with Python, Java, C/C++, JavaScript, Haskell, and 30+ other languages. "
        "Use when the user wants to check if code is plagiarized, compare code submissions, "
        "or check code originality."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "Path to directory of code files or a single file to check.",
            },
            "language": {
                "type": "STRING",
                "description": (
                    "Source language (auto-detected if omitted). "
                    "Examples: python, java, cc, javascript, haskell, go, rust."
                ),
            },
            "base_files": {
                "type": "STRING",
                "description": "Comma-separated paths to base/instructor files to exclude from matches.",
            },
            "comment": {
                "type": "STRING",
                "description": "Comment string to attach to the MOSS report.",
            },
        },
        "required": ["path"],
    },
    "handler": _handler,
}
