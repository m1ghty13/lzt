"""
Telegram bot for managing the RuneScape account recovery runner.

Setup:
  1. Create a bot via @BotFather, copy the token
  2. Find your Telegram user ID via @userinfobot
  3. Fill BOT_TOKEN and OWNER_ID below (or set env vars TG_BOT_TOKEN / TG_OWNER_ID)
  4. python bot.py

Commands:
  /status  — runner state + queued files
  /run     — start runner in watch mode
  /stop    — stop runner
  /files   — list all account files
  /logs    — last log lines  (/logs 2 for file #2)
  Upload a .txt file — validates and adds to queue
"""

import asyncio
import io
import os
import subprocess
import sys
import signal
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ── Config ──────────────────────────────────────────────────────
BOT_TOKEN  = os.getenv("TG_BOT_TOKEN",  "YOUR_TOKEN_HERE")
OWNER_ID   = int(os.getenv("TG_OWNER_ID", "0"))   # your Telegram numeric user ID

RESULTS_FOLDER = Path(__file__).parent / "results"
RUNNER_SCRIPT  = Path(__file__).parent / "run.py"
PID_FILE       = Path(__file__).parent / ".runner.pid"

# ── Process tracking ─────────────────────────────────────────────
_proc: subprocess.Popen | None = None


def _is_alive() -> bool:
    global _proc
    if _proc is not None:
        if _proc.poll() is None:
            return True
        _proc = None
    # Fallback: check PID file (survives bot restart)
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


# ── File helpers ─────────────────────────────────────────────────
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
    return True, proxy.split(":")[0]  # returns proxy host as info


def _last_log(num: int, n: int = 35) -> str:
    path = RESULTS_FOLDER / f"log_{num}.txt"
    if not path.exists():
        return f"No log found for #{num}"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = lines[-n:] if len(lines) > n else lines
    return "\n".join(tail)


# ── Auth ─────────────────────────────────────────────────────────
def auth(fn):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if OWNER_ID and update.effective_user.id != OWNER_ID:
            if update.message:
                await update.message.reply_text("Unauthorized.")
            return
        return await fn(update, ctx)
    return wrapper


# ── Status keyboard ───────────────────────────────────────────────
def _status_text_and_kb():
    alive = _is_alive()
    files = _file_list()
    runner_icon = "🟢 Running" if alive else "🔴 Stopped"
    files_str = " ".join(f"#{n}" for n in files) if files else "none"
    text = (
        f"<b>Runner:</b> {runner_icon}\n"
        f"<b>Files queued:</b> {len(files)}\n"
        f"<b>Files:</b> {files_str}"
    )
    btn_toggle = (
        InlineKeyboardButton("⏹ Stop", callback_data="stop")
        if alive else
        InlineKeyboardButton("▶ Start", callback_data="run")
    )
    kb = InlineKeyboardMarkup([[btn_toggle, InlineKeyboardButton("🔄 Refresh", callback_data="status")]])
    return text, kb


# ── Handlers ─────────────────────────────────────────────────────
@auth
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "<b>Recovery Bot</b>\n\n"
        "/status — runner state + files\n"
        "/run    — start runner (watch mode)\n"
        "/stop   — stop runner\n"
        "/files  — list account files\n"
        "/logs   — recent logs  (<code>/logs 2</code> for file #2)\n\n"
        "Send a <code>.txt</code> account file to add it to the queue."
    )


@auth
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text, kb = _status_text_and_kb()
    await update.message.reply_html(text, reply_markup=kb)


@auth
async def cmd_run(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if _is_alive():
        await update.message.reply_text("Runner is already running.")
        return
    _start()
    await update.message.reply_text("✅ Runner started (watch mode).")


@auth
async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_alive():
        await update.message.reply_text("Runner is not running.")
        return
    _stop()
    await update.message.reply_text("⏹ Runner stopped.")


@auth
async def cmd_files(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    files = _file_list()
    if not files:
        await update.message.reply_text("No account files found.")
        return
    lines = []
    for n in files:
        path = RESULTS_FOLDER / f"{n}.txt"
        try:
            username = path.read_text(encoding="utf-8").splitlines()[0]
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

    ok, info = _validate(text)
    if not ok:
        await update.message.reply_html(f"❌ <b>Invalid file:</b> {info}")
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
    q = update.callback_query
    await q.answer()
    if OWNER_ID and q.from_user.id != OWNER_ID:
        return

    if q.data == "run":
        _start()
    elif q.data == "stop":
        _stop()

    # Always refresh status message
    text, kb = _status_text_and_kb()
    try:
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass


# ── Entry point ───────────────────────────────────────────────────
def main():
    if BOT_TOKEN == "YOUR_TOKEN_HERE":
        print("ERROR: Set BOT_TOKEN in bot.py or TG_BOT_TOKEN env variable.")
        print("       Set OWNER_ID in bot.py or TG_OWNER_ID env variable.")
        sys.exit(1)

    RESULTS_FOLDER.mkdir(exist_ok=True)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("run",    cmd_run))
    app.add_handler(CommandHandler("stop",   cmd_stop))
    app.add_handler(CommandHandler("files",  cmd_files))
    app.add_handler(CommandHandler("logs",   cmd_logs))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("Bot running. Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
