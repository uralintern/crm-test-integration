import logging
import sys

def setup_logging() -> None:
    root = logging.getLogger()
    
    if not root.handlers:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

        root.setLevel(logging.INFO)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

setup_logging()