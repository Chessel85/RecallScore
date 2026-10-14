# tests/support/virtual_clock.py
from typing import Callable, List, Optional


class VirtualClock:
    """A shared virtual clock for several ClockTimers: run() fires
    whichever armed timer is due first, so a PlaybackController and its
    Sequencer interleave exactly as their real QTimers would, without any
    wall-clock wait. (FakeTimer drives one timer by hand; this orders
    several.)"""

    def __init__(self):
        self.now = 0
        self.timers: List["ClockTimer"] = []
        self._order = 0

    def timer(self) -> "ClockTimer":
        timer = ClockTimer(self)
        self.timers.append(timer)
        return timer

    def run(self, max_fires: int, until: Optional[Callable[[], bool]] = None) -> None:
        for _ in range(max_fires):
            if until is not None and until():
                return
            due = [t for t in self.timers if t.running]
            if not due:
                return
            min(due, key=lambda t: (t.due, t.order)).fire()

    def _next_order(self) -> int:
        self._order += 1
        return self._order


class ClockTimer:
    """QTimer stand-in on a VirtualClock: start(ms) arms it at now + ms."""

    def __init__(self, clock: VirtualClock):
        self.clock = clock
        self.running = False
        self.due = 0
        self.order = 0
        self._callback: Optional[Callable[[], None]] = None
        self.timeout = self  # so `.timeout.connect(cb)` works like the real signal

    def setSingleShot(self, value: bool) -> None:
        pass

    def setTimerType(self, value) -> None:
        pass

    def connect(self, callback: Callable[[], None]) -> None:
        self._callback = callback

    def start(self, ms: int) -> None:
        self.running = True
        self.due = self.clock.now + ms
        self.order = self.clock._next_order()

    def stop(self) -> None:
        self.running = False

    def isActive(self) -> bool:
        return self.running

    def fire(self) -> None:
        self.running = False
        self.clock.now = max(self.clock.now, self.due)
        self._callback()
