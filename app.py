"""ScamShield service: FastAPI health + dashboard, Telegram polling in lifespan.

Render runs:  uvicorn app:app --host 0.0.0.0 --port $PORT
Local runs:   python app.py  (polling)  or  uvicorn app:app --port 8000
"""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
import sentry_sdk  # noqa: E402

DSN = os.getenv("SENTRY_DSN", "").strip()
if DSN:
    sentry_sdk.init(dsn=DSN, traces_sample_rate=1.0, profiles_sample_rate=0.2)

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402

DB = Path(__file__).with_name("verdicts.db")
STARTED = time.time()
BOT_TASK_ERR: str | None = None

log = logging.getLogger("scamshield")


class _DemotePollConflict(logging.Filter):
    """Render restarts overlap: old + new instance poll briefly, Telegram
    kills one getUpdates stream. Benign and self-healing — keep it out of
    Sentry (error level) while staying visible as a warning in logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if "terminated by other getUpdates request" in record.getMessage():
                record.levelno = logging.WARNING
                record.levelname = "WARNING"
        except Exception:
            pass
        return True


logging.getLogger("telegram.ext.Updater").addFilter(_DemotePollConflict())


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB)
    c.execute(
        "CREATE TABLE IF NOT EXISTS verdicts"
        "(id INTEGER PRIMARY KEY, chat_id TEXT, level TEXT, score INT,"
        " preview TEXT, created REAL)"
    )
    return c


def save_verdict(chat_id: str, level: str, score: int, preview: str) -> None:
    try:
        c = db()
        c.execute(
            "INSERT INTO verdicts(chat_id, level, score, preview, created)"
            " VALUES (?,?,?,?,?)",
            (str(chat_id), level, score, (preview or "")[:300], time.time()),
        )
        c.commit()
        c.close()
    except Exception:
        log.exception("save_verdict failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    async def poll() -> None:
        global BOT_TASK_ERR
        try:
            from bot import build_app

            tg = build_app()
            if tg is None:
                log.warning("polling disabled: TELEGRAM_BOT_TOKEN not set")
                return
            await tg.initialize()
            await tg.start()
            assert tg.updater is not None
            await tg.updater.start_polling(drop_pending_updates=True)
            log.warning("telegram polling up")
            while True:
                await asyncio.sleep(3600)
        except Exception as e:  # surfaced on /health so Render deploys visibly fail
            BOT_TASK_ERR = f"{type(e).__name__}: {e}"
            log.exception("telegram polling crashed")

    task = asyncio.create_task(poll())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    tok = bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip())
    body: dict = {
        "ok": BOT_TASK_ERR is None,
        "uptime_s": int(time.time() - STARTED),
        "token_set": tok,
        "poller_error": BOT_TASK_ERR,
        "gemma": bool(os.getenv("GEMMA_BASE_URL", "").strip()),
        "serpapi": bool(os.getenv("SERPAPI_KEY", "").strip()),
    }
    return JSONResponse(body, status_code=200 if body["ok"] else 500)


@app.get("/api/verdicts")
def verdicts(limit: int = 20):
    try:
        c = db()
        rows = c.execute(
            "SELECT level, score, preview, created FROM verdicts"
            " ORDER BY id DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
        c.close()
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=200)
    return {
        "verdicts": [
            {"level": l, "score": s, "preview": p, "created": t} for l, s, p, t in rows
        ]
    }


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>ScamShield 🛡️ live</title><style>body{font-family:system-ui;max-width:640px;margin:24px auto;padding:0 16px}</style>
<h1>🛡️ ScamShield is live</h1>
<p>Forward any suspicious message to the Telegram bot. Latest verdicts load below (page never spends API credits).</p>
<p><a href="/health">health</a> · <a href="/api/verdicts">verdicts json</a></p>
<ul id=v></ul><script>
setInterval(async()=>{try{const j=await(await fetch('/api/verdicts')).json();
v.innerHTML=(j.verdicts||[]).map(x=>`<li><b>${x.level}</b> ${x.score} — ${x.preview||''}</li>`).join('')||'<li>no checks yet — be the first</li>'}catch(e){}},2000)
</script>"""


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
