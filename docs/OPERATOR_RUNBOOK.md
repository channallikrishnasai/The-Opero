# OPERO operator runbook

## Before first use

1. Install with `pip install -e .` in a Python 3.11–3.13 environment.
2. Start with `python main.py`.
3. Add the Gemini key through OPERO Settings; do not paste it into source files.
4. Run the `opero_health` action and resolve any failed check.

## Integrations

- Gmail: copy the Google client JSON to `config/google_oauth_client.json`, then run Gmail `connect` once and complete Google’s consent screen.
- Instagram: copy `config/examples/instagram.example.json` to `config/instagram.json`, add a Meta Graph token and professional account ID, then run Instagram `status`.

The real credential and token files are ignored by Git. Do not use account passwords for Instagram.

## Recovery and troubleshooting

- Run `task_status` after an action to inspect its result or failure.
- Run `opero_health` for read-only system checks.
- Recovery creates a local backup before applying a human-reviewed source change; inspect `opero_health` with `mode=recovery_history` before any rollback. Use the `recovery` action to view history or request an approved rollback.
- A recovery mechanism is not an automatic code editor. Keep source changes reviewed and run the test suite after changes.

## Release verification

```powershell
python -m compileall -q main.py actions core dashboard memory ui
python -m pytest tests --basetemp .test-tmp -q
ruff check . --select F821
```

CI repeats these checks on Python 3.11, 3.12, and 3.13 once the changes are pushed.

