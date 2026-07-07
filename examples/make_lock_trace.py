#!/usr/bin/env python3
"""Generate demo_lock_trace.json: a profiler snapshot with locks + a deadlock.

Two threads run the same story as the scripted demos, but for real, recorded
by viztracer:

1. **Clean phase** (like lock.py): each thread acquires its own mutex, works,
   and releases it.
2. **Deadlock phase** (like deadlock.py): task_a holds mutex1 and wants
   mutex2; task_b holds mutex2 and wants mutex1 — synchronized with a
   barrier so the cycle always closes. Both use ``acquire(timeout=)``, so
   the deadlock is detected, recorded as BLOCKED markers, and the program
   still terminates.

Lock operations are recorded as instant events named ``LOCK <mutex>`` /
``RELEASE <mutex>`` / ``BLOCKED <mutex>`` — the marker convention
``rvdebugger.trace.replay_trace`` maps back onto lock pins, spans, and
mutex boxes. Replay with: python examples/replay_trace.py examples/demo_lock_trace.json

Run with: python examples/make_lock_trace.py   (needs: pip install viztracer)
"""

import json
import os
import sys
import threading
import time

# Make the repo-root ``rvdebugger`` package importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rvdebugger.trace import rename_dummy_threads

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_lock_trace.json")
LOCK_TIMEOUT = 0.03  # seconds before a blocked acquire gives up

tracer = None  # set in main()
mutex1 = threading.Lock()
mutex2 = threading.Lock()


def acquire(lock, name, timeout=None):
    ok = lock.acquire(timeout=timeout) if timeout else lock.acquire()
    tracer.log_instant(f"LOCK {name}" if ok else f"BLOCKED {name}")
    if ok:  # watch-panel variable: who owns the mutex right now
        tracer.log_var(f"{name}.owner", threading.current_thread().name)
    return ok


def release(lock, name):
    lock.release()
    tracer.log_instant(f"RELEASE {name}")
    tracer.log_var(f"{name}.owner", "-")


def prepare():
    time.sleep(0.004)


def work(duration):
    time.sleep(duration)


def clean_phase(lock, name):
    """Acquire -> work -> release: the well-behaved lock lifecycle."""
    acquire(lock, name)
    work(0.008)
    release(lock, name)


def deadlock_phase(held, held_name, wanted, wanted_name, ready):
    """Hold one mutex, then want the other — the classic lock cycle."""
    acquire(held, held_name)
    work(0.005)
    ready.wait()  # both threads now hold their first mutex: cycle is closed
    got = acquire(wanted, wanted_name, timeout=LOCK_TIMEOUT)
    ready.wait()  # keep holding until both attempts resolve: both must block
    if got:
        release(wanted, wanted_name)  # unreachable when the cycle closes
    release(held, held_name)


def task_a(ready):
    prepare()
    clean_phase(mutex1, "mutex1")
    work(0.004)
    deadlock_phase(mutex1, "mutex1", mutex2, "mutex2", ready)


def task_b(ready):
    prepare()
    clean_phase(mutex2, "mutex2")
    work(0.004)
    deadlock_phase(mutex2, "mutex2", mutex1, "mutex1", ready)


def run_workload():
    ready = threading.Barrier(2)
    threads = [threading.Thread(target=task_a, args=(ready,), name="task_a"),
               threading.Thread(target=task_b, args=(ready,), name="task_b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def fix_thread_names(path):
    """Repair ``Dummy-N`` thread names in the saved JSON, in place."""
    with open(path) as f:
        data = json.load(f)
    rename_dummy_threads(data["traceEvents"])
    with open(path, "w") as f:
        json.dump(data, f)


def main():
    global tracer
    try:
        from viztracer import VizTracer
    except ImportError:
        sys.exit("viztracer is required to generate the trace: pip install viztracer")

    tracer = VizTracer(output_file=OUTPUT, max_stack_depth=12,
                       ignore_c_function=True, ignore_frozen=True,
                       log_func_args=True, verbose=0)
    tracer.start()
    run_workload()
    tracer.stop()
    tracer.save()
    fix_thread_names(OUTPUT)
    print(f"trace saved to {OUTPUT}")


if __name__ == "__main__":
    main()
