# MONARCH PREMIUM BOT — TELEGRAM EDITION (v50.0 AI SNIPER)

Poora TRADOWIX AI engine ab Telegram par — buttons se sab kuch control.

## Files

| File | Kaam |
|---|---|
| `telegram_bot.py` | Telegram front-end (menu, buttons, engine control) — **yehi run karna hai** |
| `monarch_core.py` | Pura trading engine (v50 AI Sniper — 4700+ lines, kuch nahi hata) |
| `requirements.txt` | Dependencies |
| `.env.example` | Token / owner id sample |
| `start.sh` | Termux / Linux ek-click start |
| `Procfile`, `runtime.txt`, `Dockerfile` | Railway / Render / Docker deploy |

## 1. Bot banao

1. Telegram me **@BotFather** kholo → `/newbot` → naam do → **BOT TOKEN** milega.
2. **@userinfobot** ko `/start` bhejo → apna **chat id** (OWNER_ID) note karo.

## 2. Termux / Mobile me chalao

```bash
pkg update && pkg install python git -y
git clone https://github.com/<tumhara-username>/<repo>.git
cd <repo>
pip install -r requirements.txt
export BOT_TOKEN="123456:AA...tumhara_token"
export OWNER_ID="123456789"
python telegram_bot.py
```

Ya `start.sh` use karo:

```bash
chmod +x start.sh && ./start.sh
```

Agar `OWNER_ID` na do, to jo pehla banda bot ko `/start` karega wahi owner ban jayega.

## 3. Telegram me kya milega

`/start` bhejte hi full menu:

- 🚀 **Auto Scan** — 3-din pre-analysis + AI training + har candle se 10s pehle best signal
- 🎯 **Manual Pair** — koi bhi live pair chuno, sirf usi ko watch karega
- 📡 **Live Status** — engine, route, next candle, live trade, cutoff, AI gate
- 📊 **Stats** — win/loss, win-rate, day family profile
- 🧠 **AI Brain** — model accuracy, live learning, pattern memory, accuracy guard
- ⏰ **Best Times** — kaunse ghante me best signal (power score)
- 📤 **Send Partial** / ♻️ **Reset Partial**
- 🔁 **Re-Analysis** (pre-analysis + AI retrain) / 🌐 **Test Route**
- ⚙️ **Settings** — timeframe, charts, max loss-risk %, send-before sec, strict mode, AI on/off, proxy
- 📋 **Pairs**, 📜 **Last Signals**, 🗒 **Logs**, ❓ **Help**

Commands bhi hain: `/auto /manual /stop /status /stats /ai /times /partial /reset /pairs /settings /recalib /route /logs /id /help`

Signal, chart aur RESULT messages apne aap owner chat me aate hain (chart ON hai to photo ke saath).

## 4. Accuracy high rakhne ke rules

1. Bot har 8 ghante me AI model auto-retrain karta hai — 🔁 Re-Analysis se turant bhi.
2. Har result se live model + pattern memory seekhta hai (jitna chalega utna sharp).
3. Rolling accuracy 80% se niche gayi → gate khud strict, 68% se niche → emergency mode.
4. 3 back-to-back miss wale pair 45 min auto-suspend.
5. ⏰ Best Times me power **66+** wale ghante me hi zyada trade karo.
6. Ek hi settings par roz chalao — bar-bar badalne se learning reset ho jati hai.
7. Payout 75%+ aur stable internet — verification miss = learning miss.
8. Ek time par ek hi trade — bot khud result aane tak naya signal nahi bhejta.

## 5. Deploy (24/7)

**Railway / Render**: repo connect karo, env me `BOT_TOKEN` + `OWNER_ID` daalo. `Procfile` already hai (`worker: python telegram_bot.py`).

**Docker**:

```bash
docker build -t monarch-tg .
docker run -e BOT_TOKEN=xxx -e OWNER_ID=yyy monarch-tg
```

## 6. Notes

- Proxy ki zarurat nahi — bot khud working API route dhundhta hai (Settings → Proxy me manual bhi de sakte ho).
- Broker clock UTC+6 hai; badalna ho to `TRADOWIX_TZ` env set karo.
- `monarch_*.json` files bot khud banata hai (config, results, AI model, calibration) — inhe GitHub par upload mat karo (`.gitignore` me already hain).
