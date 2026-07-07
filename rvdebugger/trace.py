"""Load and replay Chrome Trace Event Format JSON onto a VisualDebugger.

Works with the ``traceEvents`` JSON emitted by viztracer, ``torch.profiler``,
``chrome://tracing``, and other Trace Event Format producers. Replayed
events: complete events (``ph: "X"``), matched begin/end pairs
(``ph: "B"``/``"E"``), and instant events (``ph: "i"``, zero duration).
``thread_name`` metadata events label the lanes; everything else is skipped.

Lock semantics: the Trace Event Format has no notion of locks, so this
module uses a marker convention — events named ``LOCK <mutex>``,
``RELEASE <mutex>``, or ``BLOCKED <mutex>`` (however produced; e.g.
viztracer's ``log_instant``) are replayed as lock operations, driving the
debugger's lock pins, spans, and mutex boxes. See
``examples/make_lock_trace.py`` for a workload instrumented this way.
"""

import json
import re
from collections import defaultdict

import rerun as rr

_DUMMY_NAME = re.compile(r"^Dummy-\d+$")


def rename_dummy_threads(raw_events):
    """Rename ``Dummy-N`` thread_name metadata to each thread's entry function.

    viztracer on Python 3.12+ cannot capture ``threading.Thread`` names and
    records helper threads as ``Dummy-N``. Each such thread is renamed to its
    entry point — the longest complete event outside ``threading.py`` — with
    ``-2``/``-3`` suffixes on duplicates, so lanes stay readable in any Trace
    Event viewer. Mutates and returns ``raw_events``.
    """
    entry = {}  # (pid, tid) -> (dur, function short name)
    for ev in raw_events:
        if ev.get("ph") != "X" or "threading.py" in ev.get("name", ""):
            continue
        key = (ev.get("pid"), ev.get("tid"))
        if ev.get("dur", 0) > entry.get(key, (0,))[0]:
            entry[key] = (ev["dur"], _short_name(ev.get("name", "?")))

    used = {}
    for ev in raw_events:
        if ev.get("ph") != "M" or ev.get("name") != "thread_name":
            continue
        args = ev.get("args", {})
        key = (ev.get("pid"), ev.get("tid"))
        if _DUMMY_NAME.match(args.get("name", "")) and key in entry:
            base = entry[key][1]
            used[base] = used.get(base, 0) + 1
            args["name"] = base if used[base] == 1 else f"{base}-{used[base]}"
    return raw_events


