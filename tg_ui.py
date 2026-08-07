# ============================================================
#  MONARCH TELEGRAM UI  —  keyboards + premium HTML panels
# ============================================================
from telebot import types

BRAND = "👑 <b>MONARCH PREMIUM</b>"
LINE = "━━━━━━━━━━━━━━━━━━━━"


def kb(rows):
    m = types.InlineKeyboardMarkup()
    for row in rows:
        m.row(*[types.InlineKeyboardButton(t, callback_data=d) for t, d in row])
    return m


def main_panel(cfg, broker_label, scanning, mode, version, weekday, clock, session):
    st = "🟢 RUNNING" if scanning else "🔴 IDLE"
    return (
        f"{BRAND}  <code>{version}</code>\n{LINE}\n"
        f"🏦 Broker        : <b>{broker_label}</b>\n"
        f"📡 Engine        : <b>{st}</b>{f'  ({mode})' if scanning else ''}\n"
        f"🕒 Broker time   : <b>{clock}</b>  (UTC+6)\n"
        f"📅 Day / Session : <b>{weekday}</b> • {session}\n"
        f"⏱ Timeframe     : <b>{cfg.get('timeframe', 'M1')}</b>\n"
        f"🖼 Charts        : <b>{'ON' if cfg.get('charts') else 'OFF'}</b>\n"
        f"🛡 Max loss-risk : <b>{int(cfg.get('max_loss_prob', 0.35) * 100)}%</b>\n"
        f"⚡ Send before   : <b>{cfg.get('send_before', 10)}s</b>\n{LINE}\n"
        f"<i>Neeche se option choose karo 👇</i>"
    )


def main_kb(scanning):
    rows = [
        [("⚡ Auto Scan", "m:auto"), ("🎯 Manual Signal", "m:manual")],
        [("⚙️ Settings", "m:settings"), ("📊 Stats", "m:stats")],
        [("🔁 Pre-Analysis", "m:calib"), ("🧠 AI Brain", "m:ai")],
        [("⏰ Best Times", "m:times"), ("📤 Send Partial", "m:partial")],
        [("♻️ Reset Partial", "m:reset"), ("🔄 Refresh", "m:home")],
    ]
    if scanning:
        rows.insert(0, [("⛔ STOP ENGINE", "m:stop")])
    return kb(rows)


def broker_panel(mode, current):
    return (
        f"{BRAND}\n{LINE}\n"
        f"🎛 <b>SELECT BROKER FOR {mode}</b>\n{LINE}\n"
        f"🟦 <b>Quotex</b>   — Qx.php candles + Qx live ticks\n"
        f"🟩 <b>Tradowix</b> — railway candle API + live ticks\n{LINE}\n"
        f"<i>Last used: {current}</i>"
    )


def broker_kb(mode_key):
    return kb([
        [("🟦 Quotex", f"b:{mode_key}:quotex"), ("🟩 Tradowix", f"b:{mode_key}:tradowix")],
        [("◀ Back", "m:home")],
    ])


def settings_panel(cfg, broker_label):
    return (
        f"{BRAND}\n{LINE}\n⚙️ <b>SETTINGS</b>\n{LINE}\n"
        f"🏦 Broker        : <b>{broker_label}</b>\n"
        f"⏱ Timeframe     : <b>{cfg.get('timeframe', 'M1')}</b>\n"
        f"🖼 Charts        : <b>{'ON' if cfg.get('charts') else 'OFF'}</b>\n"
        f"📤 Auto partial  : <b>{'ON' if cfg.get('auto_partial') else 'OFF'}</b>\n"
        f"🛡 Max loss-risk : <b>{int(cfg.get('max_loss_prob', 0.35) * 100)}%</b>\n"
        f"⚡ Send before   : <b>{cfg.get('send_before', 10)}s</b>\n{LINE}"
    )


def settings_kb(cfg, timeframes):
    rows = [
        [("🏦 Broker", "s:broker"), ("🖼 Charts ON/OFF", "s:charts")],
        [("📤 Auto partial", "s:autopartial")],
        [(f"⏱ {t}", f"s:tf:{t}") for t in timeframes[:4]],
        [("🛡 Risk −5%", "s:risk:-5"), ("🛡 Risk +5%", "s:risk:5")],
        [("⚡ Send −5s", "s:sb:-5"), ("⚡ Send +5s", "s:sb:5")],
        [("◀ Back", "m:home")],
    ]
    return kb(rows)


def tf_kb(timeframes):
    return kb([[(f"⏱ {t}", f"mtf:{t}") for t in timeframes[:4]], [("◀ Back", "m:home")]])


def back_kb():
    return kb([[("◀ Main Menu", "m:home")]])


def stop_kb():
    return kb([[("⛔ STOP ENGINE", "m:stop")], [("◀ Main Menu", "m:home")]])


def block(title, body):
    return f"{BRAND}\n{LINE}\n<b>{title}</b>\n{LINE}\n<pre>{body}</pre>"