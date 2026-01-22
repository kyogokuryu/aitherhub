"""Utilities for Azure Blob uploads and SAS generation."""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple

from azure.storage.blob import (
    BlobServiceClient,
    BlobSasPermissions,
    generate_blob_sas,
)

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
CONTAINER_NAME = os.getenv("AZURE_BLOB_CONTAINER", "videos")
SAS_EXP_MINUTES = int(os.getenv("AZURE_BLOB_SAS_EXP_MINUTES", "60"))
SAS_DOWNLOAD_EXP_MINUTES = int(os.getenv("AZURE_BLOB_SAS_DOWNLOAD_MINUTES", "1440"))  # Default 24 hours


def _parse_account_key(conn_str: str) -> str:
    """Extract AccountKey from connection string."""
    if not conn_str:
        raise ValueError("Missing AZURE_STORAGE_CONNECTION_STRING")
    parts = conn_str.split(";")
    for p in parts:
        if p.startswith("AccountKey="):
            return p.split("=", 1)[1]
    raise ValueError("AccountKey not found in connection string")


def _ensure_container(service_client: BlobServiceClient, container: str) -> None:
    container_client = service_client.get_container_client(container)
    try:
        container_client.create_container()
    except Exception:
        # ignore if already exists or cannot create (Azurite already present)
        pass


def generate_blob_name(email: str, video_id: str, filename: str | None = None) -> str:
    """Create a blob name using folder structure: email/video_id/filename"""
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[1]
        blob_filename = f"{video_id}.{ext}"
    else:
        blob_filename = f"{video_id}.mp4"
    return f"{email}/{video_id}/{blob_filename}"


async def generate_upload_sas(email: str, video_id: str | None = None, filename: str | None = None) -> Tuple[str, str, str, datetime]:
    """
    Generate a write-only SAS URL for a single blob with folder structure: email/video_id/filename

    Returns:
        upload_url: full SAS URL for direct upload
        blob_url: public blob URL (without SAS)
        expiry: datetime in UTC
    """
    vid = video_id or str(uuid.uuid4())

    if not CONNECTION_STRING:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is required to generate SAS")

    blob_name = generate_blob_name(email, vid, filename)
    account_key = _parse_account_key(CONNECTION_STRING)
    expiry = datetime.now(timezone.utc) + timedelta(minutes=SAS_EXP_MINUTES)

    # Detect Azurite vs Azure
    is_azurite = "devstoreaccount1" in ACCOUNT_NAME.lower()
    
    # Generate SAS token (works for both Azurite and Azure)
    sas_token = generate_blob_sas(
        account_name=ACCOUNT_NAME,
        container_name=CONTAINER_NAME,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(write=True, create=True),
        expiry=expiry,
    )

    if is_azurite:
        # Azurite: extract BlobEndpoint from connection string
        # For local dev: http://localhost:10000/devstoreaccount1
        # For Docker: http://azurite:10000/devstoreaccount1
        blob_endpoint = "http://localhost:10000/devstoreaccount1"  # Default for local
        for part in CONNECTION_STRING.split(";"):
            if part.startswith("BlobEndpoint="):
                blob_endpoint = part.split("=", 1)[1]
                break
        blob_url = f"{blob_endpoint}/{CONTAINER_NAME}/{blob_name}"
    else:
        # Production Azure: use HTTPS
        blob_url = f"https://{ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}"
    
    upload_url = f"{blob_url}?{sas_token}"
    print(f"[storage_service] upload_url: {upload_url}")
    return vid, upload_url, blob_url, expiry