def load_chrome_trace(path):
    """Parse the trace at ``path`` into replayable events, sorted by start time.

    Returns a list of dicts with keys ``thread`` (thread name, or ``tid-N``
    when unnamed), ``name``, ``ts`` (start, seconds), ``dur`` (seconds),
    ``depth`` (0-based call-stack depth, recovered from event nesting),
    ``vars`` (dict or None), and ``counter`` (True for standalone variable
    updates). ``ts``/``dur`` are converted from the format's microseconds.
    ``Dummy-N`` thread names are repaired via :func:`rename_dummy_threads`.

    Variables: function arguments recorded in ``args.func_args`` (viztracer's
    ``log_func_args=True``) become the event's ``vars``; variable samples —
    counter events (``ph: "C"``, viztracer ``log_var`` with numbers) and
    ``log_var`` instants carrying ``args.object`` — become ``counter``
    events whose ``vars`` hold the sampled values.
    """
    with open(path) as f:
        data = json.load(f)
    raw = data["traceEvents"] if isinstance(data, dict) else data
    rename_dummy_threads(raw)

    thread_names = {}
    per_thread = defaultdict(list)  # (pid, tid) -> [(ts_us, dur_us, name, vars, counter)]
    open_stacks = defaultdict(list)  # (pid, tid) -> [(name, ts_us)] for B/E

    for ev in sorted(raw, key=lambda e: e.get("ts", 0)):
        ph = ev.get("ph")
        key = (ev.get("pid", 0), ev.get("tid", 0))
        args = ev.get("args")
        func_args = args.get("func_args") if isinstance(args, dict) else None
        if ph == "X":
            per_thread[key].append((ev["ts"], ev.get("dur", 0),
                                    ev.get("name", "?"), func_args, False))
        elif ph == "i":
            name = ev.get("name", "?")
            if isinstance(args, dict) and set(args) == {"object"}:
                # viztracer log_var with a non-numeric value
                per_thread[key].append((ev["ts"], 0, name,
                                        {name: args["object"]}, True))
            else:
                per_thread[key].append((ev["ts"], 0, name, func_args, False))
        elif ph == "C" and isinstance(args, dict):
            name = ev.get("name", "?")
            values = args if len(args) > 1 else {name: next(iter(args.values()))}
            per_thread[key].append((ev["ts"], 0, name, values, True))
        elif ph == "B":
            open_stacks[key].append((ev.get("name", "?"), ev["ts"]))
        elif ph == "E" and open_stacks[key]:
            name, start = open_stacks[key].pop()
            per_thread[key].append((start, ev["ts"] - start, name, None, False))
        elif ph == "M" and ev.get("name") == "thread_name":
            thread_names[key] = ev.get("args", {}).get("name", "")

    events = []
    seen_names = set()
    for key, complete in per_thread.items():
        label = thread_names.get(key) or f"tid-{key[1]}"
        if label in seen_names:  # disambiguate duplicate thread names
            label = f"{label}-{key[1]}"
        seen_names.add(label)

        # Parents sort before their children ((ts, -dur)); depth = how many
        # enclosing events are still open when this one starts.
        ends = []
        for ts, dur, name, ev_vars, counter in sorted(complete, key=lambda e: (e[0], -e[1])):
            while ends and ends[-1] <= ts:
                ends.pop()
            events.append({
                "thread": label,
                "name": name,
                "ts": ts / 1e6,
                "dur": dur / 1e6,
                "depth": len(ends),
                "vars": ev_vars,
                "counter": counter,
            })
            ends.append(ts + dur)

    events.sort(key=lambda e: e["ts"])
    return events


def _short_name(name):
    """Strip viztracer-style ``func (/path/file.py:12)`` location suffixes."""
    return name.split(" (")[0]


_LOCK_MARKER = re.compile(r"^(LOCK|RELEASE|BLOCKED)\s+(.+)$")

# A successful LOCK that waited at least this long (seconds) counts as a
# contended wait for deadlock detection — the acquire may only have
# succeeded because the other side timed out and backed off.
_CONTENDED_WAIT = 0.001


def _holder_during(intervals, start, end):
    """Thread holding the lock at some point within [start, end], if any."""
    for thread, h_start, h_end in intervals:
        if h_start <= end and (h_end is None or h_end >= start):
            return thread
    return None


def _draw_deadlock(step_a, step_b):
    """Mark two mutually-blocked steps with a red deadlock node and links."""
    x = (step_a.x + step_b.x) / 2
    y = (step_a.y + step_b.y) / 2
    tag = re.sub(r"[^\w-]", "_", f"{step_a.thread_id}_{step_b.thread_id}")
    rr.log(
        f"deadlock_{tag}",
        rr.Points3D(positions=[[x, y, 1.2]], radii=[0.35],
                    colors=[[255, 0, 0]], labels=["DEADLOCK DETECTED"]),
    )
    rr.log(
        f"deadlock_{tag}/links",
        rr.LineStrips3D(
            strips=[[[step_a.x, step_a.y, 0.0], [x, y, 1.2]],
                    [[step_b.x, step_b.y, 0.0], [x, y, 1.2]]],
            colors=[[255, 0, 0]], radii=[0.05],
        ),
    )


