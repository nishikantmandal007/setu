from __future__ import annotations

import logging

log = logging.getLogger("setu")
log.addHandler(logging.NullHandler())

RULE = "-" * 40


def enable_reports(level: int = logging.INFO) -> None:
    # Replaces any handlers a host application already installed on this logger.
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    log.handlers = [handler]
    log.setLevel(level)


def report(title: str, rows: dict[str, str]) -> None:
    label_width = max((len(label) for label in rows), default=0)

    log.info("")
    log.info(RULE)
    log.info(title)
    log.info(RULE)
    for label, value in rows.items():
        log.info(f"{label:<{label_width}} = {value}")
    log.info(RULE)
