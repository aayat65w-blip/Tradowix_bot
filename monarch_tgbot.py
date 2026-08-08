# ============================================================
#  MONARCH PREMIUM — TELEGRAM BOT (ALL-IN-ONE FILE)
#  tg_ui.py + tg_engine.py + monarch_tgbot.py  ===>  is ek file me
#  quotex.py ko chua nahi gaya — sirf usse import kiya jata hai.
#
#  Run: python -u monarch_tgbot.py
#  Env: BOT_TOKEN, OWNER_ID   (Railway Variables)
# ============================================================
import html
import logging
import os
import sys
import threading
import time

import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

# ------------------------------------------------------------
# logging
# ------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("monarch.telegram")

# ------------------------------------------------------------
# secrets
# ------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OWNER_ID_RAW = os.environ.get("OWNER_ID", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Add it in Railway Variables.")
if not OWNER_ID_RAW.lstrip("-").isdigit():
    raise RuntimeError("OWNER_ID must be a numeric Telegram user ID in Railway Variables.")
OWNER_ID = int(OWNER_ID_RAW)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True)


def esc(t):
    return html.escape(str(t))


# ============================================================
#  SECTION 1 — UI  (ex tg_ui.py)  •  LIGHT BLUE PREMIUM THEME
# ============================================================
BRAND = "🩵 <b>M O N A R C H   P R E M I U M</b> 🩵"
LINE = "🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹"
SOFT = "╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌"


def kb(rows):
    m = types.InlineKeyboardMarkup(row_width=2)
    for row in rows:
        buttons = [types.InlineKeyboardButton(t, callback_data=d) for t, d in row if t]
        if buttons:
            m.row(*buttons)
    return m


def header(title=None):
    out = f"{BRAND}\n{LINE}\n"
    if title:
        out += f"💠 <b>{title}</b>\n{SOFT}\n"
    return out


def main_panel(cfg, broker_label, scanning, mode, version, weekday, clock, session):
    st = "🟦 <b>RUNNING</b>" if scanning else "🔷 <b>IDLE</b>"
    return (
        f"{header()}"
        f"<code>{esc(version)}</code>\n{SOFT}\n"
        f"🔹 <b>Broker</b>        : <b>{esc(broker_label)}</b>\n"
        f"🔹 <b>Engine</b>        : {st}{f'  <i>({esc(mode)})</i>' if scanning and mode else ''}\n"
        f"🔹 <b>Broker time</b>   : <code>{esc(clock)}</code>  <i>(UTC+6)</i>\n"
        f"🔹 <b>Day / Session</b> : <b>{esc(weekday)}</b> • {esc(session)}\n"
        f"🔹 <b>Timeframe</b>     : <b>{esc(cfg.get('timeframe', 'M1'))}</b>\n"
        f"🔹 <b>Charts</b>        : <b>{'🟦 ON' if cfg.get('charts') else '⬜ OFF'}</b>\n"
        f"🔹 <b>Max loss-risk</b> : <b>{int(float(cfg.get('max_loss_prob', 0.35)) * 100)}%</b>\n"
        f"🔹 <b>Send before</b>   : <b>{cfg.get('send_before', 10)}s</b>\n"
        f"{LINE}\n💙 <i>Neeche se option choose karo</i> 👇"
    )


def main_kb(scanning):
    rows = [
        [("💠 Auto Scan", "m:auto"), ("🔹 Manual Signal", "m:manual")],
        [("🔧 Settings", "m:settings"), ("🔷 Stats", "m:stats")],
        [("🩵 Pre-Analysis", "m:calib"), ("🧊 AI Brain", "m:ai")],
        [("🕓 Best Times", "m:times"), ("📨 Send Partial", "m:partial")],
        [("♻️ Reset Partial", "m:reset"), ("🔄 Refresh", "m:home")],
    ]
    if scanning:
        rows.insert(0, [("⛔ STOP ENGINE", "m:stop")])
    return kb(rows)


def broker_panel(mode, current):
    return (
        f"{header(f'SELECT BROKER — {esc(mode)}')}"
        f"🟦 <b>Quotex</b>   — Qx candles + live ticks\n"
        f"🩵 <b>Tradowix</b> — candle API + live ticks\n{LINE}\n"
        f"<i>Last used:</i> <b>{esc(current)}</b>"
    )


