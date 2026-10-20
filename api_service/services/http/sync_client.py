"""Buffered HTTP bridge for existing synchronous integration routes."""
import base64
import json

from api_service.services.http.guarded_session import OutboundHTTPError, send_bytes
from api_service.utils.asyncio_loop import run_coroutine_sync


class BufferedResponse:
    def __init__(self, status, body):
        self.status_code, self.content = status, body

    def json(self):
        return json.loads(self.content)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise OutboundHTTPError(f'Upstream HTTP {self.status_code}')


def _request(method, url, **kwargs):
    kwargs.pop('timeout', None)  # The shared transport has a ten-second timeout.
    auth = kwargs.pop('auth', None)
    if auth:
        headers = dict(kwargs.get('headers') or {})
        headers['Authorization'] = 'Basic ' + base64.b64encode(f'{auth[0]}:{auth[1]}'.encode()).decode('ascii')
        kwargs['headers'] = headers
    return BufferedResponse(*run_coroutine_sync(send_bytes(method, url, **kwargs)))


def get(url, **kwargs):
    return _request('GET', url, **kwargs)


def post(url, **kwargs):
    return _request('POST', url, **kwargs)
