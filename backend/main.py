"""
main.py – Go2 Autonomy Dashboard Backend

Environment variables:
  MOCK_MODE          true/false  (default false) – run without ROS2/hardware
  BACKEND_PIN        optional shared PIN for control endpoints (empty = no PIN)
  KEEPOUT_OUTPUT_DIR path where keepout PGM+YAML are written (default /tmp/go2_keepout)
  ZONES_FILE         path to persist zone JSON across restarts (default /tmp/go2_zones.json)
  STATIC_DIR         path to built frontend (default ../frontend/dist)
  HOST               uvicorn bind host (default 0.0.0.0)
  PORT               uvicorn bind port (default 8000)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from keepout import build_keepout_map, Zone
from ros2_bridge import bridge

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("main")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BACKEND_PIN: str = os.environ.get("BACKEND_PIN", "")
KEEPOUT_DIR = Path(os.environ.get("KEEPOUT_OUTPUT_DIR", "/tmp/go2_keepout"))
ZONES_FILE = Path(os.environ.get("ZONES_FILE", "/tmp/go2_zones.json"))
STATIC_DIR = Path(os.environ.get("STATIC_DIR", str(Path(__file__).parent.parent / "frontend" / "dist")))
MOCK_MODE: bool = os.environ.get("MOCK_MODE", "false").lower() in ("1", "true", "yes")

# OpenAI key – lives ONLY in memory, never logged, never returned to client
_openai_key_in_memory: str = ""

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Backend starting (MOCK_MODE=%s)", MOCK_MODE)
    KEEPOUT_DIR.mkdir(parents=True, exist_ok=True)
    await bridge.init()
    yield
    await bridge.shutdown()


app = FastAPI(title="Go2 Dashboard", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Local WLAN only; no internet exposure expected
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# PIN guard
# ---------------------------------------------------------------------------

def verify_pin(x_pin: str | None = None) -> None:
    """
    Dependency: checks X-Pin header for control endpoints.
    If BACKEND_PIN is empty, all requests pass through.
    """
    if not BACKEND_PIN:
        return
    if x_pin != BACKEND_PIN:
        logger.warning("Rejected request – wrong or missing PIN")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing PIN",
        )


# FastAPI dependency that reads the X-Pin header
from fastapi import Header

def pin_required(x_pin: str | None = Header(default=None)) -> None:
    verify_pin(x_pin)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ZonesPayload(BaseModel):
    zones: list[Zone]


class NavigatePayload(BaseModel):
    x: float
    y: float
    yaw_deg: float = 0.0


class ChatPayload(BaseModel):
    message: str


class OpenAIKeyPayload(BaseModel):
    key: str


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "mock": MOCK_MODE, "pin_enabled": bool(BACKEND_PIN)}


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

@app.get("/api/map")
async def get_map() -> dict:
    try:
        data = await bridge.get_map()
        logger.info("Map served: %dx%d px, res=%.3f m/px", data.width, data.height, data.resolution)
        return data.to_dict()
    except Exception as exc:
        logger.error("get_map error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))


# ---------------------------------------------------------------------------
# Zones (keepout polygons)
# ---------------------------------------------------------------------------

def _load_zones() -> list[Zone]:
    if ZONES_FILE.exists():
        try:
            return json.loads(ZONES_FILE.read_text())
        except Exception as exc:
            logger.warning("Could not load zones file: %s", exc)
    return []


def _save_zones(zones: list[Zone]) -> None:
    try:
        ZONES_FILE.write_text(json.dumps(zones, indent=2))
    except Exception as exc:
        logger.warning("Could not persist zones to disk: %s", exc)


@app.get("/api/zones")
async def get_zones() -> dict:
    zones = _load_zones()
    return {"zones": zones}


@app.post("/api/zones")
async def save_zones(
    payload: ZonesPayload,
    _: None = Depends(pin_required),
) -> dict:
    zones = payload.zones
    logger.info("Saving %d zone(s): %s", len(zones), [z.get("name") for z in zones])

    # Persist zones to disk so they survive backend restarts
    _save_zones(zones)

    # Build keepout map from current ROS2 map metadata
    try:
        map_data = await bridge.get_map()
        map_meta = {
            "origin_x": map_data.origin_x,
            "origin_y": map_data.origin_y,
            "resolution": map_data.resolution,
            "width": map_data.width,
            "height": map_data.height,
        }
        pgm, yml = build_keepout_map(zones, map_meta, KEEPOUT_DIR)
        logger.info("Keepout map written: %s", yml)

        # Tell Nav2 to reload
        await bridge.reload_keepout_filter(str(yml))
    except NotImplementedError as exc:
        # Expected on real robot until Nav2 integration is wired up
        logger.warning("Keepout filter reload not implemented: %s", exc)
    except Exception as exc:
        logger.error("Keepout map build error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "ok", "count": len(zones)}


# ---------------------------------------------------------------------------
# Control endpoints (all PIN-protected)
# ---------------------------------------------------------------------------

@app.post("/api/control/mapping/start")
async def start_mapping(_: None = Depends(pin_required)) -> dict:
    logger.info("Control: start_mapping")
    try:
        await bridge.start_mapping()
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    return {"status": "ok"}


@app.post("/api/control/mapping/save")
async def save_map(
    map_name: str = "go2_map",
    _: None = Depends(pin_required),
) -> dict:
    logger.info("Control: save_map name=%s", map_name)
    try:
        await bridge.save_map(map_name)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    return {"status": "ok", "map_name": map_name}


@app.post("/api/control/navigate")
async def navigate(
    payload: NavigatePayload,
    _: None = Depends(pin_required),
) -> dict:
    logger.info("Control: navigate_to x=%.2f y=%.2f yaw=%.1f", payload.x, payload.y, payload.yaw_deg)
    try:
        await bridge.navigate_to(payload.x, payload.y, payload.yaw_deg)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    return {"status": "ok"}


@app.post("/api/control/stop")
async def stop_robot(_: None = Depends(pin_required)) -> dict:
    logger.info("Control: STOP")
    try:
        await bridge.stop()
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    return {"status": "ok"}


@app.get("/api/status")
async def get_status() -> dict:
    status_data = await bridge.get_status()
    return status_data.to_dict()


# ---------------------------------------------------------------------------
# Chat (OpenAI)
# ---------------------------------------------------------------------------

@app.post("/api/chat")
async def chat(payload: ChatPayload) -> dict:
    global _openai_key_in_memory
    if not _openai_key_in_memory:
        raise HTTPException(
            status_code=400,
            detail="Kein OpenAI-Key gesetzt. Bitte zuerst den Key in den Einstellungen eingeben.",
        )

    logger.info("Chat request received (message length=%d)", len(payload.message))

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=_openai_key_in_memory)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du bist der Sprachassistent eines Roboterhunds in einer Schule. "
                        "Antworte kurz, freundlich und altersgerecht auf Deutsch. "
                        "Du heißt Robo und bist neugierig und hilfreich."
                    ),
                },
                {"role": "user", "content": payload.message},
            ],
            max_tokens=300,
        )
        answer = response.choices[0].message.content
        logger.info("Chat response: %d chars", len(answer or ""))
        return {"answer": answer}
    except Exception as exc:
        err = str(exc)
        logger.error("Chat error: %s", err)
        # Surface a friendly error so the frontend can show the right message
        if "connection" in err.lower() or "network" in err.lower() or "timeout" in err.lower():
            raise HTTPException(
                status_code=503,
                detail="Keine Internetverbindung für ChatGPT erreichbar. Mapping und Navigation funktionieren weiterhin normal.",
            )
        raise HTTPException(status_code=500, detail=err)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.post("/api/settings/openai-key")
async def set_openai_key(payload: OpenAIKeyPayload) -> dict:
    """
    Store the OpenAI API key ONLY in memory.
    It is never written to disk, never logged, never echoed back.
    """
    global _openai_key_in_memory
    _openai_key_in_memory = payload.key
    # Deliberately log only whether a key is set, not the key itself
    logger.info("OpenAI key %s", "set" if payload.key else "cleared")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# WebSocket: live map stream
# ---------------------------------------------------------------------------

@app.websocket("/ws/map")
async def ws_map(websocket: WebSocket) -> None:
    await websocket.accept()
    client = websocket.client
    logger.info("WS /ws/map connected: %s", client)
    try:
        while True:
            try:
                data = await bridge.get_map()
                await websocket.send_json(data.to_dict())
            except Exception as exc:
                logger.error("WS map error: %s", exc)
                await websocket.send_json({"error": str(exc)})
            await asyncio.sleep(1.0)  # 1 Hz update rate
    except WebSocketDisconnect:
        logger.info("WS /ws/map disconnected: %s", client)


# ---------------------------------------------------------------------------
# WebSocket: live status stream
# ---------------------------------------------------------------------------

@app.websocket("/ws/status")
async def ws_status(websocket: WebSocket) -> None:
    await websocket.accept()
    client = websocket.client
    logger.info("WS /ws/status connected: %s", client)
    try:
        while True:
            try:
                data = await bridge.get_status()
                await websocket.send_json(data.to_dict())
            except Exception as exc:
                logger.error("WS status error: %s", exc)
                await websocket.send_json({"error": str(exc)})
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        logger.info("WS /ws/status disconnected: %s", client)


# ---------------------------------------------------------------------------
# Serve built frontend (must come LAST so API routes take priority)
# ---------------------------------------------------------------------------

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    logger.info("Serving frontend from %s", STATIC_DIR)
else:
    logger.warning(
        "Frontend build not found at %s – run `npm run build` in /frontend first",
        STATIC_DIR,
    )

    @app.get("/")
    async def root() -> dict:
        return {
            "message": "Frontend not built yet. Run: cd frontend && npm install && npm run build"
        }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
        log_level="info",
    )
