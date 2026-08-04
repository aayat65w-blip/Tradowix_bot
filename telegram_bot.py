# ============================================================
#   MONARCH PREMIUM BOT — TELEGRAM EDITION  v50.0-TG
#   Full Telegram front-end for the TRADOWIX AI SNIPER engine.
#
#   Har feature jo terminal bot me tha, yahan button par hai:
#     1  Auto Scan            (pre-analysis + AI + 10s early signal)
#     2  Manual Pair          (koi bhi pair + timeframe)
#     3  Settings             (charts / timeframe / risk / send-before / proxy)
#     4  Stats + Day Profile
#     5  Re-run Pre-Analysis + API Route test + AI retrain
#     6  Send Partial   7 Reset Partial
#     8  Stop engine
#     9  AI Brain + Accuracy panel
#     0  Best Trading Times
#     +  Live status, pair list, last signals, logs, help
#
#   Engine file : monarch_core.py  (tradowix9.py = v50 AI SNIPER)
#   Run         : python telegram_bot.py
# ============================================================

import os
import io
import json
import time
import html
import threading
import traceback
from collections import deque

import requests

import monarch_core as core

# ─────────────────────────────────────────────────────────────
#  CREDENTIALS
#  BOT_TOKEN / OWNER_ID env se, warna telegram_config.json se.
# ─────────────────────────────────────────────────────────────
TG_CONFIG_FILE = "telegram_config.json"