def broker_kb(mode_key):
    return kb([
        [("🟦 Quotex", f"b:{mode_key}:quotex"), ("🩵 Tradowix", f"b:{mode_key}:tradowix")],
        [("🔹 Back", "m:home")],
    ])


def settings_panel(cfg, broker_label):
    return (
        f"{header('SETTINGS')}"
        f"🔹 <b>Broker</b>        : <b>{esc(broker_label)}</b>\n"
        f"🔹 <b>Timeframe</b>     : <b>{esc(cfg.get('timeframe', 'M1'))}</b>\n"
        f"🔹 <b>Charts</b>        : <b>{'🟦 ON' if cfg.get('charts') else '⬜ OFF'}</b>\n"
        f"🔹 <b>Auto partial</b>  : <b>{'🟦 ON' if cfg.get('auto_partial') else '⬜ OFF'}</b>\n"
        f"🔹 <b>Max loss-risk</b> : <b>{int(float(cfg.get('max_loss_prob', 0.35)) * 100)}%</b>\n"
        f"🔹 <b>Send before</b>   : <b>{cfg.get('send_before', 10)}s</b>\n{LINE}\n"
        f"💙 <i>Tap karke value change karo</i>"
    )


def _tf_rows(timeframes, prefix, current=None):
    """Timeframes ko 3-per-row me todo, saare dikhao (pehle sirf 4 dikhte the)."""
    tfs = [str(t) for t in timeframes] or ["M1"]
    rows, row = [], []
    for t in tfs:
        mark = "🟦" if current and str(current) == t else "🔹"
        row.append((f"{mark} {t}", f"{prefix}{t}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def settings_kb(cfg, timeframes):
    rows = [
        [("🏦 Broker", "s:broker"), ("🖼 Charts ON/OFF", "s:charts")],
        [("📨 Auto partial ON/OFF", "s:autopartial")],
    ]
    rows += _tf_rows(timeframes, "s:tf:", cfg.get("timeframe"))
    rows += [
        [("🛡 Risk −5%", "s:risk:-5"), ("🛡 Risk +5%", "s:risk:5")],
        [("⏱ Send −5s", "s:sb:-5"), ("⏱ Send +5s", "s:sb:5")],
        [("🔹 Back", "m:home")],
    ]
    return kb(rows)


def tf_kb(timeframes):
    return kb(_tf_rows(timeframes, "mtf:") + [[("🔹 Back", "m:home")]])


def back_kb():
    return kb([[("🔹 Main Menu", "m:home")]])


def stop_kb():
    return kb([[("⛔ STOP ENGINE", "m:stop")], [("🔹 Main Menu", "m:home")]])


def block(title, body):
    return f"{header(title)}<pre>{body}</pre>"


# ============================================================
#  SECTION 2 — ENGINE  (ex tg_engine.py)  •  bridge to quotex.py
#  quotex.py me koi change nahi — sirf import.
# ============================================================
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CORE_ERROR = None
try:
    import quotex as core  # noqa: E402
except Exception as _e:  # core import fail hone par bhi bot zinda rahe
    core = None
    CORE_ERROR = _e
    log.exception("quotex core import failed")


def capture(fn, *a, **kw):
    try:
        with core.console.capture() as cap:
            fn(*a, **kw)
        return cap.get()[:3500] or "—"
    except Exception as e:
        return f"error: {e}"


class Engine:
    """Ek time par ek scan session (auto ya manual), background thread me."""

    def __init__(self, notify):
        self.notify = notify
        self.cfg = core.load_config()
        self.signals, self.wins, self.losses = [], [0], [0]
        self.rc = core.ResultChecker(self.cfg, self.signals, self.wins, self.losses)
        try:
            self.rc.start()
        except Exception as e:
            core.log_line(f"tg rc start: {e}")
        self.stop_event = threading.Event()
        self.thread = None
        self.mode = None

    # ── config ──────────────────────────────────────────────
    def save(self):
        core.save_config(self.cfg)

    def broker_label(self, key=None):
        try:
            return core.broker_label(key or self.cfg.get("broker"))
        except Exception:
            return str(self.cfg.get("broker", "—"))

    def set_broker(self, key):
        core.set_broker(self.cfg, key)
        self.save()
        try:
            core._LIVE_CACHE.update({"t": 0, "pairs": [], "broker": None})
        except Exception:
            pass
        if core.active_broker(self.cfg) == "tradowix":
            try:
                core.ensure_route(self.cfg)
            except Exception as e:
                core.log_line(f"tg route: {e}")

    def bind_telegram(self, token, chat_id):
        self.cfg["telegram"] = True
        self.cfg["token"] = token
        self.cfg["chat_id"] = str(chat_id)
        self.save()

    # ── state ───────────────────────────────────────────────
    def running(self):
        return bool(self.thread and self.thread.is_alive())

    def stop(self):
        self.stop_event.set()

    def _start(self, target, mode, *a):
        if self.running():
            return False
        self.stop_event = threading.Event()
        self.mode = mode
        self.thread = threading.Thread(target=self._guard, args=(target, a), daemon=True)
        self.thread.start()
        return True

    def _guard(self, target, a):
        try:
            target(*a)
        except Exception as e:
            core.log_line(f"tg engine fatal: {e}")
            self.notify(f"⚠️ <b>Engine error</b>\n<code>{esc(e)}</code>")
        finally:
            self.mode = None
            try:
                core.stop_rolling_prefetch()
            except Exception:
                pass
            self.notify("⛔ <b>Engine stopped</b> — main menu se dobara start karo.")

    # ── shared candle cycle ─────────────────────────────────
    def _busy_wait(self, tf, send_before):
        core.trade_watchdog()
        if core.trade_busy():
            time.sleep(2)
            return True
        rem = core.seconds_to_next(tf)
        if rem > core.PRESCAN_START_BEFORE:
            time.sleep(min(rem - core.PRESCAN_START_BEFORE, 3))
            return True
        if rem < send_before + 2:
            time.sleep(max(rem + 0.6, 0.5))
            return True
        return False

    def _fire(self, cand_list, tf, send_before):
        while core.seconds_to_next(tf) > send_before + 3 and not self.stop_event.is_set():
            time.sleep(0.1)
        final = None
        for cand in cand_list:
            if core.seconds_to_next(tf) < core.MIN_SEND_BUFFER:
                break
            final = core.confirm_with_forming(cand, self.cfg)
            if final:
                break
        if not final:
            return None
        while core.seconds_to_next(tf) > send_before and not self.stop_event.is_set():
            time.sleep(0.05)
        if core.seconds_to_next(tf) < core.MIN_SEND_BUFFER:
            return None
        return core.dispatch(final, self.cfg, self.rc, self.signals)

    # ── AUTO SCAN ───────────────────────────────────────────
    def start_auto(self, broker):
        return self._start(self._auto, "AUTO SCAN", broker)

    def _auto(self, broker):
        self.set_broker(broker)
        tf = self.cfg.get("timeframe", "M1")
        send_before = int(self.cfg.get("send_before", core.SIGNAL_SEND_BEFORE))
        self.notify(f"🔎 <b>{self.broker_label()}</b> — live pairs check ho rahe hain…")
        pairs = core.pick_pairs(self.cfg, quiet=True)
        if not pairs:
            self.notify("❌ Is broker par abhi koi live pair nahi mila.")
            return
        self.notify(f"🧪 Pre-analysis + AI training on <b>{len(pairs)}</b> pairs — thoda ruko…")
        try:
            core.run_pre_analysis(pairs, self.cfg)
            core.AI.train_all(pairs, self.cfg)
        except Exception as e:
            core.log_line(f"tg pre-analysis: {e}")
        pairs = core.pick_pairs(self.cfg, quiet=True) or pairs
        tradable = [p for p in pairs
                    if (core.pair_stats(p) or {}).get("quality", 1) >= core.MIN_PAIR_QUALITY]
        pairs = (tradable or pairs)[:core.MAX_PAIRS]
        core.start_rolling_prefetch(pairs, self.cfg)
        self.notify(
            f"💠 <b>AUTO SCAN LIVE</b>\n🔹 {self.broker_label()} • {len(pairs)} pairs • {tf}\n"
            f"🔹 Signal {send_before}s before candle open\n<i>Stop karne ke liye ⛔ dabao.</i>")

        last_refresh = time.time()
        while not self.stop_event.is_set():
            try:
                if self._busy_wait(tf, send_before):
                    continue
                if time.time() - last_refresh > 7200:
                    fresh = core.pick_pairs(self.cfg, quiet=True) or pairs
                    pairs = fresh[:core.MAX_PAIRS]
                    core.start_rolling_prefetch(pairs, self.cfg)
                    last_refresh = time.time()
                ranked, _ = core.scan_best(pairs, tf, self.cfg)
                if not ranked:
                    time.sleep(max(core.seconds_to_next(tf) + 0.5, 1))
                    continue
                sendable = ([a for a in ranked if a.get("grade") in core.SENDABLE_GRADES]
                            if core.STRICT_MODE else ranked)
                if not sendable:
                    time.sleep(max(core.seconds_to_next(tf) + 0.5, 1))
                    continue
                self._fire(sendable, tf, send_before)
                time.sleep(max(core.seconds_to_next(tf) + 1, 2))
            except Exception as e:
                core.log_line(f"tg auto-loop: {e}")
                time.sleep(5)

    # ── MANUAL SIGNAL ───────────────────────────────────────
    def live_pairs(self, broker=None):
        if broker:
            self.set_broker(broker)
        return core.pick_pairs(self.cfg, quiet=True) or []

    def match_pair(self, raw, pairs):
        try:
            p = core._norm_pair(raw)
        except Exception:
            p = str(raw).strip().upper()
        if p in pairs:
            return p
        key = str(raw).upper().replace("-OTC", "").replace("_OTC", "").replace("/", "").strip()
        near = [x for x in pairs if key and key in x.upper().replace("/", "")]
        return near[0] if near else None

    def start_manual(self, broker, pair, tf):
        return self._start(self._manual, "MANUAL SIGNAL", broker, pair, tf)

    def _manual(self, broker, pair, tf):
        self.set_broker(broker)
        self.cfg["timeframe"] = tf
        self.save()
        send_before = int(self.cfg.get("send_before", core.SIGNAL_SEND_BEFORE))
        try:
            core.run_pre_analysis([pair], self.cfg)
        except Exception as e:
            core.log_line(f"tg manual pre-analysis: {e}")
        self.notify(
            f"🔹 <b>MANUAL WATCH LIVE</b>\n🩵 {self.broker_label()} • "
            f"<b>{esc(core.pretty_pair(pair))}</b> • {tf}\n📨 Signal {send_before}s before candle open")
        while not self.stop_event.is_set():
            try:
                if self._busy_wait(tf, send_before):
                    continue
                a = core.analyze(pair, tf, self.cfg)
                if not a:
                    time.sleep(5)
                    continue
                a["grade"], a["stake"], a["why"] = core.grade_setup(a, self.cfg)
                a["score"] = core.rank_score(a)
                if core.STRICT_MODE and a["grade"] not in core.SENDABLE_GRADES:
                    time.sleep(max(core.seconds_to_next(tf) + 1, 2))
                    continue
                self._fire([a], tf, send_before)
                time.sleep(max(core.seconds_to_next(tf) + 1, 2))
            except Exception as e:
                core.log_line(f"tg manual-loop: {e}")
                time.sleep(5)

    # ── ONE-SHOT PANELS ─────────────────────────────────────
    def stats_text(self):
        return capture(core.show_stats)

    def ai_text(self):
        return capture(core.show_ai_panel)

    def times_text(self):
        return capture(core.show_best_times)

    def recalibrate(self, broker=None):
        if broker:
            self.set_broker(broker)
        pairs = core.pick_pairs(self.cfg, quiet=True)
        if not pairs:
            return "❌ Koi live pair nahi mila."
        core.run_pre_analysis(pairs, self.cfg, force=True)
        core.AI.train_all(pairs, self.cfg, force=True)
        return f"✅ Pre-analysis + AI retrain done on {len(pairs)} pairs ({self.broker_label()})."

    def send_partial(self):
        ok = core.send_partial_now(self.cfg, self.signals, "telegram")
        return "📨 Partial bhej diya." if ok else "⚠️ Partial khali hai."

    def reset_partial(self):
        core.reset_partial(self.signals)
        return "♻️ Partial reset — naya batch shuru."

    def timeframes(self):
        try:
            return [str(t) for t in list(core.TIMEFRAMES)]
        except Exception:
            return ["M1", "M5", "M15"]

    def clock(self):
        return core.get_now().strftime("%H:%M:%S")

    def weekday(self):
        return core.weekday_name()

    def session(self):
        s = core.get_session()
        return s[0] if isinstance(s, (list, tuple)) else str(s)

    def version(self):
        return f"{core.BOT_NAME} {core.BOT_VERSION}"


# ============================================================
#  SECTION 3 — BOT  (ex monarch_tgbot.py)
# ============================================================
def notify(text):
    try:
        bot.send_message(OWNER_ID, text, disable_web_page_preview=True)
    except Exception:
        log.exception("Could not send engine notification")


ENGINE = None
ENGINE_ERROR = None
_engine_lock = threading.Lock()


def get_engine():
    """Engine ko lazy banao: core error aane par bhi /start reply karega."""
    global ENGINE, ENGINE_ERROR
    if ENGINE is not None:
        return ENGINE
    with _engine_lock:
        if ENGINE is not None:
            return ENGINE
        if core is None:
            ENGINE_ERROR = CORE_ERROR
            return None
        try:
            eng = Engine(notify)
            eng.bind_telegram(BOT_TOKEN, OWNER_ID)
            ENGINE = eng
            ENGINE_ERROR = None
        except Exception as e:
            ENGINE_ERROR = e
            log.exception("Engine init failed")
        return ENGINE


# chat_id -> {"broker":..., "pair":..., "await_pair": bool}
STATE = {}


def st(chat_id):
    return STATE.setdefault(chat_id, {"broker": None, "pair": None, "await_pair": False})


def is_owner(user_id):
    return user_id == OWNER_ID


def engine_down_text():
    return (
        f"{header('ENGINE NOT READY')}"
        f"quotex.py core load nahi hua.\n<code>{esc(ENGINE_ERROR or CORE_ERROR or 'unknown')}</code>\n"
        f"{SOFT}\n<i>quotex.py repo root me hona chahiye + requirements install hona chahiye.</i>"
    )


def panel_text():
    eng = get_engine()
    if not eng:
        return engine_down_text()
    return main_panel(
        eng.cfg, eng.broker_label(), eng.running(), eng.mode,
        eng.version(), eng.weekday(), eng.clock(), eng.session(),
    )


def current_kb():
    eng = get_engine()
    return main_kb(bool(eng and eng.running())) if eng else back_kb()


def send_home(chat_id, message_id=None):
    text, keyboard = panel_text(), current_kb()
    if message_id is not None:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=keyboard)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=keyboard, disable_web_page_preview=True)


