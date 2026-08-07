# 👑 MONARCH PREMIUM — Telegram Control Bot

Terminal bot (`quotex.py`) ke **saare options** Telegram par, premium inline UI ke saath.
Do broker support: **Quotex** (Qx.php candles + Qx ticks) aur **Tradowix** (railway candle API + live ticks).

## Files

```text
quotex.py                    # core engine (broker-select flow added)
telegram_bot/
  monarch_tgbot.py           # bot entry — handlers, callbacks, panels
  tg_ui.py                   # keyboards + HTML panels (premium style)
  tg_engine.py               # quotex.py bridge — auto/manual runner, stop flag
  requirements.txt
  .env.example
  Procfile / runtime.txt     # Railway / Heroku
```

## Install (Termux / VPS)

```bash
pip install -r telegram_bot/requirements.txt
export BOT_TOKEN="8759815176:AAESNRA5N_hfhnk6_5oDrmNNJtzFFxF3lx0"
export OWNER_ID="6417401051"
python telegram_bot/monarch_tgbot.py
```

Token/owner id already default me set hai, so `python telegram_bot/monarch_tgbot.py` seedha bhi chalega.

## Telegram flow

```text
/start  →  MONARCH CONTROL PANEL
  ⚡ Auto Scan   → [🟦 Quotex] [🟩 Tradowix] → scan start
  🎯 Manual      → [🟦 Quotex] [🟩 Tradowix] → pair bhejo → timeframe → watch start
  ⚙️ Settings    → broker / charts / timeframe / risk % / send-before / auto partial
  📊 Stats   🧠 AI Brain   ⏰ Best Times   🔁 Pre-Analysis
  📤 Send Partial   ♻️ Reset Partial   ⛔ Stop Engine
```

- Broker select **hamesha** scan se pehle — direct scan start nahi hota (terminal me bhi same).
- Signals chart + full detail ke saath aate hain; result (WIN/LOSS/MTG) core ke result checker se automatic.
- Sirf owner (`OWNER_ID`) bot use kar sakta hai.

## Terminal bot

```bash
python quotex.py
# 1 Auto scan  → SELECT BROKER (1 Quotex / 2 Tradowix / 3 Back) → scan
# 2 Manual     → SELECT BROKER → pair + timeframe → watch
```

## GitHub upload

```bash
git init && git add quotex.py telegram_bot
git commit -m "Monarch premium bot + telegram control bot"
git branch -M main && git remote add origin <your-repo-url> && git push -u origin main
```