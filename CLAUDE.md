# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`rvdebugger` is an experimental toolkit for **visualizing concurrent program
execution in 3D** using [Rerun](https://rerun.io/) (`rerun-sdk`). Instead of
reading interleaved thread logs, you watch threads run as spatial nodes, flow
lines, and lock pins laid out across space and time in the Rerun viewer.

The code is currently a set of **scripted demos** (not a general-purpose
debugger that attaches to arbitrary programs). Each demo manually drives a
`VisualDebugger` with a fixed sequence of steps for two threads.

The repo also contains one unrelated geometry script (`ortho_to_3d.py`).

Sample videos and specs live in a Google Drive folder linked from `README.md`.

## Development Commands

**Setup virtual environment** (this repo already has one at `venv/`, Python 3.14):
```bash
source venv/bin/activate   # existing env
# or create a fresh one (AGENTS.md prefers .venv for new envs):
python -m venv .venv && source .venv/bin/activate
```

**Install dependencies**:
```bash
pip install -r requirements.txt
```

**Run the demos** (each spawns the Rerun viewer automatically):
```bash
python examples/lock.py       # clean lock acquire/use/release across two threads
python examples/deadlock.py   # deadlock: locks acquired in opposite orders
```

**Run the orthographic-to-3D script** (expects a Rerun gRPC server on
`127.0.0.1:9876`; it connects rather than spawning):
```bash
python ortho_to_3d.py
```

## Conventions (see AGENTS.md for the full guidelines)

- PEP 8, 4-space indent, ≤88–100 char lines; imports ordered standard →
  third-party → local; concise docstrings on public functions/classes.
- **There is no test suite yet.** If adding tests: pytest, in a `tests/`
  directory mirroring the package structure (e.g. `tests/test_lock.py`), run
  with `pytest -q`.
- Commits: imperative mood, scoped and atomic, e.g.
  `fix(lock): prevent double acquire deadlock`; body explains why over what.
- New example scripts stay thin (scenario only, shared logic goes in
  `rvdebugger/`) and are guarded with `if __name__ == "__main__":`.

## Project Structure

```
rvdebugger/
├── rvdebugger/         # Reusable package (shared by the examples)
│   ├── __init__.py     # Public exports
│   ├── model.py        # StepNode dataclass
│   ├── style.py        # Mutex colors/heights + default step color
│   ├── debugger.py     # VisualDebugger class
│   └── runtime.py      # init_viewer() and run_simulation() helpers
├── examples/
│   ├── lock.py         # Two threads with a clean lock lifecycle (good case)
│   └── deadlock.py     # Deadlock scenario with opposite lock ordering
├── ortho_to_3d.py      # Reconstruct a 3D mesh from orthographic drawing dimensions
├── requirements.txt    # Single dependency: rerun-sdk>=0.24.0
├── AGENTS.md           # Repository contribution guidelines
├── CLAUDE.md           # This file
└── venv/               # Local virtual environment (not committed)
```

## Architecture Notes

### `rvdebugger/` package (shared library)

The reusable logic lives here; `examples/` only holds scenario scripts.

- **`model.StepNode`**: one execution step — `thread_id` (any hashable),
  `step_id`, `function_name`, position (`x`, `y`), `timestamp`, lock flags
  (`has_lock`, `lock_acquired`, `lock_released`, `lock_name`), plus `depth`
  (call-stack depth), `duration` (seconds, optional), and `state` (dict of
  variable values, optional).
- **`debugger.VisualDebugger`**: coordinator. `add_step(...)` records a step,
  logs its geometry to Rerun, draws the flow link from the previous step, and
  handles lock pins / mutex nodes. Thread ids may be any hashable value (real
  OS TIDs, names); each id is assigned a lane in first-seen order. Every step
  stamps the `trace_time` Rerun timeline with its timestamp — pass
  `timestamp=` (seconds since epoch) to replay recorded traces (with
  `step_delay=0`), or omit it for wall-clock live runs. `depth=` indents the
  step within its lane, `duration=` draws a cost bar along the timeline axis,
  `state=` appends `key=value` pairs to the step label. Threads call
  `add_step` directly (no automatic instrumentation); the call is
  mutex-guarded so it is safe to call concurrently. Customize without editing
  the class:
  - constructor args `entity_prefix` (per-thread entity tree name),
    `step_color_fn` (recolor step nodes), `depth_indent`, `duration_scale`,
    and `timeline` (Rerun timeline name, `None` to disable);
  - override `on_lock_acquired` / `on_lock_released` to draw extra geometry.
- **`style`**: per-mutex color/height tables (`mutex1`..`mutex4`) and the
  default green/orange step color.
- **`runtime`**: `init_viewer(...)` (Rerun init + clean Y-up scene) and
  `run_simulation(debugger, *tasks)` (one thread per task function).

### Examples

- **`lock.py`**: uses `VisualDebugger` directly; defines `simulate_task_1` /
  `simulate_task_2` and runs them via `run_simulation`.
- **`deadlock.py`**: subclasses `VisualDebugger` as `DeadlockDebugger`
  (`entity_prefix="task"`, a custom step color, and `on_lock_acquired` drawing
  the shared mutex nodes + deadlock-detection marker). The deadlock-specific
  drawing stays in the example, not the package.

Each example prepends the repo root to `sys.path` so `import rvdebugger` works
when run directly as `python examples/<name>.py` without installing anything.

### Orthographic reconstruction (`ortho_to_3d.py`)

Standalone and unrelated to the debugger. `build_shape()` defines a solid
(rectangular base + trapezoidal upper prism) from engineering-drawing
dimensions and emits a triangle mesh plus feature-edge wireframe;
`main()` logs them as `rr.Mesh3D` and `rr.LineStrips3D`.

## Visualization Layout (the concurrency demos)

- **X-axis**: thread separation — `x = lane * 4.0` (lanes assigned to thread
  ids in first-seen order), plus `depth * 0.6` indentation for call depth.
- **Y-axis**: timeline / step progression — `y = step_id * 2.0`; steps with a
  `duration` also get a cost bar (`Boxes3D`) extending along Y.
- **Z-axis**: lock operations, elevated above the execution plane (lock pins,
  with per-mutex heights ~2.0–2.6).
- **Steps**: spheres (`Points3D`), green for normal work, orange while holding
  a lock, labeled with the function name (plus `key=value` state, if given).
- **Time scrubber**: each step stamps the `trace_time` timeline with its
  timestamp, so the viewer scrubs on event time (recorded or wall clock).
- **Flow links**: thin blue (`LineStrips3D`) between consecutive steps.
- **Locks**: an elevated pin per acquire/release, a gray Z-line tying the pin
  to its step, a colored acquire→release span, and a mutex box node
  (`Boxes3D`) placed between the two threads. Distinct mutexes use distinct
  colors/heights (e.g. magenta `mutex1`, cyan `mutex2`).

## Key Features Demonstrated

- **Proper synchronization** (`lock.py`): a clean acquire → hold → release
  lifecycle visualized per thread.
- **Deadlock** (`deadlock.py`): two threads acquiring `mutex1`/`mutex2` in
  opposite orders, with deadlock-attempt tracking.
- **3D execution view**: threads, flow, and lock lifecycles as inspectable
  geometry in the Rerun viewer.

## Notes for Future Work

- `VisualDebugger` supports **any number of threads with arbitrary hashable
  ids** (mapped to lanes in first-seen order); the examples happen to use two
  with ids 0/1.
- Variable state is **display-only**: `state=` dicts land in step labels;
  there is no state history panel or time-series plotting.
- Replaying a profiler snapshot = construct with `step_delay=0` and call
  `add_step(...)` per event with the recorded `timestamp=`; there is no
  built-in adapter for any specific trace format yet.
- The package is not pip-installable (no `pyproject.toml`); examples reach it
  via a `sys.path` shim. Add packaging if it needs to be imported elsewhere.
