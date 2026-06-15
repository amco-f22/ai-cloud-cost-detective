"""
AI Cloud Cost Detective — FastAPI Backend
Main application entry point with all routes, WebSocket, and startup logic.
"""

import time
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from auth import get_current_user, hash_password, verify_password, create_token
from aws_scanner import get_regions, scan_all_resources, get_caller_identity
from cost_detector import detect_all_cost_flags
from ai_analyzer import analyze_costs
from db import init_db, close_pool, create_user, get_user_by_email, create_analysis, update_analysis, get_user_analyses, get_analysis_by_id
from progress import progress_manager, ANALYSIS_STEPS

# Load environment variables
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─── Lifespan ───

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")
    yield
    close_pool()
    logger.info("Shutdown complete")


# ─── App ───

app = FastAPI(
    title="AI Cloud Cost Detective",
    description="AI-powered AWS cloud cost optimization tool",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Models ───

class SignupRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AnalyzeRequest(BaseModel):
    region: str


# ─── Auth Routes ───

@app.post("/api/auth/signup")
async def signup(req: SignupRequest):
    """Create a new user account."""
    # Validate email format (basic)
    if "@" not in req.email or "." not in req.email:
        raise HTTPException(status_code=400, detail="Invalid email format")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    # Check if user exists
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Create user
    hashed = hash_password(req.password)
    user = create_user(req.email, hashed)
    token = create_token(user["id"], user["email"])

    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"]},
    }


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    """Authenticate and return JWT token."""
    user = get_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(user["id"], user["email"])

    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"]},
    }


# ─── AWS Routes ───

@app.get("/api/regions")
async def list_regions(user: dict = Depends(get_current_user)):
    """Return available AWS regions."""
    try:
        regions = get_regions()
        if not regions:
            raise HTTPException(status_code=500, detail="Could not fetch AWS regions. Ensure AWS CLI is configured.")
        return {"regions": regions}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/verify-aws")
async def verify_aws(user: dict = Depends(get_current_user)):
    """Verify AWS CLI configuration."""
    try:
        identity = get_caller_identity()
        if not identity:
            raise HTTPException(status_code=500, detail="AWS CLI is not configured")
        return {
            "status": "connected",
            "account": identity.get("Account", "unknown"),
            "arn": identity.get("Arn", "unknown"),
        }
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Analysis Routes ───

@app.post("/api/analyze")
async def run_analysis(
    req: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Start a cost analysis for the given AWS region."""
    # Create analysis record
    try:
        analysis_id = create_analysis(user["user_id"], req.region)
    except Exception as e:
        logger.error(f"Failed to create analysis record: {e}")
        raise HTTPException(status_code=500, detail="Failed to start analysis")

    # Run analysis in background
    background_tasks.add_task(_run_analysis_pipeline, analysis_id, req.region, user["user_id"])

    return {
        "analysis_id": analysis_id,
        "status": "started",
        "message": f"Analysis started for region {req.region}",
    }


async def _run_analysis_pipeline(analysis_id: int, region: str, user_id: int):
    """Execute the full analysis pipeline with progress updates."""
    aid = str(analysis_id)
    start_time = time.time()

    try:
        # Step 1: Verify AWS config
        await progress_manager.send_progress(aid, "Fetching AWS regions", "in_progress", "Verifying AWS CLI configuration...")
        await asyncio.sleep(0.5)

        # Step 2-10: Scan resources (runs synchronously via subprocess)
        await progress_manager.send_progress(aid, "Scanning resources", "in_progress", f"Scanning all resources in {region}...")

        # Run scan in thread pool to not block event loop
        loop = asyncio.get_event_loop()
        
        def scan_progress(msg: str):
            # Send live progress updates from the synchronous thread
            asyncio.run_coroutine_threadsafe(
                progress_manager.send_progress(aid, "Scanning resources", "in_progress", msg),
                loop
            )

        scan_data = await loop.run_in_executor(None, scan_all_resources, region, scan_progress)

        await progress_manager.send_progress(
            aid, "Scanning resources", "completed",
            f"Found {scan_data['total_resources']} resources"
        )

        # Step 11: Detect cost flags
        await progress_manager.send_progress(aid, "Detecting cost issues", "in_progress", "Running cost detection rules...")
        cost_flags = await loop.run_in_executor(None, detect_all_cost_flags, scan_data)

        await progress_manager.send_progress(
            aid, "Detecting cost issues", "completed",
            f"Found {len(cost_flags)} potential issues"
        )

        # Step 12: AI Analysis
        await progress_manager.send_progress(aid, "Analyzing costs with AI", "in_progress", "Sending data to AI for deep analysis...")
        analysis_result = await loop.run_in_executor(None, analyze_costs, scan_data, cost_flags)

        await progress_manager.send_progress(aid, "Analyzing costs with AI", "completed", "AI analysis complete")

        # Step 13: Store results
        await progress_manager.send_progress(aid, "Storing results", "in_progress", "Saving analysis to database...")

        end_time = time.time()
        analysis_result["time_taken_seconds"] = round(end_time - start_time)

        update_analysis(
            analysis_id=analysis_id,
            resources_scanned=analysis_result.get("total_resources_scanned", 0),
            issues_found=analysis_result.get("total_issues_found", 0),
            estimated_savings=analysis_result.get("estimated_monthly_savings", ""),
            analysis_result=analysis_result,
            status="completed",
        )

        await progress_manager.send_progress(aid, "Storing results", "completed", "Results saved")

        # Step 14: Done
        await progress_manager.send_progress(aid, "Analysis complete", "completed", "Your cost report is ready!")

    except Exception as e:
        logger.error(f"Analysis pipeline error: {e}")
        try:
            update_analysis(
                analysis_id=analysis_id,
                resources_scanned=0,
                issues_found=0,
                estimated_savings="",
                analysis_result={"error": str(e)},
                status="failed",
            )
        except Exception:
            pass
        await progress_manager.send_progress(aid, "Error", "error", str(e))


# ─── History Routes ───

@app.get("/api/history")
async def get_history(user: dict = Depends(get_current_user)):
    """Return past analyses for the authenticated user."""
    analyses = get_user_analyses(user["user_id"])
    # Convert datetime objects to ISO strings
    for a in analyses:
        if a.get("created_at"):
            a["created_at"] = a["created_at"].isoformat()
    return {"analyses": analyses}


@app.get("/api/analysis/{analysis_id}")
async def get_analysis(analysis_id: int, user: dict = Depends(get_current_user)):
    """Return a specific analysis result."""
    analysis = get_analysis_by_id(analysis_id, user["user_id"])
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.get("created_at"):
        analysis["created_at"] = analysis["created_at"].isoformat()
    return analysis


# ─── WebSocket ───

@app.websocket("/ws/progress/{analysis_id}")
async def websocket_progress(websocket: WebSocket, analysis_id: str):
    """WebSocket endpoint for live analysis progress updates."""
    await progress_manager.connect(analysis_id, websocket)
    try:
        while True:
            # Keep connection alive, client sends ping
            await websocket.receive_text()
    except WebSocketDisconnect:
        progress_manager.disconnect(analysis_id, websocket)


# ─── Health Check ───

@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "AI Cloud Cost Detective"}
