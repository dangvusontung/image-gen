from dataclasses import replace

import pytest

from app.main import app
from app.providers.bfl import BflProvider
from app.providers.mock import MockProvider
from tests.conftest import wait_for_job


def test_flux2_estimate_includes_each_normalized_reference():
    provider = BflProvider(None, api_key="fake")
    pro = provider.get_model("flux-2-pro")
    # A 4000x3000 input becomes 2048x1536 (~3.15MP), rounded to 4 billed MP.
    assert provider.estimate_request_cost_usd(pro, "2MP", [(4000, 3000), (64, 48)]) == pytest.approx(0.12)
    maximum = provider.get_model("flux-2-max")
    assert provider.estimate_request_cost_usd(maximum, "1MP", [(64, 48)]) == pytest.approx(0.10)
    flux3 = provider.get_model("flux-3-image")
    assert provider.estimate_request_cost_usd(flux3, "1.5k", []) is None


def test_unknown_submission_outcome_keeps_spend_reserved(client, project, enqueue):
    class PaidMock(MockProvider):
        name = "paid-test"

        def models(self):
            return [replace(super().models()[0], price_per_image_usd=0.25)]

    app.state.registry._providers["paid-test"] = PaidMock(delay_seconds=0)
    uncertain = enqueue(provider_name="paid-test", options={"mock": "ambiguous"})
    result = wait_for_job(client, uncertain)
    assert result["status"] == "failed" and result["attempts"] == 1
    assert result["submitted_at"] is not None
    assert client.get('/api/spend').json()["spent_24h_usd"] == pytest.approx(0.25)
    rejected = enqueue(provider_name="paid-test", options={"mock": "fail"})
    result = wait_for_job(client, rejected)
    assert result["status"] == "failed" and result["submitted_at"] is None
    assert client.get('/api/spend').json()["spent_24h_usd"] == pytest.approx(0.25)
