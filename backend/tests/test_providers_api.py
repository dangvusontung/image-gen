import base64
import json
import logging

import httpx

from app.main import app
from app.providers.bfl import BflProvider
from app.providers.gemini import GeminiProvider
from tests.conftest import make_image, wait_for_job

GEMINI_KEY = "AIzaSECRET-gemini-key-000000000000000"
BFL_KEY = "bfl-SECRET-key-999999999"


def test_lists_all_providers_with_status(client):
    providers = {p["name"]: p for p in client.get("/api/providers").json()}
    assert list(providers) == ["mock", "gemini", "bfl", "modelark", "openai", "midjourney"]
    assert providers["mock"]["enabled"] is True
    assert providers["gemini"]["key_configured"] is False and providers["gemini"]["enabled"] is False
    assert providers["midjourney"]["selectable"] is False and providers["midjourney"]["models"] == []
    gemini_default = [m for m in providers["gemini"]["models"] if m["default"]]
    assert [m["id"] for m in gemini_default] == ["gemini-nano-banana-2.1"]
    assert providers["bfl"]["models"][0]["max_reference_images"] == 8
    assert providers["modelark"]["key_configured"] is False and providers["modelark"]["enabled"] is False
    assert providers["openai"]["key_configured"] is False and providers["openai"]["enabled"] is False
    assert {m["id"] for m in providers["openai"]["models"]} == {"gpt-image-2.5-sunburst", "gpt-image-2.5-flare", "gpt-image-1"}

    models = client.get("/api/providers/bfl/models").json()
    assert {m["id"] for m in models} == {"flux-2-pro", "flux-2-max", "flux-3-image"}
    ark = client.get("/api/providers/modelark/models").json()
    assert {m["id"] for m in ark} == {"seedream-4-5-251128", "seedream-5-0-pro-260628",
                                      "seedream-5-0-flash-260915", "seedream-4-0-250828"}
    # No published per-image price ships with the adapter; ARK_PRICE_PER_IMAGE_USD supplies it.
    assert all(m["price_per_image_usd"] is None for m in ark)
    assert client.get("/api/providers/nope/models").status_code == 404


def test_connection_test_endpoint(client):
    assert client.post("/api/providers/mock/test").json()["ok"] is True
    result = client.post("/api/providers/gemini/test").json()
    assert result == {"ok": False, "message": "Chưa cấu hình GEMINI_API_KEY", "code": "provider_not_configured"}
    assert client.post("/api/providers/midjourney/test").json()["ok"] is False


def test_project_provider_selection(client, project):
    resp = client.patch(f"/api/projects/{project}", json={"provider": "bfl"})
    assert resp.status_code == 200
    assert (resp.json()["provider"], resp.json()["model"]) == ("bfl", "flux-2-pro")
    assert client.patch(f"/api/projects/{project}", json={"model": "flux-2-max"}).json()["model"] == "flux-2-max"
    bad = client.patch(f"/api/projects/{project}", json={"model": "gemini-3-pro-image"})
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "unknown_model"
    assert client.patch(f"/api/projects/{project}", json={"provider": "midjourney"}).json()["detail"]["code"] == "provider_disabled"


def test_secrets_never_leak_to_responses_or_logs(client, project, enqueue, caplog):
    png = base64.b64encode(make_image()).decode()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "gemini.test":
            if request.method == "GET":
                return httpx.Response(200, json={"name": "m"})
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": png}}]}}]})
        if request.url.path == "/v1/credits":
            return httpx.Response(200, json={"credits": 10})
        return httpx.Response(401, json={"detail": f"bad key {request.headers.get('x-key')}"})

    fake = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    registry = app.state.registry
    registry._providers["gemini"] = GeminiProvider(fake, api_key=GEMINI_KEY, base_url="https://gemini.test/v1beta")
    registry._providers["bfl"] = BflProvider(fake, api_key=BFL_KEY, base_url="https://api.bfl.ai")

    caplog.set_level(logging.DEBUG)
    bodies = [
        client.get("/api/providers").text,
        client.post("/api/providers/gemini/test").text,
        client.post("/api/providers/bfl/test").text,
    ]
    job = wait_for_job(client, enqueue(provider_name="gemini", model_id="gemini-nano-banana-2.1", skip_spend_check=True))
    assert job["status"] == "succeeded"
    bfl_job = wait_for_job(client, enqueue(provider_name="bfl", skip_spend_check=True))
    assert bfl_job["status"] == "failed"  # 401 echoing the key back must be redacted
    bodies += [
        client.get(f"/api/jobs/{job['id']}").text,
        client.get(f"/api/jobs/{bfl_job['id']}").text,
        client.get(f"/api/projects/{project}/jobs").text,
    ]

    providers = {p["name"]: p for p in json.loads(bodies[0])}
    assert providers["gemini"]["key_configured"] is True
    everything = "\n".join(bodies) + "\n" + caplog.text
    assert GEMINI_KEY not in everything and BFL_KEY not in everything
    assert png not in caplog.text


