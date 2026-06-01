from urllib.parse import quote


def processed_rtsp_url(base_url: str, stream_path: str) -> str:
    return f"{base_url.rstrip('/')}/{quote(stream_path)}"
