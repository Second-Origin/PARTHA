"""Standalone entry point for the Repository Intelligence golden benchmark.

Run from ``apps/backend`` (CI does exactly this)::

    python tests/benchmark/run.py --report-dir "$RUNNER_TEMP/ri-benchmark"

It writes ``benchmark.json`` and ``benchmark.md`` to the report directory,
optionally appends a summary to ``$GITHUB_STEP_SUMMARY``, and exits non-zero when
any enforced gate fails. Reports are written to a caller-supplied (temporary /
git-ignored) directory and are never committed.

This launcher fixes ``sys.path`` so it works whether or not pytest configured
it: it adds the backend root (for ``app``) and the tests root (for the
``benchmark`` package).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_TESTS_ROOT = Path(__file__).resolve().parents[1]      # apps/backend/tests
_BACKEND_ROOT = Path(__file__).resolve().parents[2]    # apps/backend
for _entry in (str(_BACKEND_ROOT), str(_TESTS_ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from benchmark import report as report_module  # noqa: E402
from benchmark import runner  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Repository Intelligence golden benchmark.")
    parser.add_argument("--report-dir", type=Path, default=None, help="Directory for benchmark.json / benchmark.md.")
    parser.add_argument("--step-summary-file", type=Path, default=None, help="Optional file to append a summary to.")
    args = parser.parse_args(argv)

    result = runner.run()

    if args.report_dir is not None:
        json_path, markdown_path = report_module.write_reports(result, args.report_dir)
        print(f"Wrote {json_path}")
        print(f"Wrote {markdown_path}")

    summary_target = args.step_summary_file or (
        Path(os.environ["GITHUB_STEP_SUMMARY"]) if os.environ.get("GITHUB_STEP_SUMMARY") else None
    )
    if summary_target is not None:
        with summary_target.open("a", encoding="utf-8") as handle:
            handle.write(report_module.to_step_summary(result))

    print(report_module.to_console_summary(result))
    for reason in result.failures():
        print(f"  - {reason}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