def edit(call, text, keyboard=None):
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard, disable_web_page_preview=True)


def safe_block(title, body):
    return block(title, esc(body)[:3500])


# ── COMMANDS ────────────────────────────────────────────────
@bot.message_handler(commands=["start", "menu", "help", "home", "panel"])
def cmd_start(message):
    if not is_owner(message.from_user.id):
        bot.send_message(message.chat.id, "⛔ This bot is private.")
        return
    st(message.chat.id)["await_pair"] = False
    send_home(message.chat.id)


@bot.message_handler(commands=["id", "whoami"])
def cmd_id(message):
    bot.send_message(message.chat.id, f"🔹 Your ID: <code>{message.from_user.id}</code>")


@bot.message_handler(commands=["stop"])
def cmd_stop(message):
    if not is_owner(message.from_user.id):
        return
    eng = get_engine()
    if eng:
        eng.stop()
    bot.send_message(message.chat.id, "⛔ Stop requested.", reply_markup=back_kb())


@bot.message_handler(commands=["stats"])
def cmd_stats(message):
    if not is_owner(message.from_user.id):
        return
    eng = get_engine()
    if not eng:
        bot.send_message(message.chat.id, engine_down_text(), reply_markup=back_kb())
        return
    bot.send_message(message.chat.id, safe_block("STATS", eng.stats_text()), reply_markup=back_kb())


