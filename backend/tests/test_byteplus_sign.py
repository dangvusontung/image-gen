from datetime import datetime, timezone

from app.providers.byteplus_sign import SIGNED_HEADERS, action_query, sign_request, signing_key

AK = "AKLTtest-access-key"
SK = "c2VjcmV0LXRlc3Qta2V5"
WHEN = datetime(2026, 10, 9, 7, 37, 2, tzinfo=timezone.utc)


def signed(**kw):
    defaults = dict(method="POST", host="open.byteplusapi.com", service="ark", region="ap-southeast-1",
                    query=action_query("ListFoundationModels", "2024-01-01"), body=b'{"PageNumber": 1}',
                    content_type="application/json", access_key=AK, secret_key=SK, now=WHEN)
    return sign_request(**{**defaults, **kw})


def test_action_query_is_sorted_and_only_carries_action_and_version():
    assert action_query("ListFoundationModels", "2024-01-01") == "Action=ListFoundationModels&Version=2024-01-01"


def test_canonical_request_follows_the_byteplus_layout():
    _, canonical = signed()
    lines = canonical.split("\n")
    assert lines[0] == "POST" and lines[1] == "/"
    assert lines[2] == "Action=ListFoundationModels&Version=2024-01-01"
    # Canonical headers are lowercase, newline-terminated and sorted, then signed headers, then payload hash.
    assert lines[3] == "content-type:application/json"
    assert lines[4] == "host:open.byteplusapi.com"
    assert lines[5].startswith("x-content-sha256:")
    assert lines[6] == "x-date:20261009T073702Z"
    assert lines[7] == "" and lines[8] == SIGNED_HEADERS
    assert lines[9] == lines[5].split(":", 1)[1]


def test_authorization_header_shape_and_scope():
    headers, _ = signed()
    assert headers["X-Date"] == "20261009T073702Z"
    assert headers["Host"] == "open.byteplusapi.com"
    auth = headers["Authorization"]
    assert auth.startswith(f"HMAC-SHA256 Credential={AK}/20261009/ap-southeast-1/ark/request, ")
    assert f"SignedHeaders={SIGNED_HEADERS}, " in auth
    signature = auth.split("Signature=")[1]
    assert len(signature) == 64 and int(signature, 16) >= 0


def test_signing_key_chain_starts_from_the_raw_secret_and_ends_with_request():
    # BytePlus/Volcengine differ from AWS here: no "AWS4" prefix, terminator is "request".
    import hashlib
    import hmac

    expected = SK.encode()
    for part in ("20261009", "ap-southeast-1", "ark", "request"):
        expected = hmac.new(expected, part.encode(), hashlib.sha256).digest()
    assert signing_key(SK, "20261009", "ap-southeast-1", "ark") == expected


def test_signature_is_deterministic_and_sensitive_to_every_signed_input():
    base = signed()[0]["Authorization"]
    assert signed()[0]["Authorization"] == base
    assert signed(body=b'{"PageNumber": 2}')[0]["Authorization"] != base
    assert signed(region="eu-west-1")[0]["Authorization"] != base
    assert signed(service="other")[0]["Authorization"] != base
    assert signed(query=action_query("ListEndpoints", "2024-01-01"))[0]["Authorization"] != base
    assert signed(now=datetime(2026, 10, 9, 7, 37, 3, tzinfo=timezone.utc))[0]["Authorization"] != base
