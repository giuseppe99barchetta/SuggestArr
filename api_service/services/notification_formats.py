"""Turn webhook events into chat notifications for Discord, ntfy and Telegram.

All three services accept a JSON POST, so a native notification is just a
different body (and, for ntfy, a different URL) stored on the delivery row.
The webhook worker then sends it with the same retries, allowlist and SSRF
checks as a signed SuggestArr webhook.
"""
import json
from urllib.parse import parse_qs, urlsplit, urlunsplit

WEBHOOK_FORMATS = ('json', 'discord', 'ntfy', 'telegram')

_TITLE_EVENTS = {
    'suggestion.created': 'New suggestion: {title}',
    'suggestion.awaiting_approval': 'Waiting for your approval: {title}',
    'suggestion.approved': 'Approved: {title}',
    'suggestion.rejected': 'Rejected: {title}',
    'request.submitted': 'Requested in Seer: {title}',
    'request.failed': 'Request failed: {title}',
}
_JOB_EVENTS = {
    'job.completed': 'Job finished: {job}',
    'job.skipped': 'Job skipped: {job}',
    'run.failed': 'Job run failed: {job}',
}


def notification_target_error(fmt, url):
    """
    Explain why a URL cannot receive notifications in the given format.

    Args:
        fmt: One of WEBHOOK_FORMATS.
        url: Destination URL entered by the administrator.

    Returns:
        An error message, or None when the URL fits the format.
    """
    parts = urlsplit(url)
    if fmt == 'ntfy' and not parts.path.strip('/'):
        return 'An ntfy URL must include the topic, for example https://ntfy.sh/my-topic.'
    if fmt == 'telegram' and not parse_qs(parts.query).get('chat_id'):
        return 'A Telegram URL must include ?chat_id=, for example https://api.telegram.org/bot<token>/sendMessage?chat_id=123.'
    return None


def describe_event(event, data, title=None, job_name=None):
    """
    Write one human sentence for a webhook event.

    Args:
        event: Event name, such as 'request.submitted'.
        data: The event payload.
        title: Title of the movie or show, when the event is about one.
        job_name: Name of the job, when the event is about one.

    Returns:
        The notification text.
    """
    if event in _TITLE_EVENTS:
        label = title or f"{data.get('media_type', 'title')} {data.get('tmdb_id', '')}".strip()
        return _TITLE_EVENTS[event].format(title=label)
    if event in _JOB_EVENTS:
        text = _JOB_EVENTS[event].format(job=job_name or f"#{data.get('job_id')}")
        return f"{text} ({data['reason']})" if data.get('reason') else text
    return event


def render_notification(fmt, url, text):
    """
    Build the destination URL and JSON body of a native notification.

    Args:
        fmt: 'discord', 'ntfy' or 'telegram'.
        url: Destination URL as configured (validated by notification_target_error).
        text: Notification text from describe_event.

    Returns:
        Tuple (url, body) where body is the JSON string to POST.
    """
    if fmt == 'discord':
        return url, json.dumps({'content': text, 'username': 'SuggestArr'})
    if fmt == 'ntfy':
        # JSON publishing goes to the server root with the topic in the body.
        parts = urlsplit(url)
        base_path, _, topic = parts.path.rstrip('/').rpartition('/')
        base = urlunsplit((parts.scheme, parts.netloc, base_path + '/', '', ''))
        return base, json.dumps({'topic': topic, 'title': 'SuggestArr', 'message': text})
    if fmt == 'telegram':
        chat_id = parse_qs(urlsplit(url).query)['chat_id'][0]
        return url, json.dumps({'chat_id': chat_id, 'text': text})
    raise ValueError(f'Unsupported notification format: {fmt}')
