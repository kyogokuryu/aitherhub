from openai import OpenAI
import base64
import cv2

client = OpenAI()


def caption_keyframe(frame):
    """
    Key frame -> visual description
    """
    _, buf = cv2.imencode(".jpg", frame)
    img_b64 = base64.b64encode(buf).decode()

    resp = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Describe what is happening in this livestream frame."},
                    {"type": "input_image", "image_base64": img_b64}
                ]
            }
        ]
    )

    return resp.output_text
