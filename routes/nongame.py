from fastapi import APIRouter
from fastapi.responses import FileResponse
import os

router = APIRouter()


@router.get("/")
async def serve_index():
    """Serve the index.html landing page for mrieg.com visitors"""
    index_path = os.path.join("static", "index.html")
    return FileResponse(index_path, media_type="text/html")
