import os
import tempfile
from pathlib import Path

# Configure BEFORE the app is imported: offline, deterministic, isolated data dir.
_tmp = tempfile.mkdtemp(prefix="kda-test-")
os.environ["DATA_DIR"] = _tmp
os.environ["EMBED_BACKEND"] = "hash"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[2] / "sample_data"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def register(client, name, email):
    r = client.post("/api/auth/register", json={"org_name": name, "email": email, "password": "supersecret1"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    a = client.get("/api/assistant", headers=h).json()
    return h, a["token"]


def upload(client, headers, path: Path):
    with open(path, "rb") as f:
        return client.post("/api/kb/documents", headers=headers, files={"file": (path.name, f, "application/pdf")})


@pytest.fixture(scope="session")
def org_a(client):
    h, tok = register(client, "Northfield University", "a@example.com")
    for p in (SAMPLES / "northfield").glob("*.pdf"):
        assert upload(client, h, p).status_code == 201
    return h, tok


@pytest.fixture(scope="session")
def org_b(client):
    h, tok = register(client, "Acme Corp", "b@example.com")
    for p in (SAMPLES / "acme").glob("*.pdf"):
        assert upload(client, h, p).status_code == 201
    return h, tok
