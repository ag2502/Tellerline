"""Run the mock bank: python -m tellerline.bank [--port 8090] [--db results/bank.sqlite]"""

import argparse

import uvicorn

from tellerline.bank.api import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--db", default=":memory:", help="SQLite file; in-memory by default")
    args = parser.parse_args()
    uvicorn.run(create_app(args.db), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
