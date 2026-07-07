#!/usr/bin/env python3
"""Generate demo_trace.json: a real multithreaded profiler snapshot.

Runs a producer/consumer workload (1 producer, 3 workers contending on a
shared lock) under viztracer and saves the profile as Chrome Trace Event
Format JSON — the same format as chrome://tracing / speedscope's Chrome
samples. Replay it with: python examples/replay_trace.py

Run with: python examples/make_trace.py   (needs: pip install viztracer)
"""

import json
import os
import queue
import sys
import threading
import time

# Make the repo-root ``rvdebugger`` package importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rvdebugger.trace import rename_dummy_threads

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_trace.json")
N_ITEMS = 12
N_WORKERS = 3

results_lock = threading.Lock()
results = []


def checksum(item):
    time.sleep(0.002)
    total = 0
    for char in item:
        total += ord(char)
    return total


def parse(item):
    time.sleep(0.004)
    return {"item": item, "checksum": checksum(item)}


def transform(record):
    time.sleep(0.006)
    record["value"] = record["checksum"] * 2
    return record


def store(record):
    with results_lock:
        time.sleep(0.003)  # hold the lock while "writing"
        results.append(record)


def process(item):
    store(transform(parse(item)))


def worker(work_queue):
    while True:
        item = work_queue.get()
        if item is None:
            return
        process(item)


def produce(work_queue):
    for i in range(N_ITEMS):
        time.sleep(0.005)
        work_queue.put(f"item-{i}")
    for _ in range(N_WORKERS):
        work_queue.put(None)


def run_workload():
    work_queue = queue.Queue(maxsize=4)
    threads = [threading.Thread(target=produce, args=(work_queue,), name="producer")]
    threads += [threading.Thread(target=worker, args=(work_queue,), name=f"worker-{i}")
                for i in range(N_WORKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def fix_thread_names(path):
    """Repair ``Dummy-N`` thread names in the saved JSON, in place.

    The replay adapter fixes them on load anyway; rewriting the file keeps
    the sample readable in other Trace Event viewers (speedscope, Perfetto).
    """
    with open(path) as f:
        data = json.load(f)
    rename_dummy_threads(data["traceEvents"])
    with open(path, "w") as f:
        json.dump(data, f)


def main():
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
    print(f"processed {len(results)} items; trace saved to {OUTPUT}")


if __name__ == "__main__":
    main()
