"""
ros2_bridge.py – Thin abstraction over ROS2.

In MOCK_MODE (env MOCK_MODE=true) every call returns plausible fake data so
the full stack can be tested without hardware.

HARDWARE NOTE: Every method tagged with  # [HARDWARE]  only executes on a real
robot with ROS2 sourced.  The rclpy import is deferred so the backend can start
on machines without ROS2 installed.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import math
import os
import time
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

logger = logging.getLogger("ros2_bridge")

MOCK_MODE: bool = os.environ.get("MOCK_MODE", "false").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Public data classes (no pydantic dependency here)
# ---------------------------------------------------------------------------

class MapData:
    def __init__(
        self,
        png_b64: str,
        width: int,
        height: int,
        resolution: float,
        origin_x: float,
        origin_y: float,
        stamp: float,
    ):
        self.png_b64 = png_b64
        self.width = width
        self.height = height
        self.resolution = resolution
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.stamp = stamp

    def to_dict(self) -> dict:
        return {
            "png_b64": self.png_b64,
            "width": self.width,
            "height": self.height,
            "resolution": self.resolution,
            "origin_x": self.origin_x,
            "origin_y": self.origin_y,
            "stamp": self.stamp,
        }


class RobotStatus:
    def __init__(
        self,
        mode: str,
        battery_percent: float | None,
        position_x: float,
        position_y: float,
        yaw_deg: float,
        stamp: float,
    ):
        self.mode = mode
        self.battery_percent = battery_percent
        self.position_x = position_x
        self.position_y = position_y
        self.yaw_deg = yaw_deg
        self.stamp = stamp

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "battery_percent": self.battery_percent,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "yaw_deg": self.yaw_deg,
            "stamp": self.stamp,
        }


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_map(t: float | None = None) -> MapData:
    """Generate a simple synthetic map with a moving robot marker."""
    t = t or time.time()
    W, H = 200, 200
    resolution = 0.05  # 5 cm/px → 10 m × 10 m room

    # Grey background (unknown space)
    arr = np.full((H, W), 128, dtype=np.uint8)
    # Free area
    arr[20:180, 20:180] = 254
    # Some walls
    arr[20:180, 20] = 0
    arr[20:180, 179] = 0
    arr[20, 20:180] = 0
    arr[179, 20:180] = 0
    # Inner obstacle
    arr[80:100, 80:120] = 0

    img = Image.fromarray(arr, mode="L").convert("RGB")
    draw = ImageDraw.Draw(img)

    # Animate robot dot
    rx = int(30 + 60 * (0.5 + 0.5 * math.sin(t * 0.3)))
    ry = int(30 + 60 * (0.5 + 0.5 * math.cos(t * 0.2)))
    draw.ellipse([rx - 4, ry - 4, rx + 4, ry + 4], fill=(255, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    return MapData(
        png_b64=b64,
        width=W,
        height=H,
        resolution=resolution,
        origin_x=-5.0,
        origin_y=-5.0,
        stamp=t,
    )


def _mock_status(t: float | None = None) -> RobotStatus:
    t = t or time.time()
    return RobotStatus(
        mode="idle",
        battery_percent=78.0,
        position_x=0.5 * math.sin(t * 0.3),
        position_y=0.5 * math.cos(t * 0.2),
        yaw_deg=(t * 20) % 360,
        stamp=t,
    )


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------

class ROS2Bridge:
    """
    Single instance shared across the FastAPI app lifetime.
    Call `await bridge.init()` once at startup.
    """

    def __init__(self) -> None:
        self._node: Any = None
        self._mock = MOCK_MODE
        self._map_cache: MapData | None = None
        self._status_cache: RobotStatus | None = None
        self._nav_status: str = "idle"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def init(self) -> None:
        if self._mock:
            logger.info("ROS2Bridge: running in MOCK MODE – no real ROS2 needed")
            return
        # [HARDWARE] Real ROS2 init
        try:
            import rclpy
            from rclpy.node import Node

            rclpy.init()
            self._node = Node("go2_dashboard_backend")
            # Subscriptions are set up in _spin which runs in a background thread
            asyncio.get_event_loop().run_in_executor(None, self._spin)
            logger.info("ROS2Bridge: rclpy initialised, node started")
        except ImportError:
            logger.error(
                "rclpy not available – set MOCK_MODE=true to run without ROS2"
            )
            raise

    async def shutdown(self) -> None:
        if self._node is not None:
            # [HARDWARE]
            try:
                import rclpy
                self._node.destroy_node()
                rclpy.shutdown()
            except Exception as exc:
                logger.warning("ROS2 shutdown error: %s", exc)

    def _spin(self) -> None:
        """Runs rclpy.spin in a background thread. [HARDWARE]"""
        import rclpy
        try:
            rclpy.spin(self._node)
        except Exception as exc:
            logger.error("ROS2 spin error: %s", exc)

    # ------------------------------------------------------------------
    # Map
    # ------------------------------------------------------------------

    async def get_map(self) -> MapData:
        if self._mock:
            return _mock_map()

        # [HARDWARE] Subscribe to /map (nav_msgs/OccupancyGrid) and return latest
        if self._map_cache is None:
            raise RuntimeError("No map received yet from /map topic")
        return self._map_cache

    def _on_map_msg(self, msg: Any) -> None:
        """ROS2 /map callback. [HARDWARE]"""
        try:
            import numpy as np
            from PIL import Image
            import io, base64, time

            info = msg.info
            data = np.array(msg.data, dtype=np.int8).reshape(info.height, info.width)
            # OccupancyGrid: -1=unknown(128), 0=free(254), 100=occupied(0)
            img_arr = np.where(data == -1, 128, np.where(data == 0, 254, 0)).astype(np.uint8)
            img = Image.fromarray(img_arr, mode="L").convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            self._map_cache = MapData(
                png_b64=b64,
                width=info.width,
                height=info.height,
                resolution=info.resolution,
                origin_x=info.origin.position.x,
                origin_y=info.origin.position.y,
                stamp=time.time(),
            )
        except Exception as exc:
            logger.error("Map callback error: %s", exc)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def get_status(self) -> RobotStatus:
        if self._mock:
            return _mock_status()
        if self._status_cache is None:
            return RobotStatus(
                mode="unknown", battery_percent=None,
                position_x=0, position_y=0, yaw_deg=0,
                stamp=time.time(),
            )
        return self._status_cache

    # ------------------------------------------------------------------
    # Control commands
    # ------------------------------------------------------------------

    async def start_mapping(self) -> None:
        logger.info("Command: start_mapping")
        if self._mock:
            self._nav_status = "mapping"
            return
        # [HARDWARE] Launch slam_toolbox via lifecycle or service call
        # Example: call /slam_toolbox/start_slam_toolbox_pose service
        raise NotImplementedError(
            "start_mapping requires real robot – see slam_toolbox launch file"
        )

    async def save_map(self, map_name: str = "go2_map") -> None:
        logger.info("Command: save_map name=%s", map_name)
        if self._mock:
            self._nav_status = "idle"
            return
        # [HARDWARE] Call /map_saver/save_map service (nav2_map_server)
        raise NotImplementedError("save_map requires real robot")

    async def navigate_to(self, x: float, y: float, yaw_deg: float = 0.0) -> None:
        logger.info("Command: navigate_to x=%.2f y=%.2f yaw=%.1f", x, y, yaw_deg)
        if self._mock:
            self._nav_status = "navigating"
            return
        # [HARDWARE] Send NavigateToPose action goal to Nav2
        # Convert yaw_deg → quaternion, publish to /navigate_to_pose action server
        raise NotImplementedError("navigate_to requires real robot and Nav2")

    async def stop(self) -> None:
        logger.info("Command: stop")
        if self._mock:
            self._nav_status = "idle"
            return
        # [HARDWARE] Cancel Nav2 action + publish zero cmd_vel
        # 1. Cancel /navigate_to_pose action
        # 2. Publish geometry_msgs/Twist(0,0,0) to /cmd_vel
        raise NotImplementedError("stop requires real robot")

    async def reload_keepout_filter(self, yaml_path: str) -> None:
        """
        Tell Nav2's costmap_filter_info_server to reload the keepout map.
        [HARDWARE] Requires lifecycle service calls on the running Nav2 stack.
        """
        logger.info("Command: reload_keepout_filter path=%s", yaml_path)
        if self._mock:
            logger.info("MOCK: keepout filter reload skipped")
            return
        # [HARDWARE]
        # Steps:
        # 1. Deactivate costmap_filter_info_server lifecycle node
        # 2. Update the params file / remap to new yaml_path
        # 3. Activate lifecycle node again
        # This is Nav2-version-dependent; see Nav2 keepout filter docs.
        raise NotImplementedError("reload_keepout_filter requires real Nav2")

    def get_nav_status(self) -> str:
        return self._nav_status


# Singleton
bridge = ROS2Bridge()
