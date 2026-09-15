"""Run mlx-lm's server with a capped MLX buffer cache.

MLX keeps freed GPU buffers for reuse. Without a limit that cache grows to several gigabytes,
and alongside the speech models on a 16 GB Mac the system starts swapping, which turns 300 ms
turns into multi-second ones. Arguments are passed straight to ``mlx_lm.server``.
"""

import mlx.core as mx
from mlx_lm.server import main

from tellerline.config import MLX_CACHE_LIMIT_BYTES

if __name__ == "__main__":
    mx.set_cache_limit(MLX_CACHE_LIMIT_BYTES)
    main()
