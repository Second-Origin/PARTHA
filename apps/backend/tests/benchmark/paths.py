"""Canonical on-disk locations for the benchmark corpus and configuration."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = PACKAGE_DIR / "config"
FIXTURES_DIR = PACKAGE_DIR / "fixtures"
SUPPORT_MATRIX_PATH = CONFIG_DIR / "benchmark_support_matrix.json"
THRESHOLDS_PATH = CONFIG_DIR / "thresholds.json"
