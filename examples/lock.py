#!/usr/bin/env python3
"""Two threads sharing locks cleanly: acquire, work, release.

Run with: python examples/lock.py
"""

import os
import sys
import time

# Make the repo-root ``rvdebugger`` package importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rvdebugger import VisualDebugger, init_viewer, run_simulation


def simulate_task_1(debugger):
    """Thread 0: read from a database under mutex1, then clean up."""
    tid = 0
    debugger.add_step(tid, "init")
    debugger.add_step(tid, "load")
    debugger.add_step(tid, "validate")

    debugger.add_step(tid, "connect", has_lock=True, lock_acquired=True, lock_name="mutex1")
    debugger.add_step(tid, "read", has_lock=True)
    debugger.add_step(tid, "check", has_lock=True)
    debugger.add_step(tid, "disconnect", has_lock=True, lock_released=True, lock_name="mutex1")

    debugger.add_step(tid, "process")
    debugger.add_step(tid, "cleanup")


def simulate_task_2(debugger):
    """Thread 1: write to a database under mutex2, then finalize."""
    tid = 1
    debugger.add_step(tid, "init")
    time.sleep(0.05)  # slight offset

    debugger.add_step(tid, "setup")
    debugger.add_step(tid, "config")
    debugger.add_step(tid, "prepare")

    time.sleep(0.5)  # wait longer before acquiring the lock
    debugger.add_step(tid, "open", has_lock=True, lock_acquired=True, lock_name="mutex2")
    debugger.add_step(tid, "query", has_lock=True)
    debugger.add_step(tid, "update", has_lock=True)
    debugger.add_step(tid, "calculate", has_lock=True)
    debugger.add_step(tid, "commit", has_lock=True)
    debugger.add_step(tid, "close", has_lock=True, lock_released=True, lock_name="mutex2")

    debugger.add_step(tid, "finalize")
    debugger.add_step(tid, "save")


def main():
    init_viewer()
    run_simulation(VisualDebugger(), simulate_task_1, simulate_task_2)


if __name__ == "__main__":
    main()
