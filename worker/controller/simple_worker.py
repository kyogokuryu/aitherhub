#!/usr/bin/env python3
"""Simple queue worker that polls Azure Queue and runs batch processing.
Supports concurrent processing of multiple jobs using ThreadPoolExecutor."""
import os
import sys
import json
import time
import subprocess
import fcntl
import signal
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, Future
from threading import Lock
from azure.storage.queue import QueueClient
from dotenv import load_dotenv

# Load .env from project root
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

# Add batch directory to path so we can import if needed
BATCH_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "batch"))
sys.path.insert(0, BATCH_DIR)

# Maximum concurrent jobs
MAX_WORKERS = int(os.getenv("WORKER_MAX_CONCURRENT", "3"))

# Visibility timeout: 4 hours (video analysis can take 1-3 hours)
VISIBILITY_TIMEOUT = 4 * 60 * 60  # 14400 seconds

# Track active jobs
active_jobs: dict[str, Future] = {}
active_jobs_lock = Lock()

# Graceful shutdown flag
shutdown_requested = False


def signal_handler(signum, frame):
    global shutdown_requested
    print(f"\n[worker] Received signal {signum}, shutting down gracefully...")
    shutdown_requested = True


def get_queue_client():
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    queue_name = os.getenv("AZURE_QUEUE_NAME", "video-jobs")
    if not conn_str:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING required")
    return QueueClient.from_connection_string(conn_str, queue_name)


def process_job(payload: dict):
    """Process a single job. Runs in a thread."""
    job_type = payload.get("job_type", "video_analysis")
    job_id = payload.get("video_id", payload.get("clip_id", "unknown"))

    try:
        if job_type == "generate_clip":
            return process_clip_job(payload)
        else:
            return process_video_job(payload)
    except Exception as e:
        print(f"[worker] Error processing job {job_id}: {e}")
        return False
    finally:
        with active_jobs_lock:
            active_jobs.pop(job_id, None)


def process_clip_job(payload: dict):
    """Handle clip generation job."""
    clip_id = payload.get("clip_id")
    video_id = payload.get("video_id")
    blob_url = payload.get("blob_url")
    time_start = payload.get("time_start")
    time_end = payload.get("time_end")

    if not all([clip_id, video_id, blob_url, time_start is not None, time_end is not None]):
        print("[worker] Invalid clip payload, skipping")
        return False

    phase_index = payload.get("phase_index", -1)
    speed_factor = payload.get("speed_factor", 1.0)

    print(f"[worker] Starting clip generation for clip_id={clip_id} (speed={speed_factor}x)")
    cmd = [
        sys.executable,
        os.path.join(BATCH_DIR, "generate_clip.py"),
        "--clip-id", clip_id,
        "--video-id", video_id,
        "--blob-url", blob_url,
        "--time-start", str(time_start),
        "--time-end", str(time_end),
        "--phase-index", str(phase_index),
        "--speed-factor", str(speed_factor),
    ]

    result = subprocess.run(
        cmd,
        cwd=BATCH_DIR,
        env={**os.environ, "PYTHONPATH": BATCH_DIR},
    )

    if result.returncode == 0:
        print(f"[worker] Clip generation completed for {clip_id}")
        return True
    else:
        print(f"[worker] Clip generation failed for {clip_id} with exit code {result.returncode}")
        return False


def process_video_job(payload: dict):
    """Handle video analysis job."""
    video_id = payload.get("video_id")
    blob_url = payload.get("blob_url")

    if not video_id or not blob_url:
        print("[worker] Invalid payload, skipping")
        return False

    print(f"[worker] Starting batch for video_id={video_id}")
    cmd = [
        sys.executable,
        os.path.join(BATCH_DIR, "process_video.py"),
        "--video-id", video_id,
        "--blob-url", blob_url,
    ]

    result = subprocess.run(
        cmd,
        cwd=BATCH_DIR,
        env={**os.environ, "PYTHONPATH": BATCH_DIR},
    )

    if result.returncode == 0:
        print(f"[worker] Batch completed successfully for {video_id}")
        return True
    else:
        print(f"[worker] Batch failed for {video_id} with exit code {result.returncode}")
        return False


def get_active_count():
    """Get the number of currently active jobs."""
    with active_jobs_lock:
        # Clean up completed futures
        completed = [k for k, v in active_jobs.items() if v.done()]
        for k in completed:
            active_jobs.pop(k, None)
        return len(active_jobs)


def poll_and_process(executor: ThreadPoolExecutor):
    """Poll queue and submit jobs to the thread pool."""
    active_count = get_active_count()

    if active_count >= MAX_WORKERS:
        return  # All worker slots are busy

    # How many slots are available
    available_slots = MAX_WORKERS - active_count

    client = get_queue_client()

    # Receive up to available_slots messages
    messages = client.receive_messages(
        messages_per_page=min(available_slots, 5),
        visibility_timeout=VISIBILITY_TIMEOUT,
    )

    for msg in messages:
        try:
            payload = json.loads(msg.content)
            job_type = payload.get("job_type", "video_analysis")
            job_id = payload.get("video_id", payload.get("clip_id", "unknown"))

            # Check if this job is already being processed
            with active_jobs_lock:
                if job_id in active_jobs and not active_jobs[job_id].done():
                    print(f"[worker] Job {job_id} already in progress, skipping duplicate")
                    continue

            print(f"[worker] Received job: type={job_type}, id={job_id} (active: {get_active_count()}/{MAX_WORKERS})")

            # Delete message from queue before processing
            client.delete_message(msg.id, msg.pop_receipt)

            # Submit job to thread pool
            future = executor.submit(process_job, payload)
            with active_jobs_lock:
                active_jobs[job_id] = future

        except Exception as e:
            print(f"[worker] Error parsing message: {e}")
            # Don't delete on parse error; message will reappear after visibility timeout


def acquire_lock():
    """Acquire a file lock to prevent multiple worker instances."""
    lock_file = Path("/tmp/simple_worker.lock")
    fp = open(lock_file, "w")
    try:
        fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fp.write(str(os.getpid()))
        fp.flush()
        return fp
    except IOError:
        print("[worker] Another worker instance is already running. Exiting.")
        sys.exit(1)


def main():
    # Acquire lock to prevent duplicate instances
    lock_fp = acquire_lock()

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    print(f"[worker] Starting simple queue worker (max_concurrent={MAX_WORKERS})...")
    print(f"[worker] Queue: {os.getenv('AZURE_QUEUE_NAME', 'video-jobs')}")
    print(f"[worker] Visibility timeout: {VISIBILITY_TIMEOUT}s ({VISIBILITY_TIMEOUT // 3600}h)")

    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    try:
        while not shutdown_requested:
            try:
                poll_and_process(executor)
                time.sleep(5)  # Poll every 5 seconds
            except Exception as e:
                print(f"[worker] Unexpected error: {e}")
                time.sleep(10)
    finally:
        print(f"[worker] Waiting for {get_active_count()} active jobs to complete...")
        executor.shutdown(wait=True)
        lock_fp.close()
        print("[worker] Worker shut down.")


if __name__ == "__main__":
    main()
