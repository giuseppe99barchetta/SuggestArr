"""Exercise response callbacks that start the next request on a connection."""

import asyncio
import contextvars
from unittest.mock import Mock

import pytest
from flask import Flask, Response, request, stream_with_context
from uvicorn import Config
from uvicorn.protocols.http.h11_impl import H11Protocol
from uvicorn.server import ServerState

from api_service.asgi import ContextSafeWsgiToAsgi


@pytest.mark.asyncio
@pytest.mark.parametrize('async_view', [False, True])
@pytest.mark.parametrize('streamed', [False, True])
async def test_pipelined_requests_do_not_inherit_finished_executor(async_view, streamed):
    app = Flask(__name__)
    app.config['TESTING'] = True
    callback_context = contextvars.ContextVar('callback_context', default=None)

    def render_index():
        callback_context.set('application')
        if streamed:
            @stream_with_context
            def body():
                yield 'ok'
                yield request.path
            return Response(body())
        return 'ok'

    async def async_index():
        await asyncio.sleep(0)
        return render_index()

    def sync_index():
        return render_index()

    app.add_url_rule('/', view_func=async_index if async_view else sync_index)
    config = Config(ContextSafeWsgiToAsgi(app), access_log=False, lifespan='off')
    state = ServerState()
    protocol = H11Protocol(config, state, {})
    output = []
    send_contexts = []

    def write(data):
        output.append(data)
        send_contexts.append(callback_context.get())

    transport = Mock(spec=asyncio.Transport)
    transport.get_extra_info.side_effect = lambda name: {
        'sockname': ('127.0.0.1', 5000),
        'peername': ('127.0.0.1', 12345),
    }.get(name)
    transport.is_closing.return_value = False
    transport.write.side_effect = write
    protocol.connection_made(transport)

    context_token = callback_context.set('server')
    try:
        # Uvicorn starts each queued request from the previous response's send
        # callback, which must not expose AsyncToSync's temporary executor.
        protocol.data_received(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n' * 3)
        async with asyncio.timeout(5):
            while state.tasks:
                await asyncio.gather(*state.tasks)
                await asyncio.sleep(0)
        response = b''.join(output)
        assert response.count(b'HTTP/1.1 200 OK') == 3
        assert b'500 Internal Server Error' not in response
        assert state.total_requests == 3
        assert set(send_contexts) == {'server'}
    finally:
        protocol.connection_lost(None)
        callback_context.reset(context_token)
