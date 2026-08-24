"""How setu says what it is doing.

A library must not print. It logs, and the program using it decides whether
anyone sees that. But the reports the original bridge scripts printed were
genuinely useful to read while a model was being built, so `enable_reports()`
turns them back on in one line.
"""

from __future__ import annotations

import logging

log = logging.getLogger("setu")
log.addHandler(logging.NullHandler())


def enable_reports(level: int = logging.INFO) -> None:
    """Prints setu's progress reports to the console, as the original scripts did."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    log.handlers = [handler]
    log.setLevel(level)


def report(title: str, rows: dict[str, str]) -> None:
    """Logs one aligned report block, with its values in a column."""
    label_width = max((len(label) for label in rows), default=0)

    log.info("")
    log.info("-" * 40)
    log.info(title)
    log.info("-" * 40)
    for label, value in rows.items():
        log.info(f"{label:<{label_width}} = {value}")
    log.info("-" * 40)
