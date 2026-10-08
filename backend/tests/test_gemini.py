import asyncio
import base64
import json

import httpx
import pytest

from app.providers.base import ErrorKind, ImageRequest, ProviderError, ReferenceImage, SubmissionState
from app.providers.gemini import GeminiProvider
from tests.conftest import make_image

KEY = "AIzaFAKE-test-key-0000000000000000000"
PNG = make_image()


def provider_with(handler) -> tuple[GeminiProvider, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(wrapped))
    return GeminiProvider(client, api_key=KEY, base_url="https://gemini.test/v1beta"), seen


def image_response(**extra) -> httpx.Response:
    body = {
        "responseId": "resp-123",
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {
                    "parts": [
                        {"text": "thinking…", "thought": True},
                        {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(b"thought-image").decode()}, "thought": True},
                        {"text": "Đây là ảnh"},
                        {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(PNG).decode()}},
                    ]
                },
            }
        ],
        **extra,
    }
    return httpx.Response(200, json=body)


def request(n_refs=2, **kw) -> ImageRequest:
    refs = [ReferenceImage(PNG, "image/png", f"reference photo {i}") for i in range(1, n_refs + 1)]
    return ImageRequest(model="gemini-nano-banana-2.1", prompt="Tạo nhân vật", references=refs, aspect_ratio="3:4", **kw)


def test_submit_builds_documented_payload_and_parses_image():
    provider, seen = provider_with(lambda r: image_response())
    result = asyncio.run(provider.submit(request(seed=7, options={"size": "1K"})))

    sent = seen[0]
    assert str(sent.url) == "https://gemini.test/v1beta/models/gemini-nano-banana-2.1:generateContent"
    assert sent.headers["x-goog-api-key"] == KEY
    assert "key=" not in str(sent.url)
    body = json.loads(sent.content)
    parts = body["contents"][0]["parts"]
    assert parts[0] == {"text": "Tạo nhân vật"}
    assert parts[1] == {"text": "Image 1: reference photo 1"}
    assert parts[2]["inlineData"]["mimeType"] == "image/png"
    assert base64.b64decode(parts[2]["inlineData"]["data"]) == PNG
    assert len([p for p in parts if "inlineData" in p]) == 2
    cfg = body["generationConfig"]
    assert cfg["imageConfig"] == {"aspectRatio": "3:4", "imageSize": "1K"}
    assert cfg["responseModalities"] == ["TEXT", "IMAGE"] and cfg["seed"] == 7

    assert result.state == SubmissionState.READY
    assert result.provider_request_id == "resp-123"
    assert [i.data for i in result.images] == [PNG]  # thought image skipped


def test_default_size_comes_from_model():
    provider, seen = provider_with(lambda r: image_response())
    asyncio.run(provider.submit(request()))
    assert json.loads(seen[0].content)["generationConfig"]["imageConfig"]["imageSize"] == "2K"


def test_snake_case_response_is_accepted():
    body = {"candidates": [{"content": {"parts": [{"inline_data": {"mime_type": "image/png", "data": base64.b64encode(PNG).decode()}}]}}]}
    provider, _ = provider_with(lambda r: httpx.Response(200, json=body))
    assert asyncio.run(provider.submit(request())).images[0].data == PNG


@pytest.mark.parametrize(
    "body,code",
    [
        ({"promptFeedback": {"blockReason": "SAFETY"}}, "content_moderated"),
        ({"candidates": [{"finishReason": "IMAGE_SAFETY", "content": {"parts": []}}]}, "content_moderated"),
        ({"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "Tôi không thể"}]}}]}, "no_image"),
    ],
)
def test_blocked_or_empty_responses_are_permanent(body, code):
    provider, _ = provider_with(lambda r: httpx.Response(200, json=body))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.submit(request()))
    assert exc.value.code == code and exc.value.kind == ErrorKind.PERMANENT


@pytest.mark.parametrize(
    "status,headers,message,code,kind",
    [
        (429, {"retry-after": "7"}, "Resource has been exhausted (e.g. check quota) per minute", "rate_limited", ErrorKind.TRANSIENT_SAFE),
        (429, {}, "You exceeded your current quota", "quota_exceeded", ErrorKind.PERMANENT),
        (500, {}, "internal", "provider_unavailable", ErrorKind.TRANSIENT_SAFE),
        (503, {}, "overloaded", "provider_unavailable", ErrorKind.TRANSIENT_SAFE),
        (504, {}, "deadline", "timeout", ErrorKind.AMBIGUOUS),
        (400, {}, "bad image", "invalid_request", ErrorKind.PERMANENT),
        (403, {}, "denied", "auth_failed", ErrorKind.PERMANENT),
        (404, {}, "no model", "model_not_found", ErrorKind.PERMANENT),
    ],
)
def test_http_error_classification(status, headers, message, code, kind):
    provider, _ = provider_with(lambda r: httpx.Response(status, headers=headers, json={"error": {"message": message}}))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.submit(request()))
    assert (exc.value.code, exc.value.kind) == (code, kind)
    if headers:
        assert exc.value.retry_after == 7


def test_timeout_after_send_is_ambiguous_but_connect_error_is_safe():
    def read_timeout(r):
        raise httpx.ReadTimeout("slow", request=r)

    def connect_error(r):
        raise httpx.ConnectError("down", request=r)

    for handler, kind in ((read_timeout, ErrorKind.AMBIGUOUS), (connect_error, ErrorKind.TRANSIENT_SAFE)):
        provider, _ = provider_with(handler)
        with pytest.raises(ProviderError) as exc:
            asyncio.run(provider.submit(request()))
        assert exc.value.kind == kind


def test_reference_limit_enforced_before_any_http_call():
    provider, seen = provider_with(lambda r: image_response())
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.submit(request(n_refs=15)))
    assert exc.value.code == "reference_limit_exceeded"
    assert seen == []


def test_connection_check_uses_models_get():
    provider, seen = provider_with(lambda r: httpx.Response(200, json={"name": "models/gemini-nano-banana-2.1"}))
    assert "OK" in asyncio.run(provider.test_connection())
    assert seen[0].method == "GET" and seen[0].url.path == "/v1beta/models/gemini-nano-banana-2.1"
