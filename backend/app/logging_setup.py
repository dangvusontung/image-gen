import logging
import re

from app.config import SECRET_VALUES

_BASE64_RUN = re.compile(r"[A-Za-z0-9+/=_-]{200,}")
_KEY_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),  # Google API key shape
    re.compile(r"(?i)(x-key|x-goog-api-key|api[_-]?key|[?&]key)(['\"]?\s*[:=]\s*['\"]?)[^\s'\",}&]+"),
)


def redact(text: str, secrets: tuple[str, ...] = ()) -> str:
    for secret in (*SECRET_VALUES, *secrets):
        if not secret:
            continue
        text = text.replace(secret, "[REDACTED]")
    for pattern in _KEY_PATTERNS:
        text = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]" if m.lastindex else "[REDACTED]", text)
    return _BASE64_RUN.sub(lambda m: f"[{len(m.group(0))} chars omitted]", text)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        cleaned = redact(message)
        if cleaned != message:
            record.msg, record.args = cleaned, None
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    if not any(isinstance(f, RedactingFilter) for h in root.handlers for f in h.filters):
        if not root.handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        for handler in root.handlers:
            handler.addFilter(RedactingFilter())
    for name in ("uvicorn.access", "uvicorn.error"):
        for handler in logging.getLogger(name).handlers:
            handler.addFilter(RedactingFilter())
    # httpx logs full request URLs at INFO; keep it quiet.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
