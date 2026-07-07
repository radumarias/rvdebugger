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

**Profiler trace replay** (Chrome Trace Event Format — viztracer,
torch.profiler, chrome://tracing):
```bash
python examples/replay_trace.py [trace.json]  # defaults to examples/demo_trace.json
python examples/replay_trace.py examples/demo_lock_trace.json  # locks + deadlock
# regenerate the committed samples (needs: pip install viztracer):
python examples/make_trace.py       # producer/consumer workload
python examples/make_lock_trace.py  # lock lifecycle + detected deadlock
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
│   ├── runtime.py      # init_viewer() and run_simulation() helpers
│   └── trace.py        # Chrome Trace Event JSON loader + replay
├── examples/
│   ├── lock.py         # Two threads with a clean lock lifecycle (good case)
│   ├── deadlock.py     # Deadlock scenario with opposite lock ordering
│   ├── make_trace.py   # Generate demo_trace.json via viztracer (optional dep)
│   ├── make_lock_trace.py   # Generate demo_lock_trace.json (locks + deadlock)
│   ├── replay_trace.py # Replay a Chrome trace JSON in the 3D viewer
│   ├── demo_trace.json # Committed sample trace (producer + 3 workers)
│   └── demo_lock_trace.json # Committed sample with lock markers + deadlock
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
- **`trace`**: `load_chrome_trace(path)` parses Chrome Trace Event Format
  JSON (`ph: "X"` complete events, `"B"`/`"E"` pairs, `"i"` instants, `"C"`
  counters; `thread_name` metadata; µs → seconds) into events with call
  depth recovered from nesting; `replay_trace(debugger, events,
  min_duration=, max_depth=)` feeds them to `add_step`. Build the debugger
  with `step_delay=0` for replays. Two conventions bridge what the format
  lacks:
  - **Lock markers**: events named `LOCK <mutex>` / `RELEASE <mutex>` /
    `BLOCKED <mutex>` (e.g. viztracer `log_instant`) replay as lock
    operations — pins, spans, mutex boxes — and steps between acquire and
    release are drawn as holding the lock. `BLOCKED` steps get a red
    duration bar for the time spent waiting, and when two threads' lock
    waits overlap while each held the lock the other wanted (pairwise
    check; successful-but-contended acquires count too), a red `DEADLOCK
    DETECTED` node links the two steps. See `examples/make_lock_trace.py`.
  - **Variables**: `args.func_args` (viztracer `log_func_args=True`) becomes
    each step's `state`; `log_var` samples (counters or `args.object`
    instants) ride along on the thread's next drawn step.

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
- **Watch panel**: steps with `state=` also update a per-thread
  `TextDocument` at `<thread>/vars` — a debugger-style watch window whose
  values merge across steps and follow the time scrubber.
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
- Profiler replay has a built-in adapter only for **Chrome Trace Event
  Format** (`rvdebugger/trace.py`); other formats (speedscope native,
  collapsed stacks, pprof) would need their own loaders. The format has no
  native lock semantics — lock pins only appear for traces instrumented with
  the `LOCK`/`RELEASE`/`BLOCKED <mutex>` marker convention (see
  `examples/make_lock_trace.py`); plain traces exercise steps, depth,
  duration, vars, and the timeline.
- viztracer (used only by `examples/make_trace.py`) is **not** in
  `requirements.txt`; it is an optional dev dependency. On Python 3.12+ it
  records helper threads as `Dummy-N`; `trace.rename_dummy_threads` repairs
  this (renaming each thread to its entry function) — applied automatically
  by `load_chrome_trace` and by `make_trace.py` when saving the sample file.
- The package is not pip-installable (no `pyproject.toml`); examples reach it
  via a `sys.path` shim. Add packaging if it needs to be imported elsewhere.
