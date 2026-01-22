from app.services.storage_service import generate_upload_sas, generate_download_sas, generate_view_sas, generate_blob_name
# TODO: Add Azure Media Services imports when implementing true streaming
# from azure.mgmt.media import AzureMediaServices
# from azure.mgmt.media.models import Asset, StreamingLocator
from app.repository.video_repository import VideoRepository
from app.services.queue_service import enqueue_job
import os


class VideoService:
    """Service layer for video operations"""

    def __init__(self, video_repository: VideoRepository | None = None):
        self.video_repository = video_repository

    async def generate_upload_url(self, email: str, video_id: str | None = None, filename: str | None = None):
        """Generate SAS upload URL for video file"""
        vid, upload_url, blob_url, expiry = await generate_upload_sas(
            email=email,
            video_id=video_id,
            filename=filename,
        )
        return {
            "video_id": vid,
            "upload_url": upload_url,
            "blob_url": blob_url,
            "expires_at": expiry,
        }

    async def generate_download_url(self, email: str, video_id: str, filename: str | None = None, expires_in_minutes: int | None = None):
        """Generate SAS download URL for video file"""
        download_url, expiry = await generate_download_sas(
            email=email,
            video_id=video_id,
            filename=filename,
            expires_in_minutes=expires_in_minutes,
        )
        return {
            "video_id": video_id,
            "download_url": download_url,
            "expires_at": expiry,
        }

    async def generate_view_url(self, email: str, video_id: str, filename: str | None = None, expires_in_minutes: int | None = None):
        """Generate SAS view URL optimized for video streaming/playback"""
        view_url, expiry = await generate_view_sas(
            email=email,
            video_id=video_id,
            filename=filename,
            expires_in_minutes=expires_in_minutes,
        )

        # Determine content type for proper streaming
        content_type = "video/mp4"  # Default
        if filename:
            if filename.lower().endswith('.webm'):
                content_type = "video/webm"
            elif filename.lower().endswith('.avi'):
                content_type = "video/avi"
            elif filename.lower().endswith('.mov'):
                content_type = "video/quicktime"
            elif filename.lower().endswith('.mkv'):
                content_type = "video/x-matroska"

        return {
            "video_id": video_id,
            "view_url": view_url,
            "content_type": content_type,
            "expires_at": expiry,
        }

    async def handle_upload(self, db, blob_url):
        """Handle video upload completion"""
        # TODO: create job in database and enqueue for processing
        # from app.repositories.video_repo import create_job
        # from app.services.queue_service import enqueue_job
        # job_id = "uuid_here"
        # await create_job(db, job_id, blob_url)
        # await enqueue_job(blob_url, job_id)
        # return job_id
        pass

    async def handle_upload_complete(self, user_id: int, email: str, video_id: str, original_filename: str) -> dict:
        """Handle video upload completion - save to database and prepare for streaming"""
        if not self.video_repository:
            raise RuntimeError("VideoRepository not initialized")

        # 1) Persist video record (status=uploaded)
        video = await self.video_repository.create_video(
            user_id=user_id,
            video_id=video_id,
            original_filename=original_filename,
            status="uploaded",
        )

        # 2) Generate view SAS URL so worker can fetch the video
        view_url, _ = await generate_view_sas(
            email=email,
            video_id=str(video.id),
            filename=original_filename,
            expires_in_minutes=1440,  # 24h for processing
        )

        # 3) TODO: For true streaming, create Media Services Asset and Locator
        # This would generate HLS/DASH streaming URLs instead of download URLs
        # Current implementation uses Blob Storage + SAS (download URLs)

        # 4) Enqueue a message so worker can start processing
        await enqueue_job({
            "video_id": str(video.id),
            "blob_url": view_url,  # SAS URL optimized for streaming
            "original_filename": original_filename,
            "user_id": user_id,
        })

        return {
            "video_id": str(video.id),
            "status": video.status,
            "message": "Video upload completed; queued for analysis",
        }

    async def generate_streaming_url(self, email: str, video_id: str, filename: str | None = None) -> dict:
        """Generate true streaming URL using Media Services (Future implementation)"""
        # TODO: Implement Media Services integration
        # 1. Create Asset from blob
        # 2. Create Streaming Locator
        # 3. Return HLS/DASH URLs

        # For now, fall back to download URL
        streaming_url, expiry = await generate_download_sas(
            email=email,
            video_id=video_id,
            filename=filename,
            expires_in_minutes=60,
        )

        return {
            "video_id": video_id,
            "streaming_url": streaming_url,
            "streaming_type": "download_url",  # Will be "hls"/"dash" with Media Services
            "expires_at": expiry,
        }