async def generate_download_sas(email: str, video_id: str, filename: str | None = None, expires_in_minutes: int | None = None) -> Tuple[str, datetime]:
    """
    Generate a read-only SAS URL for downloading a blob with folder structure: email/video_id/filename

    Args:
        email: User email for folder path
        video_id: Video ID for folder path
        filename: Optional filename (to determine extension)
        expires_in_minutes: Optional custom expiry in minutes (defaults to SAS_DOWNLOAD_EXP_MINUTES)

    Returns:
        download_url: full SAS URL for direct download
        expiry: datetime in UTC
    """
    if not CONNECTION_STRING:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is required to generate SAS")

    blob_name = generate_blob_name(email, video_id, filename)
    account_key = _parse_account_key(CONNECTION_STRING)
    
    ttl_minutes = expires_in_minutes if expires_in_minutes is not None else SAS_DOWNLOAD_EXP_MINUTES
    expiry = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

    # Detect Azurite vs Azure
    is_azurite = "devstoreaccount1" in ACCOUNT_NAME.lower()
    
    # Generate SAS token with read permission + additional permissions for streaming
    permissions = BlobSasPermissions(read=True)
    # Note: Azure Blob Storage automatically supports range requests with read permission
    # No additional permissions needed for basic streaming

    sas_token = generate_blob_sas(
        account_name=ACCOUNT_NAME,
        container_name=CONTAINER_NAME,
        blob_name=blob_name,
        account_key=account_key,
        permission=permissions,
        expiry=expiry,
    )

    if is_azurite:
        blob_endpoint = "http://localhost:10000/devstoreaccount1"
        for part in CONNECTION_STRING.split(";"):
            if part.startswith("BlobEndpoint="):
                blob_endpoint = part.split("=", 1)[1]
                break
        blob_url = f"{blob_endpoint}/{CONTAINER_NAME}/{blob_name}"
    else:
        blob_url = f"https://{ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}"
    
    download_url = f"{blob_url}?{sas_token}"
    print(f"[storage_service] download_url: {download_url} (expires in {ttl_minutes} min)")
    return download_url, expiry


async def generate_view_sas(email: str, video_id: str, filename: str | None = None, expires_in_minutes: int | None = None) -> Tuple[str, datetime]:
    """
    Generate a view/streaming SAS URL optimized for video playback with folder structure: email/video_id/filename

    Args:
        email: User email for folder path
        video_id: Video ID for folder path
        filename: Optional filename (to determine extension)
        expires_in_minutes: Optional custom expiry in minutes (defaults to SAS_DOWNLOAD_EXP_MINUTES)

    Returns:
        view_url: full SAS URL optimized for streaming/viewing
        expiry: datetime in UTC
    """
    if not CONNECTION_STRING:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is required to generate SAS")

    blob_name = generate_blob_name(email, video_id, filename)
    account_key = _parse_account_key(CONNECTION_STRING)

    ttl_minutes = expires_in_minutes if expires_in_minutes is not None else SAS_DOWNLOAD_EXP_MINUTES
    expiry = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

    # Detect Azurite vs Azure
    is_azurite = "devstoreaccount1" in ACCOUNT_NAME.lower()

    # For view/streaming, use enhanced permissions for better streaming support
    permissions = BlobSasPermissions(
        read=True,
        list=True,  # Allow listing blobs for better streaming discovery
        # Note: create/write permissions not needed for viewing
    )

    # Generate SAS token for view/streaming
    sas_token = generate_blob_sas(
        account_name=ACCOUNT_NAME,
        container_name=CONTAINER_NAME,
        blob_name=blob_name,
        account_key=account_key,
        permission=permissions,
        expiry=expiry,
    )

    if is_azurite:
        # Azurite: extract BlobEndpoint from connection string
        blob_endpoint = "http://localhost:10000/devstoreaccount1"  # Default for local
        for part in CONNECTION_STRING.split(";"):
            if part.startswith("BlobEndpoint="):
                blob_endpoint = part.split("=", 1)[1]
                break
        blob_url = f"{blob_endpoint}/{CONTAINER_NAME}/{blob_name}"
    else:
        # Production Azure: use CDN if available, fallback to direct blob URL
        cdn_endpoint = os.getenv("AZURE_CDN_ENDPOINT")
        if cdn_endpoint:
            # Use CDN URL: https://your-cdn-endpoint.azureedge.net/container/blob
            blob_url = f"https://{cdn_endpoint}.azureedge.net/{CONTAINER_NAME}/{blob_name}"
        else:
            # Fallback to direct blob URL
            blob_url = f"https://{ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}"

    view_url = f"{blob_url}?{sas_token}"
    print(f"[storage_service] view_url: {view_url} (expires in {ttl_minutes} min)")
    return view_url, expiry

