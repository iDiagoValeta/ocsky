"""The system clock as a ForTellingTime adapter."""
from __future__ import annotations

import time


class SystemClock:
    def now_ms(self) -> int:
        return int(time.time() * 1000)
