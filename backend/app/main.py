# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
import os
import logging

# --------------------------------------------------
# Logging Configuration
# --------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --------------------------------------------------
# Import Routers
# --------------------------------------------------
from .api import (
    upload,
    transcription,
    summarization,
    video_processing,
    download,
    share,
    video_info,
)

# --------------------------------------------------
# Initialize FastAPI App
# --------------------------------------------------
app = FastAPI(
    title="AI-Powered Video Shortener API",
    description="API for uploading, transcribing, summarizing, and shortening videos.",
    version="1.0.0",
)

# --------------------------------------------------
# CORS Configuration
# --------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# Health Endpoints
# --------------------------------------------------
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/api/health")
async def api_health_check():
    return {"status": "healthy"}

# --------------------------------------------------
# Include API Routers
# IMPORTANT: Routers must NOT contain prefix="/api"
# --------------------------------------------------
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(transcription.router, prefix="/api", tags=["Transcription"])
app.include_router(summarization.router, prefix="/api", tags=["Summarization"])
app.include_router(video_processing.router, prefix="/api", tags=["Video Processing"])
app.include_router(download.router, prefix="/api", tags=["Download"])
app.include_router(share.router, prefix="/api", tags=["Share"])
app.include_router(video_info.router, prefix="/api", tags=["Video Info"])

# --------------------------------------------------
# Static Files (Uploads, Outputs, Captions)
# --------------------------------------------------
static_dir = os.path.join(os.path.dirname(__file__), "static")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"Static files mounted from: {static_dir}")
else:
    logger.warning("Static directory not found.")

# --------------------------------------------------
# Serve React Frontend (Production Build)
# --------------------------------------------------
frontend_dist_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
)

logger.info(f"Frontend dist path: {frontend_dist_path}")
logger.info(f"Frontend exists: {os.path.exists(frontend_dist_path)}")

if os.path.exists(frontend_dist_path):

    logger.info(f"Serving React frontend from: {frontend_dist_path}")

    # Serve static assets
    assets_path = os.path.join(frontend_dist_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
        logger.info(f"Assets mounted from: {assets_path}")

    # SPA fallback (IMPORTANT FIX)
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        """
        Serve React app for all non-API routes.
        Prevent API route override.
        """

        # 🔥 Prevent API routes from being intercepted
        if full_path.startswith("api"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        index_file = os.path.join(frontend_dist_path, "index.html")

        if os.path.exists(index_file):
            return FileResponse(
                index_file,
                media_type="text/html",
                headers={"Cache-Control": "no-cache"}
            )

        return JSONResponse(
            status_code=404,
            content={"detail": "Frontend not built."}
        )

else:
    logger.warning("Frontend build not found.")

    @app.get("/")
    async def root():
        return {
            "message": "AI Video Shortener API",
            "docs": "/docs",
            "health": "/health",
            "note": "Frontend not built. Run 'npm run build' in frontend directory."
        }

# --------------------------------------------------
# Global Exception Handlers
# --------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler to catch all unhandled exceptions.
    This prevents the server from crashing silently and provides better error logging.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred on the server. Please try again.",
            "error_type": type(exc).__name__,
            "message": str(exc)
        }
    )

# --------------------------------------------------
# Run Directly
# --------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        timeout_keep_alive=300,  # 5 minutes timeout for keep-alive connections
    )