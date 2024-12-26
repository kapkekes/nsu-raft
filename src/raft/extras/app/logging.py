__all__ = (
    "ColorFormatter",
)

import logging
from collections.abc import Mapping
from typing import Any, Literal

TRACE_INT = 5
TRACE_NAME = "TRACE"
logging.addLevelName(5, "TRACE")

COLORS = {
    TRACE_INT: "\x1b[37;20m",
    logging.DEBUG: "\x1b[36;20m",
    logging.INFO: "\x1b[32;20m",
    logging.WARNING: "\x1b[33;20m",
    logging.ERROR: "\x1b[31;20m",
    logging.CRITICAL: "\x1b[31;1m",
}


class ColorFormatter(logging.Formatter):
    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: Literal["%", "{", "$"] = "%",
        validate: bool = True,
        *,
        defaults: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(fmt, datefmt, style, validate, defaults=defaults)
        self._switch = (defaults or {}).get("$switch", True)

    def switch(self, value: bool) -> None:
        self._switch = value

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        if self._switch:
            message = COLORS[record.levelno] + message + "\x1b[0m"
        return message