@bot.message_handler(commands=["settings"])
def cmd_settings(message):
    if not is_owner(message.from_user.id):
        return
    eng = get_engine()
    if not eng:
        bot.send_message(message.chat.id, engine_down_text(), reply_markup=back_kb())
        return
    bot.send_message(message.chat.id, settings_panel(eng.cfg, eng.broker_label()),
                     reply_markup=settings_kb(eng.cfg, eng.timeframes()))


# ── MANUAL PAIR TEXT (next_step_handler ki jagah state machine) ──
@bot.message_handler(func=lambda m: True, content_types=["text"])
def any_text(message):
    if not message.from_user or not is_owner(message.from_user.id):
        return
    chat_id = message.chat.id
    state = st(chat_id)
    text = (message.text or "").strip()
    if text.startswith("/"):
        send_home(chat_id)
        return
    if not state.get("await_pair"):
        send_home(chat_id)
        return

    eng = get_engine()
    if not eng:
        bot.send_message(chat_id, engine_down_text(), reply_markup=back_kb())
        return
    broker = state.get("broker") or eng.cfg.get("broker", "tradowix")
    try:
        pairs = eng.live_pairs(broker)
        pair = eng.match_pair(text, pairs)
    except Exception as exc:
        log.exception("pair lookup failed")
        bot.send_message(chat_id, f"⚠️ Pair lookup failed: <code>{esc(exc)}</code>", reply_markup=back_kb())
        return
    if not pair:
        bot.send_message(chat_id, "❌ Pair not found. Dobara sahi naam bhejo (jaise <code>EURUSD</code>).",
                         reply_markup=back_kb())
        return
    state["pair"] = pair
    state["await_pair"] = False
    bot.send_message(chat_id, f"{header('PAIR SELECTED')}🔹 <b>{esc(pair)}</b>\n{SOFT}\n💙 Timeframe choose karo:",
                     reply_markup=tf_kb(eng.timeframes()))


