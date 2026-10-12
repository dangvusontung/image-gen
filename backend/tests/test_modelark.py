import asyncio
import base64
import json

import httpx
import pytest

from app.providers.base import CapabilityError, ErrorKind, ImageRequest, ProviderError, ReferenceImage, SubmissionState
from app.providers.modelark import MAX_PIXELS, MODELS, ModelArkProvider, seedream_size
from tests.conftest import make_image

KEY = "ark-fake-key-1234567890"
PNG = make_image()
BASE = "https://ark.test/api/v3"


def provider_with(handler, **kw) -> tuple[ModelArkProvider, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(wrapped))
    return ModelArkProvider(client, api_key=KEY, base_url=BASE, **kw), seen


def req(model="seedream-4-5-251128", n_refs=2, **kw) -> ImageRequest:
    refs = [ReferenceImage(PNG, "image/png", f"reference {i}") for i in range(n_refs)]
    return ImageRequest(model=model, prompt="một nhân vật 3D", references=refs, aspect_ratio="3:4", **kw)


def ok_response(data=None, **extra) -> httpx.Response:
    body = {"created": 1762000000, "data": data if data is not None else [{"b64_json": base64.b64encode(PNG).decode()}],
            "usage": {"generated_images": 1}, **extra}
    return httpx.Response(200, json=body)


def test_submit_posts_openai_shaped_request_and_returns_the_image_synchronously():
    provider, seen = provider_with(lambda r: ok_response())
    sub = asyncio.run(provider.submit(req()))

    assert len(seen) == 1
    sent = seen[0]
    assert sent.method == "POST" and str(sent.url) == f"{BASE}/images/generations"
    assert sent.headers["authorization"] == f"Bearer {KEY}"
    payload = json.loads(sent.content)
    assert payload["model"] == "seedream-4-5-251128"
    assert payload["prompt"] == "một nhân vật 3D"
    assert payload["response_format"] == "b64_json"
    assert payload["watermark"] is False
    # 3:4 at the lowest 1K tier, not a squared-off preset.
    assert payload["size"] == "1760x2352"
    assert len(payload["image"]) == 2
    assert payload["image"][0].startswith("data:image/png;base64,")
    # Never sent: both 400 on the 5.0 pro/flash models and this app wants exactly one image.
    assert "sequential_image_generation" not in payload and "stream" not in payload
    # 4.5 is JPEG-only, so no output_format is requested.
    assert "output_format" not in payload

    assert sub.state is SubmissionState.READY
    assert len(sub.images) == 1 and sub.images[0].data == PNG
    assert sub.images[0].mime_type == "image/png"


def test_png_output_is_requested_only_for_the_five_series():
    provider, seen = provider_with(lambda r: ok_response())
    asyncio.run(provider.submit(req(model="seedream-5-0-pro-260628", n_refs=1)))
    payload = json.loads(seen[0].content)
    assert payload["output_format"] == "png"
    # The default uses the lowest supported tier.
    assert payload["size"] == seedream_size("3:4", "1K", MAX_PIXELS["seedream-5-0-pro-260628"])


def test_seed_and_watermark_are_passed_through_when_set():
    provider, seen = provider_with(lambda r: ok_response(), watermark=True)
    asyncio.run(provider.submit(req(seed=7)))
    payload = json.loads(seen[0].content)
    assert payload["seed"] == 7 and payload["watermark"] is True


def test_text_to_image_omits_the_image_array():
    provider, seen = provider_with(lambda r: ok_response())
    asyncio.run(provider.submit(req(n_refs=0)))
    assert "image" not in json.loads(seen[0].content)


def test_size_tier_and_reference_limits_are_enforced_before_any_request():
    provider, seen = provider_with(lambda r: ok_response())
    with pytest.raises(CapabilityError) as exc:
        asyncio.run(provider.submit(req(model="seedream-5-0-pro-260628", options={"size": "4K"})))
    assert exc.value.code == "unsupported_size"
    with pytest.raises(CapabilityError) as exc:
        asyncio.run(provider.submit(req(n_refs=11)))
    assert exc.value.code == "reference_limit_exceeded"
    assert seen == []