def _load_tg_cfg():
    cfg = {}
    if os.path.exists(TG_CONFIG_FILE):
        try:
            with open(TG_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    cfg["token"] = (os.environ.get("BOT_TOKEN") or cfg.get("token") or "").strip()
    cfg["owner_id"] = str(os.environ.get("OWNER_ID") or cfg.get("owner_id") or "").strip()
    cfg.setdefault("allowed", [])          # extra chat ids
    return cfg


def _save_tg_cfg(cfg):
    try:
        with open(TG_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


TG = _load_tg_cfg()
TOKEN = TG["token"]
if not TOKEN:
    print("[!] BOT_TOKEN missing.  Set env BOT_TOKEN=123:ABC  (or telegram_config.json)")
    raise SystemExit(1)

API = f"https://api.telegram.org/bot{TOKEN}"
SESSION = requests.Session()

BOT_TITLE = f"{core.BOT_NAME} • {core.BROKER} {core.BOT_VERSION}"


# ─────────────────────────────────────────────────────────────
#  TELEGRAM TRANSPORT (raw + fast)
# ─────────────────────────────────────────────────────────────
def tg_call(method, payload=None, files=None, timeout=30):
    try:
        if files:
            r = SESSION.post(f"{API}/{method}", data=payload or {}, files=files, timeout=timeout)
        else:
            r = SESSION.post(f"{API}/{method}", json=payload or {}, timeout=timeout)
        j = r.json()
        if not j.get("ok"):
            core.log_line(f"tg {method} error: {r.text[:300]}")
        return j
    except Exception as e:
        core.log_line(f"tg {method} exception: {e}")
        return {"ok": False, "description": str(e)}


def esc(t):
    return html.escape(str(t), quote=False)


def send(chat_id, text, kb=None, preview=False):
    payload = {
        "chat_id": chat_id,
        "text": text[:4090],
        "parse_mode": "HTML",
        "disable_web_page_preview": not preview,
    }
    if kb:
        payload["reply_markup"] = {"inline_keyboard": kb}
    j = tg_call("sendMessage", payload)
    if not j.get("ok"):
        payload.pop("parse_mode", None)
        payload["text"] = core.strip_tags(text)[:4090]
        j = tg_call("sendMessage", payload)
    return j


def edit(chat_id, msg_id, text, kb=None):
    payload = {
        "chat_id": chat_id,
        "message_id": msg_id,
        "text": text[:4090],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if kb:
        payload["reply_markup"] = {"inline_keyboard": kb}
    j = tg_call("editMessageText", payload)
    if not j.get("ok") and "not modified" not in str(j.get("description", "")).lower():
        return send(chat_id, text, kb)
    return j


def answer(cb_id, text=""):
    tg_call("answerCallbackQuery", {"callback_query_id": cb_id, "text": text[:180]})


def broadcast(text, kb=None):
    for cid in subscribers():
        send(cid, text, kb)


# ─────────────────────────────────────────────────────────────
#  ACCESS
# ─────────────────────────────────────────────────────────────
def subscribers():
    ids = []
    if TG.get("owner_id"):
        ids.append(TG["owner_id"])
    for x in TG.get("allowed", []):
        if str(x) not in ids:
            ids.append(str(x))
    return ids


def allowed(chat_id):
    cid = str(chat_id)
    if not TG.get("owner_id"):
        TG["owner_id"] = cid
        _save_tg_cfg(TG)
        _sync_core_target()
        return True
    return cid in subscribers()


# ─────────────────────────────────────────────────────────────
#  ENGINE STATE
# ─────────────────────────────────────────────────────────────
CFG = core.load_config()
CFG["telegram"] = True
CFG["token"] = TOKEN

SIGNALS = []
WINS, LOSSES = [0], [0]
RC = core.ResultChecker(CFG, SIGNALS, WINS, LOSSES)
RC.start()

ENGINE = {
    "mode": None,           # None | "AUTO" | "MANUAL"
    "thread": None,
    "stop": threading.Event(),
    "pair": None,
    "tf": CFG.get("timeframe", "M1"),
    "started": 0,
    "scans": 0,
    "last": "",
    "pairs": [],
}
LOGS = deque(maxlen=60)
BOOT = time.time()


def _sync_core_target():
    CFG["chat_id"] = TG.get("owner_id", "")
    core.save_config(CFG)


_sync_core_target()


def note(txt, push=False):
    line = f"{core.get_now():%H:%M:%S}  {core.strip_tags(txt)}"
    LOGS.append(line)
    ENGINE["last"] = line
    try:
        core.console.print(f"[dim]{line}[/]")
    except Exception:
        print(line)
    if push:
        broadcast(f"ℹ️ {txt}")


def engine_running():
    t = ENGINE.get("thread")
    return bool(t and t.is_alive())


def uptime():
    s = int(time.time() - BOOT)
    return f"{s // 3600}h {s % 3600 // 60}m"


# ─────────────────────────────────────────────────────────────
#  KEYBOARDS
# ─────────────────────────────────────────────────────────────
def kb_main():
    run = engine_running()
    row1 = ([("⏹ Stop Engine", "stop")] if run
            else [("🚀 Auto Scan", "auto"), ("🎯 Manual Pair", "manual")])
    rows = [
        row1,
        [("📡 Live Status", "status"), ("📊 Stats", "stats")],
        [("🧠 AI Brain", "ai"), ("⏰ Best Times", "times")],
        [("📤 Send Partial", "partial"), ("♻️ Reset Partial", "preset")],
        [("🔁 Re-Analysis", "recalib"), ("🌐 Test Route", "route")],
        [("⚙️ Settings", "set"), ("📋 Pairs", "pairs")],
        [("📜 Last Signals", "hist"), ("🗒 Logs", "logs")],
        [("❓ Help / Guide", "help")],
    ]
    return [[{"text": t, "callback_data": d} for t, d in r] for r in rows]


def kb_back(extra=None):
    rows = []
    if extra:
        rows.append([{"text": t, "callback_data": d} for t, d in extra])
    rows.append([{"text": "⬅️ Menu", "callback_data": "menu"}])
    return rows


def kb_settings():
    tf = CFG.get("timeframe", "M1")
    rows = [
        [("⏱ Timeframe: " + tf, "s_tf")],
        [("🖼 Charts: " + ("ON ✅" if CFG.get("charts") else "OFF ❌"), "s_charts")],
        [("🛡 Max Loss Risk: " + f"{int(CFG.get('max_loss_prob', core.MAX_LOSS_PROB) * 100)}%", "s_risk")],
        [("➖", "s_risk_dn"), ("Risk", "noop"), ("➕", "s_risk_up")],
        [("⏳ Send Before: " + f"{int(CFG.get('send_before', core.SIGNAL_SEND_BEFORE))}s", "s_sb")],
        [("➖", "s_sb_dn"), ("Seconds", "noop"), ("➕", "s_sb_up")],
        [("🎯 Strict Mode: " + ("ON ✅" if core.STRICT_MODE else "OFF ❌"), "s_strict")],
        [("🧠 AI Layer: " + ("ON ✅" if core.AI_ENABLED else "OFF ❌"), "s_ai")],
        [("📨 Telegram Signals: " + ("ON ✅" if CFG.get("telegram") else "OFF ❌"), "s_tg")],
        [("🌐 Proxy: " + (CFG.get("proxy") or "auto"), "s_proxy")],
        [("💾 Save Settings", "s_save")],
        [("⬅️ Menu", "menu")],
    ]
    return [[{"text": t, "callback_data": d} for t, d in r] for r in rows]


# ─────────────────────────────────────────────────────────────
#  TEXT PANELS  (terminal panels ka Telegram version)
# ─────────────────────────────────────────────────────────────
def panel_main():
    run = engine_running()
    mode = ENGINE["mode"] or "IDLE"
    trade = core._TRADE.get("sig") or {}
    acc = core.GUARD.accuracy()
    return (
        f"🏆 <b>{esc(BOT_TITLE)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🗓 {esc(core.weekday_name())} • {esc(core.get_session()[0])} • "
        f"{core.get_now():%H:%M:%S} (UTC+6)\n"
        f"⚙️ Engine: <b>{'🟢 ' + mode if run else '🔴 STOPPED'}</b>\n"
        f"⏱ Timeframe: <b>{esc(CFG.get('timeframe', 'M1'))}</b> • "
        f"Signal <b>{int(CFG.get('send_before', core.SIGNAL_SEND_BEFORE))}s</b> early\n"
        f"🎯 Rolling accuracy: <b>{f'{acc * 100:.1f}%' if acc is not None else 'no data'}</b>"
        f" • Hour power <b>{core.hour_power() * 100:.0f}/100</b>\n"
        f"📈 Signals today: <b>{len(SIGNALS)}</b> • Win <b>{WINS[0]}</b> / Loss <b>{LOSSES[0]}</b>\n"
        f"{'🔒 Live trade: <b>' + esc(core.pretty_pair(trade.get('pair', '?'))) + ' ' + esc(trade.get('entry_time', '--:--')) + '</b>' if core.trade_busy() else '🔓 No live trade'}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Neeche buttons se sab control karo.</i>"
    )


def panel_status():
    trade = core._TRADE.get("sig") or {}
    pend = len([s for s in SIGNALS if s.get("result", "PENDING") == "PENDING"])
    return (
        f"📡 <b>LIVE STATUS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Engine        : <b>{esc(ENGINE['mode'] or 'STOPPED')}</b>"
        f"{' (' + esc(core.pretty_pair(ENGINE['pair'])) + ')' if ENGINE.get('pair') else ''}\n"
        f"Uptime        : {esc(uptime())}\n"
        f"Scans done    : {ENGINE['scans']}\n"
        f"Pairs loaded  : {len(ENGINE['pairs'])}\n"
        f"API route     : <b>{esc(core.route_name())}</b>\n"
        f"Next candle   : {int(core.seconds_to_next(CFG.get('timeframe', 'M1')))}s\n"
        f"Live trade    : {('<b>' + esc(core.pretty_pair(trade.get('pair', '?'))) + ' ' + esc(trade.get('entry_time', '--:--')) + '</b>') if core.trade_busy() else 'none'}\n"
        f"Pending check : {pend}\n"
        f"Cutoff now    : {core.active_cutoff():.0f}  (+{core.GUARD.cutoff_bonus():.1f} guard)\n"
        f"AI gate min   : {core.GUARD.ai_min() * 100:.1f}%\n"
        f"Suspended     : {esc(', '.join(core.pretty_pair(p) for p in core.GUARD.suspended) or 'none')}\n"
        f"Last event    : <i>{esc(ENGINE['last'] or '-')}</i>"
    )


def panel_stats():
    rs = core.load_results()
    w = len([r for r in rs if r["result"] in ("WIN", "WIN MTG")])
    d = len([r for r in rs if r["result"] == "WIN"])
    m = len([r for r in rs if r["result"] == "WIN MTG"])
    l = len([r for r in rs if r["result"] == "LOSS"])
    t = w + l
    out = [
        "📊 <b>STATS + DAY PROFILE</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"TOTAL    : <b>{t}</b>",
        f"WINS     : <b>{w}</b>  (direct {d} • MTG {m})",
        f"LOSSES   : <b>{l}</b>",
        f"WIN RATE : <b>{(w / t * 100) if t else 0:.1f}%</b>",
        f"API ROUTE: {esc(core.route_name())}",
    ]
    cp = core.CALIB.get("pairs", {})
    if cp:
        avgq = sum(s["quality"] for s in cp.values()) / len(cp)
        out.append(f"PRE-ANALYSIS: {len(cp)} pairs • {core.CALIB.get('days', core.CALIB_DAYS)} days "
                   f"• avg quality {avgq * 100:.0f}")
    out += ["", f"🗓 <b>{esc(core.weekday_name())} family profile (self-learned)</b>", "<pre>"]
    wd = core.get_now().weekday()
    prof = core.DAY_PROFILE.get(str(wd), {})
    out.append("FAM  WEIGHT   W/L")
    for f in core.FAMILIES:
        node = prof.get(f, {"w": 1.0, "win": 0, "loss": 0})
        out.append(f"{f:<4} {core.day_weight(f):<8.2f} {node['win']}/{node['loss']}")
    out.append("</pre>")
    return "\n".join(out)


def panel_ai():
    acc = core.GUARD.accuracy()
    lines = [
        "🧠 <b>AI BRAIN + ACCURACY PANEL</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"AI candle models : <b>{len(core.AI.candle)} pairs</b>",
    ]
    if core.AI.candle:
        best = max(core.AI.candle.values(), key=lambda m: m["sure"])
        avg = sum(m["sure"] for m in core.AI.candle.values()) / len(core.AI.candle)
        lines.append(f"Model accuracy   : avg <b>{avg * 100:.1f}%</b> • best <b>{best['sure'] * 100:.1f}%</b>")
    lines += [
        f"Model age        : {f'{(time.time() - core.AI.trained_at) / 3600:.1f} h' if core.AI.trained_at else 'not trained'}",
        f"Live model       : {core.AI.live_n} trades learned",
        f"Pattern memory   : {len(core.AI.memory)} patterns",
        f"Rolling accuracy : <b>{f'{acc * 100:.1f}% (last {len(core.GUARD.recent)})' if acc is not None else 'no data yet'}</b>",
        f"AI gate min      : {core.GUARD.ai_min() * 100:.1f}%",
        f"Cutoff bonus     : +{core.GUARD.cutoff_bonus():.1f}",
        f"Emergency mode   : {'🔴 ON' if core.GUARD.emergency() else '🟢 off'}",
        f"Suspended pairs  : {esc(', '.join(core.pretty_pair(p) for p in core.GUARD.suspended) or 'none')}",
        f"Hour power (now) : {core.hour_power() * 100:.0f}/100",
        "",
        "<b>ACCURACY HAMESHA MAINTAIN RAKHNE KA TARIKA</b>",
        "1. Har 8 ghante me AI model auto-retrain (Re-Analysis se turant bhi).",
        "2. Har result se live model + pattern memory seekhta hai.",
        "3. Accuracy 80% se niche gayi to gate khud strict ho jata hai.",
        "4. 3 back-to-back miss wale pair 45 min auto-suspend.",
        "5. Low-power ghante me kam par behtar signal.",
        "6. Roz ek hi settings par chalao — bar-bar change = learning reset.",
        "7. Payout 75%+ aur stable internet — verification miss = learning miss.",
    ]
    return "\n".join(lines)


def panel_times():
    rows = core.best_hours_table(10)
    out = ["⏰ <b>BEST TRADING HOURS</b> (broker time UTC+6)",
           "━━━━━━━━━━━━━━━━━━━━", "<pre>",
           "HOUR         PWR  W/L    BEST PAIR"]
    for hh, p, w, l, bp, be in rows:
        out.append(f"{hh:02d}:00-{(hh + 1) % 24:02d}:00 {p * 100:>4.0f}  {w}/{l:<4} "
                   f"{core.pretty_pair(bp) if bp != '-' else '-'}")
    out += ["</pre>",
            f"Abhi ka ghanta: <b>{core.get_now():%H:00}</b> → power "
            f"<b>{core.hour_power() * 100:.0f}/100</b>",
            "",
            "• Power 66+ = best signal window",
            "• Power 50-65 = sirf ELITE/STRONG setup",
            "• Power &lt;50 = gate auto-strict (kam but clean signals)",
            "• Forex majors: London 12:00-16:00 + NY overlap 18:00-22:00 (UTC+6)",
            "• OTC pairs: weekend aur 00:00-06:00 sabse stable",
            "• News spike ke 5 min andar bot khud ruk jata hai"]
    return "\n".join(out)


def panel_hist():
    if not SIGNALS:
        return "📜 <b>LAST SIGNALS</b>\n\nAbhi tak koi signal nahi."
    out = ["📜 <b>LAST SIGNALS</b>", "━━━━━━━━━━━━━━━━━━━━"]
    for s in SIGNALS[-15:]:
        r = s.get("result", "PENDING")
        mk = ("✅" if r in ("WIN", "WIN MTG") else "❎" if r == "LOSS"
              else "⚠️" if r == "UNVERIFIED" else "⏳")
        out.append(f"{mk} {esc(s.get('entry_time', '--:--'))} • "
                   f"<b>{esc(core.pretty_pair(s.get('pair', '?')))}</b> • "
                   f"{'BUY' if s.get('direction') == core.UP else 'SELL'} • "
                   f"conf {s.get('conf', 0):.0f}%")
    return "\n".join(out)


def panel_pairs():
    pairs = ENGINE["pairs"] or core.pick_pairs(CFG, quiet=True)
    ENGINE["pairs"] = pairs
    if not pairs:
        return "📋 <b>PAIRS</b>\n\nAPI abhi reachable nahi — route dhundh raha hai. Thodi der baad try karo."
    out = [f"📋 <b>LIVE MAIN PAIRS — {len(pairs)}</b>", "━━━━━━━━━━━━━━━━━━━━"]
    for p in pairs:
        st = core.pair_stats(p) or {}
        q = st.get("quality")
        out.append(f"• <b>{esc(core.pretty_pair(p))}</b>"
                   + (f"  <i>q {q * 100:.0f} • {esc(st.get('behaviour', '-'))}</i>" if q else ""))
    return "\n".join(out)


def panel_help():
    return (
        "❓ <b>GUIDE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<b>🚀 Auto Scan</b> — sab live pairs ka 3-din pre-analysis + AI training, phir har candle "
        "se 10 sec pehle sabse best setup ka signal.\n"
        "<b>🎯 Manual Pair</b> — sirf ek chuna hua pair watch karta hai.\n"
        "<b>⚙️ Settings</b> — timeframe, chart, loss-risk %, send-before, strict mode, AI on/off.\n"
        "<b>📊 Stats</b> — win/loss, win-rate, day family profile.\n"
        "<b>🧠 AI Brain</b> — model accuracy, live learning, accuracy guard.\n"
        "<b>⏰ Best Times</b> — kis ghante me best signal milta hai.\n"
        "<b>📤 Partial</b> — ab tak ke signals ka summary bhejta hai; ♻️ Reset naya batch shuru karta hai.\n"
        "<b>🔁 Re-Analysis</b> — pre-analysis + AI model turant dobara train.\n\n"
        "<b>Commands</b>: /start /menu /auto /stop /status /stats /ai /times /partial "
        "/reset /pairs /settings /recalib /route /logs /id /help"
    )


# ─────────────────────────────────────────────────────────────
#  ENGINE LOOPS  (terminal run_auto / run_manual ka headless version)
# ─────────────────────────────────────────────────────────────
def _prepare(pairs):
    core.run_pre_analysis(pairs, CFG)
    try:
        core.AI.train_all(pairs, CFG)
    except Exception as e:
        core.log_line(f"ai boot: {e}")


def _trade_gate_wait(tf, stop):
    """Live trade ke dauran koi nayi analysis nahi."""
    if core.trade_busy():
        stop.wait(2)
        return True
    return False


def auto_loop(chat_id, stop):
    tf = CFG.get("timeframe", "M1")
    send_before = int(CFG.get("send_before", core.SIGNAL_SEND_BEFORE))
    pairs = core.pick_pairs(CFG, quiet=True)
    if not pairs:
        send(chat_id, "⚠️ API abhi reachable nahi — route dhundha ja raha hai. Thodi der baad "
                      "<b>Auto Scan</b> dobara dabao.", kb_back())
        ENGINE["mode"] = None
        return

    send(chat_id, f"🔎 <b>PRE-ANALYSIS</b> shuru — {len(pairs)} pairs • {core.CALIB_DAYS} din ka "
                  f"M1 data + AI training…\n<i>Pehli baar 1-3 min lag sakte hain.</i>")
    _prepare(pairs)

    pairs = core.pick_pairs(CFG, quiet=True)
    tradable = [p for p in pairs if (core.pair_stats(p) or {}).get("quality", 1) >= core.MIN_PAIR_QUALITY]
    if tradable:
        pairs = tradable
    pairs = pairs[:core.MAX_PAIRS]
    ENGINE["pairs"] = pairs

    core.start_rolling_prefetch(pairs, CFG)
    send(chat_id,
         f"🚀 <b>AUTO SCAN LIVE</b>\n"
         f"• Pairs: <b>{len(pairs)}</b>\n"
         f"• Timeframe: <b>{tf}</b>\n"
         f"• Signal: <b>{send_before}s</b> candle se pehle\n"
         f"• AI models: <b>{len(core.AI.candle)}</b> • hour power <b>{core.hour_power() * 100:.0f}</b>\n"
         f"• Day profile: {esc(core.weekday_name())} • route {esc(core.route_name())}\n"
         f"<i>Signal apne aap yahan aayega. Result bhi auto verify hoga.</i>",
         kb_back([("⏹ Stop Engine", "stop"), ("📡 Status", "status")]))

    try:
        while not stop.is_set():
            if _trade_gate_wait(tf, stop):
                continue
            rem = core.seconds_to_next(tf)
            if rem > core.PRESCAN_START_BEFORE:
                stop.wait(min(rem - core.PRESCAN_START_BEFORE, 3))
                continue
            if rem < send_before + 2:
                stop.wait(max(rem + 0.6, 0.5))
                continue

            ENGINE["scans"] += 1
            ranked, checked = core.scan_best(pairs, tf, CFG, verbose=False)
            note(f"scan #{ENGINE['scans']} — {checked} pairs analysed")
            if not ranked:
                stop.wait(max(core.seconds_to_next(tf) + 0.5, 1))
                continue

            while core.seconds_to_next(tf) > send_before + 3 and not stop.is_set():
                time.sleep(0.1)
            if stop.is_set():
                break

            sendable = ([a for a in ranked if a.get("grade") in core.SENDABLE_GRADES]
                        if core.STRICT_MODE else ranked)
            if not sendable:
                if ranked:
                    b = ranked[0]
                    note(f"no setup above cutoff {core.active_cutoff():.0f} — best "
                         f"{core.pretty_pair(b['pair'])} {b.get('setup_score', 0):.0f}")
                stop.wait(max(core.seconds_to_next(tf) + 0.5, 1))
                continue

            final = None
            for cand in sendable:
                if core.seconds_to_next(tf) < core.MIN_SEND_BUFFER:
                    break
                final = core.confirm_with_forming(cand, CFG)
                if final:
                    break
            if not final:
                note("live candle contradicted every setup — candle skipped")
                stop.wait(max(core.seconds_to_next(tf) + 0.5, 1))
                continue

            while core.seconds_to_next(tf) > send_before and not stop.is_set():
                time.sleep(0.05)
            if stop.is_set():
                break
            if core.seconds_to_next(tf) < core.MIN_SEND_BUFFER:
                note("send window missed — next candle")
                stop.wait(max(core.seconds_to_next(tf) + 0.5, 1))
                continue

            core.dispatch(final, CFG, RC, SIGNALS)
            note(f"SIGNAL {core.pretty_pair(final['pair'])} {final['direction']}")
            stop.wait(max(core.seconds_to_next(tf) + 1, 2))
    except Exception as e:
        core.log_line(f"auto loop: {e}\n{traceback.format_exc()}")
        send(chat_id, f"⚠️ Auto scan error: <code>{esc(e)}</code>")
    finally:
        core.stop_rolling_prefetch()
        ENGINE["mode"] = None
        ENGINE["pair"] = None
        send(chat_id, "⏹ <b>Auto scan stopped.</b>", kb_main())


def manual_loop(chat_id, pair, tf, stop):
    send_before = int(CFG.get("send_before", core.SIGNAL_SEND_BEFORE))
    send(chat_id, f"🎯 <b>MANUAL MODE</b> — {esc(core.pretty_pair(pair))} • {esc(tf)}\n"
                  f"<i>Pre-analysis + AI training chal rahi hai…</i>")
    _prepare([pair])
    ENGINE["pairs"] = [pair]
    send(chat_id, f"👁 Watching <b>{esc(core.pretty_pair(pair))} {esc(tf)}</b> — signal "
                  f"{send_before}s pehle.",
         kb_back([("⏹ Stop Engine", "stop"), ("📡 Status", "status")]))
    try:
        while not stop.is_set():
            if _trade_gate_wait(tf, stop):
                continue
            rem = core.seconds_to_next(tf)
            if rem > core.PRESCAN_START_BEFORE:
                stop.wait(min(rem - core.PRESCAN_START_BEFORE, 5))
                continue
            if rem < send_before + 2:
                stop.wait(max(rem + 0.6, 0.5))
                continue

            a = core.analyze(pair, tf, CFG)
            ENGINE["scans"] += 1
            if not a:
                note("no data for this pair right now")
                stop.wait(5)
                continue
            a["grade"], a["stake"], a["why"] = core.grade_setup(a, CFG)
            a["score"] = core.rank_score(a)
            note(f"{a['direction']} {a['grade']} conf {a['conf']:.0f}% risk {a['loss_prob'] * 100:.0f}%")

            if core.STRICT_MODE and a["grade"] not in core.SENDABLE_GRADES:
                stop.wait(max(core.seconds_to_next(tf) + 1, 2))
                continue
            while core.seconds_to_next(tf) > send_before + 3 and not stop.is_set():
                time.sleep(0.2)
            final = core.confirm_with_forming(a, CFG)
            if not final:
                stop.wait(max(core.seconds_to_next(tf) + 1, 2))
                continue
            while core.seconds_to_next(tf) > send_before and not stop.is_set():
                time.sleep(0.05)
            if stop.is_set():
                break
            core.dispatch(final, CFG, RC, SIGNALS)
            note(f"SIGNAL {core.pretty_pair(final['pair'])} {final['direction']}")
            stop.wait(max(core.seconds_to_next(tf) + 1, 2))
    except Exception as e:
        core.log_line(f"manual loop: {e}\n{traceback.format_exc()}")
        send(chat_id, f"⚠️ Manual error: <code>{esc(e)}</code>")
    finally:
        ENGINE["mode"] = None
        ENGINE["pair"] = None
        send(chat_id, "⏹ <b>Manual mode stopped.</b>", kb_main())


def start_engine(chat_id, mode, pair=None):
    if engine_running():
        send(chat_id, "⚠️ Engine pehle se chal raha hai. Pehle <b>⏹ Stop</b> karo.", kb_main())
        return
    ENGINE["stop"] = threading.Event()
    ENGINE["mode"] = mode
    ENGINE["pair"] = pair
    ENGINE["tf"] = CFG.get("timeframe", "M1")
    ENGINE["started"] = time.time()
    ENGINE["scans"] = 0
    if mode == "AUTO":
        t = threading.Thread(target=auto_loop, args=(chat_id, ENGINE["stop"]), daemon=True)
    else:
        t = threading.Thread(target=manual_loop,
                             args=(chat_id, pair, CFG.get("timeframe", "M1"), ENGINE["stop"]),
                             daemon=True)
    ENGINE["thread"] = t
    t.start()


def stop_engine(chat_id):
    if not engine_running():
        send(chat_id, "Engine already stopped.", kb_main())
        return
    ENGINE["stop"].set()
    send(chat_id, "⏹ Stopping engine… (current candle finish hone do)")


# ─────────────────────────────────────────────────────────────
#  BACKGROUND TASKS  (heavy work never blocks the bot)
# ─────────────────────────────────────────────────────────────
def bg(fn, *a, **k):
    threading.Thread(target=fn, args=a, kwargs=k, daemon=True).start()


def task_recalib(chat_id):
    send(chat_id, "🔁 <b>Re-analysis + AI retrain</b> shuru… (1-3 min)")
    try:
        pairs = core.pick_pairs(CFG, quiet=True)
        if not pairs:
            send(chat_id, "⚠️ API reachable nahi — route retry karo.", kb_back([("🌐 Test Route", "route")]))
            return
        core.run_pre_analysis(pairs, CFG, force=True)
        core.AI.train_all(pairs, CFG, force=True)
        cp = core.CALIB.get("pairs", {})
        avgq = (sum(s["quality"] for s in cp.values()) / len(cp) * 100) if cp else 0
        send(chat_id, f"✅ <b>Done.</b> {len(cp)} pairs studied ({core.CALIB_DAYS} din) • "
                      f"avg quality {avgq:.0f} • AI models {len(core.AI.candle)}",
             kb_back([("🧠 AI Brain", "ai"), ("⏰ Best Times", "times")]))
    except Exception as e:
        send(chat_id, f"⚠️ Re-analysis error: <code>{esc(e)}</code>", kb_back())


def task_route(chat_id):
    send(chat_id, "🌐 API route test ho raha hai…")
    core._ROUTE["name"] = None
    ok = core.ensure_route(CFG)
    p = core.api_pairs(CFG, force=True)
    if ok and p:
        send(chat_id, f"✅ Route <b>{esc(core.route_name())}</b> • API OK — {len(p)} symbols", kb_back())
    else:
        send(chat_id, "❌ Koi route nahi mila — bot khud retry karta rahega.", kb_back())


# ─────────────────────────────────────────────────────────────
#  PAIR PICKER (manual mode)
# ─────────────────────────────────────────────────────────────
PAIR_PAGE = 12


def kb_pairs(page=0):
    pairs = ENGINE["pairs"] or core.pick_pairs(CFG, quiet=True)
    ENGINE["pairs"] = pairs
    chunk = pairs[page * PAIR_PAGE:(page + 1) * PAIR_PAGE]
    rows, row = [], []
    for i, p in enumerate(chunk):
        row.append({"text": core.pretty_pair(p), "callback_data": f"p_{page * PAIR_PAGE + i}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    nav = []
    if page > 0:
        nav.append({"text": "⬅️ Prev", "callback_data": f"pg_{page - 1}"})
    if (page + 1) * PAIR_PAGE < len(pairs):
        nav.append({"text": "Next ➡️", "callback_data": f"pg_{page + 1}"})
    if nav:
        rows.append(nav)
    rows.append([{"text": "⬅️ Menu", "callback_data": "menu"}])
    return rows


# ─────────────────────────────────────────────────────────────
#  ROUTER
# ─────────────────────────────────────────────────────────────
def handle_action(chat_id, msg_id, data, cb_id=None):
    def reply(text, kb=None):
        if msg_id:
            edit(chat_id, msg_id, text, kb)
        else:
            send(chat_id, text, kb)

    if data in ("menu", "start"):
        reply(panel_main(), kb_main())
    elif data == "noop":
        pass
    elif data == "auto":
        reply(panel_main(), kb_main())
        start_engine(chat_id, "AUTO")
    elif data == "manual":
        reply("🎯 <b>Pair chuno</b> — manual watch mode:", kb_pairs(0))
    elif data.startswith("pg_"):
        reply("🎯 <b>Pair chuno</b> — manual watch mode:", kb_pairs(int(data[3:])))
    elif data.startswith("p_"):
        idx = int(data[2:])
        pairs = ENGINE["pairs"] or core.pick_pairs(CFG, quiet=True)
        if idx < len(pairs):
            reply(panel_main(), kb_main())
            start_engine(chat_id, "MANUAL", pairs[idx])
    elif data == "stop":
        stop_engine(chat_id)
    elif data == "status":
        reply(panel_status(), kb_back([("🔄 Refresh", "status")]))
    elif data == "stats":
        reply(panel_stats(), kb_back([("🔄 Refresh", "stats")]))
    elif data == "ai":
        reply(panel_ai(), kb_back([("🔁 Retrain AI", "recalib")]))
    elif data == "times":
        reply(panel_times(), kb_back([("🔄 Refresh", "times")]))
    elif data == "hist":
        reply(panel_hist(), kb_back([("🔄 Refresh", "hist")]))
    elif data == "pairs":
        reply(panel_pairs(), kb_back([("🔄 Refresh", "pairs")]))
    elif data == "logs":
        body = "\n".join(list(LOGS)[-25:]) or "koi log nahi"
        reply("🗒 <b>ENGINE LOG</b>\n<pre>" + esc(body) + "</pre>", kb_back([("🔄 Refresh", "logs")]))
    elif data == "help":
        reply(panel_help(), kb_back())
    elif data == "partial":
        batch = core.partial_batch(SIGNALS)
        if not batch:
            reply("⚠️ Partial khali hai — is batch me abhi koi signal nahi.", kb_back())
        else:
            core.PARTIAL["sent"] += 1
            send(chat_id, core.make_partial_msg(batch))
            reply(panel_main(), kb_main())
    elif data == "preset":
        core.reset_partial(SIGNALS)
        reply("♻️ <b>Partial reset</b> — naya batch shuru.", kb_back())
    elif data == "recalib":
        bg(task_recalib, chat_id)
        reply(panel_main(), kb_main())
    elif data == "route":
        bg(task_route, chat_id)
        reply(panel_main(), kb_main())

    # ── settings ──
    elif data == "set":
        reply("⚙️ <b>SETTINGS</b>\n<i>Button dabao — turant apply ho jata hai.</i>", kb_settings())
    elif data == "s_tf":
        tfs = core.TIMEFRAMES
        CFG["timeframe"] = tfs[(tfs.index(CFG.get("timeframe", "M1")) + 1) % len(tfs)]
        reply("⚙️ <b>SETTINGS</b>", kb_settings())
    elif data == "s_charts":
        CFG["charts"] = not CFG.get("charts")
        reply("⚙️ <b>SETTINGS</b>", kb_settings())
    elif data in ("s_risk_up", "s_risk_dn", "s_risk"):
        v = CFG.get("max_loss_prob", core.MAX_LOSS_PROB)
        if data == "s_risk_up":
            v += 0.01
        elif data == "s_risk_dn":
            v -= 0.01
        CFG["max_loss_prob"] = max(0.15, min(0.45, round(v, 3)))
        reply("⚙️ <b>SETTINGS</b>", kb_settings())
    elif data in ("s_sb_up", "s_sb_dn", "s_sb"):
        v = int(CFG.get("send_before", core.SIGNAL_SEND_BEFORE))
        if data == "s_sb_up":
            v += 1
        elif data == "s_sb_dn":
            v -= 1
        CFG["send_before"] = max(5, min(30, v))
        reply("⚙️ <b>SETTINGS</b>", kb_settings())
    elif data == "s_strict":
        core.STRICT_MODE = not core.STRICT_MODE
        reply("⚙️ <b>SETTINGS</b>", kb_settings())
    elif data == "s_ai":
        core.AI_ENABLED = not core.AI_ENABLED
        reply("⚙️ <b>SETTINGS</b>", kb_settings())
    elif data == "s_tg":
        CFG["telegram"] = not CFG.get("telegram")
        reply("⚙️ <b>SETTINGS</b>", kb_settings())
    elif data == "s_proxy":
        PENDING[str(chat_id)] = "proxy"
        reply("🌐 Manual proxy URL bhejo (ya <code>auto</code> likho).", kb_back())
    elif data == "s_save":
        core.save_config(CFG)
        reply("💾 Settings saved.", kb_settings())
    else:
        reply(panel_main(), kb_main())

    if cb_id:
        answer(cb_id)


PENDING = {}

COMMANDS = {
    "/start": "menu", "/menu": "menu", "/auto": "auto", "/stop": "stop",
    "/status": "status", "/stats": "stats", "/ai": "ai", "/times": "times",
    "/partial": "partial", "/reset": "preset", "/pairs": "pairs",
    "/settings": "set", "/recalib": "recalib", "/route": "route",
    "/logs": "logs", "/help": "help", "/manual": "manual", "/history": "hist",
}


def handle_message(msg):
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    if text.startswith("/id"):
        send(chat_id, f"🆔 Your chat id: <code>{chat_id}</code>")
        return
    if not allowed(chat_id):
        send(chat_id, "⛔ Access denied. Owner se chat id add karwao.\n"
                      f"Your id: <code>{chat_id}</code>")
        return

    key = str(chat_id)
    if key in PENDING:
        kind = PENDING.pop(key)
        if kind == "proxy":
            CFG["proxy"] = "" if text.lower() in ("auto", "none", "-") else text
            core._ROUTE["name"] = None
            core.save_config(CFG)
            send(chat_id, f"🌐 Proxy set: <b>{esc(CFG['proxy'] or 'auto')}</b>", kb_settings())
        return

    cmd = text.split()[0].lower() if text else ""
    if cmd in COMMANDS:
        if cmd == "/start":
            send(chat_id, panel_main(), kb_main())
        else:
            handle_action(chat_id, None, COMMANDS[cmd])
        return
    send(chat_id, panel_main(), kb_main())


def handle_callback(cb):
    chat_id = cb["message"]["chat"]["id"]
    if not allowed(chat_id):
        answer(cb["id"], "Access denied")
        return
    handle_action(chat_id, cb["message"]["message_id"], cb.get("data", ""), cb["id"])


# ─────────────────────────────────────────────────────────────
#  MAIN LOOP  (long polling — fast + light)
# ─────────────────────────────────────────────────────────────
def set_commands():
    tg_call("setMyCommands", {"commands": [
        {"command": "start", "description": "Main menu"},
        {"command": "auto", "description": "Auto scan start"},
        {"command": "manual", "description": "Manual pair watch"},
        {"command": "stop", "description": "Stop engine"},
        {"command": "status", "description": "Live status"},
        {"command": "stats", "description": "Stats + day profile"},
        {"command": "ai", "description": "AI brain + accuracy"},
        {"command": "times", "description": "Best trading hours"},
        {"command": "partial", "description": "Send partial"},
        {"command": "reset", "description": "Reset partial"},
        {"command": "pairs", "description": "Live pairs"},
        {"command": "settings", "description": "Settings"},
        {"command": "recalib", "description": "Re-analysis + AI retrain"},
        {"command": "route", "description": "Test API route"},
        {"command": "logs", "description": "Engine log"},
        {"command": "id", "description": "Show chat id"},
        {"command": "help", "description": "Guide"},
    ]})


def main():
    print(f"● {BOT_TITLE} — Telegram edition booting…")
    tg_call("deleteWebhook", {"drop_pending_updates": True})
    set_commands()
    core.ensure_route(CFG)
    p = core.api_pairs(CFG)
    print(f"● API: {len(p)} symbols via {core.route_name()}")
    for cid in subscribers():
        send(cid, f"✅ <b>{esc(BOT_TITLE)}</b> online.\n"
                  f"API: {len(p)} symbols • route {esc(core.route_name())}", kb_main())

    offset = None
    while True:
        try:
            r = SESSION.get(f"{API}/getUpdates",
                            params={"timeout": 25, "offset": offset,
                                    "allowed_updates": json.dumps(["message", "callback_query"])},
                            timeout=40)
            j = r.json()
            for u in j.get("result", []):
                offset = u["update_id"] + 1
                try:
                    if "message" in u:
                        handle_message(u["message"])
                    elif "callback_query" in u:
                        handle_callback(u["callback_query"])
                except Exception as e:
                    core.log_line(f"update error: {e}\n{traceback.format_exc()}")
        except requests.exceptions.ReadTimeout:
            continue
        except KeyboardInterrupt:
            print("\n● stopped")
            break
        except Exception as e:
            core.log_line(f"poll error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    main()