# ── CALLBACKS ───────────────────────────────────────────────
@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    if not call.from_user or not is_owner(call.from_user.id):
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
    state = st(chat_id)
    eng = get_engine()

    if data == "m:home":
        state["await_pair"] = False
        send_home(chat_id, call.message.message_id)
        return
    if not eng:
        edit(call, engine_down_text(), back_kb())
        return

    try:
        # ---- manual timeframe ----
        if data.startswith("mtf:"):
            pair = state.get("pair")
            broker = state.get("broker") or eng.cfg.get("broker", "tradowix")
            if not pair:
                edit(call, "⚠️ Pehle Manual Signal se pair choose karo.", back_kb())
                return
            tf = data.split(":", 1)[-1]
            if eng.start_manual(broker, pair, tf):
                edit(call, f"{header('MANUAL WATCH STARTING')}🔹 {esc(pair)} • <b>{esc(tf)}</b>", stop_kb())
            else:
                edit(call, "⚠️ Engine already running — pehle stop karo.", stop_kb())
            return

        if data == "m:auto":
            edit(call, broker_panel("AUTO SCAN", eng.broker_label()), broker_kb("auto"))
        elif data == "m:manual":
            edit(call, broker_panel("MANUAL SIGNAL", eng.broker_label()), broker_kb("manual"))
        elif data.startswith("b:auto:"):
            broker = data.rsplit(":", 1)[-1]
            if eng.running():
                edit(call, "⚠️ Engine already running — pehle stop karo.", stop_kb())
            elif eng.start_auto(broker):
                edit(call, f"{header('AUTO SCAN STARTING')}💠 <i>Pairs + AI ready ho rahe hain…</i>", stop_kb())
            else:
                edit(call, "⚠️ Engine start nahi hua.", back_kb())
        elif data.startswith("b:manual:"):
            broker = data.rsplit(":", 1)[-1]
            state["broker"] = broker
            state["pair"] = None
            state["await_pair"] = True
            edit(call, f"{header('MANUAL SIGNAL')}🔹 <i>Live pairs load ho rahe hain…</i>", back_kb())
            threading.Thread(target=send_pair_prompt, args=(chat_id, broker), daemon=True).start()
        elif data == "m:settings":
            show_settings(call)
        elif data == "m:stats":
            edit(call, safe_block("STATS", eng.stats_text()), back_kb())
        elif data == "m:ai":
            edit(call, safe_block("AI BRAIN", eng.ai_text()), back_kb())
        elif data == "m:times":
            edit(call, safe_block("BEST TIMES", eng.times_text()), back_kb())
        elif data == "m:calib":
            edit(call, f"{header('PRE-ANALYSIS')}🩵 <i>Chal raha hai… result aa jayega.</i>", back_kb())
            threading.Thread(target=run_calibration, args=(chat_id,), daemon=True).start()
        elif data == "m:partial":
            bot.send_message(chat_id, eng.send_partial(), reply_markup=back_kb())
        elif data == "m:reset":
            bot.send_message(chat_id, eng.reset_partial(), reply_markup=back_kb())
        elif data == "m:stop":
            eng.stop()
            bot.send_message(chat_id, "⛔ Stop requested. Current task safely band hoga.", reply_markup=back_kb())
        elif data == "s:broker":
            edit(call, broker_panel("SETTINGS", eng.broker_label()), broker_kb("setting"))
        elif data.startswith("b:setting:"):
            eng.set_broker(data.rsplit(":", 1)[-1])
            show_settings(call)
        elif data == "s:charts":
            eng.cfg["charts"] = not eng.cfg.get("charts", True)
            eng.save()
            show_settings(call)
        elif data == "s:autopartial":
            eng.cfg["auto_partial"] = not eng.cfg.get("auto_partial", True)
            eng.save()
            show_settings(call)
        elif data.startswith("s:tf:"):
            eng.cfg["timeframe"] = data.rsplit(":", 1)[-1]
            eng.save()
            show_settings(call)
        elif data.startswith("s:risk:"):
            cur = float(eng.cfg.get("max_loss_prob", 0.35))
            eng.cfg["max_loss_prob"] = round(min(0.8, max(0.05, cur + int(data.rsplit(":", 1)[-1]) / 100)), 2)
            eng.save()
            show_settings(call)
        elif data.startswith("s:sb:"):
            cur = int(eng.cfg.get("send_before", 10))
            eng.cfg["send_before"] = min(50, max(5, cur + int(data.rsplit(":", 1)[-1])))
            eng.save()
            show_settings(call)
        else:
            send_home(chat_id, call.message.message_id)
    except Exception as exc:
        log.exception("Callback failed: %s", data)
        bot.send_message(chat_id, f"⚠️ <b>Error</b>\n<code>{esc(exc)}</code>", reply_markup=back_kb())


