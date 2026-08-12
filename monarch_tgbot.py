# ============================================================
#  MONARCH PREMIUM — TELEGRAM BOT (ALL-IN-ONE FILE)
#  tg_ui.py + tg_engine.py + monarch_tgbot.py  ===>  all in one file
#  quotex.py is never modified — it is only imported.
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

# 3rd-party ka shor band (matplotlib fontManager, urllib3, telebot internals)
for _noisy in ("matplotlib", "matplotlib.font_manager", "PIL",
               "urllib3", "TeleBot", "telebot"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

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
NO_LINK_PREVIEW = types.LinkPreviewOptions(is_disabled=True)


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
        f"{LINE}\n💙 <i>Choose an option below</i> 👇"
    )


def main_kb(scanning):
    rows = [
        [("💠 Auto Scan", "m:auto"), ("🔹 Manual Signal", "m:manual")],
        [("🔧 Settings", "m:settings"), ("🔷 Stats", "m:stats")],
        [("🩵 Pre-Analysis", "m:calib"), ("🧊 AI Brain", "m:ai")],
        [("🔮 OTC FS", "m:fs")],

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
        f"💙 <i>Tap any item to change its value</i>"
    )


def _tf_rows(timeframes, prefix, current=None):
    """Show every timeframe, split 3 per row."""
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
#  No changes to quotex.py — import only.
# ============================================================
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CORE_ERROR = None
try:
    import quotex as core  # noqa: E402
except Exception as _e:  # keep the bot alive even if the core import fails
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
    """One scan session at a time (auto or manual), running in a background thread."""

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
            self.notify("⛔ <b>Engine stopped</b> — start it again from the main menu.")

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
        self.notify(f"🔎 <b>{self.broker_label()}</b> — checking live pairs…")
        pairs = core.pick_pairs(self.cfg, quiet=True)
        if not pairs:
            self.notify("❌ No live pair is available on this broker right now.")
            return
        self.notify(f"🧪 Pre-analysis + AI training on <b>{len(pairs)}</b> pairs — please wait…")
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
            f"🔹 Signal {send_before}s before candle open\n<i>Press ⛔ to stop.</i>")

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
            return "❌ No live pair found."
        core.run_pre_analysis(pairs, self.cfg, force=True)
        core.AI.train_all(pairs, self.cfg, force=True)
        return f"✅ Pre-analysis + AI retrain done on {len(pairs)} pairs ({self.broker_label()})."

    def send_partial(self):
        ok = core.send_partial_now(self.cfg, self.signals, "telegram")
        return "📨 Partial report sent." if ok else "⚠️ The partial report is empty."

    def reset_partial(self):
        core.reset_partial(self.signals)
        return "♻️ Partial reset — a new batch has started."

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
        bot.send_message(OWNER_ID, text, link_preview_options=NO_LINK_PREVIEW)
    except Exception:
        log.exception("Could not send engine notification")


ENGINE = None
ENGINE_ERROR = None
_engine_lock = threading.Lock()


def get_engine():
    """Build the engine lazily so /start still replies even if the core fails."""
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


# chat_id -> {"broker":..., "pair":..., "await_pair": bool, ...}
STATE = {}


def st(chat_id):
    return STATE.setdefault(chat_id, {
        "broker": None,
        "pair": None,
        "await_pair": False,
        "await_channel": False,
        "pending_broker": None,
        "channel_id": None,
        "channel_title": None,
        "fs": None,          # OTC FUTURE SIGNAL wizard state
    })


def is_owner(user_id):
    return user_id == OWNER_ID


# ============================================================
#  SECTION 3.5 — OTC FS  (Future Signal • future3.py bridge)
# ============================================================
FS_CORE = None
FS_ERROR = None
_fs_lock = threading.Lock()
FS_BUSY = {}          # chat_id -> True while a scan runs


def fs_core():
    """Import future3.py lazily so the bot starts even if it is missing."""
    global FS_CORE, FS_ERROR
    if FS_CORE is not None:
        return FS_CORE
    with _fs_lock:
        if FS_CORE is None:
            try:
                import future3 as _fs
                FS_CORE = _fs
                FS_ERROR = None
            except Exception as e:
                FS_ERROR = e
                log.exception("future3 import failed")
    return FS_CORE


