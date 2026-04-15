import asyncio
import logging
logging.basicConfig(level=logging.INFO)
from .main import main as _main

def main() -> None:
    asyncio.run(_main())