def show_settings(call):
    eng = get_engine()
    if not eng:
        edit(call, engine_down_text(), back_kb())
        return
    edit(call, settings_panel(eng.cfg, eng.broker_label()), settings_kb(eng.cfg, eng.timeframes()))


def send_pair_prompt(chat_id, broker):
    """Live pairs fetch background me — Telegram timeout se bachne ke liye."""
    eng = get_engine()
    try:
        pairs = eng.live_pairs(broker) if eng else []
    except Exception as exc:
        log.exception("live pairs failed")
        bot.send_message(chat_id, f"⚠️ Live pairs failed: <code>{esc(exc)}</code>", reply_markup=back_kb())
        return
    preview = ", ".join(pairs[:30]) if pairs else ""
    bot.send_message(
        chat_id,
        f"{header('SEND A PAIR NAME')}<code>{esc(preview or 'No live pairs returned yet')}</code>\n"
        f"{SOFT}\n💙 <i>Pair ka naam type karke bhejo.</i>",
        reply_markup=back_kb(),
    )


def run_calibration(chat_id):
    eng = get_engine()
    try:
        result = eng.recalibrate() if eng else "⚠️ Engine not ready."
    except Exception as exc:
        result = f"⚠️ Calibration failed: {exc}"
        log.exception("Calibration failed")
    bot.send_message(chat_id, esc(result), reply_markup=back_kb())


