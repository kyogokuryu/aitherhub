import subprocess
import tempfile
from openai import OpenAI

client = OpenAI()


def extract_audio(video_path: str) -> str:
    """
    Extract WAV audio from video using ffmpeg
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-ar", "16000",
            "-ac", "1",
            tmp.name
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return tmp.name


def speech_to_text(audio_path: str, start_sec: float, end_sec: float) -> str:
    """
    PoC:
    - Send full audio to GPT-4o
    - Filter transcript by timestamp
    """

    with open(audio_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            file=f,
            model="gpt-4o-transcribe",
            response_format="verbose_json"  # cần timestamp
        )

    texts = []
    for seg in transcript["segments"]:
        if start_sec <= seg["start"] <= end_sec:
            texts.append(seg["text"])

    return " ".join(texts)
