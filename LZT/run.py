"""
Batch runner — processes account files one by one.

Usage:
    python run.py              # process ALL files found in results/
    python run.py 2            # process only file #2
    python run.py 1 3 5        # process files 1, 3, 5 in that order
    python run.py 2-6          # process files 2 through 6
"""

import sys
import os
import time
import importlib.util

RESULTS_FOLDER = os.path.join(os.path.dirname(__file__), "results")
DELAY_BETWEEN_RUNS = 5  # seconds between accounts so Kameleo fully releases resources


def _load_main():
    path = os.path.join(os.path.dirname(__file__), "1.py")
    spec = importlib.util.spec_from_file_location("recovery_script", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


def _available_files():
    numbers = []
    for name in os.listdir(RESULTS_FOLDER):
        stem, ext = os.path.splitext(name)
        if ext == ".txt" and stem.isdigit():
            numbers.append(int(stem))
    return sorted(numbers)


def _parse_args(argv):
    if not argv:
        return _available_files()

    # "2-6" range syntax
    if len(argv) == 1 and "-" in argv[0]:
        a, b = argv[0].split("-", 1)
        a, b = int(a), int(b)
        available = set(_available_files())
        return [n for n in range(a, b + 1) if n in available]

    # explicit list: "1 3 5"
    return sorted(int(x) for x in argv)


def _fmt(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s:02d}s" if m else f"{s}s"


def main():
    file_numbers = _parse_args(sys.argv[1:])

    if not file_numbers:
        print("No account files found in results/")
        print("Add files named 1.txt, 2.txt, ... to the results/ folder.")
        return

    recovery_main = _load_main()
    total = len(file_numbers)
    results = {}  # num -> ("OK" | "ERROR", elapsed, [error_msg])

    print("=" * 60)
    print(f"  BATCH RUNNER  |  {total} account(s) queued")
    print("=" * 60)

    batch_start = time.time()

    for idx, num in enumerate(file_numbers, 1):
        print(f"\n{'─' * 60}")
        print(f"  [{idx}/{total}]  File #{num}")
        print(f"{'─' * 60}")

        t0 = time.time()
        try:
            recovery_main(num)
            elapsed = time.time() - t0
            results[num] = ("OK", elapsed, "")
            print(f"\n  [{idx}/{total}]  File #{num} — DONE  ({_fmt(elapsed)})")
        except Exception as e:
            elapsed = time.time() - t0
            results[num] = ("ERROR", elapsed, str(e))
            print(f"\n  [{idx}/{total}]  File #{num} — ERROR  ({_fmt(elapsed)}): {e}")

        if idx < total:
            print(f"  Waiting {DELAY_BETWEEN_RUNS}s before next account...")
            time.sleep(DELAY_BETWEEN_RUNS)

    # ── Summary ──────────────────────────────────────────────────
    total_elapsed = time.time() - batch_start
    ok_count = sum(1 for r in results.values() if r[0] == "OK")

    print(f"\n{'=' * 60}")
    print(f"  SUMMARY  |  {ok_count}/{total} OK  |  total {_fmt(total_elapsed)}")
    print(f"{'=' * 60}")
    for num in file_numbers:
        status, elapsed, err = results.get(num, ("?", 0, ""))
        tag = "OK   " if status == "OK" else "ERROR"
        line = f"  File #{num:>3}  [{tag}]  {_fmt(elapsed)}"
        if err:
            line += f"  — {err}"
        print(line)
    print("=" * 60)


if __name__ == "__main__":
    main()
