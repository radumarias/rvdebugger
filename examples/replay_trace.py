#!/usr/bin/env python3
"""Replay a Chrome Trace Event JSON profile in the 3D viewer.

Works with any Trace Event Format producer (viztracer, torch.profiler,
chrome://tracing). Steps are placed per thread, indented by call depth,
with duration bars scaled to the longest event; the viewer's ``trace_time``
timeline scrubs on the recorded event times.

Run with: python examples/replay_trace.py [trace.json]
Defaults to demo_trace.json (generate it with: python examples/make_trace.py)
"""

import os
import sys

# Make the repo-root ``rvdebugger`` package importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rvdebugger import VisualDebugger, init_viewer, load_chrome_trace, replay_trace

# Events shorter than this are profiler noise (queue/lock internals), not
# workload; dropping them keeps the scene readable.
MIN_DURATION = 0.001  # seconds


def step_color(step):
    """Red for blocked lock attempts, else the default green/orange."""
    if step.function_name.startswith("blocked"):
        return [255, 0, 0]
    return [255, 165, 0] if step.has_lock else [0, 255, 0]


def main():
    default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_trace.json")
    path = sys.argv[1] if len(sys.argv) > 1 else default
    if not os.path.exists(path):
        sys.exit(f"{path} not found — generate it with: python examples/make_trace.py")

    events = load_chrome_trace(path)
    if not events:
        sys.exit(f"no duration events found in {path}")
    longest = max(ev["dur"] for ev in events)

    init_viewer("trace_replay")
    debugger = VisualDebugger(
        step_delay=0,                    # instant replay; time lives on the trace_time timeline
        duration_scale=4.0 / longest,    # longest event -> a 4-unit bar
        step_color_fn=step_color,
    )
    drawn = replay_trace(debugger, events, min_duration=MIN_DURATION)
    print(f"Replayed {drawn} of {len(events)} events from {path} "
          f"(skipped events shorter than {MIN_DURATION * 1e3:.0f} ms). "
          f"Check the rerun viewer.")


if __name__ == "__main__":
    main()
