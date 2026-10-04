# 🛡️ ScamShield — built for my mum (Hacktoberfest Weekend Challenge)

Forward any suspicious SMS / link / wallet address to the Telegram bot, get a
verdict in seconds: **SCAM / SUSPICIOUS / LIKELY SAFE** with reasons in Thai +
English, grounded receipts, and what to do next.

## Why open-source AI is the core

- Triage runs on an **open-weight model (Gemma 3)** via any OpenAI-compatible
  endpoint (Ollama locally, 1-Click model, `GEMMA_BASE_URL`). No family chat
  needs to live on a closed server to stay safe.
- **Local-first fallback:** the rule engine (pressure tactics, shorteners,
  impersonation, on-chain probes) works offline and is labelled honestly, so
  the demo never fakes intelligence.
- Swap models, self-host, inspect every rule — impossible with a closed API.

## Live

- Bot: `https://t.me/<your-bot>` (after deploy, put real link here)
- Dashboard: `https://scamshield.onrender.com` (health + verdict feed, 0 credits burned)

## Run locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill TELEGRAM_BOT_TOKEN (BotFather)
python app.py
```

## Deploy (Render)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/memeshee/scamshield)

Free credits: claim at hacktoberfest.com/my. `render.yaml` sets the web
service; add `TELEGRAM_BOT_TOKEN` (+ optional `SERPAPI_KEY`, `SENTRY_DSN`,
`GEMMA_BASE_URL`) in the Render dashboard.

## Categories entered

SerpApi (live search grounding) · Sentry Agent Tracing (traces in write-up) ·
Mastra-style agent orchestration · Render (hosting) · Gemma (open-weight core)

## Demo script (judges, 60s)

1. `/start` → intro in Thai
2. Forward Thai parcel-scam SMS with `bit.ly` link → 🚨 SCAM + receipts
3. Send `0x...` drainer address → contract hit via public RPC
4. Send benign family message → ✅ LIKELY SAFE
5. Open `/` dashboard → verdict feed updates live
