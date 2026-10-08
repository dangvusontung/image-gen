import logging

from app.logging_setup import RedactingFilter, redact


def test_redact_known_secrets_key_shapes_and_base64():
    blob = "QUJD" * 100
    text = f'GET https://x.test/v1/models?key=sk-live-123&alt=json x-key: abcdef {{"x-goog-api-key": "zzz"}} AIzaSyA1234567890123456789012 img={blob} mine'
    out = redact(text, ("mine",))
    assert "sk-live-123" not in out and "&alt=json" in out and "abcdef" not in out and '"zzz"' not in out
    assert "AIzaSyA" not in out and blob not in out and "mine" not in out
    assert "chars omitted]" in out


def test_filter_rewrites_record_and_exception_text():
    record = logging.LogRecord("t", logging.ERROR, __file__, 1, "sending %s", ("AIzaSyA1234567890123456789012",), None)
    try:
        raise RuntimeError("api_key=topsecret")
    except RuntimeError:
        import sys

        record.exc_info = sys.exc_info()
    RedactingFilter().filter(record)
    assert "AIzaSyA" not in record.getMessage()
    assert "topsecret" not in record.exc_text and "[REDACTED]" in record.exc_text
