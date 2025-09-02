from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class _TimerAgg:
    sum_ms: float = 0.0
    count: int = 0

@dataclass
class _Counter:
    value: int = 0

class Metrics:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._timers: Dict[str, _TimerAgg] = {}
        self._counters: Dict[str, _Counter] = {}

    async def observe_ms(self, name: str, ms: float) -> None:
        async with self._lock:
            agg = self._timers.setdefault(name, _TimerAgg())
            agg.sum_ms += float(ms)
            agg.count += 1

    async def inc(self, name: str, n: int = 1) -> None:
        async with self._lock:
            c = self._counters.setdefault(name, _Counter())
            c.value += int(n)

    async def export_prom(self) -> str:
        # very small Prometheus-like text format
        lines: list[str] = []
        async with self._lock:
            for k, v in self._counters.items():
                lines.append(f'# TYPE {k} counter')
                lines.append(f'{k} {v.value}')
            for k, v in self._timers.items():
                lines.append(f'# TYPE {k}_ms summary')
                lines.append(f'{k}_ms_sum {v.sum_ms:.3f}')
                lines.append(f'{k}_ms_count {v.count}')
        return "\n".join(lines) + "\n"

METRICS = Metrics()
