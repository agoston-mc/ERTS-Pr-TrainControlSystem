import asyncio
import logging

logging.basicConfig(level=logging.DEBUG)

from .main import main as _main, _build_arg_parser

def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    asyncio.run(_main(track_name=args.track, train_name=args.train, publish_frequency=args.publish_frequency))
