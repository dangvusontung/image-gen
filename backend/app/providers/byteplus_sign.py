"""BytePlus/Volcengine OpenAPI request signing (HMAC-SHA256, SigV4-style).

Verified 2026-10-09 against https://docs.byteplus.com/byteplus-platform/reference/how-to-calculate-a-signature
and https://docs.byteplus.com/en/docs/byteplus-platform/reference-example.

It differs from AWS SigV4 in three places that matter: the signing key chain starts from the raw
secret (no "AWS4" prefix), the credential scope terminator is "request" (not "aws4_request"), and
the timestamp/payload headers are X-Date / X-Content-Sha256 (not X-Amz-*).

Control-plane actions on Ark are the POST/JSON shape: only Action and Version ride in the signed
query string, everything else goes in the JSON body.
"""

import hashlib
import hmac
from datetime import datetime, timezone
from urllib.parse import urlencode

SIGNED_HEADERS = "content-type;host;x-content-sha256;x-date"
ALGORITHM = "HMAC-SHA256"
TERMINATOR = "request"


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def signing_key(secret_key: str, short_date: str, region: str, service: str) -> bytes:
    return _hmac(_hmac(_hmac(_hmac(secret_key.encode(), short_date), region), service), TERMINATOR)


def action_query(action: str, version: str) -> str:
    """The signed query string for a POST/JSON action call."""
    return urlencode(sorted([("Action", action), ("Version", version)]))


def sign_request(*, method: str, host: str, service: str, region: str, query: str, body: bytes,
                 content_type: str, access_key: str, secret_key: str,
                 now: datetime | None = None) -> tuple[dict[str, str], str]:
    """Signed headers for one request, plus the canonical request (returned for testability)."""
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    short_date = stamp[:8]
    payload_hash = hashlib.sha256(body).hexdigest()
    canonical_headers = f"content-type:{content_type}\nhost:{host}\nx-content-sha256:{payload_hash}\nx-date:{stamp}\n"
    canonical_request = "\n".join([method, "/", query, canonical_headers, SIGNED_HEADERS, payload_hash])
    scope = f"{short_date}/{region}/{service}/{TERMINATOR}"
    string_to_sign = "\n".join([ALGORITHM, stamp, scope, hashlib.sha256(canonical_request.encode()).hexdigest()])
    signature = hmac.new(signing_key(secret_key, short_date, region, service),
                         string_to_sign.encode(), hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": content_type,
        "Host": host,
        "X-Date": stamp,
        "X-Content-Sha256": payload_hash,
        "Authorization": f"{ALGORITHM} Credential={access_key}/{scope}, "
                         f"SignedHeaders={SIGNED_HEADERS}, Signature={signature}",
    }
    return headers, canonical_request
