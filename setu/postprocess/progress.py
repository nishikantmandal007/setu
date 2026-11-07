import time

# How far the current stage has got, as (items done, items in the stage). The stage itself is announced by phase(text);
# report is set by whoever runs the analysis and stays a no-op otherwise. Counts are reported at most every REPORT_EVERY_S,
# and always when the stage finishes, so a fast stage does not flood the caller.
REPORT_EVERY_S = 0.5

report = None
_total = 0
_done = 0
_last_sent = 0.0


def start(total):
    global _total, _done, _last_sent
    _total, _done, _last_sent = int(total), 0, 0.0
    if report is not None:
        report(0, _total)


def step(count=1):
    global _done, _last_sent
    _done += count
    if report is None:
        return
    now = time.monotonic()
    if _done >= _total or now - _last_sent >= REPORT_EVERY_S:
        _last_sent = now
        report(min(_done, _total), _total)


# counts one item done and hands its value on, for use inside a comprehension
def passing(value):
    step()
    return value

