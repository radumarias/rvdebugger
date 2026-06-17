"""Colors and heights used to render steps and lock operations.

Colors are RGB triples in the 0-255 range. The tables cover ``mutex1``..
``mutex4``; unknown lock names fall back to ``mutex1``'s styling.
"""

from .model import StepNode

_DEFAULT_LOCK = "mutex1"

# Z height of each mutex's lock pins, stacked so multiple locks stay readable.
MUTEX_HEIGHTS = {"mutex1": 2.0, "mutex2": 2.2, "mutex3": 2.4, "mutex4": 2.6}

# (acquire_color, release_color) for the lock pin of each mutex.
PIN_COLORS = {
    "mutex1": ([255, 0, 0], [0, 255, 0]),       # red / green
    "mutex2": ([255, 165, 0], [0, 0, 255]),     # orange / blue
    "mutex3": ([128, 0, 128], [255, 192, 203]),  # purple / pink
    "mutex4": ([0, 128, 128], [255, 255, 0]),   # teal / yellow
}

# Color of the mutex node box and its acquire->release span for each mutex.
MUTEX_COLORS = {
    "mutex1": [255, 0, 255],   # magenta
    "mutex2": [0, 255, 255],   # cyan
    "mutex3": [255, 255, 0],   # yellow
    "mutex4": [0, 255, 0],     # green
}


def mutex_height(lock_name):
    """Z height of ``lock_name``'s pins."""
    return MUTEX_HEIGHTS.get(lock_name, MUTEX_HEIGHTS[_DEFAULT_LOCK])


def pin_color(lock_name, is_acquire):
    """Pin color for an acquire (``is_acquire=True``) or release."""
    acquire, release = PIN_COLORS.get(lock_name, PIN_COLORS[_DEFAULT_LOCK])
    return acquire if is_acquire else release


def mutex_color(lock_name):
    """Color of ``lock_name``'s mutex node and connection span."""
    return MUTEX_COLORS.get(lock_name, MUTEX_COLORS[_DEFAULT_LOCK])


def default_step_color(step: StepNode):
    """Green for normal steps, orange while a lock is held."""
    return [255, 165, 0] if step.has_lock else [0, 255, 0]
