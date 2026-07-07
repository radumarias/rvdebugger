# rvdebugger
A small experimental toolkit for visualizing concurrent program execution in 3D using Rerun (https://rerun.io/) (rerun-sdk). Instead of reading thread logs or stack traces, you watch threads run as nodes, lines, and lock-pins laid out in space and time.

## Sample videos and specs

Sample videos and specs are available [here](https://drive.google.com/drive/folders/16biiLop1_xw1l9iQu_55u6xRU_f18CNv?usp=sharing).  

## Example of a deadlock

<img width="2552" height="1536" alt="Screenshot From 2026-06-16 12-11-30" src="https://github.com/user-attachments/assets/1dc6170e-6baf-43bc-bd7a-28f4db775dc2" />

## Examples of performance profiles files

https://github.com/jlfwong/speedscope/tree/main/sample

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# scripted live demos (each spawns the Rerun viewer)
python examples/lock.py       # clean lock acquire/use/release across two threads
python examples/deadlock.py   # deadlock: locks acquired in opposite orders
```

## Replaying profiler traces

`rvdebugger` can replay **Chrome Trace Event Format** JSON — the format
emitted by [viztracer](https://github.com/gaogaotiantian/viztracer),
`torch.profiler`, `chrome://tracing`, and others — as a 3D scene: one lane
per thread, steps indented by call depth, duration bars, and a `trace_time`
timeline that scrubs on the recorded event times.

```bash
python examples/replay_trace.py                                # committed sample: producer + 3 workers
python examples/replay_trace.py examples/demo_lock_trace.json  # committed sample: locks + detected deadlock
python examples/replay_trace.py path/to/your_trace.json        # any Chrome trace
```

### Getting sample data

Two samples are committed (`examples/demo_trace.json`,
`examples/demo_lock_trace.json`). To regenerate them, or to record your own
program:

```bash
pip install viztracer

python examples/make_trace.py        # re-record the producer/consumer workload
python examples/make_lock_trace.py   # re-record the lock lifecycle + deadlock

# record any script of yours (CLI):
viztracer --log_func_args -o my_trace.json my_script.py
python examples/replay_trace.py my_trace.json
```

The same files also load in [speedscope](https://www.speedscope.app) and
[Perfetto](https://ui.perfetto.dev) for a 2D flamegraph view of identical data.

### Recording variables

Two channels feed the step labels and the per-thread `<thread>/vars` watch
panel in the viewer:

1. **Function arguments, on every call** — enable `log_func_args`:

   ```bash
   viztracer --log_func_args -o my_trace.json my_script.py
   ```

   or programmatically:

   ```python
   from viztracer import VizTracer

   tracer = VizTracer(output_file="my_trace.json", log_func_args=True)
   tracer.start()
   run_workload()
   tracer.stop()
   tracer.save()
   ```

   Every call event then carries its arguments (`args.func_args` in the
   JSON), and each replayed step shows them as `key=value` state.
   Arguments are captured at call entry and stringified by viztracer.

2. **Explicit variable samples** — call `log_var` at the points you care
   about (locals, computed values, anything not visible as an argument):

   ```python
   tracer.log_var("mutex1.owner", threading.current_thread().name)
   tracer.log_var("queue_size", work_queue.qsize())
   ```

   Samples ride along on the thread's next replayed step and update the
   watch panel, like a debugger watch expression sampled over time.
   `examples/make_lock_trace.py` uses this to track mutex ownership.

### Lock markers

The Chrome trace format has no lock semantics, so the replayer recognizes a
marker convention — instant events named `LOCK <mutex>`, `RELEASE <mutex>`,
`BLOCKED <mutex>`:

```python
ok = lock.acquire(timeout=0.03)
tracer.log_instant("LOCK mutex1" if ok else "BLOCKED mutex1")
...
lock.release()
tracer.log_instant("RELEASE mutex1")
```

Replay then draws the full lock story: elevated acquire/release pins,
colored hold spans, mutex boxes, orange steps while a lock is held, red
wait-duration bars on blocked attempts — and when two threads' lock waits
overlap while each held the lock the other wanted, a red **DEADLOCK
DETECTED** node linking the two blocked steps. `examples/make_lock_trace.py`
is a complete instrumented workload producing all of the above.