FS_STEPS = [
    ("pairs", "SELECT PAIRS",
     "Send <code>all</code> for every pair, or numbers like <code>1,3,5</code> / "
     "<code>1-8</code>, or names like <code>EURUSD_otc,GBPUSD_otc</code>."),
    ("start", "START TIME", "Send start time <code>HH:MM</code> (UTC+6)."),
    ("end", "END TIME", "Send end time <code>HH:MM</code> (UTC+6)."),
    ("gap", "GAP", "Gap between signals in minutes (1-30)."),
    ("conf", "ACCURACY FILTER", "Minimum accuracy filter % (55-95)."),
    ("max", "MAX SIGNALS", "Maximum number of signals (1-300)."),
]


def fs_ask(chat_id, state):
    fs = state["fs"]
    key, title, hint = FS_STEPS[fs["step"]]
    default = fs["defaults"][key]
    bot.send_message(
        chat_id,
        f"{header(f'OTC FS — {title}')}{hint}\n{SOFT}\n"
        f"💙 Default: <b>{esc(default)}</b>  <i>(send</i> <code>-</code> <i>to keep it)</i>",
        reply_markup=back_kb(),
    )


def fs_start(chat_id, market):
    core_fs = fs_core()
    if not core_fs:
        bot.send_message(chat_id, f"{header('OTC FS NOT READY')}<code>{esc(FS_ERROR)}</code>\n"
                                  f"{SOFT}\n<i>future3.py must be in the repository root.</i>",
                         reply_markup=back_kb())
        return
    import datetime as _dt
    now = _dt.datetime.now(core_fs.TZ)
    pairs = core_fs.market_pairs(market)
    state = st(chat_id)
    state["fs"] = {
        "market": market,
        "step": 0,
        "answers": {},
        "pairs_list": pairs,
        "defaults": {
            "pairs": "all",
            "start": (now + _dt.timedelta(minutes=5)).strftime("%H:%M"),
            "end": (now + _dt.timedelta(hours=3)).strftime("%H:%M"),
            "gap": 3, "conf": 75, "max": 40,
        },
    }
    listing = "\n".join(
        "  ".join(f"{i:>2}.{p}" for i, p in
                  list(enumerate(pairs, 1))[k:k + 3])
        for k in range(0, len(pairs), 3)
    )
    bot.send_message(chat_id, f"{header(f'OTC FS — {market} PAIRS')}<pre>{esc(listing)}</pre>")
    fs_ask(chat_id, state)


def fs_text(chat_id, text):
    """Handle one wizard answer. Returns True if it was consumed."""
    state = st(chat_id)
    fs = state.get("fs")
    if not fs:
        return False
    key, title, hint = FS_STEPS[fs["step"]]
    value = (text or "").strip()
    if value in ("-", ""):
        value = fs["defaults"][key]
    if key in ("gap", "conf", "max"):
        try:
            value = int(str(value))
        except Exception:
            bot.send_message(chat_id, "❌ Send a number please.", reply_markup=back_kb())
            return True
    if key in ("start", "end"):
        core_fs = fs_core()
        try:
            core_fs.parse_hm(str(value))
        except Exception:
            bot.send_message(chat_id, "❌ Wrong format. Example <code>09:30</code>.",
                             reply_markup=back_kb())
            return True
    fs["answers"][key] = value
    fs["step"] += 1
    if fs["step"] < len(FS_STEPS):
        fs_ask(chat_id, state)
        return True

    if FS_BUSY.get(chat_id):
        bot.send_message(chat_id, "⏳ A future scan is already running.", reply_markup=back_kb())
        state["fs"] = None
        return True
    answers = dict(fs["answers"])
    market = fs["market"]
    pairs_list = fs["pairs_list"]
    state["fs"] = None
    bot.send_message(
        chat_id,
        f"{header('OTC FS — SCAN STARTED')}"
        f"🔹 Market : <b>{esc(market)}</b>\n"
        f"🔹 Window : <b>{esc(answers['start'])} → {esc(answers['end'])}</b> (UTC+6)\n"
        f"🔹 Gap    : <b>{esc(answers['gap'])}m</b> • Filter <b>{esc(answers['conf'])}%</b> • "
        f"Max <b>{esc(answers['max'])}</b>\n{SOFT}\n🩵 <i>Working… please wait.</i>",
        reply_markup=back_kb(),
    )
    threading.Thread(target=fs_run, args=(chat_id, market, pairs_list, answers),
                     daemon=True).start()
    return True


