"""One worker thread for all in-process MLX work.

Speech-to-text and text-to-speech both run MLX models inside the agent process. Loading and
running them on a single dedicated thread keeps GPU work off the event loop and stops the two
models from issuing MLX operations from different threads at the same time.
"""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mlx")


async def run_mlx[T](fn: Callable[..., T], *args, **kwargs) -> T:
    """Run ``fn`` on the MLX thread without blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_EXECUTOR, partial(fn, *args, **kwargs))


def limit_mlx_cache() -> None:
    """Cap MLX's freed-buffer cache for this process (see ``MLX_CACHE_LIMIT_BYTES``)."""
    import mlx.core as mx

    from tellerline.config import MLX_CACHE_LIMIT_BYTES

    mx.set_cache_limit(MLX_CACHE_LIMIT_BYTES)
