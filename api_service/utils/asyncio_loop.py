"""Helpers for safely running short-lived asyncio event loops."""

import asyncio
import concurrent.futures
from typing import Any, Coroutine, Optional


async def _drain_pending_tasks(logger=None, timeout: float = 5.0) -> None:
    """Give fire-and-forget cleanup tasks a chance to finish before loop close."""
    await asyncio.sleep(0)
    current_task = asyncio.current_task()
    pending = [
        task for task in asyncio.all_tasks()
        if task is not current_task and not task.done()
    ]
    if not pending:
        return

    done, pending = await asyncio.wait(pending, timeout=timeout)
    for task in done:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if logger:
                logger.warning("Background async cleanup task failed: %s", exc)

    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


async def _flush_ready_callbacks() -> None:
    """Run callbacks scheduled by async cleanup before loop shutdown."""
    await asyncio.sleep(0)
    await asyncio.sleep(0)


def close_event_loop(loop: asyncio.AbstractEventLoop, logger=None) -> None:
    """Drain pending cleanup tasks, then close a manually-created event loop."""
    if loop.is_closed():
        return

    try:
        loop.run_until_complete(_drain_pending_tasks(logger))
        loop.run_until_complete(_flush_ready_callbacks())
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(_flush_ready_callbacks())
        shutdown_executor = getattr(loop, "shutdown_default_executor", None)
        if shutdown_executor:
            loop.run_until_complete(shutdown_executor())
        loop.run_until_complete(_flush_ready_callbacks())
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def run_coroutine_sync(coro: Coroutine[Any, Any, Any], logger=None) -> Any:
    """Run a coroutine from sync code with deterministic loop cleanup."""
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop and running_loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_coroutine_sync, coro, logger)
            return future.result()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        close_event_loop(loop, logger)
