"""Pick the YouTube trailer to link from the videos TMDb lists for a title."""
import re

YOUTUBE_WATCH_URL = "https://www.youtube.com/watch?v="

# A YouTube video id; anything else is not put into a link.
_YOUTUBE_KEY_PATTERN = re.compile(r'^[A-Za-z0-9_-]{6,20}$')

# A trailer is preferred over a teaser; other video types are never linked.
_TYPE_RANK = {'Trailer': 0, 'Teaser': 1}


def youtube_trailer_url(videos, language='en'):
    """
    Return the YouTube URL of the best trailer among TMDb videos.

    A trailer beats a teaser, then the reader's language beats any other,
    then an official video beats an unofficial one.

    Args:
        videos: The 'results' list of a TMDb '/videos' response.
        language: TMDb language code of the reader ('de', 'pt-BR').

    Returns:
        The YouTube watch URL, or None when no usable trailer is listed.
    """
    wanted = (language or 'en').split('-')[0]
    candidates = [
        video for video in videos or []
        if isinstance(video, dict)
        and video.get('site') == 'YouTube'
        and video.get('type') in _TYPE_RANK
        and _YOUTUBE_KEY_PATTERN.match(str(video.get('key') or ''))
    ]
    if not candidates:
        return None
    best = min(candidates, key=lambda video: (
        _TYPE_RANK[video['type']],
        video.get('iso_639_1') != wanted,
        not video.get('official'),
    ))
    return f"{YOUTUBE_WATCH_URL}{best['key']}"
