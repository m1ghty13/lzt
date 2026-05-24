"""
Batch runner — processes account files one by one.

Usage:
    python run.py              # process all files, then exit
    python run.py --watch      # process all files, then WAIT for new ones forever
    python run.py 2            # process only file #2
    python run.py 1 3 5        # process files 1, 3, 5 in that order
    python run.py 2-6          # process files 2 through 6

After each file is processed it is moved to results/archive/ automatically.
On restart only unprocessed files (still in results/) are picked up.
"""

import sys
import os
import time
import logging
import shutil
import importlib.util
from pathlib import Path

RESULTS_FOLDER  = Path(__file__).parent / "results"
ARCHIVE_FOLDER  = RESULTS_FOLDER / "archive"
DELAY_BETWEEN_RUNS = 5   # seconds between accounts so Kameleo fully releases resources
WATCH_POLL_INTERVAL = 5  # seconds between folder checks in watch mode


def _load_main():
    path = Path(__file__).parent / "1.py"
    spec = importlib.util.spec_from_file_location("recovery_script", str(path))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


def _available_files() -> list[int]:
    nums = []
    for f in RESULTS_FOLDER.iterdir():
        if f.suffix == ".txt" and f.stem.isdigit():
            nums.append(int(f.stem))
    return sorted(nums)


def _close_log_handlers():
    """Close all open logging file handlers (required before renaming on Windows)."""
    root = logging.getLogger()
    for h in root.handlers[:]:
        try:
            h.flush()
            h.close()
        except Exception:
            pass
    root.handlers.clear()
    # Also clear named loggers
    for name in list(logging.Logger.manager.loggerDict):
        lgr = logging.getLogger(name)
        for h in lgr.handlers[:]:
            try:
                h.flush()
                h.close()
            except Exception:
                pass
        lgr.handlers.clear()


def _archive_file(num: int):
    """Move processed account file + log to archive/ with a timestamp suffix."""
    ARCHIVE_FOLDER.mkdir(exist_ok=True)
    _close_log_handlers()   # must happen before moving log file on Windows
    ts = time.strftime("%Y%m%d_%H%M%S")
    for src_name, dst_name in [
        (f"{num}.txt",     f"{num}_{ts}.txt"),
        (f"log_{num}.txt", f"log_{num}_{ts}.txt"),
    ]:
        src = RESULTS_FOLDER / src_name
        if src.exists():
            try:
                shutil.move(str(src), str(ARCHIVE_FOLDER / dst_name))
            except Exception as e:
                print(f"  ⚠ Could not archive {src_name}: {e}")
    print(f"  📦 File #{num} archived")


def _parse_args(argv):
    watch = "--watch" in argv
    argv  = [a for a in argv if a != "--watch"]

    if not argv:
        return _available_files(), watch

    if len(argv) == 1 and "-" in argv[0]:
        a, b = argv[0].split("-", 1)
        a, b = int(a), int(b)
        available = set(_available_files())
        return [n for n in range(a, b + 1) if n in available], watch

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
    finally:
        _archive_file(num)


def _print_summary(results, batch_start):
    total_elapsed = time.time() - batch_start
    ok_count = sum(1 for r in results.values() if r[0] == "OK")
    total    = len(results)
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY  |  {ok_count}/{total} OK  |  total {_fmt(total_elapsed)}")
    print(f"{'=' * 60}")
    for num in sorted(results):
        status, elapsed, err = results[num]
        tag  = "OK   " if status == "OK" else "ERROR"
        line = f"  File #{num:>3}  [{tag}]  {_fmt(elapsed)}"
        if err:
            line += f"  — {err}"
        print(line)
    print("=" * 60)


def main():
    file_numbers, watch = _parse_args(sys.argv[1:])

    recovery_main = _load_main()
    results       = {}
    batch_start   = time.time()
    processed     = set()

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
            if idx < total and _available_files():
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
            pending   = sorted(available - processed)

            if pending:
                for num in pending:
                    print(f"\n  New file detected: #{num}")
                    time.sleep(DELAY_BETWEEN_RUNS)
                    _run_one(recovery_main, num, "[WATCH]", results)
                    processed.add(num)
                print(f"\n  Watching for more files...  (Ctrl+C to stop)")
                dots = 0
            else:
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