def test_mime_type_is_sniffed_from_the_returned_bytes():
    jpeg = make_image("JPEG")
    provider, _ = provider_with(lambda r: ok_response([{"b64_json": base64.b64encode(jpeg).decode()}]))
    sub = asyncio.run(provider.submit(req()))
    assert sub.images[0].mime_type == "image/jpeg"


@pytest.mark.parametrize(
    "status,body,code,kind",
    [
        (400, {"error": {"message": "invalid size"}}, "invalid_request", ErrorKind.PERMANENT),
        (401, {"error": {"message": "invalid token"}}, "auth_failed", ErrorKind.PERMANENT),
        (403, {"error": {"message": "content moderation triggered"}}, "content_moderated", ErrorKind.PERMANENT),
        (403, {"error": {"message": "no access to this resource"}}, "auth_failed", ErrorKind.PERMANENT),
        (404, {"error": {"message": "model not found"}}, "model_not_found", ErrorKind.PERMANENT),
        (429, {"error": {"message": "insufficient balance"}}, "quota_exceeded", ErrorKind.PERMANENT),
        (429, {"error": {"message": "too many requests"}}, "rate_limited", ErrorKind.TRANSIENT_SAFE),
        (500, {"error": {"message": "upstream"}}, "provider_unavailable", ErrorKind.TRANSIENT_SAFE),
        (504, {"error": {"message": "gateway timeout"}}, "timeout", ErrorKind.AMBIGUOUS),
    ],
)
def test_http_errors_map_to_retryability(status, body, code, kind):
    provider, _ = provider_with(lambda r: httpx.Response(status, json=body))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.submit(req()))
    assert (exc.value.code, exc.value.kind) == (code, kind)


def test_error_text_never_echoes_the_api_key():
    provider, _ = provider_with(lambda r: httpx.Response(400, json={"error": {"message": f"bad key {KEY}"}}))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.submit(req()))
    assert KEY not in exc.value.message


def test_empty_and_malformed_results_are_rejected():
    provider, _ = provider_with(lambda r: ok_response([]))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.submit(req()))
    assert exc.value.code == "no_image"

    provider, _ = provider_with(lambda r: ok_response([{"url": "https://ark.test/img.png"}]))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.submit(req()))
    assert exc.value.code == "bad_response"

    provider, _ = provider_with(lambda r: ok_response([{"b64_json": "!!!not base64!!!"}]))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.submit(req()))
    assert exc.value.code == "bad_response"

    provider, _ = provider_with(lambda r: httpx.Response(200, text="<html>nope"))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.submit(req()))
    assert (exc.value.code, exc.value.kind) == ("bad_response", ErrorKind.AMBIGUOUS)


def test_prices_are_absent_until_configured():
    provider, _ = provider_with(lambda r: ok_response())
    model = provider.get_model("seedream-4-5-251128")
    assert model.price_per_image_usd is None
    assert provider.estimate_cost_usd(model, "2K") is None

    priced, _ = provider_with(lambda r: ok_response(), price_per_image_usd=0.03)
    assert priced.estimate_cost_usd(priced.get_model("seedream-4-5-251128"), "2K") == 0.03


def test_connection_test_reports_key_status_without_generating():
    provider, seen = provider_with(lambda r: httpx.Response(200, json={"data": [{"id": "seedream-4-5-251128"}]}))
    assert "Kết nối OK" in asyncio.run(provider.test_connection())
    assert seen[0].method == "GET" and str(seen[0].url) == f"{BASE}/models"

    provider, _ = provider_with(lambda r: httpx.Response(404, json={}))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.test_connection())
    assert exc.value.code == "test_unsupported"

    unset = ModelArkProvider(httpx.AsyncClient(transport=httpx.MockTransport(lambda r: ok_response())), api_key="")
    assert unset.key_configured is False
    with pytest.raises(ProviderError) as exc:
        asyncio.run(unset.test_connection())
    assert exc.value.code == "provider_not_configured"


def test_sizes_stay_inside_the_documented_pixel_bounds():
    for ratio in ("1:1", "3:4", "4:3", "9:16", "21:9"):
        for tier in ("1K", "1.5K", "2K", "3K", "4K"):
            width, height = (int(v) for v in seedream_size(ratio, tier).split("x"))
            assert 512 <= width <= 4096 and 512 <= height <= 4096
            assert width % 16 == 0 and height % 16 == 0
    capped = seedream_size("3:4", "4K", MAX_PIXELS["seedream-5-0-pro-260628"])
    w, h = (int(v) for v in capped.split("x"))
    assert w * h <= MAX_PIXELS["seedream-5-0-pro-260628"]


