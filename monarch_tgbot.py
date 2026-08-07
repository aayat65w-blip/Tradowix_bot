# ============================================================
#   MONARCH PREMIUM — TELEGRAM CONTROL BOT
#   Terminal ke saare options, premium inline UI ke saath.
#   Brokers: Quotex  |  Tradowix   (dono ke apne candle + tick API)
# ============================================================
import os
import sys
import time
import telebot

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tg_ui as ui
from tg_engine import Engine, esc

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8759815176:AAESNRA5N_hfhnk6_5oDrmNNJtzFFxF3lx0")
OWNER_ID = int(os.environ.get("OWNER_ID", "6417401051"))

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


def notify(text, kb=None):
    try:
        bot.send_message(OWNER_ID, text, reply_markup=kb, disable_web_page_preview=True)
    except Exception as e:
        print("notify error:", e)


ENG = Engine(notify)
ENG.bind_telegram(BOT_TOKEN, OWNER_ID)
STATE = {"await": None, "broker": None}


def owner_only(fn):
    def wrap(obj):
        uid = obj.from_user.id if obj.from_user else 0
        if uid != OWNER_ID:
            try:
                if hasattr(obj, "data"):
                    bot.answer_callback_query(obj.id, "⛔ Owner only bot.")
                else:
                    bot.reply_to(obj, "⛔ Yeh private bot hai.")
            except Exception:
                pass
            return
        return fn(obj)
    return wrap


def home_text():
    return ui.main_panel(ENG.cfg, ENG.broker_label(), ENG.running(), ENG.mode,
                         ENG.version(), ENG.weekday(), ENG.clock(), ENG.session())


def show_home(chat_id, msg_id=None):
    if msg_id:
        try:
            bot.edit_message_text(home_text(), chat_id, msg_id,
                                  reply_markup=ui.main_kb(ENG.running()))
            return
        except Exception:
            pass
    bot.send_message(chat_id, home_text(), reply_markup=ui.main_kb(ENG.running()))


@bot.message_handler(commands=["start", "menu", "panel", "home"])
@owner_only
def cmd_start(m):
    STATE["await"] = None
    show_home(m.chat.id)


@bot.message_handler(commands=["stop"])
@owner_only
def cmd_stop(m):
    ENG.stop()
    bot.reply_to(m, "⛔ Stop signal bhej diya — engine ruk raha hai.")


