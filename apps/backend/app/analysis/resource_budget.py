"""Fail-closed resource budgets for one repository analysis run."""

from __future__ import annotations

import ctypes
import importlib
import mmap
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


RESOURCE_EXCEEDED_CODE = "resource_exceeded"
DEFAULT_MAX_REPOSITORY_SOURCE_BYTES = 1024 * 1024 * 1024
DEFAULT_MAX_PROCESS_RSS_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_MAX_ANALYSIS_SECONDS = 30 * 60


class AnalysisResourceExceeded(RuntimeError):
    """A repository analysis exceeded an operator-configured resource budget."""

    def __init__(self, resource: str, limit: int | float, observed: int | float) -> None:
        self.resource = resource
        self.limit = limit
        self.observed = observed
        super().__init__(f"{RESOURCE_EXCEEDED_CODE}: {resource} budget exceeded ({observed} > {limit})")


def process_rss_bytes() -> int:
    """Return this process's resident set size without an optional dependency."""

    if sys.platform == "win32":
        # PROCESS_MEMORY_COUNTERS.WorkingSetSize is the current resident set.
        class _ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = _ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        windll = getattr(ctypes, "windll", None)
        if windll is not None:
            get_current_process = windll.kernel32.GetCurrentProcess
            get_current_process.restype = ctypes.c_void_p
            get_process_memory_info = windll.psapi.GetProcessMemoryInfo
            get_process_memory_info.argtypes = (
                ctypes.c_void_p,
                ctypes.POINTER(_ProcessMemoryCounters),
                ctypes.c_ulong,
            )
            get_process_memory_info.restype = ctypes.c_bool
            process = get_current_process()
            if get_process_memory_info(process, ctypes.byref(counters), counters.cb):
                return int(counters.WorkingSetSize)
        raise OSError("could not read the current Windows process RSS")

    statm = Path("/proc/self/statm")
    if statm.exists():
        fields = statm.read_text(encoding="ascii").split()
        if len(fields) >= 2:
            return int(fields[1]) * mmap.PAGESIZE

    # Portable Unix fallback. Linux reports KiB; macOS reports bytes.
    resource = importlib.import_module("resource")
    maximum = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return maximum if sys.platform == "darwin" else maximum * 1024


@dataclass
class AnalysisResourceBudget:
    """Track total source bytes, elapsed time, and sampled process RSS."""

    max_source_bytes: int
    max_rss_bytes: int
    max_seconds: float
    rss_reader: Callable[[], int] = process_rss_bytes
    monotonic: Callable[[], float] = time.monotonic
    source_bytes: int = 0
    peak_rss_bytes: int = 0
    _started_at: float = field(init=False)

    def __post_init__(self) -> None:
        if self.max_source_bytes <= 0 or self.max_rss_bytes <= 0 or self.max_seconds <= 0:
            raise ValueError("analysis resource budgets must be greater than zero")
        self._started_at = self.monotonic()

    def check(self) -> None:
        elapsed = self.monotonic() - self._started_at
        if elapsed > self.max_seconds:
            raise AnalysisResourceExceeded("elapsed_seconds", self.max_seconds, elapsed)
        rss = self.rss_reader()
        self.peak_rss_bytes = max(self.peak_rss_bytes, rss)
        if rss > self.max_rss_bytes:
            raise AnalysisResourceExceeded("rss_bytes", self.max_rss_bytes, rss)

    def charge_source(self, size: int) -> None:
        if size < 0:
            raise ValueError("source size cannot be negative")
        observed = self.source_bytes + size
        if observed > self.max_source_bytes:
            raise AnalysisResourceExceeded("source_bytes", self.max_source_bytes, observed)
        self.source_bytes = observed
        self.check()
