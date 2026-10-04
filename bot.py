"""Telegram handlers: hardened per telegram-bots skill (timeouts, guards, error handler)."""
from __future__ import annotations

import logging
import os
import traceback

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from app import save_verdict
from triage import triage, verdict_card

log = logging.getLogger("scamshield.bot")

INTRO = (
    "🛡️ *ScamShield* — ส่งข้อความน่าสงสัยมาได้เลย\n"
    "Forward any suspicious SMS / link / wallet address here.\n\n"
    "• ส่งข้อความหรือฟอร์เวิร์ดมา → ได้คำตอบในไม่กี่วิ\n"
    "• `/check <ข้อความ>` — ตรวจแบบระบุข้อความ\n"
    "• `/help` — วิธีใช้\n\n"
    "— built for my mum, Hacktoberfest Weekend Challenge 🤝"
)


def build_app() -> Application | None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return None
    req = HTTPXRequest(connect_timeout=20, read_timeout=30, write_timeout=30, pool_timeout=20)
    app = Application.builder().token(token).request(req).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    return app


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await update.message.reply_text(INTRO, parse_mode="Markdown")
    except Exception:
        log.exception("start failed")
        try:
            await update.message.reply_text("retry — ส่งใหม่ได้เลย")
        except Exception:
            pass


async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").split(" ", 1)
    if len(text) < 2 or not text[1].strip():
        await update.message.reply_text("ใช้แบบนี้: `/check มีลิงก์ลดราคาบอกให้โอนด่วน`", parse_mode="Markdown")
        return
    await run_triage(update, text[1].strip())


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await run_triage(update, update.message.text or "")


async def run_triage(update: Update, text: str) -> None:
    status = None
    try:
        status = await update.message.reply_text("🔍 กำลังตรวจ… / Checking…")
    except Exception:
        log.exception("status send failed")
    try:
        import asyncio

        result = await asyncio.wait_for(asyncio.to_thread(triage, text), timeout=120)
        card = verdict_card(text, result)
        try:
            save_verdict(
                str(update.effective_chat.id if update.effective_chat else "?"),
                result["level"],
                result["score"],
                text[:200],
            )
        except Exception:
            pass
        if status is not None:
            await status.edit_text(card, parse_mode="Markdown")
        else:
            await update.message.reply_text(card, parse_mode="Markdown")
    except Exception:
        log.exception("triage failed")
        tb = traceback.format_exc(limit=3)
        log.warning("triage traceback: %s", tb)
        msg = "❌ ตรวจไม่สำเร็จ ลองส่งใหม่อีกครั้ง / failed — please retry"
        try:
            if status is not None:
                await status.edit_text(msg)
            else:
                await update.message.reply_text(msg)
        except Exception:
            pass


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("update failed: %s", ctx.error)
    try:
        if isinstance(update, Update) and update.message:
            await update.message.reply_text("retry — ระบบสะดุด ส่งใหม่ได้เลย")
    except Exception:
        pass
