import collections
import threading
import time


class RateLimiter:
    """Global token bucket — limits total sends/second across all threads. 0 = unlimited."""

    def __init__(self, max_per_second: float):
        self._interval = (1.0 / max_per_second) if max_per_second > 0 else 0.0
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self):
        if self._interval <= 0:
            return
        with self._lock:
            now = time.time()
            gap = self._interval - (now - self._last)
            if gap > 0:
                time.sleep(gap)
            self._last = time.time()


class DomainThrottle:
    """Per-domain sliding-window throttle. 0 = unlimited."""

    def __init__(self, max_per_domain_per_minute: int):
        self._limit = max_per_domain_per_minute
        self._lock = threading.Lock()
        self._windows: dict = {}

    def wait(self, recipient: str):
        if self._limit <= 0:
            return
        domain = recipient.split("@")[-1].lower() if "@" in recipient else recipient.lower()
        while True:
            with self._lock:
                now = time.time()
                dq = self._windows.setdefault(domain, collections.deque())
                # Expire entries older than 60 s
                while dq and now - dq[0] > 60:
                    dq.popleft()
                if len(dq) < self._limit:
                    dq.append(now)
                    return
                # Need to wait until oldest entry ages out
                sleep_for = dq[0] + 60 - now + 0.05
            time.sleep(max(sleep_for, 0.05))
