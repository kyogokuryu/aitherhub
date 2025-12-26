from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.storage_service import generate_upload_sas

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (can be restricted to specific domains)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateUploadURLRequest(BaseModel):
    filename: str | None = None
    video_id: str | None = None


# ============= SAS UPLOAD (Azure SDK client-side) =============

@app.post("/videos/generate-upload-url")
async def generate_upload_url(payload: GenerateUploadURLRequest):
    """Generate a short-lived SAS upload URL for direct blob upload.
    
    Client uses Azure SDK (JavaScript/Python/etc) to upload file directly to Azure Blob Storage.
    
    Example flow:
    1. POST /videos/generate-upload-url → get {video_id, upload_url, expires_at}
    2. Client: Use Azure SDK to upload file to upload_url (direct to Azure, not backend)
    3. Client: POST /videos/{video_id}/complete → backend creates Video/Job records
    """
    try:
        vid, upload_url, blob_url, expiry = await generate_upload_sas(
            video_id=payload.video_id,
            filename=payload.filename,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {exc}")

    return {
        "video_id": vid,
        "upload_url": upload_url,
        "expires_at": expiry.isoformat(),
    }


