import asyncio
import base64
import json

import httpx
import pytest

from app.providers.base import ErrorKind, ImageRequest, ProviderError, ReferenceImage, Submission, SubmissionState
from app.providers.bfl import BflProvider, flux2_dimensions
from tests.conftest import make_image

KEY = "bfl-fake-key-1234567890"
PNG = make_image()
POLL = "https://api.us1.bfl.ai/v1/get_result?id=task-1"
SAMPLE = "https://delivery-us1.bfl.ai/results/abc/sample.png?se=sig"


def provider_with(routes, **kw):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return routes(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return BflProvider(client, api_key=KEY, base_url="https://api.bfl.ai", **kw), seen


def req(model="flux-2-pro", n_refs=3, **kw):
    refs = [ReferenceImage(PNG, "image/png", f"reference photo {i}") for i in range(1, n_refs + 1)]
    return ImageRequest(model=model, prompt="Nhân vật 3D", references=refs, aspect_ratio="3:4", **kw)


def test_flux2_dimensions_aligned_and_near_target():
    for ratio in ("1:1", "3:4", "16:9", "21:9"):
        w, h = flux2_dimensions(ratio, 1.0)
        assert w % 32 == 0 and h % 32 == 0
        assert 0.85e6 <= w * h <= 1.0e6
    assert flux2_dimensions("3:4", 1.0) == (864, 1152)


def test_flux2_submit_payload():
    provider, seen = provider_with(lambda r: httpx.Response(200, json={"id": "task-1", "polling_url": POLL, "cost": 4.5}))
    sub = asyncio.run(provider.submit(req(seed=3)))

    sent = seen[0]
    assert str(sent.url) == "https://api.bfl.ai/v1/flux-2-pro"
    assert sent.headers["x-key"] == KEY
    body = json.loads(sent.content)
    assert body["prompt"].startswith("Nhân vật 3D")
    assert "Image 1: reference photo 1" in body["prompt"]
    assert "Image 3: reference photo 3" in body["prompt"]
    assert (body["width"], body["height"]) == (864, 1152)
    assert body["output_format"] == "png" and body["disable_pup"] is True and body["seed"] == 3
    assert [k for k in body if k.startswith("input_image")] == ["input_image", "input_image_2", "input_image_3"]
    assert base64.b64decode(body["input_image"]) == PNG

    assert sub.state == SubmissionState.PENDING
    assert (sub.provider_request_id, sub.polling_url) == ("task-1", POLL)
    assert sub.actual_cost_usd == pytest.approx(0.045)


def test_data_url_encoding_option():
    provider, seen = provider_with(lambda r: httpx.Response(200, json={"id": "t", "polling_url": POLL}), image_encoding="data_url")
    asyncio.run(provider.submit(req(n_refs=1)))
    assert json.loads(seen[0].content)["input_image"].startswith("data:image/png;base64,")


def test_flux3_payload_uses_images_list_and_disables_grounding():
    provider, seen = provider_with(lambda r: httpx.Response(200, json={"id": "t", "polling_url": POLL}))
    asyncio.run(provider.submit(req(model="flux-3-image", n_refs=10, seed=1)))
    body = json.loads(seen[0].content)
    assert len(body["images"]) == 10
    assert body["grounding"] is False
    assert body["aspect_ratio"] == "3:4" and body["resolution"] == "768sq"
    assert "seed" not in body and "output_format" not in body and "input_image" not in body


def test_reference_limit_enforced_before_http():
    provider, seen = provider_with(lambda r: httpx.Response(200, json={}))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.submit(req(n_refs=9)))
    assert exc.value.code == "reference_limit_exceeded" and seen == []


def test_refuses_to_send_key_to_foreign_polling_url():
    provider, _ = provider_with(lambda r: httpx.Response(200, json={"id": "t", "polling_url": "https://evil.example/poll"}))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.submit(req()))
    assert exc.value.code == "bad_response"
    with pytest.raises(ProviderError):
        asyncio.run(provider.poll(Submission(SubmissionState.PENDING, "t", "http://api.bfl.ai/insecure")))


def test_poll_pending_then_ready_downloads_without_key():
    statuses = iter(["Pending", "Generating", "Ready"])

    def routes(r: httpx.Request):
        if str(r.url) == POLL:
            status = next(statuses)
            body = {"id": "t", "status": status}
            if status == "Ready":
                body.update(result={"sample": SAMPLE}, cost=4.5)
            return httpx.Response(200, json=body)
        if str(r.url) == SAMPLE:
            return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
        return httpx.Response(404)

    provider, seen = provider_with(routes)
    sub = Submission(SubmissionState.PENDING, "t", POLL)

    async def run():
        s = sub
        for _ in range(3):
            s = await provider.poll(s)
        return s

    result = asyncio.run(run())
    assert result.state == SubmissionState.READY and result.images[0].data == PNG
    assert result.actual_cost_usd == pytest.approx(0.045)
    poll_req = [r for r in seen if str(r.url) == POLL][0]
    download_req = [r for r in seen if str(r.url) == SAMPLE][0]
    assert poll_req.headers["x-key"] == KEY
    assert "x-key" not in download_req.headers


@pytest.mark.parametrize(
    "status,code",
    [("Content Moderated", "content_moderated"), ("Request Moderated", "content_moderated"),
     ("Task not found", "task_not_found"), ("Error", "provider_error"), ("Failed", "provider_error")],
)
def test_poll_terminal_failures_are_permanent(status, code):
    provider, _ = provider_with(lambda r: httpx.Response(200, json={"status": status, "details": {"Moderation Reasons": ["x"]}}))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.poll(Submission(SubmissionState.PENDING, "t", POLL)))
    assert (exc.value.code, exc.value.kind) == (code, ErrorKind.PERMANENT)


@pytest.mark.parametrize(
    "status,code,kind",
    [(402, "insufficient_credits", ErrorKind.PERMANENT), (422, "invalid_request", ErrorKind.PERMANENT),
     (429, "rate_limited", ErrorKind.TRANSIENT_SAFE), (503, "provider_unavailable", ErrorKind.TRANSIENT_SAFE),
     (500, "provider_error", ErrorKind.AMBIGUOUS)],
)
def test_submit_http_errors(status, code, kind):
    provider, _ = provider_with(lambda r: httpx.Response(status, json={"detail": "nope"}))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.submit(req()))
    assert (exc.value.code, exc.value.kind) == (code, kind)


def test_poll_5xx_is_safe_to_retry():
    provider, _ = provider_with(lambda r: httpx.Response(500, json={"detail": "x"}))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.poll(Submission(SubmissionState.PENDING, "t", POLL)))
    assert exc.value.kind == ErrorKind.TRANSIENT_SAFE


def test_credits_connection_check():
    provider, seen = provider_with(lambda r: httpx.Response(200, json={"credits": 250}))
    assert "250 credits" in asyncio.run(provider.test_connection())
    assert seen[0].url.path == "/v1/credits"
