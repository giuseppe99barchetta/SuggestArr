"""Helpers for normalizing TMDB image paths to absolute URLs."""

from typing import Optional

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"


def tmdb_image_url(path: Optional[str], size: str = "w500") -> Optional[str]:
    """Return a full TMDB image URL for a poster/logo/backdrop path fragment.

    Args:
        path: TMDB path (e.g. ``/abc.jpg``) or an already-absolute URL.
        size: TMDB size token (e.g. ``w500``, ``w1280``).

    Returns:
        Absolute URL, or ``None`` when *path* is empty.
    """
    if not path:
        return None

    text = str(path).strip()
    if not text:
        return None
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if not text.startswith("/"):
        text = f"/{text}"
    return f"{TMDB_IMAGE_BASE}/{size}{text}"
