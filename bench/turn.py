"""Benchmark Smart Turn v3.2 (bundled with Pipecat) end-of-turn inference time on CPU.

The model always looks at the last 8 seconds of audio, so inference time does not depend on
what was said; random audio is enough to time it.

Usage:
    python -m bench.turn --iterations 300
"""

import argparse

import numpy as np
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3

from bench.common import ResultWriter, ms, now, summarize
from tellerline.config import STT_SAMPLE_RATE


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--iterations", type=int, default=300)
    parser.add_argument("--cpu-counts", type=int, nargs="+", default=[1, 2])
    args = parser.parse_args()

    rng = np.random.default_rng(0)
    audio = (rng.standard_normal(STT_SAMPLE_RATE * 4) * 0.05).astype(np.float32)
    summaries = {}

    with ResultWriter("turn", vars(args)) as writer:
        for cpu_count in args.cpu_counts:
            analyzer = LocalSmartTurnAnalyzerV3(cpu_count=cpu_count)
            analyzer.set_sample_rate(STT_SAMPLE_RATE)
            for _ in range(10):
                analyzer._predict_endpoint(audio)  # warm-up; private API, benchmark only

            timings = []
            for _ in range(args.iterations):
                start = now()
                analyzer._predict_endpoint(audio)
                timings.append(now() - start)
            summaries[cpu_count] = summarize(timings)
            writer.sample(cpu_count=cpu_count, timings_s=timings)
        writer.summary(inference_s={str(k): v for k, v in summaries.items()})

    for cpu_count, stats in summaries.items():
        print(f"cpu_count={cpu_count}: p50 {ms(stats['p50'])} ms, p90 {ms(stats['p90'])} ms")
    print(f"Results: {writer.path}")


if __name__ == "__main__":
    main()
