import logging
import sys


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s service=ai-inference logger=%(name)s %(message)s",
        stream=sys.stdout,
    )
