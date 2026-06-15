"""
WebSocket Progress Manager — Broadcasts live progress updates to connected clients.
"""

import asyncio
import logging
from fastapi import WebSocket
from typing import Dict

logger = logging.getLogger(__name__)


class ProgressManager:
    """Manages WebSocket connections and broadcasts progress per analysis ID."""

    def __init__(self):
        # analysis_id -> list of connected WebSockets
        self._connections: Dict[str, list[WebSocket]] = {}

    async def connect(self, analysis_id: str, websocket: WebSocket):
        """Accept and register a WebSocket connection for an analysis."""
        await websocket.accept()
        if analysis_id not in self._connections:
            self._connections[analysis_id] = []
        self._connections[analysis_id].append(websocket)
        logger.info(f"WebSocket connected for analysis {analysis_id}")

    def disconnect(self, analysis_id: str, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if analysis_id in self._connections:
            self._connections[analysis_id] = [
                ws for ws in self._connections[analysis_id] if ws != websocket
            ]
            if not self._connections[analysis_id]:
                del self._connections[analysis_id]
        logger.info(f"WebSocket disconnected for analysis {analysis_id}")

    async def send_progress(self, analysis_id: str, step: str, status: str = "in_progress", detail: str = ""):
        """
        Broadcast a progress update to all WebSockets listening on an analysis.

        Args:
            analysis_id: The analysis ID
            step: Current step name (e.g., "Scanning EC2 instances")
            status: One of "in_progress", "completed", "error"
            detail: Optional detail message
        """
        message = {
            "analysis_id": analysis_id,
            "step": step,
            "status": status,
            "detail": detail,
        }

        if analysis_id not in self._connections:
            return

        dead_connections = []
        for ws in self._connections.get(analysis_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)

        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(analysis_id, ws)


# Singleton instance
progress_manager = ProgressManager()


# Predefined progress steps for the analysis pipeline
ANALYSIS_STEPS = [
    ("Fetching AWS regions", "Verifying AWS CLI configuration..."),
    ("Scanning EC2 instances", "Looking for over-provisioned instances..."),
    ("Scanning EBS volumes", "Checking for orphaned and oversized volumes..."),
    ("Scanning Elastic IPs", "Finding unused Elastic IP addresses..."),
    ("Scanning Security Groups", "Detecting overly permissive rules..."),
    ("Scanning Load Balancers", "Checking for idle load balancers..."),
    ("Scanning RDS instances", "Looking for oversized databases..."),
    ("Scanning S3 buckets", "Checking lifecycle policies..."),
    ("Scanning EBS snapshots", "Finding old snapshots..."),
    ("Scanning NAT Gateways", "Reviewing NAT Gateway usage..."),
    ("Scanning Lambda functions", "Checking Lambda configurations..."),
    ("Analyzing costs with AI", "Sending data to AI for deep analysis..."),
    ("Storing results", "Saving analysis to database..."),
    ("Analysis complete", "Your cost report is ready!"),
]
