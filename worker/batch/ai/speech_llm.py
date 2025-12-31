from openai import OpenAI

client = OpenAI()


def transcribe_audio(audio_path: str):
    """
    Audio -> text with timestamp (GPT-4o)
    """
    with open(audio_path, "rb") as f:
        return client.audio.transcriptions.create(
            file=f,
            model="gpt-4o-transcribe",
            response_format="verbose_json"
        )
