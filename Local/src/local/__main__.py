import asyncio
import logging

logging.basicConfig(level=logging.DEBUG)

from .main import main, _build_arg_parser


if __name__ == '__main__':
    parser = _build_arg_parser()
    args = parser.parse_args()
    asyncio.run(main(track_name=args.track, train_name=args.train, publish_frequency=args.publish_frequency))
