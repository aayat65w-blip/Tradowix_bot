#!/usr/bin/env bash
# MONARCH TELEGRAM BOT — one click start (Termux / Linux)
set -e
cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

if [ -z "$BOT_TOKEN" ]; then
  read -rp "Bot token: " BOT_TOKEN
  export BOT_TOKEN
fi
if [ -z "$OWNER_ID" ]; then
  read -rp "Your chat id (blank = pehla /start wala owner): " OWNER_ID
  export OWNER_ID
fi

python -m pip install -r requirements.txt --quiet || pip install -r requirements.txt
exec python telegram_bot.py
