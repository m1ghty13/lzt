"""
Telegram bot for managing the RuneScape account recovery runner.

Setup:
  1. Create a bot via @BotFather, copy the token
  2. Find your Telegram user ID via @userinfobot
  3. Fill BOT_TOKEN and OWNER_ID below (or set env vars TG_BOT_TOKEN / TG_OWNER_ID)
  4. python bot.py

Commands:
  /status        — runner state + queued files
  /run           — start runner in watch mode (auto-enables live logs)
  /stop          — stop runner
  /files         — list all account files (queue)
  /archive       — list archived (processed) files
  /retry N       — move archived file #N back to queue for reprocessing
  /logs [N]      — last log lines for file N (default: most recent)
  /follow        — toggle live log streaming to this chat
  /proxy N ip:port:user:pass  — update proxy for file #N
  Upload .txt    — validates and adds to queue
"""

import asyncio
import io
import os
import subprocess
import sys
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ── Config ──────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "YOUR_TOKEN_HERE")
OWNER_ID  = int(os.getenv("TG_OWNER_ID", "0"))

RESULTS_FOLDER = Path(__file__).parent / "results"
ARCHIVE_FOLDER = RESULTS_FOLDER / "archive"
RUNNER_SCRIPT  = Path(__file__).parent / "run.py"
PID_FILE       = Path(__file__).parent / ".runner.pid"

LOG_STREAM_INTERVAL = 3   # seconds between log checks

# ── Global state ─────────────────────────────────────────────────
_proc: subprocess.Popen | None = None
_stream_chat_id: int | None = None       # None = streaming off
_log_positions: dict[int, int] = {}      # file_num -> bytes read so far


# ── Process management ────────────────────────────────────────────
def _is_alive() -> bool:
    global _proc
    if _proc is not None:
        if _proc.poll() is None:
            return True
        _proc = None
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True,
        )
        if str(pid) in result.stdout:
            return True
    except Exception:
        pass
    PID_FILE.unlink(missing_ok=True)
    return False


def _start() -> bool:
    global _proc
    if _is_alive():
        return False
    _proc = subprocess.Popen(
        [sys.executable, str(RUNNER_SCRIPT), "--watch"],
        cwd=str(RUNNER_SCRIPT.parent),
    )
    PID_FILE.write_text(str(_proc.pid))
    return True


def _stop() -> bool:
    global _proc
    if not _is_alive():
        return False
    if _proc:
        _proc.terminate()
        _proc = None
    else:
        try:
            pid = int(PID_FILE.read_text().strip())
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        except Exception:
            pass
    PID_FILE.unlink(missing_ok=True)
    return True


# ── File helpers ──────────────────────────────────────────────────
def _file_list() -> list[int]:
    nums = []
    for f in RESULTS_FOLDER.iterdir():
        if f.suffix == ".txt" and f.stem.isdigit():
            nums.append(int(f.stem))
    return sorted(nums)


def _next_num() -> int:
    existing = _file_list()
    return (max(existing) + 1) if existing else 1


def _validate(text: str) -> tuple[bool, str]:
    lines = [l.rstrip() for l in text.splitlines()]
    proxy = next(
        (l for l in reversed(lines) if l.count(".") == 3 and l.count(":") >= 3),
        None,
    )
    if not proxy:
        return False, "Proxy line not found. Expected: ip:port:user:pass"
    if len(proxy.split(":")) < 4:
        return False, f"Proxy format invalid: {proxy}"
    idx = lines.index(proxy)
    account = [l for l in lines[:idx] if l.strip()]
    if not account:
        return False, "No account data before proxy line"
    return True, ""


def _archived_entries() -> list[tuple[int, str, Path]]:
    """Return list of (original_num, timestamp, path) sorted newest-first."""
    if not ARCHIVE_FOLDER.exists():
        return []
    entries = []
    for f in ARCHIVE_FOLDER.iterdir():
        if f.suffix != ".txt" or f.stem.startswith("log_"):
            continue
        parts = f.stem.split("_", 1)
        if len(parts) == 2 and parts[0].isdigit():
            entries.append((int(parts[0]), parts[1], f))
    return sorted(entries, key=lambda x: x[1], reverse=True)