# ── POLLING ─────────────────────────────────────────────────
def prepare_polling():
    """Webhook hatao + purane updates drop karo (409 Conflict ka fix)."""
    for attempt in range(5):
        try:
            bot.delete_webhook(drop_pending_updates=True)
            return True
        except ApiTelegramException as exc:
            log.warning("delete_webhook failed (%s), retry %s/5", exc, attempt + 1)
            time.sleep(3)
        except Exception as exc:
            log.warning("delete_webhook error (%s), retry %s/5", exc, attempt + 1)
            time.sleep(3)
    return False


def set_commands():
    try:
        bot.set_my_commands([
            types.BotCommand("start", "Main panel"),
            types.BotCommand("menu", "Main panel"),
            types.BotCommand("settings", "Settings"),
            types.BotCommand("stats", "Stats"),
            types.BotCommand("stop", "Stop engine"),
            types.BotCommand("id", "Your Telegram ID"),
        ])
    except Exception:
        log.warning("set_my_commands failed", exc_info=True)


def run():
    log.info("Starting Telegram polling")
    set_commands()
    if core is None:
        notify(engine_down_text())
    backoff = 5
    while True:
        try:
            if not prepare_polling():
                log.error("Webhook cleanup failed; polling retry in %ss", backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            bot.infinity_polling(timeout=30, long_polling_timeout=25, skip_pending=False)
            backoff = 5
        except ApiTelegramException as exc:
            if getattr(exc, "error_code", None) == 409:
                log.error("409 Conflict: dusra instance same bot ko poll kar raha hai.")
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
