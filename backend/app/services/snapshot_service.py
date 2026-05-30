import base64
import hashlib
from io import BytesIO

from PIL import Image

from app.core.config import get_settings


def normalize_snapshot(snapshot_jpeg_base64: str | None) -> tuple[bytes | None, str | None]:
    if not snapshot_jpeg_base64:
        return None, None

    settings = get_settings()
    raw = base64.b64decode(snapshot_jpeg_base64)
    image = Image.open(BytesIO(raw)).convert("RGB")

    if image.width > settings.snapshot_max_width:
        ratio = settings.snapshot_max_width / image.width
        image = image.resize((settings.snapshot_max_width, int(image.height * ratio)))

    output = BytesIO()
    image.save(output, format="JPEG", quality=settings.snapshot_jpeg_quality, optimize=True)
    blob = output.getvalue()
    return blob, hashlib.sha256(blob).hexdigest()