def _last_log(num: int, n: int = 40) -> str:
    path = RESULTS_FOLDER / f"log_{num}.txt"
    if not path.exists():
        return f"No log found for #{num}"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = lines[-n:] if len(lines) > n else lines
    return "\n".join(tail)


def _set_stream_positions_to_end():
    """Mark all current log files as 'already read' so we only stream new content."""
    for num in _file_list():
        path = RESULTS_FOLDER / f"log_{num}.txt"
        if path.exists():
            _log_positions[num] = path.stat().st_size


# ── Background log streaming loop ────────────────────────────────
async def _log_stream_loop(app: Application) -> None:
    while True:
        await asyncio.sleep(LOG_STREAM_INTERVAL)
        if not _stream_chat_id:
            continue
        try:
            for num in _file_list():
                path = RESULTS_FOLDER / f"log_{num}.txt"
                if not path.exists():
                    continue
                size = path.stat().st_size
                pos = _log_positions.get(num, size)  # new log files: start from end
                if size <= pos:
                    continue
                with open(path, encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    new_text = f.read()
                _log_positions[num] = size
                lines = [l for l in new_text.splitlines() if l.strip()]
                if not lines:
                    continue
                # Send in chunks of 30 lines max
                chunk = "\n".join(lines[-30:])
                if len(chunk) > 3500:
                    chunk = "...\n" + chunk[-3500:]
                await app.bot.send_message(
                    _stream_chat_id,
                    f"<b>Log #{num}</b>\n<pre>{chunk}</pre>",
                    parse_mode="HTML",
                )
        except Exception:
            pass


async def _post_init(app: Application) -> None:
    asyncio.create_task(_log_stream_loop(app))


# ── Auth ──────────────────────────────────────────────────────────
def auth(fn):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if OWNER_ID and update.effective_user.id != OWNER_ID:
            if update.message:
                await update.message.reply_text("Unauthorized.")
            return
        return await fn(update, ctx)
    return wrapper


# ── Status helpers ────────────────────────────────────────────────
def _status_text_and_kb():
    alive = _is_alive()
    files = _file_list()
    streaming = "🔔" if _stream_chat_id else "🔕"
    runner_icon = "🟢 Running" if alive else "🔴 Stopped"
    files_str = " ".join(f"#{n}" for n in files) if files else "none"
    text = (
        f"<b>Runner:</b> {runner_icon}\n"
        f"<b>Live logs:</b> {streaming}\n"
        f"<b>Files queued:</b> {len(files)}\n"
        f"<b>Files:</b> {files_str}"
    )
    btn_toggle = (
        InlineKeyboardButton("⏹ Stop", callback_data="stop")
        if alive else
        InlineKeyboardButton("▶ Start", callback_data="run")
    )
    kb = InlineKeyboardMarkup([[
        btn_toggle,
        InlineKeyboardButton("🔄 Refresh", callback_data="status"),
    ]])
    return text, kb


# ── Command handlers ──────────────────────────────────────────────
@auth
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "<b>Recovery Bot</b>\n\n"
        "/status  — runner state + files\n"
        "/run     — start runner (watch mode)\n"
        "/stop    — stop runner\n"
        "/files   — list queued account files\n"
        "/archive — list processed (archived) files\n"
        "/retry N — requeue file #N from archive\n"
        "/logs    — recent logs  (<code>/logs 2</code> for file #2)\n"
        "/follow  — toggle live log streaming\n"
        "/proxy   — update proxy  (<code>/proxy 1 ip:port:user:pass</code>)\n\n"
        "Send a <code>.txt</code> account file to add it to the queue."
    )


@auth
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text, kb = _status_text_and_kb()
    await update.message.reply_html(text, reply_markup=kb)


