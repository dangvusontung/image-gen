import io
import os
import tempfile
import time

_TMP = tempfile.mkdtemp(prefix="charstudio-test-")
os.environ.update(
    {
        "DATA_DIR": _TMP,
        "ASSETS_DIR": os.path.join(_TMP, "assets"),
        "DATABASE_URL": f"sqlite:///{os.path.join(_TMP, 'test.db')}",
        # Explicit empty values win over anything in the developer's .env.
        "GEMINI_API_KEY": "",
        "BFL_API_KEY": "",
        "MOCK_DELAY_SECONDS": "0.2",
        "JOB_POLL_INTERVAL_SECONDS": "0.05",
        "JOB_BACKOFF_BASE_SECONDS": "0.05",
        "JOB_TICK_SECONDS": "0.05",
        "JOB_CONCURRENCY": "2",
        "SPEND_LIMIT_USD_PER_DAY": "1",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

FINAL = {"succeeded", "failed", "cancelled"}


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


def make_image(fmt: str = "PNG", size=(64, 48), color=(120, 80, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture()
def project(client):
    resp = client.post("/api/projects", json={"name": "Dự án thử"})
    project_id = resp.json()["id"]
    client.patch(f"/api/projects/{project_id}", json={"rights_confirmed": True})
    return project_id


@pytest.fixture()
def reference_ids(client, project):
    files = [("files", (f"r{i}.png", make_image(color=(40 * i, 90, 160)), "image/png")) for i in range(3)]
    return [a["id"] for a in client.post(f"/api/projects/{project}/assets", files=files).json()]


@pytest.fixture()
def enqueue(client, project, reference_ids):
    """Create a job through the service layer (domain endpoints arrive in Phase 3)."""
    from app.jobs.service import enqueue_job
    from app.models import Project

    def _enqueue(**kwargs):
        kwargs.setdefault("purpose", "test")
        kwargs.setdefault("prompt", "Một nhân vật 3D thử nghiệm")
        kwargs.setdefault("reference_asset_ids", reference_ids)
        with SessionLocal() as db:
            job = enqueue_job(db, app.state.registry, db.get(Project, project), **kwargs)
            db.commit()
            job_id = job.id
        app.state.runner.notify()
        return job_id

    return _enqueue


def wait_for_job(client, job_id, statuses=FINAL, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in statuses:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} stuck in {job['status']}")
