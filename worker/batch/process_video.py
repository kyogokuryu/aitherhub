import os
import argparse
import requests
from dotenv import load_dotenv
from ultralytics import YOLO

from vision_pipeline import caption_keyframes
from db_ops import init_db_sync, close_db_sync

# Load environment variables
load_dotenv()
from video_frames import extract_frames, detect_phases
from phase_pipeline import (
    extract_phase_stats,
    build_phase_units,
    build_phase_descriptions,
)
from audio_pipeline import extract_audio_chunks, transcribe_audio_chunks
from grouping_pipeline import (
    embed_phase_descriptions,
    load_global_groups,
    assign_phases_to_groups,
    save_global_groups,
)
from best_phase_pipeline import (
    load_group_best_phases,
    update_group_best_phases,
    save_group_best_phases,
)
from report_pipeline import (
    build_report_1_timeline,
    build_report_2_phase_insights_raw,
    rewrite_report_2_with_gpt,
    build_report_3_video_insights_raw,
    rewrite_report_3_with_gpt,
    save_reports,
)

VIDEO_PATH = "uploadedvideo/1_HairDryer.mp4"  # fallback for local quick run
FRAMES_ROOT = "frames"

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _download_blob(blob_url: str, dest_path: str):
    with requests.get(blob_url, stream=True) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def _resolve_inputs(args) -> tuple[str, str]:
    # Determine video_path and video_id from CLI args (prefer queue payload), fallback to default
    video_id = args.video_id
    video_path = args.video_path
    blob_url = args.blob_url

    if video_path:
        # If explicit path is provided, derive id from filename if not set
        if not video_id:
            video_id = os.path.splitext(os.path.basename(video_path))[0]
        return video_path, video_id

    # No explicit path: use video_id (+ optional blob_url) to get a local file
    if not video_id:
        # Fallback to default hardcoded path (local quick run)
        local_path = VIDEO_PATH
        return local_path, os.path.splitext(os.path.basename(local_path))[0]

    local_dir = "uploadedvideo"
    _ensure_dir(local_dir)
    local_path = os.path.join(local_dir, f"{video_id}.mp4")

    if os.path.exists(local_path):
        return local_path, video_id

    if blob_url:
        print(f"[DL] Downloading video from blob: {blob_url}")
        _download_blob(blob_url, local_path)
        return local_path, video_id

    # As a last resort, use default path if present
    if os.path.exists(VIDEO_PATH):
        return VIDEO_PATH, os.path.splitext(os.path.basename(VIDEO_PATH))[0]

    raise FileNotFoundError("No video_path found. Provide --video-path or --video-id with --blob-url, or set envs.")


def main():
    parser = argparse.ArgumentParser(description="Process a livestream video")
    parser.add_argument("--video-id", dest="video_id", type=str, help="Video UUID to process")
    parser.add_argument("--video-path", dest="video_path", type=str, help="Local path to video file")
    parser.add_argument("--blob-url", dest="blob_url", type=str, help="Blob URL (with SAS) to download if needed")
    args = parser.parse_args()

    # Initialize database connection
    print("[DB] Initializing database connection...")
    init_db_sync()

    try:
        video_path, video_id = _resolve_inputs(args)

        # =========================
        # STEP 0 – FRAME EXTRACTION
        # =========================
        print("=== STEP 0 – EXTRACT FRAMES ===")
        frame_dir = extract_frames(
            video_path=video_path,
            fps=1,
            frames_root=FRAMES_ROOT,
        )

        # =========================
        # STEP 1 – PHASE DETECTION
        # =========================
        print("=== STEP 1 – PHASE DETECTION ===")
        model = YOLO("yolov8s.pt", verbose=False)

        keyframes, rep_frames, total_frames = detect_phases(
            frame_dir=frame_dir,
            model=model,
        )

        # =========================
        # STEP 2 – PHASE METRICS
        # =========================
        print("=== STEP 2 – PHASE METRICS ===")
        phase_stats = extract_phase_stats(
            keyframes=keyframes,
            total_frames=total_frames,
            frame_dir=frame_dir,
        )

        # =========================
        # STEP 3 – AUDIO → TEXT
        # =========================
        print("=== STEP 3 – AUDIO TO TEXT ===")
        audio_dir = extract_audio_chunks(video_path)
        transcribe_audio_chunks(audio_dir)

        audio_text_dir = os.path.join("audio_text", video_id)

        # =========================
        # STEP 4 – IMAGE CAPTION
        # =========================
        print("=== STEP 4 – IMAGE CAPTION ===")
        keyframe_captions = caption_keyframes(
            frame_dir=frame_dir,
            rep_frames=rep_frames,
        )

        # =========================
        # STEP 5 – BUILD PHASE UNITS
        # =========================
        print("=== STEP 5 – BUILD PHASE UNITS ===")
        phase_units = build_phase_units(
            keyframes=keyframes,
            rep_frames=rep_frames,
            keyframe_captions=keyframe_captions,
            phase_stats=phase_stats,
            total_frames=total_frames,
            frame_dir=frame_dir,
            audio_text_dir=audio_text_dir,
            video_id=video_id,
        )

        # =========================
        # STEP 6 – PHASE DESCRIPTION
        # =========================
        print("=== STEP 6 – PHASE DESCRIPTION ===")
        phase_units = build_phase_descriptions(phase_units)

        # phases were inserted inside build_phase_units using the provided video_id

        # =========================
        # STEP 7 – GLOBAL GROUPING
        # =========================
        print("=== STEP 7 – GLOBAL PHASE GROUPING ===")
        phase_units = embed_phase_descriptions(phase_units)

        groups = load_global_groups()
        phase_units, groups = assign_phases_to_groups(phase_units, groups)
        save_global_groups(groups)

        # =========================
        # STEP 8 – GROUP BEST PHASES
        # =========================
        print("=== STEP 8 – GROUP BEST PHASES ===")
        best_data = load_group_best_phases()
        best_data = update_group_best_phases(
            phase_units=phase_units,
            best_data=best_data,
            video_id=video_id,
        )
        save_group_best_phases(best_data)

        # =========================
        # STEP 9 – BUILD REPORTS
        # =========================
        print("=== STEP 9 – BUILD REPORTS ===")
        r1 = build_report_1_timeline(phase_units)

        r2_raw = build_report_2_phase_insights_raw(phase_units, best_data)
        r2_gpt = rewrite_report_2_with_gpt(r2_raw)

        r3_raw = build_report_3_video_insights_raw(phase_units)
        r3_gpt = rewrite_report_3_with_gpt(r3_raw)

        save_reports(
            video_id,
            r1,
            r2_raw,
            r2_gpt,
            r3_raw,
            r3_gpt,
        )

        print("\n[SUCCESS] Video processing completed successfully")

    except Exception as e:
        print(f"\n[ERROR] Video processing failed: {e}")
        raise
    finally:
        # Cleanup database connection
        print("[DB] Closing database connection...")
        close_db_sync()


if __name__ == "__main__":
    main()