def replay_trace(debugger, events, *, min_duration=0.0, max_depth=None,
                 label_fn=_short_name):
    """Feed ``events`` (from :func:`load_chrome_trace`) to ``debugger``.

    Construct the debugger with ``step_delay=0`` so the replay is instant.
    Events shorter than ``min_duration`` seconds or deeper than ``max_depth``
    are skipped. Events matching the lock-marker convention (``LOCK m``,
    ``RELEASE m``, ``BLOCKED m``) always replay, as lock operations; steps
    between an acquire and its release are drawn as holding the lock. A
    ``BLOCKED`` step gets a duration bar for the time spent waiting (its
    enclosing span's start to the marker), and when two threads' failed
    waits overlap while each held the lock the other wanted, a red
    ``DEADLOCK DETECTED`` node is drawn linking the two blocked steps.

    Variables: an event's ``vars`` (function arguments) become the step's
    ``state``, feeding the labels and the per-thread watch panel. ``counter``
    events draw no step; their values ride along on the thread's next drawn
    step. Returns the number of steps drawn.
    """
    held = defaultdict(set)      # thread -> mutex names currently held
    pending = defaultdict(dict)  # thread -> counter vars awaiting a step
    spans = defaultdict(list)    # thread -> open (start, end) enclosing spans
    holds = defaultdict(list)    # lock -> [thread, acquired_ts, released_ts|None]
    waits = []                   # (thread, lock, start, end, blocked step)
    count = 0
    for ev in events:
        thread = ev["thread"]
        if ev.get("counter"):
            pending[thread].update(ev["vars"])
            continue

        stack = spans[thread]
        while stack and stack[-1][1] <= ev["ts"]:
            stack.pop()

        marker = _LOCK_MARKER.match(ev["name"])
        if not marker:
            # viztracer's own frames (e.g. log_instant) are profiler
            # plumbing, not user code — they must not count as the
            # enclosing span of a lock marker.
            if ev["dur"] > 0 and "viztracer" not in ev["name"]:
                stack.append((ev["ts"], ev["ts"] + ev["dur"]))
            if ev["dur"] < min_duration:
                continue
            if max_depth is not None and ev["depth"] > max_depth:
                continue

        state = {**pending.pop(thread, {}), **(ev.get("vars") or {})} or None
        if marker:
            verb, lock_name = marker.groups()
            wait_start = stack[-1][0] if stack else ev["ts"]
            waited = ev["ts"] - wait_start
            if verb == "LOCK":
                held[thread].add(lock_name)
                holds[lock_name].append([thread, ev["ts"], None])
            step = debugger.add_step(thread, ev["name"].lower(),
                                     timestamp=ev["ts"], depth=ev["depth"],
                                     duration=waited if verb == "BLOCKED" and waited > 0 else None,
                                     has_lock=bool(held[thread]),
                                     lock_acquired=verb == "LOCK",
                                     lock_released=verb == "RELEASE",
                                     lock_name=lock_name, state=state)
            if verb == "RELEASE":
                held[thread].discard(lock_name)
                for hold in reversed(holds[lock_name]):
                    if hold[0] == thread and hold[2] is None:
                        hold[2] = ev["ts"]
                        break
            if verb == "BLOCKED" or (verb == "LOCK" and waited >= _CONTENDED_WAIT):
                for o_thread, o_lock, o_start, o_end, o_step in waits:
                    overlap = (max(wait_start, o_start), min(ev["ts"], o_end))
                    if (o_thread != thread and overlap[0] <= overlap[1]
                            and _holder_during(holds[lock_name], *overlap) == o_thread
                            and _holder_during(holds[o_lock], *overlap) == thread):
                        _draw_deadlock(step, o_step)
                waits.append((thread, lock_name, wait_start, ev["ts"], step))
        else:
            debugger.add_step(thread, label_fn(ev["name"]),
                              timestamp=ev["ts"], depth=ev["depth"],
                              duration=ev["dur"], has_lock=bool(held[thread]),
                              state=state)
        count += 1
    return count
