"""Helpers to start the Rerun viewer and run threaded simulations."""

import threading

import rerun as rr


def init_viewer(app_id="concurrent_flow_debugger", *, spawn=True):
    """Initialize Rerun and prepare a clean right-handed, Y-up 3D scene."""
    rr.init(app_id, spawn=spawn)
    rr.log("", rr.ViewCoordinates.RIGHT_HAND_Y_UP)
    rr.log("world", rr.Clear(recursive=True))


def run_simulation(debugger, *tasks,
                   start_message="Starting concurrent execution visualization...",
                   done_message="Execution complete. Check the rerun viewer for visualization."):
    """Run each task function in its own thread, each called as ``task(debugger)``.

    Blocks until every thread has finished. Pass ``start_message=None`` or
    ``done_message=None`` to silence the console output.
    """
    threads = [threading.Thread(target=task, args=(debugger,)) for task in tasks]

    if start_message:
        print(start_message)
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if done_message:
        print(done_message)