def fs_run(chat_id, market, pairs_list, answers):
    FS_BUSY[chat_id] = True
    core_fs = fs_core()
    last = {"msg": None}

    def progress(msg):
        try:
            if last["msg"] is None:
                last["msg"] = bot.send_message(chat_id, esc(msg)).message_id
            else:
                bot.edit_message_text(esc(msg), chat_id, last["msg"])
        except Exception:
            pass

    try:
        pairs = core_fs.parse_pairs(str(answers["pairs"]), pairs_list)
        result = core_fs.run_signals(
            market=market, pairs=pairs, start=str(answers["start"]),
            end=str(answers["end"]), gap=answers["gap"],
            min_conf=answers["conf"], max_signals=answers["max"],
            progress=progress,
        )
        text = core_fs.format_signals(result)
    except Exception as exc:
        log.exception("OTC FS failed")
        text = f"⚠️ <b>OTC FS failed</b>\n<code>{esc(exc)}</code>"
    finally:
        FS_BUSY.pop(chat_id, None)

    for chunk in [text[i:i + 3500] for i in range(0, len(text), 3500)] or ["⚠️ empty"]:
        try:
            bot.send_message(chat_id, chunk, reply_markup=back_kb(),
                             link_preview_options=NO_LINK_PREVIEW)
        except Exception:
            log.exception("could not send FS result")



def engine_down_text():
    return (
        f"{header('ENGINE NOT READY')}"
        f"The quotex.py core failed to load.\n<code>{esc(ENGINE_ERROR or CORE_ERROR or 'unknown')}</code>\n"
        f"{SOFT}\n<i>quotex.py must be in the repository root and all requirements must be installed.</i>"
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
    bot.send_message(chat_id, text, reply_markup=keyboard, link_preview_options=NO_LINK_PREVIEW)


def edit(call, text, keyboard=None):
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except Exception:
        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=keyboard,
            link_preview_options=NO_LINK_PREVIEW,
        )


def safe_block(title, body):
    return block(title, esc(body)[:3500])


# ── CHANNEL BINDING (AUTO SCAN -> SIGNALS IN YOUR CHANNEL) ──
def channel_prompt(broker_label_text):
    return (
        f"{header('CONNECT YOUR CHANNEL')}"
        f"🔹 <b>Broker</b> : <b>{esc(broker_label_text)}</b>\n{SOFT}\n"
        f"💙 <b>Send your channel ID</b> (for example <code>-1001234567890</code>)\n"
        f"💙 <b>or forward any message from your channel</b> — I will detect the ID automatically.\n"
        f"{SOFT}\n"
        f"⚠️ <b>Make this bot an ADMIN in your channel</b> (with the post messages permission), "
        f"otherwise the signals cannot be posted to your channel.\n"
        f"{SOFT}\n<i>As soon as the channel is connected, AUTO SCAN starts automatically.</i>"
    )


def ask_channel(call, broker):
    state = st(call.message.chat.id)
    state["pending_broker"] = broker
    state["await_channel"] = True
    state["await_pair"] = False
    edit(call, channel_prompt(get_engine().broker_label(broker) if get_engine() else broker), back_kb())


def raw_update(message):
    """Raw dict of the update — deprecated Message properties ko touch nahi karte."""
    data = getattr(message, "json", None)
    return data if isinstance(data, dict) else {}


def extract_channel_id(message):
    """Extract the channel id + title from a forwarded message (new and old Telegram formats)."""
    raw = raw_update(message)
    chat = raw.get("forward_from_chat")
    if not chat:
        origin = raw.get("forward_origin") or {}
        chat = origin.get("chat") or origin.get("sender_chat")
    if not isinstance(chat, dict):
        return None, None
    return chat.get("id"), chat.get("title")


