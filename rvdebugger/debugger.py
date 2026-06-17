"""3D visual debugger for concurrent execution flow, logged to Rerun."""

import threading
import time
from collections import defaultdict

import rerun as rr

from . import style
from .model import StepNode


class VisualDebugger:
    """Logs threaded execution steps and lock operations as 3D geometry.

    Scene layout (right-handed, Y up):

    * **X** separates threads (``thread_id * thread_spacing``).
    * **Y** is the per-thread timeline (``step_id * step_spacing``).
    * **Z** lifts lock pins above the execution plane.

    The class is general-purpose; scenarios customize it without copying the
    drawing code:

    * pass ``step_color_fn`` to recolor step nodes, and ``entity_prefix`` to
      name the per-thread entity trees;
    * override :meth:`on_lock_acquired` / :meth:`on_lock_released` to draw
      extra geometry when a lock changes hands.

    ``add_step`` is safe to call from multiple threads concurrently.
    """

    def __init__(self, *, entity_prefix="thread", step_color_fn=None,
                 step_delay=0.1, thread_spacing=4.0, step_spacing=2.0,
                 mutex_lane_x=2.0):
        self.entity_prefix = entity_prefix
        self.step_color_fn = step_color_fn or style.default_step_color
        self.step_delay = step_delay
        self.thread_spacing = thread_spacing
        self.step_spacing = step_spacing
        self.mutex_lane_x = mutex_lane_x

        self.steps = []
        self.current_step = defaultdict(int)  # next step id per thread
        self._last_step = {}                  # last StepNode per thread
        self.pending_locks = {}               # f"{tid}_{lock}" -> step index
        self.mutex = threading.Lock()

    # -- public API -------------------------------------------------------

    def add_step(self, thread_id, function_name, *, has_lock=False,
                 lock_acquired=False, lock_released=False, lock_name="mutex1"):
        """Record and draw one execution step for ``thread_id``."""
        with self.mutex:
            step_id = self.current_step[thread_id]
            self.current_step[thread_id] += 1

            step = StepNode(
                thread_id=thread_id,
                step_id=step_id,
                function_name=function_name,
                x=thread_id * self.thread_spacing,
                y=step_id * self.step_spacing,
                timestamp=time.time(),
                has_lock=has_lock,
                lock_acquired=lock_acquired,
                lock_released=lock_released,
                lock_name=lock_name,
            )
            self.steps.append(step)

            prev_step = self._last_step.get(thread_id)
            self._last_step[thread_id] = step

            self._visualize_step(step)
            if prev_step is not None:
                self._visualize_flow_link(prev_step, step)

            if lock_acquired:
                self._visualize_lock_pin(step, is_acquire=True)
                self.pending_locks[f"{thread_id}_{lock_name}"] = len(self.steps) - 1
                self.on_lock_acquired(step)
            elif lock_released:
                self._visualize_lock_pin(step, is_acquire=False)
                self._connect_lock_pins(step)
                self._create_mutex_node_and_connections(step)
                self.on_lock_released(step)

        time.sleep(self.step_delay)  # paced outside the lock so threads overlap

    # -- override hooks ---------------------------------------------------

    def on_lock_acquired(self, step):
        """Called after an acquire step is drawn. Override to add geometry."""

    def on_lock_released(self, step):
        """Called after a release step is drawn. Override to add geometry."""

    # -- drawing ----------------------------------------------------------

    def _thread_path(self, thread_id):
        return f"{self.entity_prefix}_{thread_id}"

    def _visualize_step(self, step):
        """Render the step node as a labeled sphere."""
        rr.log(
            f"{self._thread_path(step.thread_id)}/step_{step.step_id}",
            rr.Points3D(
                positions=[[step.x, step.y, 0.0]],
                radii=[0.3],
                colors=[self.step_color_fn(step)],
                labels=[step.function_name],
            ),
        )

    def _visualize_flow_link(self, prev_step, step):
        """Draw the line connecting two sequential steps of a thread."""
        rr.log(
            f"{self._thread_path(step.thread_id)}/flow_{prev_step.step_id}_{step.step_id}",
            rr.LineStrips3D(
                strips=[[[prev_step.x, prev_step.y, 0.0], [step.x, step.y, 0.0]]],
                colors=[[100, 149, 237]],  # cornflower blue
                radii=[0.02],
            ),
        )

    def _visualize_lock_pin(self, step, *, is_acquire):
        """Draw the elevated lock pin and the Z-line tying it to the step."""
        pin_z = style.mutex_height(step.lock_name)
        path = self._thread_path(step.thread_id)
        verb = "LOCK" if is_acquire else "RELEASE"

        rr.log(
            f"{path}/lock_pin_{step.step_id}",
            rr.Points3D(
                positions=[[step.x, step.y, pin_z]],
                radii=[0.15],
                colors=[style.pin_color(step.lock_name, is_acquire)],
                labels=[f"{verb} {step.lock_name}"],
            ),
        )
        rr.log(
            f"{path}/z_line_{step.step_id}",
            rr.LineStrips3D(
                strips=[[[step.x, step.y, 0.0], [step.x, step.y, pin_z]]],
                colors=[[128, 128, 128]],
                radii=[0.03],
            ),
        )

    def _acquire_for(self, release_step):
        """Return the acquire step matching ``release_step``, or ``None``."""
        idx = self.pending_locks.get(f"{release_step.thread_id}_{release_step.lock_name}")
        return self.steps[idx] if idx is not None else None

    def _connect_lock_pins(self, release_step):
        """Span a thick line between an acquire pin and its release pin."""
        acquire_step = self._acquire_for(release_step)
        if acquire_step is None:
            return
        pin_z = style.mutex_height(release_step.lock_name)
        rr.log(
            f"pin_connection_{acquire_step.step_id}_{release_step.step_id}",
            rr.LineStrips3D(
                strips=[[[acquire_step.x, acquire_step.y, pin_z],
                         [release_step.x, release_step.y, pin_z]]],
                colors=[style.mutex_color(release_step.lock_name)],
                radii=[0.08],
            ),
        )

    def _create_mutex_node_and_connections(self, release_step):
        """Drop a mutex box midway between acquire/release and link both."""
        key = f"{release_step.thread_id}_{release_step.lock_name}"
        acquire_step = self._acquire_for(release_step)
        if acquire_step is None:
            return

        mutex_x = self.mutex_lane_x
        mutex_y = (acquire_step.y + release_step.y) / 2
        color = style.mutex_color(release_step.lock_name)
        tag = f"{acquire_step.step_id}_{release_step.step_id}"

        rr.log(
            f"mutex_{release_step.lock_name}_{tag}",
            rr.Boxes3D(
                centers=[[mutex_x, mutex_y, 0.0]],
                sizes=[[0.4, 0.4, 0.4]],
                colors=[color],
                labels=[f"MUTEX {release_step.lock_name}"],
            ),
        )
        rr.log(
            f"acquire_to_mutex_{tag}",
            rr.LineStrips3D(
                strips=[[[acquire_step.x, acquire_step.y, 0.0], [mutex_x, mutex_y, 0.0]]],
                colors=[[128, 128, 128]],
                radii=[0.01],
            ),
        )
        rr.log(
            f"mutex_to_release_{tag}",
            rr.LineStrips3D(
                strips=[[[mutex_x, mutex_y, 0.0], [release_step.x, release_step.y, 0.0]]],
                colors=[[128, 128, 128]],
                radii=[0.01],
            ),
        )
        del self.pending_locks[key]
