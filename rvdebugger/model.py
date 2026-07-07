"""Data model for a single step in a thread's execution flow."""

from dataclasses import dataclass


@dataclass
class StepNode:
    """One execution step logged by :class:`~rvdebugger.debugger.VisualDebugger`.

    The attributes capture a moment in a thread's run: where it sits in the 3D
    scene (``x``/``y``), what it did (``function_name``), and any lock
    operation it performed at that step.

    ``thread_id`` may be any hashable value (an index, a real OS TID, a
    name); the debugger assigns each id a lane for X placement. ``timestamp``
    is seconds since the epoch — wall clock for live runs, or the recorded
    event time when replaying a trace. ``depth`` is the call-stack depth,
    ``duration`` the step's cost in seconds (drawn as a bar when set), and
    ``state`` an optional dict of variable values shown in the step label.
    """

    thread_id: int | str
    step_id: int
    function_name: str
    x: float
    y: float
    timestamp: float
    has_lock: bool = False
    lock_acquired: bool = False
    lock_released: bool = False
    lock_name: str = "mutex1"
    depth: int = 0
    duration: float | None = None
    state: dict | None = None
