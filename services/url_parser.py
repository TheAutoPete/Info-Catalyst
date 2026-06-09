from urllib.parse import parse_qs, urlparse


class YouTubeUrlError(ValueError):
    pass


def extract_video_id(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().removeprefix("www.")

    if host in {"youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_ids = parse_qs(parsed.query).get("v", [])
            if video_ids and _is_valid_video_id(video_ids[0]):
                return video_ids[0]
        if parsed.path.startswith("/shorts/") or parsed.path.startswith("/embed/"):
            video_id = parsed.path.split("/")[2]
            if _is_valid_video_id(video_id):
                return video_id

    if host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
        if _is_valid_video_id(video_id):
            return video_id

    raise YouTubeUrlError("Enter a valid YouTube video URL.")


def _is_valid_video_id(video_id: str) -> bool:
    return len(video_id) == 11 and all(char.isalnum() or char in {"_", "-"} for char in video_id)

