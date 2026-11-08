"""Fault injection for resilience testing and the UI chaos panel. Pure Python, deterministic given a seed.

Faults: network cut (ChaosLink raises ConnectionError), duplicate events, late/out-of-order delivery,
sensor dropout (a channel goes null / the device stops sending), and a mains->UPS->shutdown power model.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field


class ChaosLink:
    """Wraps a sender(event)->dict. While `network_up` is False every call raises ConnectionError."""

    def __init__(self, sender, rng: random.Random | None = None):
        self.sender = sender
        self.network_up = True
        self.calls = 0
        self.failures = 0
        self.rng = rng or random.Random(0)

    def __call__(self, event: dict) -> dict:
        self.calls += 1
        if not self.network_up:
            self.failures += 1
            raise ConnectionError("chaos: network cut")
        return self.sender(event)


def with_duplicates(events: list[dict], rate: float, rng: random.Random, max_copies: int = 3) -> list[dict]:
    out = []
    for e in events:
        out.append(e)
        if rng.random() < rate:
            out.extend(dict(e) for _ in range(rng.randint(1, max_copies - 1)))
    return out


def with_late_delivery(events: list[dict], rng: random.Random, window: int = 8) -> list[dict]:
    """Shuffle within a sliding window so events arrive out of order (late) but none are lost."""
    out = list(events)
    for i in range(0, len(out), window):
        chunk = out[i:i + window]
        rng.shuffle(chunk)
        out[i:i + window] = chunk
    return out


def sensor_dropout(events: list[dict], channel: str | None, start: int, end: int) -> list[dict]:
    """channel=None: device sends nothing between indexes [start,end) (events never exist);
    otherwise that vital channel is null for the span but the rest of the reading still arrives."""
    out = []
    for i, e in enumerate(events):
        if start <= i < end:
            if channel is None:
                continue
            e = {**e, channel: None}
        out.append(e)
    return out


@dataclass
class PowerModel:
    """Mains -> UPS -> shutdown. `tick(minutes)` advances time. UI shows state + battery %."""
    mains: bool = True
    battery_pct: float = 100.0
    drain_pct_per_min: float = 2.0      # while on battery
    charge_pct_per_min: float = 1.0     # while on mains
    shutdown_below: float = 5.0
    log: list = field(default_factory=list)

    @property
    def state(self) -> str:
        if self.battery_pct <= self.shutdown_below and not self.mains:
            return "shutdown"
        return "mains" if self.mains else "ups_battery"

    @property
    def can_transmit(self) -> bool:
        return self.state != "shutdown"

    def cut_power(self):
        self.mains = False
        self.log.append("mains_lost")

    def restore_power(self):
        self.mains = True
        self.log.append("mains_restored")

    def tick(self, minutes: float = 1.0) -> str:
        if self.mains:
            self.battery_pct = min(100.0, self.battery_pct + self.charge_pct_per_min * minutes)
        else:
            self.battery_pct = max(0.0, self.battery_pct - self.drain_pct_per_min * minutes)
        return self.state
