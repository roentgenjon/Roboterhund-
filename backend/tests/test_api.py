"""
API integration tests – run entirely in MOCK_MODE (no ROS2, no hardware).
Uses httpx AsyncClient against the live FastAPI app.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Force MOCK_MODE before any app import
os.environ["MOCK_MODE"] = "true"
os.environ["BACKEND_PIN"] = ""   # no PIN for most tests
os.environ["ZONES_FILE"] = "/tmp/go2_test_zones.json"

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="module")
def app():
    from main import app
    return app


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["mock"] is True


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_map_returns_base64_png(client):
    r = await client.get("/api/map")
    assert r.status_code == 200
    data = r.json()
    assert "png_b64" in data
    assert len(data["png_b64"]) > 100
    assert data["width"] > 0
    assert data["height"] > 0
    assert data["resolution"] > 0


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_has_expected_fields(client):
    r = await client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert "mode" in data
    assert "battery_percent" in data
    assert "position_x" in data


# ---------------------------------------------------------------------------
# Zones
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_zones_empty_initially(client):
    # Remove stale test file
    Path("/tmp/go2_test_zones.json").unlink(missing_ok=True)
    r = await client.get("/api/zones")
    assert r.status_code == 200
    assert r.json()["zones"] == []


@pytest.mark.asyncio
async def test_save_zones_and_retrieve(client):
    zones = [
        {"name": "Schulflur", "points": [[0, 0], [1, 0], [1, 1], [0, 1]]},
    ]
    r = await client.post("/api/zones", json={"zones": zones})
    assert r.status_code == 200
    assert r.json()["count"] == 1

    r2 = await client.get("/api/zones")
    assert r2.status_code == 200
    saved = r2.json()["zones"]
    assert len(saved) == 1
    assert saved[0]["name"] == "Schulflur"


# ---------------------------------------------------------------------------
# Control (MOCK_MODE returns ok without hardware)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_mapping(client):
    r = await client.post("/api/control/mapping/start")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_stop(client):
    r = await client.post("/api/control/stop")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_navigate(client):
    r = await client.post("/api/control/navigate", json={"x": 1.5, "y": 2.0, "yaw_deg": 90})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# PIN protection
# ---------------------------------------------------------------------------

@pytest.fixture
def app_with_pin(monkeypatch):
    os.environ["BACKEND_PIN"] = "1234"
    # Re-import to pick up new env var
    import importlib
    import main as m
    importlib.reload(m)
    os.environ["BACKEND_PIN"] = ""
    return m.app


@pytest.mark.asyncio
async def test_pin_required_rejects_without_pin():
    os.environ["BACKEND_PIN"] = "secret99"
    import importlib, main as m
    importlib.reload(m)
    async with AsyncClient(transport=ASGITransport(app=m.app), base_url="http://test") as c:
        r = await c.post("/api/control/stop")
        assert r.status_code == 401
    os.environ["BACKEND_PIN"] = ""
    importlib.reload(m)


@pytest.mark.asyncio
async def test_pin_accepted_with_correct_header():
    os.environ["BACKEND_PIN"] = "secret99"
    import importlib, main as m
    importlib.reload(m)
    async with AsyncClient(transport=ASGITransport(app=m.app), base_url="http://test") as c:
        r = await c.post("/api/control/stop", headers={"X-Pin": "secret99"})
        assert r.status_code == 200
    os.environ["BACKEND_PIN"] = ""
    importlib.reload(m)


# ---------------------------------------------------------------------------
# Chat – no internet needed because we check error handling before API call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_without_key_returns_400(client):
    r = await client.post("/api/chat", json={"message": "Hallo!"})
    assert r.status_code == 400
    assert "Key" in r.json()["detail"] or "key" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Settings – key stored in memory, never echoed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_openai_key_returns_ok(client):
    r = await client.post("/api/settings/openai-key", json={"key": "sk-test-1234"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_openai_key_not_in_health_response(client):
    await client.post("/api/settings/openai-key", json={"key": "sk-very-secret"})
    r = await client.get("/api/health")
    assert "sk-very-secret" not in r.text
    assert "key" not in r.json()
