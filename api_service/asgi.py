"""Flask's ASGI adapter with isolated server response callbacks."""

import asyncio
import contextvars

from asgiref.wsgi import WsgiToAsgi


class ContextSafeWsgiToAsgi(WsgiToAsgi):
    """Keep AsyncToSync's temporary executor out of server callbacks.

    Uvicorn can start a pipelined request inside ``send``. Running that
    callback in the WSGI bridge's context lets the next request inherit a
    CurrentThreadExecutor that quits as soon as the previous send returns.
    Use the original ASGI context for server callbacks instead.
    """

    async def __call__(self, scope, receive, send):
        server_context = contextvars.copy_context()

        async def server_send(message):
            await asyncio.create_task(send(message), context=server_context.copy())

        await super().__call__(scope, receive, server_send)
