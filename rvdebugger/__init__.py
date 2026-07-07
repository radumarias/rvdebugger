"""rvdebugger: 3D visualization of concurrent execution flow with Rerun.

Reusable building blocks shared by the scripts in ``examples/``:

* :class:`StepNode` -- a single logged execution step.
* :class:`VisualDebugger` -- logs steps and lock operations as 3D geometry.
* :func:`init_viewer` / :func:`run_simulation` -- viewer and thread helpers.
* :func:`load_chrome_trace` / :func:`replay_trace` -- replay Chrome Trace
  Event Format JSON (viztracer, torch.profiler, ...) in the viewer.
"""

from .debugger import VisualDebugger
from .model import StepNode
from .runtime import init_viewer, run_simulation
from .trace import load_chrome_trace, replay_trace

__all__ = ["StepNode", "VisualDebugger", "init_viewer", "run_simulation",
           "load_chrome_trace", "replay_trace"]
