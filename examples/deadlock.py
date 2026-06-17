#!/usr/bin/env python3
"""Two threads acquiring mutex1/mutex2 in opposite orders -> deadlock.

Run with: python examples/deadlock.py
"""

import os
import sys
import time

import rerun as rr

# Make the repo-root ``rvdebugger`` package importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rvdebugger import VisualDebugger, init_viewer, run_simulation

# Fixed scene positions for the two shared mutex nodes.
DEADLOCK_MUTEXES = {
    "mutex1": {"y": 6.0, "color": [255, 0, 255]},   # magenta
    "mutex2": {"y": 10.0, "color": [0, 255, 255]},  # cyan
}


def deadlock_step_color(step):
    """Red for the lock attempt that closes the cycle, gray once blocked."""
    closes_cycle = (
        (step.thread_id == 0 and step.function_name == "lock_m2")
        or (step.thread_id == 1 and step.function_name == "lock_m1")
    )
    if closes_cycle:
        return [255, 0, 0]
    if step.function_name == "blocked":
        return [128, 128, 128]
    if step.has_lock:
        return [255, 165, 0]
    return [0, 255, 0]


class DeadlockDebugger(VisualDebugger):
    """VisualDebugger that draws shared mutex nodes and a deadlock marker."""

    def __init__(self):
        super().__init__(entity_prefix="task", step_color_fn=deadlock_step_color)
        self.mutex_nodes = set()        # lock names already drawn
        self.deadlock_attempts = set()  # f"{tid}_{lock}" for cycle-closing tries

    def on_lock_acquired(self, step):
        if step.lock_name in DEADLOCK_MUTEXES:
            self._draw_shared_mutex(step)

    def _draw_shared_mutex(self, step):
        """Draw the shared mutex box (once) and a red line from the step to it."""
        spec = DEADLOCK_MUTEXES[step.lock_name]
        mutex_x, mutex_y = self.mutex_lane_x, spec["y"]

        if step.lock_name not in self.mutex_nodes:
            rr.log(
                f"shared_mutex_{step.lock_name}",
                rr.Boxes3D(
                    centers=[[mutex_x, mutex_y, 0.0]],
                    sizes=[[0.4, 0.4, 0.4]],
                    colors=[spec["color"]],
                    labels=[f"MUTEX {step.lock_name}"],
                ),
            )
            self.mutex_nodes.add(step.lock_name)

        # Every deadlock-scenario lock line is thick red.
        rr.log(
            f"connect_to_mutex_{step.step_id}_{step.lock_name}",
            rr.LineStrips3D(
                strips=[[[step.x, step.y, 0.0], [mutex_x, mutex_y, 0.0]]],
                colors=[[255, 0, 0]],
                radii=[0.08],
            ),
        )

        closes_cycle = (
            (step.thread_id == 0 and step.lock_name == "mutex2")
            or (step.thread_id == 1 and step.lock_name == "mutex1")
        )
        if closes_cycle:
            self.deadlock_attempts.add(f"{step.thread_id}_{step.lock_name}")
            self._mark_deadlock_if_complete()

    def _mark_deadlock_if_complete(self):
        """Once both cycle-closing attempts are present, mark the deadlock."""
        if {"0_mutex2", "1_mutex1"} <= self.deadlock_attempts:
            mid_y = sum(m["y"] for m in DEADLOCK_MUTEXES.values()) / len(DEADLOCK_MUTEXES)
            rr.log(
                "deadlock_detection",
                rr.Points3D(
                    positions=[[self.mutex_lane_x, mid_y, 0.5]],
                    radii=[0.3],
                    colors=[[255, 0, 0]],
                    labels=["DEADLOCK DETECTED"],
                ),
            )


def simulate_task_1(debugger):
    """Thread 0: hold mutex1, then block trying for mutex2."""
    tid = 0
    debugger.add_step(tid, "init")
    debugger.add_step(tid, "load")
    debugger.add_step(tid, "validate")

    debugger.add_step(tid, "lock_m1", has_lock=True, lock_acquired=True, lock_name="mutex1")
    debugger.add_step(tid, "work_m1", has_lock=True)

    debugger.add_step(tid, "lock_m2", has_lock=True, lock_acquired=True, lock_name="mutex2")
    debugger.add_step(tid, "blocked")  # deadlocked here


def simulate_task_2(debugger):
    """Thread 1: hold mutex2, then block trying for mutex1."""
    tid = 1
    debugger.add_step(tid, "init")
    time.sleep(0.05)  # slight offset

    debugger.add_step(tid, "setup")
    debugger.add_step(tid, "config")
    debugger.add_step(tid, "prepare")

    debugger.add_step(tid, "lock_m2", has_lock=True, lock_acquired=True, lock_name="mutex2")
    debugger.add_step(tid, "work_m2", has_lock=True)

    debugger.add_step(tid, "lock_m1", has_lock=True, lock_acquired=True, lock_name="mutex1")
    debugger.add_step(tid, "blocked")  # deadlocked here


def main():
    init_viewer()
    run_simulation(DeadlockDebugger(), simulate_task_1, simulate_task_2)


if __name__ == "__main__":
    main()
