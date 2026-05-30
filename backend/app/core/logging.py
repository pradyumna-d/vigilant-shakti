import logging
import sys


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s service=backend logger=%(name)s %(message)s",
        stream=sys.stdout,
    )