@bot.callback_query_handler(func=lambda c: True)
@owner_only
def on_cb(c):
    data = c.data or ""
    chat, mid = c.message.chat.id, c.message.message_id
    try:
        bot.answer_callback_query(c.id)
    except Exception:
        pass

    # ── main menu ───────────────────────────────────────────
    if data == "m:home":
        STATE["await"] = None
        return show_home(chat, mid)

    if data == "m:stop":
        ENG.stop()
        return bot.edit_message_text("⛔ <b>Engine stop ho raha hai…</b>", chat, mid,
                                     reply_markup=ui.back_kb())

    if data in ("m:auto", "m:manual", "m:calib"):
        if data != "m:calib" and ENG.running():
            return bot.edit_message_text(
                f"⚠️ <b>{ENG.mode}</b> already chal raha hai — pehle ⛔ se stop karo.",
                chat, mid, reply_markup=ui.stop_kb())
        mode_key = {"m:auto": "auto", "m:manual": "manual", "m:calib": "calib"}[data]
        title = {"auto": "AUTO SCAN", "manual": "MANUAL SIGNAL",
                 "calib": "PRE-ANALYSIS"}[mode_key]
        return bot.edit_message_text(ui.broker_panel(title, ENG.broker_label()), chat, mid,
                                     reply_markup=ui.broker_kb(mode_key))

    if data == "m:settings":
        return bot.edit_message_text(ui.settings_panel(ENG.cfg, ENG.broker_label()), chat, mid,
                                     reply_markup=ui.settings_kb(ENG.cfg, ENG.timeframes()))

    if data == "m:stats":
        return bot.edit_message_text(ui.block("📊 STATS + DAY PROFILE", esc(ENG.stats_text())),
                                     chat, mid, reply_markup=ui.back_kb())

    if data == "m:ai":
        return bot.edit_message_text(ui.block("🧠 AI BRAIN + ACCURACY", esc(ENG.ai_text())),
                                     chat, mid, reply_markup=ui.back_kb())

    if data == "m:times":
        return bot.edit_message_text(ui.block("⏰ BEST TRADING TIMES", esc(ENG.times_text())),
                                     chat, mid, reply_markup=ui.back_kb())

    if data == "m:partial":
        return bot.edit_message_text(ENG.send_partial(), chat, mid, reply_markup=ui.back_kb())

    if data == "m:reset":
        return bot.edit_message_text(ENG.reset_partial(), chat, mid, reply_markup=ui.back_kb())

    # ── broker chosen ───────────────────────────────────────
    if data.startswith("b:"):
        _, mode_key, broker = data.split(":")
        STATE["broker"] = broker
        label = ENG.broker_label(broker)

        if mode_key == "auto":
            bot.edit_message_text(
                f"⚡ <b>AUTO SCAN</b> starting on <b>{label}</b>…\n"
                f"<i>Pairs check + pre-analysis + AI training — 1-3 min lag sakta hai.</i>",
                chat, mid, reply_markup=ui.stop_kb())
            ENG.start_auto(broker)
            return

        if mode_key == "manual":
            bot.edit_message_text(f"🎯 <b>MANUAL SIGNAL</b> • {label}\n"
                                  f"<i>Live pairs load ho rahe hain…</i>", chat, mid)
            pairs = ENG.live_pairs(broker)
            if not pairs:
                return bot.send_message(chat, "❌ Is broker par abhi koi live pair nahi.",
                                        reply_markup=ui.back_kb())
            STATE["await"] = "pair"
            sample = ", ".join(pairs[:24])
            return bot.send_message(
                chat,
                f"🎯 <b>{label}</b> — pair ka naam bhejo (jaise <code>EURUSD-OTC</code>)\n"
                f"{ui.LINE}\n<b>Live pairs:</b>\n<code>{esc(sample)}</code>",
                reply_markup=ui.back_kb())

        if mode_key == "calib":
            bot.edit_message_text(f"🔁 <b>Pre-analysis + AI retrain</b> on {label}…",
                                  chat, mid, reply_markup=ui.back_kb())
            return notify(ENG.recalibrate(broker), ui.back_kb())

    # ── manual timeframe pick ───────────────────────────────
    if data.startswith("mtf:"):
        tf = data.split(":")[1]
        pair = STATE.get("pair")
        broker = STATE.get("broker") or ENG.cfg.get("broker")
        if not pair:
            return show_home(chat, mid)
        bot.edit_message_text(
            f"🎯 <b>MANUAL WATCH</b>\n🏦 {ENG.broker_label(broker)} • "
            f"<b>{esc(pair)}</b> • {tf}\n<i>Engine start ho raha hai…</i>",
            chat, mid, reply_markup=ui.stop_kb())
        ENG.start_manual(broker, pair, tf)
        return

    # ── settings ────────────────────────────────────────────
    if data.startswith("s:"):
        parts = data.split(":")
        key = parts[1]
        if key == "charts":
            ENG.cfg["charts"] = not ENG.cfg.get("charts")
        elif key == "autopartial":
            ENG.cfg["auto_partial"] = not ENG.cfg.get("auto_partial")
        elif key == "tf":
            ENG.cfg["timeframe"] = parts[2]
        elif key == "risk":
            v = int(ENG.cfg.get("max_loss_prob", 0.35) * 100) + int(parts[2])
            ENG.cfg["max_loss_prob"] = max(20, min(45, v)) / 100.0
        elif key == "sb":
            v = int(ENG.cfg.get("send_before", 10)) + int(parts[2])
            ENG.cfg["send_before"] = max(5, min(30, v))
        elif key == "broker":
            return bot.edit_message_text(ui.broker_panel("DEFAULT BROKER", ENG.broker_label()),
                                         chat, mid, reply_markup=ui.broker_kb("set"))
        ENG.save()
        return bot.edit_message_text(ui.settings_panel(ENG.cfg, ENG.broker_label()), chat, mid,
                                     reply_markup=ui.settings_kb(ENG.cfg, ENG.timeframes()))

    if data.startswith("b:set:"):
        ENG.set_broker(data.split(":")[2])
        return bot.edit_message_text(ui.settings_panel(ENG.cfg, ENG.broker_label()), chat, mid,
                                     reply_markup=ui.settings_kb(ENG.cfg, ENG.timeframes()))


@bot.message_handler(func=lambda m: True, content_types=["text"])
@owner_only
def on_text(m):
    if STATE.get("await") != "pair":
        return show_home(m.chat.id)
    pairs = ENG.live_pairs()
    pair = ENG.match_pair(m.text.strip(), pairs)
    if not pair:
        return bot.reply_to(m, "❌ Yeh pair live list me nahi hai — dobara bhejo.",
                            reply_markup=ui.back_kb())
    STATE["await"] = None
    STATE["pair"] = pair
    bot.send_message(m.chat.id, f"✅ Pair: <b>{esc(pair)}</b>\n⏱ Timeframe choose karo:",
                     reply_markup=ui.tf_kb(ENG.timeframes()))


if __name__ == "__main__":
    print(f"● {ENG.version()} telegram bot starting… owner={OWNER_ID}")
    notify("👑 <b>MONARCH TELEGRAM BOT ONLINE</b>\nSend /start to open the control panel.")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
        except Exception as e:
            print("polling error:", e)
            time.sleep(5)