# --- control plane: the account's own model catalogue -------------------------------------------

AK, SK = "AKLTtest-access-key", "c2VjcmV0LXRlc3Qta2V5"
CONTROL = "open.test"


def control_provider(handler):
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(wrapped))
    provider = ModelArkProvider(client, api_key=KEY, base_url=BASE, access_key=AK, secret_key=SK,
                                control_host=CONTROL, region="ap-southeast-1")
    return provider, seen


def catalogue(items, total=None) -> httpx.Response:
    return httpx.Response(200, json={"ResponseMetadata": {"RequestId": "r-1"},
                                     "Result": {"Items": items, "TotalCount": total if total is not None else len(items),
                                                "PageNumber": 1, "PageSize": 100}})


ITEMS = [
    {"FoundationModelName": "doubao-pro-32k-240615", "State": "Available", "DisplayName": "Doubao pro"},
    {"FoundationModelName": "seedream-4-5-251128", "State": "Available", "DisplayName": "Seedream 4.5"},
    {"FoundationModelName": "seedream-9-9-ultra-261231", "State": "Available", "DisplayName": "Seedream 9.9 ultra"},
]


def test_control_plane_fetch_preserves_activated_model_ids():
    provider, seen = control_provider(lambda r: catalogue(ITEMS))
    items = asyncio.run(provider.fetch_catalogue())

    sent = seen[0]
    assert sent.method == "POST"
    assert str(sent.url) == f"https://{CONTROL}/?Action=ListModelActivations&Version=2024-01-01"
    assert sent.headers["authorization"].startswith(f"HMAC-SHA256 Credential={AK}/")
    assert "/ap-southeast-1/ark/request," in sent.headers["authorization"]
    assert json.loads(sent.content) == {"PageNumber": 1, "PageSize": 100,
                                         "Filter": {"States": ["Available"], "IncludeDeprecatedModels": False}}
    # LLMs are filtered out when the catalogue is applied, not when it is fetched.
    assert items == [{"id": "doubao-pro-32k-240615", "display_name": "Doubao pro"},
                     {"id": "seedream-4-5-251128", "display_name": "Seedream 4.5"},
                     {"id": "seedream-9-9-ultra-261231", "display_name": "Seedream 9.9 ultra"}]


def test_activated_models_require_control_plane_credentials_without_trying_bearer_models():
    provider, seen = provider_with(lambda r: httpx.Response(200, json={"data": []}))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.fetch_catalogue())
    assert exc.value.code == "catalogue_unsupported"
    assert "ARK_ACCESS_KEY" in exc.value.message
    assert seen == []


def test_applying_a_catalogue_keeps_known_capabilities_and_drops_absent_models():
    provider, _ = provider_with(lambda r: ok_response())
    models = provider.apply_catalogue([
        {"id": "doubao-pro-32k-240615", "display_name": "Doubao pro"},
        {"id": "seedream-4-5-251128", "display_name": "Seedream 4.5"},
        {"id": "seedream-9-9-ultra-261231", "display_name": "Seedream 9.9 ultra"},
    ])
    assert [m.id for m in models] == ["seedream-4-5-251128", "seedream-9-9-ultra-261231"]

    known = provider.get_model("seedream-4-5-251128")
    assert known.max_reference_images == 10 and known.sizes == ("2K", "4K") and known.default is True
    # An unrecognised family still appears, with conservative capabilities and a clear note.
    unknown = provider.get_model("seedream-9-9-ultra-261231")
    assert unknown.sizes == ("2K",) and unknown.status == "preview"
    assert "ListModelActivations" in unknown.notes
    # A model the account does not have can no longer be selected.
    with pytest.raises(CapabilityError):
        provider.get_model("seedream-5-0-pro-260628")


def test_an_empty_catalogue_reverts_to_the_builtin_records():
    provider, _ = provider_with(lambda r: ok_response())
    provider.apply_catalogue([{"id": "seedream-4-5-251128", "display_name": "x"}])
    assert len(provider.models()) == 1
    assert [m.id for m in provider.apply_catalogue([])] == [m.id for m in MODELS]


