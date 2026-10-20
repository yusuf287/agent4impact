"""Multimodal helper: read an image (thermometer, pill bottle, form, map screenshot) into structured text."""
import mimetypes
import os
from pathlib import Path

from google import genai
from google.genai import types

from ..config import LOCATION, MODEL_NAME, PROJECT_ID


def analyze_image(image_uri: str, instruction: str) -> dict:
    """Extract information from an image file (local path or gs:// URI) according to an instruction.

    Use for photos the user provides: read a thermometer, a medication label, a document, a sign.

    Args:
        image_uri: local file path or gs:// URI of the image.
        instruction: what to extract, ideally naming the fields wanted as JSON keys.

    Returns:
        dict with 'text' (the model's answer) or an error.
    """
    try:
        mime = mimetypes.guess_type(image_uri)[0] or "image/jpeg"
        if image_uri.startswith("gs://"):
            part = types.Part.from_uri(file_uri=image_uri, mime_type=mime)
        else:
            part = types.Part.from_bytes(data=Path(image_uri).read_bytes(), mime_type=mime)
        client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
        resp = client.models.generate_content(model=os.environ.get("VISION_MODEL", MODEL_NAME),
                                              contents=[part, instruction])
        return {"status": "success", "text": resp.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}
