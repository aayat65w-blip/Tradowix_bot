import logging
import os
import threading
import time

import telebot
from telebot.apihelper import ApiTelegramException

import tg_ui as ui
from tg_engine import Engine, esc

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("monarch.telegram")

# Prefer Railway Variables; fallback rakha hai taaki local run bhi chale.
BOT_TOKEN = (os.environ.get("BOT_TOKEN") or "8759815176:AAESNRA5N_hfhnk6_5oDrmNNJtzFFxF3lx0").strip()
OWNER_ID_RAW = (os.environ.get("OWNER_ID") or "6417401051").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Add it in Railway Variables.")
if not OWNER_ID_RAW.isdigit():
    raise RuntimeError("OWNER_ID must be a numeric Telegram user ID in Railway Variables.")
OWNER_ID = int(OWNER_ID_RAW)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True)


def notify(text):
    try:
        bot.send_message(OWNER_ID, text, disable_web_page_preview=True)
    except Exception:
        log.exception("Could not send engine notification")


engine = Engine(notify)
engine.bind_telegram(BOT_TOKEN, OWNER_ID)
manual_selection = {}


def is_owner(user_id):
    return user_id == OWNER_ID


def panel_text():
    return ui.main_panel(
        engine.cfg,
        engine.broker_label(),
        engine.running(),
        engine.mode,
        engine.version(),
        engine.weekday(),
        engine.clock(),
        engine.session(),
    )


def send_home(chat_id, message_id=None):
    if message_id is not None:
        try:
            bot.edit_message_text(panel_text(), chat_id, message_id, reply_markup=ui.main_kb(engine.running()))
            return
        except Exception:
            pass
    bot.send_message(chat_id, panel_text(), reply_markup=ui.main_kb(engine.running()))


def edit(call, text, keyboard=None):
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard)


def safe_block(title, body):
    return ui.block(title, esc(body)[:3500])


@bot.message_handler(commands=["start", "menu", "help"])
def start(message):
    if not is_owner(message.from_user.id):
        bot.send_message(message.chat.id, "⛔ This bot is private.")
        return
    send_home(message.chat.id)


@bot.callback_query_handler(func=lambda call: (call.data or "").startswith("mtf:"))
def manual_timeframe(call):
    if not is_owner(call.from_user.id):
        return
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    selected = manual_selection.get(call.message.chat.id, "")
    if "|" not in selected:
        bot.send_message(call.message.chat.id, "⚠️ Choose Manual Signal and pair again.", reply_markup=ui.back_kb())
        return
    broker, pair = selected.split("|", 1)
    tf = call.data.split(":", 1)[-1]
    if engine.start_manual(broker, pair, tf):
        edit(call, f"🎯 <b>Manual watch starting</b>\n{esc(pair)} • {esc(tf)}", ui.stop_kb())
    else:
        bot.send_message(call.message.chat.id, "⚠️ Engine is already running.", reply_markup=ui.stop_kb())


@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    if not is_owner(call.from_user.id):
        try:
            bot.answer_callback_query(call.id, "Private bot", show_alert=True)
        except Exception:
            pass
        return
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    data = call.data or ""
    chat_id = call.message.chat.id
    try:
        if data == "m:home":
            send_home(chat_id, call.message.message_id)
        elif data == "m:auto":
            edit(call, ui.broker_panel("AUTO SCAN", engine.broker_label()), ui.broker_kb("auto"))
        elif data == "m:manual":
            edit(call, ui.broker_panel("MANUAL SIGNAL", engine.broker_label()), ui.broker_kb("manual"))
        elif data.startswith("b:auto:"):
            broker = data.rsplit(":", 1)[-1]
            if engine.start_auto(broker):
                edit(call, "⚡ <b>Auto scan starting…</b>", ui.stop_kb())
            else:
                bot.send_message(chat_id, "⚠️ Engine is already running.", reply_markup=ui.stop_kb())
        elif data.startswith("b:manual:"):
            broker = data.rsplit(":", 1)[-1]
            engine.set_broker(broker)
            pairs = engine.live_pairs()
            preview = ", ".join(pairs[:30]) if pairs else "No live pairs returned yet"
            msg = bot.send_message(
                chat_id, f"🎯 <b>Send a pair name</b>\n<code>{esc(preview)}</code>", reply_markup=ui.back_kb()
            )
            manual_selection[chat_id] = broker
            bot.register_next_step_handler(msg, receive_manual_pair)
        elif data == "m:settings":
            show_settings(call)
        elif data == "m:stats":
            edit(call, safe_block("📊 STATS", engine.stats_text()), ui.back_kb())
        elif data == "m:ai":
            edit(call, safe_block("🧠 AI BRAIN", engine.ai_text()), ui.back_kb())
        elif data == "m:times":
            edit(call, safe_block("⏰ BEST TIMES", engine.times_text()), ui.back_kb())
        elif data == "m:calib":
            edit(call, "🔁 <b>Pre-analysis running…</b>", ui.back_kb())
            threading.Thread(target=run_calibration, args=(chat_id,), daemon=True).start()
        elif data == "m:partial":
            bot.send_message(chat_id, engine.send_partial(), reply_markup=ui.back_kb())
        elif data == "m:reset":
            bot.send_message(chat_id, engine.reset_partial(), reply_markup=ui.back_kb())
        elif data == "m:stop":
            engine.stop()
            bot.send_message(chat_id, "⛔ Stop requested. Current task will close safely.", reply_markup=ui.back_kb())
        elif data == "s:broker":
            edit(call, ui.broker_panel("SETTINGS", engine.broker_label()), ui.broker_kb("setting"))
        elif data.startswith("b:setting:"):
            engine.set_broker(data.rsplit(":", 1)[-1])
            show_settings(call)
        elif data == "s:charts":
            engine.cfg["charts"] = not engine.cfg.get("charts", True)
            engine.save()
            show_settings(call)
        elif data == "s:autopartial":
            engine.cfg["auto_partial"] = not engine.cfg.get("auto_partial", True)
            engine.save()
            show_settings(call)
        elif data.startswith("s:tf:"):
            engine.cfg["timeframe"] = data.rsplit(":", 1)[-1]
            engine.save()
            show_settings(call)
        elif data.startswith("s:risk:"):
            current = float(engine.cfg.get("max_loss_prob", 0.35))
            engine.cfg["max_loss_prob"] = min(0.8, max(0.05, current + int(data.rsplit(":", 1)[-1]) / 100))
            engine.save()
            show_settings(call)
        elif data.startswith("s:sb:"):
            current = int(engine.cfg.get("send_before", 10))
            engine.cfg["send_before"] = min(50, max(5, current + int(data.rsplit(":", 1)[-1])))
            engine.save()
            show_settings(call)
    except Exception as exc:
        log.exception("Callback failed: %s", data)
        bot.send_message(chat_id, f"⚠️ <b>Error</b>\n<code>{esc(exc)}</code>", reply_markup=ui.back_kb())