def parse_channel_text(text):
    t = (text or "").strip()
    if not t:
        return None
    if t.startswith("https://t.me/") or t.startswith("t.me/") or t.startswith("@"):
        name = t.split("t.me/")[-1].lstrip("@").strip("/")
        if name and not name.startswith("+") and "/" not in name:
            return "@" + name
        return None
    cleaned = t.replace(" ", "")
    if cleaned.lstrip("-").isdigit():
        return cleaned
    return None


def bot_is_admin(channel_id):
    """Return (ok, detail): whether the bot is an admin in the channel."""
    try:
        me = bot.get_me()
        member = bot.get_chat_member(channel_id, me.id)
        status = getattr(member, "status", "")
        if status in ("administrator", "creator"):
            return True, status
        return False, status or "not admin"
    except Exception as exc:
        return False, str(exc)


def connect_channel_and_start(chat_id, target):
    """Verify the channel, bind it and start AUTO SCAN."""
    state = st(chat_id)
    eng = get_engine()
    if not eng:
        bot.send_message(chat_id, engine_down_text(), reply_markup=back_kb())
        return

    try:
        info = bot.get_chat(target)
        channel_id = info.id
        title = getattr(info, "title", None) or str(channel_id)
    except Exception as exc:
        bot.send_message(
            chat_id,
            f"❌ <b>Channel not found</b>\n<code>{esc(exc)}</code>\n{SOFT}\n"
            f"💙 First make this bot an <b>admin</b> in the channel, then forward a message from it.",
            reply_markup=back_kb(),
        )
        return

    ok, detail = bot_is_admin(channel_id)
    if not ok:
        bot.send_message(
            chat_id,
            f"⚠️ <b>The bot is not an admin in this channel</b>\n"
            f"🔹 Channel : <b>{esc(title)}</b>\n🔹 Status : <code>{esc(detail)}</code>\n{SOFT}\n"
            f"💙 Channel → Administrators → Add Admin → add this bot (Post Messages ON), "
            f"then send the channel ID again or forward a message from it.",
            reply_markup=back_kb(),
        )
        return

    state["channel_id"] = str(channel_id)
    state["channel_title"] = title
    state["await_channel"] = False
    broker = state.get("pending_broker") or eng.cfg.get("broker", "tradowix")

    try:
        eng.bind_telegram(BOT_TOKEN, channel_id)
    except Exception as exc:
        bot.send_message(chat_id, f"⚠️ Channel bind failed: <code>{esc(exc)}</code>", reply_markup=back_kb())
        return

    try:
        bot.send_message(channel_id, f"{header('CHANNEL CONNECTED')}💠 <i>Signals will be posted in this channel.</i>")
    except Exception as exc:
        bot.send_message(
            chat_id,
            f"⚠️ <b>Cannot post messages to this channel</b>\n<code>{esc(exc)}</code>\n{SOFT}\n"
            f"💙 Give the bot the <b>Post Messages</b> permission, then try again.",
            reply_markup=back_kb(),
        )
        return

    if eng.running():
        bot.send_message(chat_id, "⚠️ Engine is already running — stop it first.", reply_markup=stop_kb())
        return

    if eng.start_auto(broker):
        bot.send_message(
            chat_id,
            f"{header('AUTO SCAN STARTING')}"
            f"🔹 <b>Channel</b> : <b>{esc(title)}</b>\n"
            f"🔹 <b>Channel ID</b> : <code>{esc(channel_id)}</code>\n{SOFT}\n"
            f"💠 <i>Preparing pairs + AI… signals will go straight to your channel.</i>",
            reply_markup=stop_kb(),
        )
    else:
        bot.send_message(chat_id, "⚠️ The engine did not start.", reply_markup=back_kb())


@bot.message_handler(
    func=lambda m: bool(raw_update(m).get("forward_from_chat") or raw_update(m).get("forward_origin")),
    content_types=["text", "photo", "video", "document", "audio", "voice", "animation",
                   "sticker", "video_note", "poll", "location", "contact"],
)
def forwarded_channel_message(message):
    if not message.from_user or not is_owner(message.from_user.id):
        return
    chat_id = message.chat.id
    state = st(chat_id)
    channel_id, title = extract_channel_id(message)
    if not channel_id:
        if state.get("await_channel"):
            bot.send_message(
                chat_id,
                "❌ This forward is not from a channel. Forward a message from your <b>channel</b> "
                "or send the channel ID.",
                reply_markup=back_kb(),
            )
        return
    if not state.get("await_channel"):
        bot.send_message(
            chat_id,
            f"🔹 Channel ID: <code>{esc(channel_id)}</code>"
            f"{f' • <b>{esc(title)}</b>' if title else ''}",
            reply_markup=back_kb(),
        )
        return
    bot.send_message(chat_id, f"🔎 Channel detected: <code>{esc(channel_id)}</code> — verifying…")
    threading.Thread(target=connect_channel_and_start, args=(chat_id, channel_id), daemon=True).start()


