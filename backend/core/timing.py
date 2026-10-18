"""Simple timing collector for profiling business workflows."""

from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional


class TimingCollector:
    """Collect ordered stage timings and build a duration ranking."""

    def __init__(self) -> None:
        self._started_at = perf_counter()
        self.items: List[Dict[str, Any]] = []

    def add(
        self,
        stage: str,
        duration_seconds: float,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add one timing item."""
        item: Dict[str, Any] = {
            "stage": stage,
            "category": category,
            "duration_ms": round(duration_seconds * 1000, 2),
            "duration_seconds": round(duration_seconds, 3),
        }
        if metadata:
            item["metadata"] = metadata

        self.items.append(item)
        return item

    @contextmanager
    def measure(
        self,
        stage: str,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Measure a sync or awaited block used inside a regular with statement."""
        start = perf_counter()
        try:
            yield
        finally:
            self.add(stage, perf_counter() - start, category, metadata)

    def extend(
        self,
        items: Iterable[Dict[str, Any]],
        prefix: str = "",
        category: Optional[str] = None,
    ) -> None:
        """Merge timing items produced by a nested component."""
        for item in items:
            copied = dict(item)
            if prefix:
                copied["stage"] = f"{prefix}{copied.get('stage', '')}"
            if category:
                copied["category"] = category
            self.items.append(copied)

    def report(self) -> Dict[str, Any]:
        """Return ordered timings plus a slowest-first ranking."""
        total_seconds = perf_counter() - self._started_at
        rank = sorted(self.items, key=lambda item: item.get("duration_ms", 0), reverse=True)
        return {
            "total_duration_ms": round(total_seconds * 1000, 2),
            "total_duration_seconds": round(total_seconds, 3),
            "items": self.items,
            "rank": rank,
        }
