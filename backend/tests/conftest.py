import io
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="charstudio-test-")
os.environ["DATA_DIR"] = _TMP
os.environ["ASSETS_DIR"] = os.path.join(_TMP, "assets")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'unused.db')}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


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
