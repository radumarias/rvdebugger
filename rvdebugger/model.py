"""Data model for a single step in a thread's execution flow."""

from dataclasses import dataclass


@dataclass
class StepNode:
    """One execution step logged by :class:`~rvdebugger.debugger.VisualDebugger`.

    The attributes capture a moment in a thread's run: where it sits in the 3D
    scene (``x``/``y``), what it did (``function_name``), and any lock
    operation it performed at that step.
    """

    thread_id: int
    step_id: int
    function_name: str
    x: float
    y: float
    timestamp: float
    has_lock: bool = False
    lock_acquired: bool = False
    lock_released: bool = False
    lock_name: str = "mutex1"
