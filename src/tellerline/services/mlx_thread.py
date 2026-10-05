"""One worker thread for all in-process MLX work, most urgent first.

Speech-to-text and text-to-speech both run MLX models inside the agent process. Running them on
a single dedicated thread keeps GPU work off the event loop and stops the two models from
issuing MLX operations from different threads at the same time.

With several calls at once, that thread is shared, so the order of its queue matters. A caller
who has just stopped speaking is waiting on their transcript; the first clause of a reply is
what they hear next; the rest of a reply has time to spare, since it renders while the first
clause plays. Work runs in that order (``Priority``), first come first served within each.
"""

import asyncio
import itertools
import queue
import threading
from collections.abc import Callable
from concurrent.futures import Future
from enum import IntEnum
from functools import partial
from typing import Any


class Priority(IntEnum):
    TRANSCRIBE = 0  # a caller is waiting for their turn to be understood
    FIRST_AUDIO = 1  # the first clause of a reply, or anything else on the critical path
    LATER_AUDIO = 2  # the rest of a reply, rendered while the first clause plays


class _Worker:
    def __init__(self) -> None:
        self._queue: queue.PriorityQueue[tuple[int, int, Callable[[], Any], Future]] = (
            queue.PriorityQueue()
        )
        self._order = itertools.count()
        self._thread = threading.Thread(target=self._run, name="mlx", daemon=True)
        self._thread.start()

    def submit(self, priority: Priority, fn: Callable[[], Any]) -> Future:
        future: Future = Future()
        self._queue.put((int(priority), next(self._order), fn, future))
        return future

    def _run(self) -> None:
        while True:
            _, _, fn, future = self._queue.get()
            if not future.set_running_or_notify_cancel():
                continue
            try:
                future.set_result(fn())
            except BaseException as error:  # handed to the awaiting coroutine
                future.set_exception(error)


_WORKER = _Worker()


async def run_mlx[T](
    fn: Callable[..., T], *args, priority: Priority = Priority.FIRST_AUDIO, **kwargs
) -> T:
    """Run ``fn`` on the MLX thread without blocking the event loop."""
    return await asyncio.wrap_future(_WORKER.submit(priority, partial(fn, *args, **kwargs)))


def limit_mlx_cache() -> None:
    """Cap MLX's freed-buffer cache for this process (see ``MLX_CACHE_LIMIT_BYTES``)."""
    import mlx.core as mx

    from tellerline.config import MLX_CACHE_LIMIT_BYTES

    mx.set_cache_limit(MLX_CACHE_LIMIT_BYTES)
