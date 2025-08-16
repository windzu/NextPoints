import time
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def time_block() -> Iterator[float]:
    start = time.time()
    yield start
    end = time.time()
    # Caller calculates duration if needed
