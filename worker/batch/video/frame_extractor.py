import cv2
import os

def extract_frames(
    video_path,
    fps=1,
    frames_root="frames"
):
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    out_dir = os.path.join(frames_root, video_name)
    os.makedirs(out_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)

    sec = 0
    idx = 0

    while cap.isOpened():
        cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
        ret, frame = cap.read()
        if not ret:
            break

        out_path = os.path.join(
            out_dir,
            f"frame_{idx:04d}_{sec}s.jpg"
        )
        cv2.imwrite(out_path, frame)

        sec += fps
        idx += 1

    cap.release()
    print(f"[OK] Frame extraction done → {out_dir}")

    return out_dir
