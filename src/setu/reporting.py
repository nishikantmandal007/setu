# How setu says what it is doing. A library must not print - it logs, and the
# host program decides whether anyone sees that. The original bridge scripts'
# progress reports were genuinely useful to read while a model was being
# built, so enable_reports() turns them back on in one line.

from __future__ import annotations

import logging

log = logging.getLogger("setu")
log.addHandler(logging.NullHandler())


def enable_reports(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    # Replaces any handlers a host application already installed on this
    # logger (Osdag, for one) - fine for a script, but a host that wants its
    # own handlers kept should attach to "setu" itself rather than call this.
    log.handlers = [handler]
    log.setLevel(level)


def report(title: str, rows: dict[str, str]) -> None:
    label_width = max((len(label) for label in rows), default=0)

    log.info("")
    log.info("-" * 40)
    log.info(title)
    log.info("-" * 40)
    for label, value in rows.items():
        log.info(f"{label:<{label_width}} = {value}")
    log.info("-" * 40)