def test_control_plane_paginates_until_the_total_is_reached():
    pages = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = json.loads(request.content)["PageNumber"]
        pages.append(page)
        batch = [{"FoundationModelName": f"seedream-p{page}-{i}-1", "State": "Available"} for i in range(100)]
        return catalogue(batch, total=150) if page == 1 else catalogue(batch[:50], total=150)

    provider, _ = control_provider(handler)
    assert len(provider.apply_catalogue(asyncio.run(provider.fetch_catalogue()))) == 150
    assert pages == [1, 2]


def test_control_plane_errors_surface_as_typed_provider_errors():
    provider, _ = control_provider(
        lambda r: httpx.Response(200, json={"ResponseMetadata": {"Error": {"Code": "InvalidCredential",
                                                                          "Message": f"bad {SK}"}}}))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.fetch_catalogue())
    assert exc.value.code == "auth_failed"
    assert SK not in exc.value.message

    provider, _ = control_provider(lambda r: httpx.Response(403, json={"error": {"message": f"nope {SK}"}}))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.fetch_catalogue())
    assert exc.value.code == "auth_failed" and SK not in exc.value.message

    provider, _ = control_provider(lambda r: httpx.Response(503, text="unavailable"))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.fetch_catalogue())
    assert (exc.value.code, exc.value.kind) == ("provider_unavailable", ErrorKind.TRANSIENT_SAFE)


def test_connection_test_uses_the_control_plane_when_configured():
    provider, seen = control_provider(lambda r: catalogue(ITEMS))
    message = asyncio.run(provider.test_connection())
    assert "2 model ảnh" in message and "seedream-4-5-251128" in message
    assert str(seen[0].url).startswith(f"https://{CONTROL}/?Action=ListModelActivations")
    assert [m.id for m in provider.models()] == ["seedream-4-5-251128", "seedream-9-9-ultra-261231"]


def test_configured_price_applies_to_fetched_models():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: catalogue(ITEMS)))
    provider = ModelArkProvider(client, api_key=KEY, base_url=BASE, access_key=AK, secret_key=SK,
                                control_host=CONTROL, price_per_image_usd=0.04)
    provider.apply_catalogue(asyncio.run(provider.fetch_catalogue()))
    assert all(m.price_per_image_usd == 0.04 for m in provider.models())


def test_dola_pro_catalogue_preserves_invocation_id_and_png_capabilities():
    provider, seen = provider_with(lambda r: ok_response())
    model_id = "dola-seedream-5-0-pro-260628"
    assert provider.get_model(model_id).sizes == ("1K", "2K")
    models = provider.apply_catalogue([{"id": model_id, "display_name": "Dola pro"}])
    assert len(models) == 1
    assert models[0].status == "ga"
    asyncio.run(provider.submit(req(model=model_id, n_refs=1)))
    payload = json.loads(seen[0].content)
    assert payload["model"] == model_id
    assert payload["output_format"] == "png"
    assert payload["size"] == seedream_size("3:4", "1K", MAX_PIXELS[model_id])


def test_activation_catalogue_excludes_unavailable_and_deprecated_models():
    provider, _ = control_provider(lambda r: catalogue([
        {"FoundationModelName": "dola-seedream-5-0-pro-260628", "State": "Available", "DisplayName": "Dola pro"},
        {"FoundationModelName": "seedream-disabled", "State": "Unavailable"},
        {"FoundationModelName": "seedream-old", "State": "Available", "IsDeprecated": True},
    ]))
    assert asyncio.run(provider.fetch_catalogue()) == [
        {"id": "dola-seedream-5-0-pro-260628", "display_name": "Dola pro"}]


def test_no_activated_image_models_is_reported_instead_of_falling_back_to_builtin_models():
    provider, _ = control_provider(lambda r: catalogue([]))
    with pytest.raises(ProviderError) as exc:
        asyncio.run(provider.fetch_catalogue())
    assert exc.value.code == "no_activated_image_models"


def test_seedream_45_upgrades_old_1k_requests_to_valid_minimum():
    provider, seen = provider_with(lambda r: ok_response())
    asyncio.run(provider.submit(req(options={"size": "1K"})))
    payload = json.loads(seen[0].content)
    width, height = map(int, payload["size"].split("x"))
    assert width * height >= 3_686_400
    assert provider.get_model("seedream-4-5-251128").default_size == "2K"
