import asyncio
import math
import time
from collections import deque
from collections.abc import Callable

RATE_WINDOW_SECONDS = 60


class RequestLimitReached(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__("model_rate_limited")


class ModelRequestGate:
    def __init__(
        self, per_minute: int, concurrent: int, clock: Callable[[], float] = time.monotonic
    ):
        self.per_minute = per_minute
        self.concurrent = concurrent
        self.active = 0
        self.started: deque[float] = deque()
        self.lock = asyncio.Lock()
        self.clock = clock

    async def acquire(self) -> None:
        async with self.lock:
            now = self.clock()
            while self.started and now - self.started[0] >= RATE_WINDOW_SECONDS:
                self.started.popleft()
            if self.active >= self.concurrent:
                raise RequestLimitReached(1)
            if len(self.started) >= self.per_minute:
                remaining = RATE_WINDOW_SECONDS - (now - self.started[0])
                raise RequestLimitReached(max(1, math.ceil(remaining)))
            self.started.append(now)
            self.active += 1

    async def release(self) -> None:
        async with self.lock:
            self.active -= 1
