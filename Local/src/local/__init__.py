import asyncio
from .main import main as _main

def main() -> None:
    asyncio.run(_main())