def show_settings(call):
    edit(call, ui.settings_panel(engine.cfg, engine.broker_label()), ui.settings_kb(engine.cfg, engine.timeframes()))


def run_calibration(chat_id):
    try:
        result = engine.recalibrate()
    except Exception as exc:
        result = f"⚠️ Calibration failed: {exc}"
        log.exception("Calibration failed")
    bot.send_message(chat_id, esc(result), reply_markup=ui.back_kb())


def receive_manual_pair(message):
    if not message.from_user or not is_owner(message.from_user.id):
        return
    if (message.text or "").startswith("/"):
        send_home(message.chat.id)
        return
    broker = manual_selection.get(message.chat.id, engine.cfg.get("broker", "tradowix"))
    if "|" in broker:
        broker = broker.split("|", 1)[0]
    try:
        pairs = engine.live_pairs(broker)
        pair = engine.match_pair(message.text or "", pairs)
    except Exception as exc:
        bot.send_message(message.chat.id, f"⚠️ Pair lookup failed: <code>{esc(exc)}</code>", reply_markup=ui.back_kb())
        return
    if not pair:
        bot.send_message(message.chat.id, "❌ Pair not found. Open Manual Signal and try again.", reply_markup=ui.back_kb())
        return
    manual_selection[message.chat.id] = f"{broker}|{pair}"
    bot.send_message(
        message.chat.id, f"Pair: <b>{esc(pair)}</b>\nChoose timeframe:", reply_markup=ui.tf_kb(engine.timeframes())
    )


def prepare_polling():
    """Webhook hatao aur purane updates drop karo (409 Conflict ka main fix)."""
    for attempt in range(5):
        try:
            bot.remove_webhook()
            time.sleep(1)
            bot.delete_webhook(drop_pending_updates=True)
            return True
        except ApiTelegramException as exc:
            log.warning("remove_webhook failed (%s), retry %s/5", exc, attempt + 1)
            time.sleep(3)
        except Exception as exc:
            log.warning("remove_webhook error (%s), retry %s/5", exc, attempt + 1)
            time.sleep(3)
    return False


def run():
    log.info("Starting Telegram polling")
    backoff = 5
    while True:
        try:
            prepare_polling()
            # skip_pending hata diya: wo internally get_updates karta hai aur
            # 409 Conflict par crash hota tha. drop_pending_updates isi kaam ko safe way me karta hai.
            bot.infinity_polling(timeout=30, long_polling_timeout=30, allowed_updates=None)
            backoff = 5
        except KeyboardInterrupt:
            log.info("Shutting down")
            raise
        except ApiTelegramException as exc:
            if getattr(exc, "error_code", None) == 409:
                log.error("409 Conflict: bot ka doosra instance chal raha hai. Waiting %ss", backoff)
            elif getattr(exc, "error_code", None) == 401:
                log.error("401 Unauthorized: BOT_TOKEN galat hai. Fix the token and redeploy.")
                time.sleep(60)
            else:
                log.exception("Telegram API error; retrying in %ss", backoff)
            try:
                bot.stop_polling()
            except Exception:
                pass
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except Exception:
            log.exception("Polling stopped; retrying in %ss", backoff)
            try:
                bot.stop_polling()
            except Exception:
                pass
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    run()