def test_fetching_models_persists_them_and_survives_a_restart(client):
    from app.main import app, load_saved_catalogues
    from app.providers.modelark import ModelArkProvider, MODELS

    class FakeArk(ModelArkProvider):
        calls = 0

        @property
        def key_configured(self):
            return True

        async def fetch_catalogue(self):
            type(self).calls += 1
            return [{"id": "seedream-4-5-251128", "display_name": "Seedream 4.5"},
                    {"id": "doubao-pro-32k", "display_name": "Doubao"}]

    registry = app.state.registry
    original = registry._providers["modelark"]
    registry._providers["modelark"] = FakeArk(original._client)
    try:
        before = {p["name"]: p for p in client.get("/api/providers").json()}["modelark"]
        assert before["catalogue_source"] == "modelark" and before["catalogue_fetched_at"] is None
        assert len(before["models"]) == len(MODELS)

        saved = client.post("/api/providers/modelark/models/fetch")
        assert saved.status_code == 200, saved.text
        # The LLM is filtered out; only the account's image model remains selectable.
        assert [m["id"] for m in saved.json()["models"]] == ["seedream-4-5-251128"]

        listed = {p["name"]: p for p in client.get("/api/providers").json()}["modelark"]
        assert [m["id"] for m in listed["models"]] == ["seedream-4-5-251128"]
        assert listed["catalogue_fetched_at"] is not None

        # A restart rebuilds the providers from scratch; the saved catalogue is reapplied.
        fresh = FakeArk(original._client)
        registry._providers["modelark"] = fresh
        assert [m.id for m in fresh.models()] == [m.id for m in MODELS]
        load_saved_catalogues(registry)
        assert [m.id for m in fresh.models()] == ["seedream-4-5-251128"]
        assert FakeArk.calls == 1, "startup must not call the provider's API"

        reset = client.delete("/api/providers/modelark/models/fetch")
        assert reset.status_code == 200
        assert [m["id"] for m in reset.json()["models"]] == [m.id for m in MODELS]
        after = {p["name"]: p for p in client.get("/api/providers").json()}["modelark"]
        assert after["catalogue_fetched_at"] is None
    finally:
        registry._providers["modelark"] = original


def test_fetch_reports_provider_errors_and_unsupported_providers(client):
    from app.main import app
    from app.providers.base import ProviderError
    from app.providers.modelark import ModelArkProvider

    class BrokenArk(ModelArkProvider):
        @property
        def key_configured(self):
            return True

        async def fetch_catalogue(self):
            raise ProviderError("catalogue_unsupported", "không có endpoint /models")

    registry = app.state.registry
    original = registry._providers["modelark"]
    registry._providers["modelark"] = BrokenArk(original._client)
    try:
        failed = client.post("/api/providers/modelark/models/fetch")
        assert failed.status_code == 400
        assert failed.json()["detail"]["code"] == "catalogue_unsupported"
    finally:
        registry._providers["modelark"] = original

    # Providers with no catalogue API say so rather than pretending to fetch.
    assert client.post("/api/providers/mock/models/fetch").json()["detail"]["code"] == "catalogue_unsupported"
    # Ones that have a catalogue but no key report the missing key instead.
    assert client.post("/api/providers/gemini/models/fetch").json()["detail"]["code"] == "provider_not_configured"
    assert client.post("/api/providers/nope/models/fetch").status_code == 404
