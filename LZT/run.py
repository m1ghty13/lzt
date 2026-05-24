"""
Batch runner — processes account files one by one.

Usage:
    python run.py              # process all files, then exit
    python run.py --watch      # process all files, then WAIT for new ones forever
    python run.py 2            # process only file #2
    python run.py 1 3 5        # process files 1, 3, 5 in that order
    python run.py 2-6          # process files 2 through 6

Watch mode:
    Keeps running after all files are done.
    As soon as a new N.txt appears in results/, it gets processed automatically.
    Stop with Ctrl+C.
"""

import sys
import os
import time
import importlib.util

RESULTS_FOLDER = os.path.join(os.path.dirname(__file__), "results")
DELAY_BETWEEN_RUNS = 5   # seconds between accounts so Kameleo fully releases resources
WATCH_POLL_INTERVAL = 5  # seconds between folder checks in watch mode


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
    watch = "--watch" in argv
    argv = [a for a in argv if a != "--watch"]

    if not argv:
        return _available_files(), watch

    # "2-6" range syntax
    if len(argv) == 1 and "-" in argv[0]:
        a, b = argv[0].split("-", 1)
        a, b = int(a), int(b)
        available = set(_available_files())
        return [n for n in range(a, b + 1) if n in available], watch

    # explicit list: "1 3 5"
    return sorted(int(x) for x in argv), watch


def _fmt(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s:02d}s" if m else f"{s}s"


def _run_one(recovery_main, num, label, results):
    print(f"\n{'─' * 60}")
    print(f"  {label}  File #{num}")
    print(f"{'─' * 60}")
    t0 = time.time()
    try:
        recovery_main(num)
        elapsed = time.time() - t0
        results[num] = ("OK", elapsed, "")
        print(f"\n  {label}  File #{num} — DONE  ({_fmt(elapsed)})")
    except Exception as e:
        elapsed = time.time() - t0
        results[num] = ("ERROR", elapsed, str(e))
        print(f"\n  {label}  File #{num} — ERROR  ({_fmt(elapsed)}): {e}")


def _print_summary(results, batch_start):
    total_elapsed = time.time() - batch_start
    ok_count = sum(1 for r in results.values() if r[0] == "OK")
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY  |  {ok_count}/{total} OK  |  total {_fmt(total_elapsed)}")
    print(f"{'=' * 60}")
    for num in sorted(results):
        status, elapsed, err = results[num]
        tag = "OK   " if status == "OK" else "ERROR"
        line = f"  File #{num:>3}  [{tag}]  {_fmt(elapsed)}"
        if err:
            line += f"  — {err}"
        print(line)
    print("=" * 60)


def main():
    file_numbers, watch = _parse_args(sys.argv[1:])

    recovery_main = _load_main()
    results = {}
    batch_start = time.time()
    processed = set()

    # ── Initial batch ────────────────────────────────────────────
    if file_numbers:
        total = len(file_numbers)
        print("=" * 60)
        mode_label = "WATCH MODE" if watch else "BATCH RUNNER"
        print(f"  {mode_label}  |  {total} account(s) queued")
        print("=" * 60)

        for idx, num in enumerate(file_numbers, 1):
            _run_one(recovery_main, num, f"[{idx}/{total}]", results)
            processed.add(num)
            if idx < total:
                print(f"  Waiting {DELAY_BETWEEN_RUNS}s before next account...")
                time.sleep(DELAY_BETWEEN_RUNS)
    else:
        if not watch:
            print("No account files found in results/")
            print("Add files named 1.txt, 2.txt, ... to the results/ folder.")
            print("Or use --watch to wait for files automatically.")
            return
        print("=" * 60)
        print("  WATCH MODE  |  No files yet — waiting...")
        print("=" * 60)

    if not watch:
        _print_summary(results, batch_start)
        return

    # ── Watch loop ───────────────────────────────────────────────
    print(f"\n  Watching results/ for new files...  (Ctrl+C to stop)")
    dots = 0
    try:
        while True:
            available = set(_available_files())
            pending = sorted(available - processed)

            if pending:
                for num in pending:
                    print(f"\n  New file detected: #{num}")
                    time.sleep(DELAY_BETWEEN_RUNS)
                    _run_one(recovery_main, num, "[WATCH]", results)
                    processed.add(num)
                print(f"\n  Watching for more files...  (Ctrl+C to stop)")
                dots = 0
            else:
                # Print a dot every 30s so user knows it's alive
                time.sleep(WATCH_POLL_INTERVAL)
                dots += WATCH_POLL_INTERVAL
                if dots >= 30:
                    print(f"  [{time.strftime('%H:%M:%S')}] Waiting for new files...")
                    dots = 0

    except KeyboardInterrupt:
        print("\n\n  Stopped by user.")
        _print_summary(results, batch_start)


if __name__ == "__main__":
    main()
