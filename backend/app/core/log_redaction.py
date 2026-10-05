"""Keeps secrets that are part of a URL path out of the access log."""

import logging
import re

ACCESS_LOGGER = "uvicorn.access"


class PathRedactionFilter(logging.Filter):
    """Replaces the path segment after the given prefixes in uvicorn access log records."""

    def __init__(self, prefixes: tuple[str, ...]):
        super().__init__()
        escaped = "|".join(re.escape(prefix) for prefix in prefixes)
        self._pattern = re.compile(rf"({escaped})[^/?\s]+")

    def redact(self, text: str) -> str:
        return self._pattern.sub(r"\1[redacted]", text)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                self.redact(arg) if isinstance(arg, str) else arg for arg in record.args
            )
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        return True


def redact_paths_in_access_log(*prefixes: str) -> None:
    logger = logging.getLogger(ACCESS_LOGGER)
    if not any(isinstance(f, PathRedactionFilter) for f in logger.filters):
        logger.addFilter(PathRedactionFilter(prefixes))
