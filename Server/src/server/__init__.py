import logging
logging.basicConfig(level=logging.INFO)
from .main import main as _main


def main():
    _main()