# ── COMMANDS ────────────────────────────────────────────────
@bot.message_handler(commands=["start", "menu", "help", "home", "panel"])
def cmd_start(message):
    if not is_owner(message.from_user.id):
        bot.send_message(message.chat.id, "⛔ This bot is private.")
        return
    _s = st(message.chat.id)
    _s["await_pair"] = False
    _s["await_channel"] = False
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


# ── MANUAL PAIR TEXT (state machine instead of next_step_handler) ──
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

    if state.get("await_channel"):
        target = parse_channel_text(text)
        if not target:
            bot.send_message(
                chat_id,
                "❌ That is not a valid channel ID. Send an ID like <code>-1001234567890</code>, "
                "send an <code>@username</code>, or forward any message from the channel.",
                reply_markup=back_kb(),
            )
            return
        bot.send_message(chat_id, "🔎 Verifying the channel…")
        threading.Thread(target=connect_channel_and_start, args=(chat_id, target), daemon=True).start()
        return

    if state.get("fs") and fs_text(chat_id, text):
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
        bot.send_message(chat_id, "❌ Pair not found. Send a correct pair name (for example <code>EURUSD</code>).",
                         reply_markup=back_kb())
        return
    state["pair"] = pair
    state["await_pair"] = False
    bot.send_message(chat_id, f"{header('PAIR SELECTED')}🔹 <b>{esc(pair)}</b>\n{SOFT}\n💙 Choose a timeframe:",
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
        state["await_channel"] = False
        state["fs"] = None
        send_home(chat_id, call.message.message_id)
        return

    # ---- OTC FS (future3.py) — works even if the quotex engine is down ----
    if data == "m:fs":
        edit(call, f"{header('OTC FS — FUTURE SIGNAL')}"
                   f"🔮 <b>GHOST FUTURE AI v8.0</b> • 25-engine + backtest\n{SOFT}\n"
                   f"💙 <i>Select the market</i>",
             kb([[("🩵 OTC", "fs:mkt:OTC"), ("🟦 LIVE", "fs:mkt:LIVE")],
                 [("🔹 Main Menu", "m:home")]]))
        return
    if data.startswith("fs:mkt:"):
        market = data.rsplit(":", 1)[-1]
        threading.Thread(target=fs_start, args=(chat_id, market), daemon=True).start()
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
                edit(call, "⚠️ Choose a pair from Manual Signal first.", back_kb())
                return
            tf = data.split(":", 1)[-1]
            if eng.start_manual(broker, pair, tf):
                edit(call, f"{header('MANUAL WATCH STARTING')}🔹 {esc(pair)} • <b>{esc(tf)}</b>", stop_kb())
            else:
                edit(call, "⚠️ Engine is already running — stop it first.", stop_kb())
            return

        if data == "m:auto":
            edit(call, broker_panel("AUTO SCAN", eng.broker_label()), broker_kb("auto"))
        elif data == "m:manual":
            edit(call, broker_panel("MANUAL SIGNAL", eng.broker_label()), broker_kb("manual"))
        elif data.startswith("b:auto:"):
            broker = data.rsplit(":", 1)[-1]
            if eng.running():
                edit(call, "⚠️ Engine is already running — stop it first.", stop_kb())
            else:
                eng.set_broker(broker)
                ask_channel(call, broker)
        elif data.startswith("b:manual:"):
            broker = data.rsplit(":", 1)[-1]
            state["broker"] = broker
            state["pair"] = None
            state["await_pair"] = True
            edit(call, f"{header('MANUAL SIGNAL')}🔹 <i>Loading live pairs…</i>", back_kb())
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
            edit(call, f"{header('PRE-ANALYSIS')}🩵 <i>Running… the result will arrive shortly.</i>", back_kb())
            threading.Thread(target=run_calibration, args=(chat_id,), daemon=True).start()
        elif data == "m:partial":
            bot.send_message(chat_id, eng.send_partial(), reply_markup=back_kb())
        elif data == "m:reset":
            bot.send_message(chat_id, eng.reset_partial(), reply_markup=back_kb())
        elif data == "m:stop":
            eng.stop()
            bot.send_message(chat_id, "⛔ Stop requested. The current task will shut down safely.", reply_markup=back_kb())
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
    """Fetch live pairs in the background to avoid a Telegram timeout."""
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
        f"{SOFT}\n💙 <i>Type and send the pair name.</i>",
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


# ── POLLING (409-Conflict proof) ────────────────────────────
#  Error 409 = koi dusra process/deployment isi BOT_TOKEN par
#  getUpdates maar raha hai. Neeche ka "takeover" loop purani
#  polling session ko force-close karke hi polling start karta hai.

POLL_TIMEOUT = 25          # long-poll seconds
TAKEOVER_TRIES = 30        # ~ up to 2.5 min waiting for old instance to die


def _force_release_session():
    """Webhook hatao + offset -1 se ek dummy getUpdates maar ke purani
    long-poll session ko Telegram se todo. True = ab hum akele hain."""
    try:
        bot.delete_webhook(drop_pending_updates=True)
    except Exception as exc:
        log.warning("delete_webhook failed: %s", exc)
    try:
        # offset=-1, timeout=0 -> instantly returns; agar 409 aaya to
        # matlab dusra instance abhi bhi zinda hai.
        bot.get_updates(offset=-1, timeout=0, long_polling_timeout=0)
        return True
    except ApiTelegramException as exc:
        if getattr(exc, "error_code", None) == 409:
            return False
        log.warning("get_updates probe error: %s", exc)
        return False
    except Exception as exc:
        log.warning("get_updates probe error: %s", exc)
        return False


def takeover():
    """Jab tak Telegram hume single instance na maan le, wait karo."""
    for attempt in range(1, TAKEOVER_TRIES + 1):
        if _force_release_session():
            if attempt > 1:
                log.info("Session acquired after %s attempts", attempt)
            return True
        log.warning(
            "409 Conflict: purana instance abhi bhi poll kar raha hai "
            "(try %s/%s). 5s wait...", attempt, TAKEOVER_TRIES
        )
        time.sleep(5)
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
    log.info("Starting Telegram polling (pid=%s)", os.getpid())

    # Railway rolling-deploy me purana container thoda der zinda reh sakta hai.
    # Default 0 — takeover() khud 409 handle kar leta hai, isliye faltu wait nahi.
    startup_delay = int(os.environ.get("STARTUP_DELAY", "0"))
    if startup_delay > 0:
        log.info("Startup delay %ss (old deployment ko marne do)", startup_delay)
        time.sleep(startup_delay)

    if not takeover():
        log.error(
            "Doosra instance abhi bhi chal raha hai. Ye process exit kar raha hai "
            "taaki dono aapas me na ladein. Railway me purani deployment / "
            "duplicate service / local run band karo."
        )
        sys.exit(1)

    log.info("Session acquired — bot ONLINE, updates sun raha hai ✅")

    set_commands()
    if core is None:
        notify(engine_down_text())

    backoff = 5
    while True:
        try:
            bot.polling(
                non_stop=True,
                interval=0,
                timeout=POLL_TIMEOUT,
                long_polling_timeout=POLL_TIMEOUT,
                skip_pending=False,
                allowed_updates=["message", "callback_query"],
            )
            backoff = 5
        except ApiTelegramException as exc:
            try:
                bot.stop_polling()
            except Exception:
                pass
            if getattr(exc, "error_code", None) == 409:
                log.error("409 Conflict — session dobara le rahe hain...")
                if not takeover():
                    log.error("Takeover fail. Exiting so Railway restarts clean.")
                    sys.exit(1)
                backoff = 5
                continue
            log.exception("Telegram API error; retry in %ss", backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except Exception:
            try:
                bot.stop_polling()
            except Exception:
                pass
            log.exception("Polling stopped; retry in %ss", backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    run()
