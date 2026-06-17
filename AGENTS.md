# Repository Guidelines

## Project Structure & Module Organization
- `rvdebugger/`: reusable package, modules grouped by concern — `model.py` (`StepNode`), `style.py` (mutex colors/heights), `debugger.py` (`VisualDebugger`), `runtime.py` (`init_viewer`, `run_simulation`). Put shared logic here.
- `examples/`: thin runnable scripts (e.g., `examples/lock.py`, `examples/deadlock.py`) that import `rvdebugger` and only define the scenario. Use these to reproduce behaviors and demonstrate fixes; keep them thin. Each prepends the repo root to `sys.path` so it runs directly without installation.
- `ortho_to_3d.py`: standalone script (orthographic-drawing → 3D mesh); unrelated to the debugger package.
- `requirements.txt`: runtime dependencies. Keep minimal and pinned with `>=` only when necessary.
- Virtual envs: prefer a local env (e.g., `.venv/`). Do not commit virtual environments; ensure they’re ignored.
- Extending the debugger: prefer the `VisualDebugger` constructor args (`entity_prefix`, `step_color_fn`) and the `on_lock_acquired` / `on_lock_released` hooks over copying drawing code into an example (see how `examples/deadlock.py` subclasses it).

## Setup, Run, and Dev Commands
- Create env: `python -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Run examples: `python examples/lock.py` or `python examples/deadlock.py`
- Freeze (optional for repro): `pip freeze > requirements.lock`

## Coding Style & Naming Conventions
- Style: follow PEP 8, 4‑space indentation, ≤ 88–100 char lines.
- Names: `snake_case` for modules/functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- Imports: standard → third‑party → local; avoid wildcard imports.
- Docstrings: use concise docstrings for public functions/classes; include expected side effects.

## Testing Guidelines
- Framework: pytest is recommended (add `pytest` as a dev dependency).
- Layout: create `tests/` mirroring package structure (`tests/test_lock.py`).
- Conventions: files start with `test_`, functions `test_*`; prefer deterministic, isolated tests.
- Run: `pytest -q` (optionally with `-k` to filter). Aim for meaningful coverage on new/changed code.

## Commit & Pull Request Guidelines
- Commits: imperative mood, scoped and atomic. Example: `fix(lock): prevent double acquire deadlock`.
- Message body: why over what; link issues (`Closes #123`).
- PRs: include a clear summary, reproduction steps (if applicable), and before/after notes or screenshots for behavioral changes. Reference issues and checklist what you tested (examples, edge cases).

## Security & Configuration Tips
- Secrets: never commit tokens or credentials. Use environment variables or `.env` kept local.
- Reproducibility: pin versions when sharing bug repros; note OS/Python version.
- Safety: keep example scripts idempotent and guarded under `if __name__ == "__main__":` when adding new ones.
