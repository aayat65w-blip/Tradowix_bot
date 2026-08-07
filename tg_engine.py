# ============================================================
#  MONARCH TELEGRAM ENGINE  —  bridge to quotex.py core
#  Koi trading logic yahan duplicate nahi hai: sab core se aata hai.
# ============================================================
import os
import sys
import html
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import quotex as core  # noqa: E402


def capture(fn, *a, **kw):
    """Run a rich-console core function and return its plain text output."""
    try:
        with core.console.capture() as cap:
            fn(*a, **kw)
        return cap.get()[:3500] or "—"
    except Exception as e:
        return f"error: {e}"


def esc(t):
    return html.escape(str(t))


class Engine:
    """One scan session at a time (auto ya manual), background thread me."""

    def __init__(self, notify):
        self.notify = notify                     # notify(text) -> None
        self.cfg = core.load_config()
        self.signals, self.wins, self.losses = [], [0], [0]
        self.rc = core.ResultChecker(self.cfg, self.signals, self.wins, self.losses)
        self.rc.start()
        self.stop_event = threading.Event()
        self.thread = None
        self.mode = None

    # ── config ──────────────────────────────────────────────
    def save(self):
        core.save_config(self.cfg)

    def broker_label(self, key=None):
        return core.broker_label(key or self.cfg.get("broker"))

    def set_broker(self, key):
        core.set_broker(self.cfg, key)
        self.save()
        if core.active_broker(self.cfg) == "tradowix":
            try:
                core.ensure_route(self.cfg)
            except Exception as e:
                core.log_line(f"tg route: {e}")

    def bind_telegram(self, token, chat_id):
        """Signals + results core se hi telegram par jayenge."""
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
        """True => is candle ko skip karo."""
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
            f"⚡ <b>AUTO SCAN LIVE</b>\n🏦 {self.broker_label()} • {len(pairs)} pairs • {tf}\n"
            f"📤 Signal {send_before}s before candle open\n<i>Stop karne ke liye ⛔ dabao.</i>")

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
        p = core._norm_pair(raw)
        if p in pairs:
            return p
        key = raw.upper().replace("-OTC", "").replace("_OTC", "").strip()
        near = [x for x in pairs if key and key in x.upper()]
        return near[0] if near else None

    def start_manual(self, broker, pair, tf):
        return self._start(self._manual, "MANUAL SIGNAL", broker, pair, tf)

    def _manual(self, broker, pair, tf):
        self.set_broker(broker)
        send_before = int(self.cfg.get("send_before", core.SIGNAL_SEND_BEFORE))
        try:
            core.run_pre_analysis([pair], self.cfg)
        except Exception as e:
            core.log_line(f"tg manual pre-analysis: {e}")
        self.notify(
            f"🎯 <b>MANUAL WATCH LIVE</b>\n🏦 {self.broker_label()} • "
            f"<b>{core.pretty_pair(pair)}</b> • {tf}\n📤 Signal {send_before}s before candle open")
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
        return "📤 Partial bhej diya." if ok else "⚠️ Partial khali hai."

    def reset_partial(self):
        core.reset_partial(self.signals)
        return "♻️ Partial reset — naya batch shuru."

    def timeframes(self):
        return list(core.TIMEFRAMES)

    def clock(self):
        return core.get_now().strftime("%H:%M:%S")

    def weekday(self):
        return core.weekday_name()

    def session(self):
        return core.get_session()[0]

    def version(self):
        return f"{core.BOT_NAME} {core.BOT_VERSION}"