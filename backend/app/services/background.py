"""Zapisy pomocnicze poza ścieżką odpowiedzi.

Zadanie trzyma silną referencję, bo samo `create_task` może zniknąć ze
śmieciarką. Pętla testów na Windowsie zmienia się między testami, więc
semafor jest wiązany z aktualną pętlą.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

_LIMIT = 1000
_CANCEL_GRACE_S = 5.0
_tasks: set[asyncio.Task[None]] = set()
_skipped = 0
_semaphore: asyncio.Semaphore | None = None
_semaphore_loop: asyncio.AbstractEventLoop | None = None


def _limiter() -> asyncio.Semaphore:
    global _semaphore, _semaphore_loop
    loop = asyncio.get_running_loop()
    if _semaphore is None or _semaphore_loop is not loop:
        _semaphore = asyncio.Semaphore(8)
        _semaphore_loop = loop
    return _semaphore


async def _run(factory: Callable[[], Awaitable[None]]) -> None:
    try:
        async with _limiter():
            await factory()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("background task failed")


def spawn_background(factory: Callable[[], Awaitable[None]], *, name: str) -> None:
    global _skipped
    if len(_tasks) >= _LIMIT:
        _skipped += 1
        if _skipped % 100 == 0:
            logger.warning("background tasks skipped: %s", _skipped)
        return
    task = asyncio.create_task(_run(factory), name=name)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain_background(timeout_s: float) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0, timeout_s)
    while True:
        pending = {task for task in _tasks if not task.done()}
        if not pending:
            return
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        await asyncio.wait(pending, timeout=remaining)

    pending = {task for task in _tasks if not task.done()}
    if pending:
        logger.warning("background shutdown deadline; cancelling %s task(s)", len(pending))
        for task in pending:
            task.cancel()
        _, still_running = await asyncio.wait(pending, timeout=_CANCEL_GRACE_S)
        if still_running:
            logger.error(
                "background shutdown: %s task(s) ignored cancellation", len(still_running)
            )