@auth
async def cmd_run(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global _stream_chat_id
    if _is_alive():
        await update.message.reply_text("Runner is already running.")
        return
    _start()
    # Auto-enable log streaming for this chat
    _stream_chat_id = update.effective_chat.id
    _set_stream_positions_to_end()
    await update.message.reply_text(
        "✅ Runner started (watch mode).\n"
        "🔔 Live logs enabled automatically — use /follow to toggle."
    )


@auth
async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_alive():
        await update.message.reply_text("Runner is not running.")
        return
    _stop()
    await update.message.reply_text("⏹ Runner stopped.")


@auth
async def cmd_follow(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global _stream_chat_id
    if _stream_chat_id:
        _stream_chat_id = None
        await update.message.reply_text("🔕 Live log streaming disabled.")
    else:
        _stream_chat_id = update.effective_chat.id
        _set_stream_positions_to_end()
        await update.message.reply_text(
            "🔔 Live log streaming enabled.\n"
            "New log lines will be sent here as they appear.\n"
            "Use /follow again to disable."
        )


@auth
async def cmd_proxy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_html(
            "Usage: <code>/proxy &lt;file#&gt; &lt;ip:port:user:pass&gt;</code>\n"
            "Example: <code>/proxy 1 70.36.107.180:46883:user:pass</code>"
        )
        return

    try:
        num = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("First argument must be a file number.")
        return

    proxy = ctx.args[1]
    parts = proxy.split(":")
    if len(parts) != 4:
        await update.message.reply_text(
            "Invalid proxy format. Expected: ip:port:user:pass\n"
            f"Got {len(parts)} parts instead of 4."
        )
        return

    path = RESULTS_FOLDER / f"{num}.txt"
    if not path.exists():
        await update.message.reply_text(f"File #{num} not found.")
        return

    text = path.read_text(encoding="utf-8")
    lines = text.rstrip().splitlines()

    # Find last proxy-like line
    proxy_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].count(".") == 3 and lines[i].count(":") >= 3:
            proxy_idx = i
            break

    if proxy_idx is None:
        await update.message.reply_text("Proxy line not found in file.")
        return

    old_proxy = lines[proxy_idx]
    lines[proxy_idx] = proxy
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    await update.message.reply_html(
        f"✅ Proxy updated for file <b>#{num}</b>\n"
        f"<s>{old_proxy}</s>\n"
        f"<code>{proxy}</code>"
    )


@auth
async def cmd_archive(update: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    entries = _archived_entries()
    if not entries:
        await update.message.reply_text("Archive is empty.")
        return
    lines = []
    for num, ts, path in entries[:30]:  # cap at 30
        try:
            username = path.read_text(encoding="utf-8").splitlines()[0]
        except Exception:
            username = "?"
        # ts format: 20260524_050538 → 05:05:38
        pretty = f"{ts[9:11]}:{ts[11:13]}:{ts[13:15]}" if len(ts) >= 15 else ts
        lines.append(f"📦 <b>#{num}</b> <code>{pretty}</code> — <code>{username}</code>")
    header = f"<b>Archive ({len(entries)} files)</b>\n"
    await update.message.reply_html(header + "\n".join(lines))


@auth
async def cmd_retry(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_html(
            "Usage: <code>/retry &lt;file#&gt;</code>\n"
            "Moves the most recent archived version of that file back to the queue.\n"
            "See /archive for available files."
        )
        return
    try:
        num = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Invalid file number.")
        return

    # Find the most recent archive entry for this num
    entries = [e for e in _archived_entries() if e[0] == num]
    if not entries:
        await update.message.reply_text(f"No archived file #{num} found.")
        return

    src = entries[0][2]  # most recent (sorted newest-first)
    dst = RESULTS_FOLDER / f"{_next_num()}.txt"

    import shutil
    try:
        shutil.copy2(str(src), str(dst))
    except Exception as e:
        await update.message.reply_text(f"❌ Copy failed: {e}")
        return

    username = next((l for l in dst.read_text(encoding="utf-8").splitlines() if l.strip()), "?")
    note = "Runner will pick it up automatically." if _is_alive() else "Use /run to start the runner."
    await update.message.reply_html(
        f"♻️ File #{num} copied from archive → <b>#{dst.stem}</b> (<code>{username}</code>)\n{note}"
    )


@auth
async def cmd_files(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    files = _file_list()
    if not files:
        await update.message.reply_text("No account files found.")
        return
    lines = []
    for n in files:
        p = RESULTS_FOLDER / f"{n}.txt"
        try:
            username = p.read_text(encoding="utf-8").splitlines()[0]
        except Exception:
            username = "?"
        has_log = (RESULTS_FOLDER / f"log_{n}.txt").exists()
        icon = "✅" if has_log else "⏳"
        lines.append(f"{icon} <b>#{n}</b> — <code>{username}</code>")
    await update.message.reply_html("\n".join(lines))


@auth
async def cmd_logs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    files = _file_list()
    if ctx.args:
        try:
            num = int(ctx.args[0])
        except ValueError:
            await update.message.reply_text("Usage: /logs 1")
            return
    elif files:
        num = files[-1]
    else:
        await update.message.reply_text("No files available.")
        return

    log = _last_log(num)
    if len(log) > 3800:
        log = "...\n" + log[-3800:]
    await update.message.reply_html(f"<b>Log #{num}:</b>\n<pre>{log}</pre>")


@auth
async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not (doc.file_name or "").endswith(".txt"):
        await update.message.reply_text("Please send a .txt file.")
        return

    tg_file = await ctx.bot.get_file(doc.file_id)
    buf = io.BytesIO()
    await tg_file.download_to_memory(buf)
    text = buf.getvalue().decode("utf-8", errors="replace")

    ok, err = _validate(text)
    if not ok:
        await update.message.reply_html(f"❌ <b>Invalid file:</b> {err}")
        return

    num = _next_num()
    (RESULTS_FOLDER / f"{num}.txt").write_text(text, encoding="utf-8")
    username = next((l for l in text.splitlines() if l.strip()), "?")
    note = (
        "Runner will pick it up automatically." if _is_alive()
        else "Use /run to start the runner."
    )
    await update.message.reply_html(
        f"✅ Saved as <b>#{num}</b> — <code>{username}</code>\n{note}"
    )


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global _stream_chat_id
    q = update.callback_query
    await q.answer()
    if OWNER_ID and q.from_user.id != OWNER_ID:
        return

    if q.data == "run":
        _start()
        _stream_chat_id = q.message.chat_id
        _set_stream_positions_to_end()
    elif q.data == "stop":
        _stop()

    text, kb = _status_text_and_kb()
    try:
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass


# ── Entry point ───────────────────────────────────────────────────
def main():
    if BOT_TOKEN == "YOUR_TOKEN_HERE":
        print("ERROR: Set BOT_TOKEN in bot.py or TG_BOT_TOKEN env variable.")
        sys.exit(1)

    RESULTS_FOLDER.mkdir(exist_ok=True)

    builder = Application.builder().token(BOT_TOKEN).post_init(_post_init)

    proxy_url = os.getenv("BOT_PROXY", "")
    if proxy_url:
        print(f"Using proxy: {proxy_url}")
        builder = builder.request(HTTPXRequest(proxy=proxy_url))  # type: ignore[arg-type]

    app = builder.build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("run",    cmd_run))
    app.add_handler(CommandHandler("stop",   cmd_stop))
    app.add_handler(CommandHandler("follow",  cmd_follow))
    app.add_handler(CommandHandler("proxy",   cmd_proxy))
    app.add_handler(CommandHandler("files",   cmd_files))
    app.add_handler(CommandHandler("archive", cmd_archive))
    app.add_handler(CommandHandler("retry",   cmd_retry))
    app.add_handler(CommandHandler("logs",    cmd_logs))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("Bot running. Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
