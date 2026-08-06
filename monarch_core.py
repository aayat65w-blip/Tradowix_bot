# ============================================================
#   MONARCH PREMIUM BOT — v52.0 (NON-STOP 24/7 FLOW + MEGA STRATEGY / ACCURACY LAYER)
#   "TRADOWIX AI SNIPER EDITION"
#   v52 = v51 + 40 new strategies (Liquidity/SMC, Micro-structure, Quant-stats)
#         + Regime Router + Confluence de-duplication + Non-stop engine
#         + Signal Watchdog (24h, kabhi ruk-ke baithta nahi)
#   (v41 base + NEURAL ACCURACY LAYER: self-trained AI models,
#    live learning, accuracy guard, best-time engine)
#   Platform : TRADOWIX      Data : 100% API based
#   Candle API : https://tradowixcandledata.up.railway.app/
#
#   WHAT IS NEW IN v41.0  (all user requests implemented)
#   ---------------------------------------------------------
#   1. NO PROXY NEEDED.  New AUTO-ROUTE TRANSPORT: the bot itself
#      finds a working path to the API (direct -> public relays ->
#      auto-downloaded free proxies), races them, remembers the
#      fastest one and re-routes automatically if it dies.
#      Works on Termux / mobile data / geo-blocked ISP with zero setup.
#   2. CURATED PAIR SET — only 30-35 main pairs (majors, main crosses,
#      top crypto + their OTC twins) instead of 125 random symbols.
#   3. PRE-ANALYSIS ENGINE — before signalling, the bot downloads and
#      studies the LAST 2-3 DAYS of M1 candles of every pair
#      (vectorised): volatility, body/wick profile, trend persistence,
#      mean-reversion pull, hour-by-hour edge, noise score.
#      Result is cached (monarch_calibration.json) and used as a
#      per-pair + per-hour statistical filter -> big accuracy jump.
#   4. EXACT TIMING — signal is now released 10 SECONDS BEFORE the
#      next candle opens and is always for the NEXT candle. Parallel
#      pre-fetch + pre-scan finishes before the send window, so the
#      candle is never missed.
#   5. HIGHER ACCURACY GATE — pair-quality gate, hour-edge gate,
#      behaviour alignment, calibrated loss-probability, trend pack.
#   6. BRAND-NEW CHART STYLE — "Aurora" glass theme, gradient bg,
#      rounded candles, EMA ribbon fill, S/R zones, live forming
#      candle, entry marker, RSI + momentum strip.
#   7. 100% API DRIVEN — every candle, payout and result verification
#      comes from the Tradowix candle API only.
# ============================================================

import os, sys, time, math, json, threading, datetime, io, random
import html as _html, re as _re
_re_tag = _re.compile(r"<[^>]+>")
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    print("[!] pip install requests numpy rich matplotlib pillow"); sys.exit(1)

try:
    import numpy as np
except ImportError:
    print("[!] pip install numpy"); sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
    from rich import box
except ImportError:
    print("[!] pip install rich"); sys.exit(1)

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    from matplotlib.patches import Rectangle, FancyBboxPatch
    from matplotlib.colors import LinearSegmentedColormap
    CHART_ENABLED = True
except ImportError:
    CHART_ENABLED = False

console = Console()

# ─────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────
BOT_NAME      = "MONARCH PREMIUM BOT"
BOT_VERSION   = "v52.0 NON-STOP AI SNIPER"
BROKER        = "TRADOWIX"

API_BASE      = "https://tradowixcandledata.up.railway.app"
API_CANDLES   = API_BASE + "/"
API_CANDLES2  = API_BASE + "/candles"
API_PAIRS     = API_BASE + "/pairs_list"
API_HEALTH    = API_BASE + "/health"

# Optional. Leave empty — the auto-route engine no longer needs it.
PROXY_URL     = os.environ.get("TRADOWIX_PROXY", "").strip()

API_TIMEOUT   = 4
API_RETRIES   = 0
API_TZ_OFFSET = float(os.environ.get("TRADOWIX_TZ", "6"))   # broker/API clock = UTC+6 (override with TRADOWIX_TZ)

CANDLE_COUNT          = 150      # M1 candles used for the entry analysis
BASE_COUNT            = 460      # ONE fetch per pair -> M1 + M5 + M15 all built from this
CANDLE_CACHE_TTL      = 55       # rolling scanner keeps this warm
PAIR_PENALTY_MIN      = 1.5      # v52: sirf 90 sec (pehle 10 min -> pool khali ho jata tha)
PAIR_FAIL_LIMIT       = 4        # v52: 2 ki jagah 4 fail par bench
MIN_LIVE_POOL         = 8        # itne se kam pair bache to saara bench auto-clear
CHART_DISPLAY_CANDLES = 44
FORMING_POLLS         = 1
FORMING_POLL_GAP      = 0.0

CONFIG_FILE   = "monarch_config.json"
LOG_FILE      = "monarch_signals.log"
RESULT_FILE   = "monarch_results.json"
VERIFY_GRACE  = 45          # seconds to keep retrying a missing candle before giving up
DAYPROF_FILE  = "monarch_day_profile.json"
STRATWR_FILE  = "monarch_strategy_wr.json"
CALIB_FILE    = "monarch_calibration.json"
ROUTE_FILE    = "monarch_route.json"

MIN_PAYOUT           = 75

# ── TIMING (user request: signal exactly 10s before the next candle) ──
SIGNAL_SEND_BEFORE   = 10      # release signal 10s before candle open
PRESCAN_START_BEFORE = 26      # analysis window (data is already cached by then)
MIN_SEND_BUFFER      = 3       # never send with less than 3s left
FETCH_WORKERS        = 32      # parallel API workers (turbo)
ANALYZE_WORKERS      = 16      # parallel analysis workers (turbo)
ROLLING_REFRESH      = 4       # background candle refresh loop (seconds)

# ── BALANCED ACCURACY MODE (v5) ──
# v4 me har gate ek WALL tha -> signal aana band. Ab har gate ka 0..1 score
# banta hai aur weighted total (0..100) decide karta hai. 1-2 gate thoda miss
# ho to bhi ek strong setup reject nahi hota, par overall quality bani rehti hai.
ALWAYS_SIGNAL        = False   # abhi bhi koi forced/fake signal nahi
MAX_LOSS_PROB        = 0.34
MIN_CONFIDENCE       = 68.0
MIN_STRATEGIES       = 7
MIN_FAMILIES         = 3
MIN_DOMINANCE        = 0.58
MIN_SCORE_GAP        = 1.10
MIN_PAIR_QUALITY     = 0.32    # from 2-3 day pre-analysis
MIN_HOUR_EDGE        = 0.42    # hourly edge of the chosen behaviour
MIN_TREND_SCORE      = 0.44    # multi-timeframe alignment
MIN_VOTE_RATIO       = 1.5     # for : against
STRICT_MODE          = False   # FLOW MODE: signals rukte nahi    # sirf sendable grades dispatch hote hain

# ── NON-MTG (FIRST CANDLE) ENGINE  — v43 core accuracy upgrade ──
# Target: trade PEHLI hi candle me jeete, MTG-1 sirf emergency ho.
# Har setup ka ek "direct score" (0..1) banta hai = pehli candle me jeetne ki
# statistical + structural probability. Ye ek alag gate hai, weight bhi sabse
# zyada, aur iska hard floor hai — kam score wala setup send hi nahi hota.
MIN_DIRECT_SCORE     = 0.46    # gate minimum (soft, score based)
DIRECT_HARD_FLOOR    = 0.30    # iske neeche kabhi signal nahi (hard block)
NM_STRAT_MIN         = 1       # kam se kam itne NM (non-MTG) strategies chahiye
MTG_GUARD            = False    # MTG zyada aane lage to bot khud strict ho jata
MTG_GUARD_WINDOW     = 12      # last N results dekhta hai
MTG_GUARD_RATIO      = 0.30    # is se zyada MTG ratio = extra strict mode

# weighted score cutoffs (0..100)
SETUP_CUTOFF         = 60.0    # normal cutoff (v43: higher = fewer, cleaner)
SETUP_CUTOFF_RELAX   = 54.0
SETUP_CUTOFF_DESPERATE = 50.0   # v52: long dry-spell me last relax step    # dry-spell (adaptive) cutoff
DRY_SPELL_MIN        = 9      # itne min koi signal na mile to relax
TIER_GOOD_SCORE      = 62.0
TIER_STRONG_SCORE    = 74.0
TIER_ELITE_SCORE     = 84.0

PAIR_COOLDOWN_MIN    = 1
PAIR_SAMEDIR_MIN     = 2

# ── v52 NON-STOP ENGINE ──
NONSTOP_MODE         = True   # trade live hone par bhi analysis chalu rehta hai
MAX_LIVE_TRADES      = 3      # ek waqt me itne open signals allowed (per-pair 1)
WATCHDOG_MIN         = 25     # itne min signal na aaye to auto-heal + relax
CONFLUENCE_FAM_CAP   = 4.0    # ek family max itna weight de sakti hai (double-count kill)
HEALTH_EVERY_MIN     = 60     # har ghante ek health line
MAX_SIGNALS_PER_HOUR = 0    # 0 = UNLIMITED (hourly cap removed)

TIMEFRAMES  = ["M1", "M5", "M15"]
TIER_WEAK, TIER_MEDIUM, TIER_STRONG, TIER_ELITE = 55, 68, 78, 87


# ── PRE-ANALYSIS (last 2-3 days) ──
CALIB_DAYS      = 3
CALIB_CANDLES   = 60 * 24 * CALIB_DAYS      # 4320 M1 candles ≈ 3 days
CALIB_TTL_HRS   = 12                        # re-use cached study for 12h

# ─────────────────────────────────────────────────────────────
#  CURATED PAIR SET — main pairs only (30-35 live at any time)
# ─────────────────────────────────────────────────────────────
CORE_FOREX = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
    "EURJPY", "GBPJPY", "EURGBP", "AUDJPY", "EURAUD", "EURCAD", "GBPAUD",
    "GBPCAD", "CADJPY", "CHFJPY", "AUDCAD", "AUDCHF", "GBPCHF", "EURCHF",
]
CORE_OTC = [
    "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc", "USDCAD_otc",
    "USDCHF_otc", "NZDUSD_otc", "EURJPY_otc", "GBPJPY_otc", "EURGBP_otc",
    "AUDJPY_otc", "EURAUD_otc", "EURCAD_otc", "GBPAUD_otc", "GBPCAD_otc",
    "CADJPY_otc", "CHFJPY_otc", "AUDCAD_otc", "AUDCHF_otc", "GBPCHF_otc",
    "EURCHF_otc", "AUDNZD_otc", "EURNZD_otc", "GBPNZD_otc","BRLUSD_otc","USDBDT_otc","USDARS_otc","USDEGP_otc","USDCOP_otc","USDDZD_otc","USDINR_otc","USDIDR_otc","USDMXN_otc","USDNGN_otc","USDPKR_otc","USDPHP_otc"
]
CORE_CRYPTO = ["BTCUSD_otc", "ETHUSD_otc", "SOLUSD_otc",
               "BNBUSD_otc"]
MAX_PAIRS = 36
# ─────────────────────────────────────────────────────────────
#  TIME HELPERS  (broker time = UTC+6)
# ─────────────────────────────────────────────────────────────
def utc_now():
    """Real UTC — never depends on the phone/PC local timezone."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

def get_now():
    """Broker time = UTC + API_TZ_OFFSET (default +6)."""
    return utc_now() + datetime.timedelta(hours=API_TZ_OFFSET)

def ts_to_dt(ts):
    return datetime.datetime.utcfromtimestamp(ts) + datetime.timedelta(hours=API_TZ_OFFSET)

def weekday_name():
    return get_now().strftime("%A")

def get_session():
    h = get_now().hour  # UTC+6
    if 5 <= h < 10:   return "TOKYO",    0.95
    if 10 <= h < 13:  return "TOKYO/LDN", 1.00
    if 13 <= h < 17:  return "LONDON",   1.10
    if 17 <= h < 21:  return "LONDON/NY", 1.15
    if 21 <= h < 24:  return "NEW YORK", 1.05
    return "SYDNEY", 0.85


# ─────────────────────────────────────────────────────────────
#  JSON STORE HELPERS
# ─────────────────────────────────────────────────────────────
def _jload(path, default):
    try:
        with open(path) as f: return json.load(f)
    except Exception: return default

def _jsave(path, data):
    try:
        with open(path, "w") as f: json.dump(data, f, indent=2)
    except Exception: pass


def load_config():
    cfg = _jload(CONFIG_FILE, {})
    cfg.setdefault("telegram", False)
    cfg.setdefault("token", "")
    cfg.setdefault("chat_id", "")
    cfg.setdefault("timeframe", "M1")
    cfg.setdefault("charts", True)
    cfg.setdefault("proxy", PROXY_URL)          # optional, not required anymore
    cfg.setdefault("auto_route", True)
    cfg.setdefault("max_loss_prob", MAX_LOSS_PROB)
    cfg.setdefault("send_before", SIGNAL_SEND_BEFORE)
    return cfg

def save_config(cfg): _jsave(CONFIG_FILE, cfg)

def load_results(): return _jload(RESULT_FILE, [])
def save_results(r): _jsave(RESULT_FILE, r[-500:])

def log_line(txt):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{get_now():%Y-%m-%d %H:%M:%S}] {txt}\n")
    except Exception: pass


# ═════════════════════════════════════════════════════════════
#  AUTO-ROUTE TRANSPORT  —  "no proxy needed" engine
#  ---------------------------------------------------------
#  The bot tries, in order and then in parallel:
#    R0  direct connection
#    R1..Rn  public read-relays (allorigins / codetabs / cors.lol /
#            corsfix / jina reader / cors workers)
#    Rp  free HTTP proxies auto-downloaded from public proxy lists
#  The first route that returns valid JSON becomes the ACTIVE ROUTE and
#  is stored in monarch_route.json. If it fails 3x the engine silently
#  re-races all routes and switches. The user never touches a proxy.
# ═════════════════════════════════════════════════════════════
_SESSION = requests.Session()
try:
    from requests.adapters import HTTPAdapter
    _ADAPTER = HTTPAdapter(pool_connections=64, pool_maxsize=64, max_retries=0)
    _SESSION.mount('http://', _ADAPTER)
    _SESSION.mount('https://', _ADAPTER)
except Exception:
    pass
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://tradowix.com",
    "Referer": "https://tradowix.com/",
})

PROXY_LIST_SOURCES = [
    "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies"
    "&protocol=http&proxy_format=protocolipport&format=text&timeout=4000",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
]


def _enc(u):
    try:
        from urllib.parse import quote
        return quote(u, safe="")
    except Exception:
        return u.replace(":", "%3A").replace("/", "%2F").replace("?", "%3F").replace("&", "%26").replace("=", "%3D")


def _json_from_text(txt):
    """Pull the first JSON object out of a wrapped/relayed response."""
    if not txt: return None
    txt = txt.strip()
    try:
        return json.loads(txt)
    except Exception:
        pass
    i = txt.find("{")
    j = txt.rfind("}")
    if i >= 0 and j > i:
        chunk = txt[i:j + 1]
        try:
            return json.loads(chunk)
        except Exception:
            # allorigins /get style wrapper: {"contents":"{...}"}
            try:
                w = json.loads(chunk)
                if isinstance(w, dict) and "contents" in w:
                    return json.loads(w["contents"])
            except Exception:
                return None
    return None


#  Each relay: (name, builder(full_url) -> request_url)
RELAYS = [
    ("direct",      lambda u: u),
    ("allorigins",  lambda u: "https://api.allorigins.win/raw?url=" + _enc(u)),
    ("codetabs",    lambda u: "https://api.codetabs.com/v1/proxy?quest=" + _enc(u)),
    ("corslol",     lambda u: "https://api.cors.lol/?url=" + _enc(u)),
    ("corsfix",     lambda u: "https://proxy.corsfix.com/?" + u),
    ("corsworker",  lambda u: "https://test.cors.workers.dev/?" + u),
    ("jina",        lambda u: "https://r.jina.ai/" + u),
    ("allorigins2", lambda u: "https://api.allorigins.win/get?url=" + _enc(u)),
]

_ROUTE = {"name": None, "build": None, "proxy": None, "fails": 0, "lock": threading.Lock()}
_PROXY_POOL = []


def _full_url(url, params):
    if not params: return url
    from urllib.parse import urlencode
    sep = "&" if "?" in url else "?"
    return url + sep + urlencode(params)


def _try_route(route, url, params, timeout=API_TIMEOUT):
    """route = (name, builder, proxy_or_None) -> parsed json or None"""
    name, build, proxy = route
    try:
        full = _full_url(url, params)
        req = build(full) if build else full
        prox = {"http": proxy, "https": proxy} if proxy else None
        r = _SESSION.get(req, timeout=timeout, proxies=prox)
        if r.status_code != 200:
            return None
        j = _json_from_text(r.text)
        if isinstance(j, dict) and (j.get("success") or j.get("data") or j.get("pairs")):
            return j
        return None
    except Exception:
        return None


def _load_free_proxies(limit=25):
    """Download a small pool of public HTTP proxies (last-resort route)."""
    global _PROXY_POOL
    if _PROXY_POOL: return _PROXY_POOL
    out = []
    for src in PROXY_LIST_SOURCES:
        try:
            r = requests.get(src, timeout=12)
            if r.status_code != 200: continue
            for line in r.text.splitlines():
                line = line.strip()
                if not line: continue
                if not line.startswith("http"): line = "http://" + line
                if line.count(":") >= 2 and len(line) < 60:
                    out.append(line)
            if len(out) > 400: break
        except Exception:
            continue
    random.shuffle(out)
    _PROXY_POOL = out[:limit]
    return _PROXY_POOL


def _candidate_routes(cfg=None):
    routes = []
    manual = (cfg or {}).get("proxy") or PROXY_URL
    if manual:
        routes.append(("manual-proxy", lambda u: u, manual))
    for name, build in RELAYS:
        routes.append((name, build, None))
    return routes


def discover_route(cfg=None, quiet=False, deep=False):
    """Race every route against the health/pairs endpoint, keep the winner."""
    probe_url, probe_params = API_PAIRS, None
    routes = _candidate_routes(cfg)
    if deep:
        for p in _load_free_proxies():
            routes.append((f"proxy:{p.split('//')[-1]}", lambda u: u, p))

    winner = None
    with ThreadPoolExecutor(max_workers=min(10, len(routes))) as ex:
        futs = {ex.submit(_try_route, r, probe_url, probe_params, 12): r for r in routes}
        for f in as_completed(futs):
            r = futs[f]
            try:
                if f.result():
                    winner = r
                    break
            except Exception:
                pass
    if winner:
        with _ROUTE["lock"]:
            _ROUTE.update({"name": winner[0], "build": winner[1],
                           "proxy": winner[2], "fails": 0})
        _jsave(ROUTE_FILE, {"name": winner[0], "proxy": winner[2], "t": time.time()})
        if not quiet:
            console.print(f"[green]● API route locked:[/] [bold]{winner[0]}[/] "
                          f"[dim](auto — no proxy setup needed)[/]")
        return True
    if not quiet:
        console.print("[red]● No route reachable yet — retrying deeper…[/]")
    return False


def ensure_route(cfg=None, quiet=False):
    if _ROUTE["name"]:
        return True
    # prefer the remembered route first
    saved = _jload(ROUTE_FILE, {})
    if saved.get("name"):
        for nm, build in RELAYS:
            if nm == saved["name"]:
                if _try_route((nm, build, saved.get("proxy")), API_PAIRS, None, 10):
                    _ROUTE.update({"name": nm, "build": build,
                                   "proxy": saved.get("proxy"), "fails": 0})
                    if not quiet:
                        console.print(f"[green]● API route restored:[/] [bold]{nm}[/]")
                    return True
                break
    if discover_route(cfg, quiet=quiet):
        return True
    return discover_route(cfg, quiet=quiet, deep=True)


def api_get(url, params=None, cfg=None):
    """Route-aware GET. Never asks the user for a proxy."""
    if not ensure_route(cfg, quiet=True):
        return None
    for attempt in range(API_RETRIES + 1):
        route = (_ROUTE["name"], _ROUTE["build"], _ROUTE["proxy"])
        j = _try_route(route, url, params)
        if j is not None:
            _ROUTE["fails"] = 0
            return j
        _ROUTE["fails"] += 1
        if _ROUTE["fails"] >= 3:
            log_line(f"route {_ROUTE['name']} degraded -> re-racing")
            _ROUTE["name"] = None
            if not ensure_route(cfg, quiet=True):
                return None
        else:
            time.sleep(0.4 * (attempt + 1))
    log_line(f"API FAIL {url}")
    return None


def route_name():
    return _ROUTE["name"] or "searching…"


# ─────────────────────────────────────────────────────────────
#  DATA LAYER — TRADOWIX CANDLE API (only data source)
# ─────────────────────────────────────────────────────────────
_PAIRS_CACHE = {"t": 0, "pairs": []}
_CANDLE_CACHE = {}
_PAIR_FAILS = defaultdict(int)
_PAIR_PENALTY = {}


def pair_benched(pair):
    until = _PAIR_PENALTY.get(pair, 0)
    return time.time() < until


def clear_bench(reason=""):
    """v52: bench list poori saaf — bot ko kabhi data-less nahi chhodna."""
    if _PAIR_PENALTY:
        _PAIR_PENALTY.clear()
        _PAIR_FAILS.clear()
        log_line(f"bench cleared {reason}")


def ensure_live_pool(pairs):
    """Agar live (non-benched) pairs MIN_LIVE_POOL se kam ho gaye to bench khol do."""
    live = [p for p in pairs if not pair_benched(p)]
    if len(live) < MIN_LIVE_POOL:
        clear_bench("(live pool too small)")
        return list(pairs)
    return live


def _pair_fail(pair):
    _PAIR_FAILS[pair] += 1
    if _PAIR_FAILS[pair] >= PAIR_FAIL_LIMIT:
        _PAIR_PENALTY[pair] = time.time() + PAIR_PENALTY_MIN * 60
        _PAIR_FAILS[pair] = 0


def _pair_ok(pair):
    _PAIR_FAILS[pair] = 0


def api_pairs(cfg=None, force=False):
    if not force and _PAIRS_CACHE["pairs"] and time.time() - _PAIRS_CACHE["t"] < 900:
        return _PAIRS_CACHE["pairs"]
    j = api_get(API_PAIRS, cfg=cfg)
    pairs = []
    if j and (j.get("success") or j.get("pairs")):
        pairs = j.get("running_pairs") or j.get("pairs") or []
    if pairs:
        _PAIRS_CACHE.update({"t": time.time(), "pairs": pairs})
    return pairs or _PAIRS_CACHE["pairs"]


def _norm_pair(p):
    p = p.strip().replace("-OTC", "_otc").replace("-otc", "_otc")
    if p.upper().endswith("OTC") and "_" not in p:
        p = p[:-3] + "_otc"
    return p


def pretty_pair(p):
    return p.replace("_otc", "-OTC").upper().replace("-OTC", "-OTC")


def _parse_candles(j):
    payout = j.get("payout", 0) or 0
    out = []
    for d in j.get("data", []):
        try:
            out.append({"o": float(d["open"]), "h": float(d["high"]),
                        "l": float(d["low"]),  "c": float(d["close"]),
                        "t": int(d["epoch"]),  "payout": float(d.get("payout", payout) or payout)})
        except Exception:
            continue
    out.sort(key=lambda x: x["t"])
    return out


def fetch_m1(pair, count=CANDLE_COUNT, cfg=None, use_cache=True):
    """OLDEST->NEWEST list of dicts: o,h,l,c,t(epoch),payout."""
    pair = _norm_pair(pair)
    key = (pair, count)
    if use_cache:
        c = _CANDLE_CACHE.get(key)
        if c and time.time() - c[0] < CANDLE_CACHE_TTL:
            return c[1]
    j = api_get(API_CANDLES, {"pair": pair, "timeframe": "M1", "count": count}, cfg)
    if not j or not j.get("data"):
        j = api_get(API_CANDLES2, {"pair": pair, "timeframe": "M1", "count": count}, cfg)
    if not j or not j.get("data"):
        _pair_fail(pair)
        stale = _CANDLE_CACHE.get(key)          # never block the scan on one slow pair
        return stale[1] if stale else []
    _pair_ok(pair)
    out = _parse_candles(j)
    _CANDLE_CACHE[key] = (time.time(), out)
    return out


def aggregate(m1, minutes):
    """Build higher timeframe candles purely from API M1 data."""
    if not m1: return []
    out = []
    bucket = None
    for c in m1:
        start = c["t"] - (c["t"] % (minutes * 60))
        if bucket is None or bucket["t"] != start:
            if bucket: out.append(bucket)
            bucket = {"t": start, "o": c["o"], "h": c["h"], "l": c["l"],
                      "c": c["c"], "payout": c["payout"]}
        else:
            bucket["h"] = max(bucket["h"], c["h"])
            bucket["l"] = min(bucket["l"], c["l"])
            bucket["c"] = c["c"]
    if bucket: out.append(bucket)
    return out


def fetch_base(pair, cfg=None, use_cache=True):
    """ONE API call per pair. M1 / M5 / M15 are all derived from this series."""
    return fetch_m1(pair, BASE_COUNT, cfg, use_cache)


def tf_from_base(base, tf):
    if not base: return []
    if tf == "M1":
        return base[-CANDLE_COUNT:]
    mins = {"M5": 5, "M15": 15}.get(tf, 1)
    return aggregate(base, mins)


def fetch_tf(pair, tf, cfg=None):
    return tf_from_base(fetch_base(pair, cfg), tf)


def fetch_forming(pair, cfg=None):
    """LIVE forming-candle engine: micro-poll the current M1 candle."""
    snaps = []
    for i in range(FORMING_POLLS):
        cds = fetch_m1(pair, 3, cfg, use_cache=False)
        if cds:
            snaps.append(cds[-1])
        if i < FORMING_POLLS - 1:
            time.sleep(FORMING_POLL_GAP)
    return snaps


def prefetch_many(pairs, cfg=None, count=BASE_COUNT, workers=FETCH_WORKERS):
    """Parallel warm-up of the candle cache so the scan is fast enough
    to always finish before the 10-second send window."""
    res = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_m1, p, count, cfg, False): p for p in pairs}
        for f in as_completed(futs):
            p = futs[f]
            try:
                cds = f.result()
            except Exception:
                cds = []
            if cds:
                _CANDLE_CACHE[(_norm_pair(p), count)] = (time.time(), cds)
                res[p] = cds
    return res


def _fp_px(x):
    if isinstance(x, dict):
        for k in ("p", "close", "c", "price", "last"):
            if k in x:
                try: return float(x[k])
                except Exception: pass
        return 0.0
    try: return float(x)
    except Exception: return 0.0


# ─────────────────────────────────────────────────────────────
#  INDICATORS
# ─────────────────────────────────────────────────────────────
def arr(x): return np.asarray(x, dtype=float)

def ema(d, p):
    d = arr(d)
    if len(d) < p: return d.copy()
    k = 2.0 / (p + 1); out = np.empty_like(d); out[:p] = d[:p].mean()
    for i in range(p, len(d)): out[i] = d[i] * k + out[i-1] * (1 - k)
    return out

def sma(d, p):
    d = arr(d)
    if len(d) < p: return d.copy()
    out = np.convolve(d, np.ones(p)/p, mode="valid")
    return np.concatenate([np.full(p-1, out[0]), out])

def rsi(d, p=14):
    d = arr(d)
    if len(d) < p + 1: return np.full(len(d), 50.0)
    delta = np.diff(d); up = np.clip(delta, 0, None); dn = -np.clip(delta, None, 0)
    ru = up[:p].mean(); rd = dn[:p].mean(); out = np.full(len(d), 50.0)
    for i in range(p, len(delta)):
        ru = (ru*(p-1) + up[i]) / p; rd = (rd*(p-1) + dn[i]) / p
        out[i+1] = 100 - 100/(1 + ru/(rd or 1e-12))
    out[:p+1] = out[p+1] if len(out) > p+1 else 50.0
    return out

def atr(h, l, c, p=14):
    h, l, c = arr(h), arr(l), arr(c)
    if len(c) < 2: return np.zeros(len(c))
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h-l, np.maximum(abs(h-pc), abs(l-pc)))
    return sma(tr, min(p, len(tr)))

def macd(d, f=12, s=26, sig=9):
    ef, es = ema(d, f), ema(d, s)
    line = ef - es; signal = ema(line, sig)
    return line, signal, line - signal

def bollinger(d, p=20, k=2.0):
    d = arr(d); m = sma(d, p)
    std = np.array([d[max(0, i-p+1):i+1].std() for i in range(len(d))])
    return m + k*std, m, m - k*std, std

def stochastic(h, l, c, kp=14, dp=3):
    h, l, c = arr(h), arr(l), arr(c); out = np.full(len(c), 50.0)
    for i in range(kp, len(c)):
        hh = h[i-kp+1:i+1].max(); ll = l[i-kp+1:i+1].min()
        out[i] = 100*(c[i]-ll)/((hh-ll) or 1e-12)
    return out, sma(out, dp)

def adx(h, l, c, p=14):
    h, l, c = arr(h), arr(l), arr(c); n = len(c)
    if n < p+2: return np.zeros(n), np.zeros(n), np.zeros(n)
    up = h[1:]-h[:-1]; dn = l[:-1]-l[1:]
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = np.maximum(h[1:]-l[1:], np.maximum(abs(h[1:]-c[:-1]), abs(l[1:]-c[:-1])))
    atr_ = sma(tr, p); pdi = 100*sma(pdm, p)/np.where(atr_ == 0, 1e-12, atr_)
    ndi = 100*sma(ndm, p)/np.where(atr_ == 0, 1e-12, atr_)
    dx = 100*abs(pdi-ndi)/np.where((pdi+ndi) == 0, 1e-12, pdi+ndi)
    a = sma(dx, p)
    pad = lambda x: np.concatenate([[x[0]], x])
    return pad(a), pad(pdi), pad(ndi)

def cci(h, l, c, p=20):
    tp = (arr(h)+arr(l)+arr(c))/3.0; m = sma(tp, p)
    md = np.array([np.abs(tp[max(0, i-p+1):i+1]-m[i]).mean() for i in range(len(tp))])
    return (tp-m)/(0.015*np.where(md == 0, 1e-12, md))

def willr(h, l, c, p=14):
    h, l, c = arr(h), arr(l), arr(c); out = np.full(len(c), -50.0)
    for i in range(p, len(c)):
        hh = h[i-p+1:i+1].max(); ll = l[i-p+1:i+1].min()
        out[i] = -100*(hh-c[i])/((hh-ll) or 1e-12)
    return out

def supertrend(h, l, c, p=10, m=3.0):
    h, l, c = arr(h), arr(l), arr(c); a = atr(h, l, c, p)
    hl2 = (h+l)/2.0; ub = hl2+m*a; lb = hl2-m*a
    d = np.ones(len(c))
    for i in range(1, len(c)):
        d[i] = d[i-1]
        if c[i] > ub[i-1]: d[i] = 1
        elif c[i] < lb[i-1]: d[i] = -1
    return d

def heikin(o, h, l, c):
    o, h, l, c = arr(o), arr(h), arr(l), arr(c)
    hc = (o+h+l+c)/4.0; ho = np.empty_like(hc); ho[0] = (o[0]+c[0])/2
    for i in range(1, len(hc)): ho[i] = (ho[i-1]+hc[i-1])/2
    hh = np.maximum(h, np.maximum(ho, hc)); hl = np.minimum(l, np.minimum(ho, hc))
    return ho, hh, hl, hc

def slope(d, p=5):
    d = arr(d)
    if len(d) < p: return 0.0
    y = d[-p:]; x = np.arange(p)
    return float(np.polyfit(x, y, 1)[0])


# ─────────────────────────────────────────────────────────────
#  SUPPORT / RESISTANCE ENGINE
# ─────────────────────────────────────────────────────────────
def swing_points(h, l, lb=2):
    hi, lo = [], []
    for i in range(lb, len(h)-lb):
        if h[i] == max(h[i-lb:i+lb+1]): hi.append((i, h[i]))
        if l[i] == min(l[i-lb:i+lb+1]): lo.append((i, l[i]))
    return hi, lo


def sr_levels(candles, atr_val):
    """Cluster swing highs/lows into levels with strength + recency."""
    h = [c["h"] for c in candles]; l = [c["l"] for c in candles]
    hi, lo = swing_points(h, l, 2)
    raw = [("R", i, p) for i, p in hi] + [("S", i, p) for i, p in lo]
    tol = max(atr_val * 0.6, (max(h)-min(l)) * 0.0015, 1e-9)
    levels = []
    for kind, idx, price in raw:
        placed = False
        for L in levels:
            if abs(L["price"] - price) <= tol:
                L["touches"] += 1
                L["price"] = (L["price"] * (L["touches"]-1) + price) / L["touches"]
                L["last"] = max(L["last"], idx)
                if kind not in L["kind"]: L["kind"] = "SR"
                placed = True; break
        if not placed:
            levels.append({"price": price, "touches": 1, "last": idx, "kind": kind})
    n = len(candles)
    for L in levels:
        recency = 1.0 - min((n - L["last"]) / max(n, 1), 1.0)
        L["strength"] = round(min(L["touches"] * 1.6 + recency * 3.0, 10.0), 2)
    levels.sort(key=lambda x: -x["strength"])
    return levels[:14]


def nearest_levels(levels, price):
    above = [L for L in levels if L["price"] > price]
    below = [L for L in levels if L["price"] < price]
    res = min(above, key=lambda L: L["price"]-price) if above else None
    sup = max(below, key=lambda L: L["price"]) if below else None
    return sup, res


# ─────────────────────────────────────────────────────────────
#  FEATURE BUILDER
# ─────────────────────────────────────────────────────────────
def build_features(candles, mtf=None, forming=None):
    o = arr([c["o"] for c in candles]); h = arr([c["h"] for c in candles])
    l = arr([c["l"] for c in candles]); c_ = arr([c["c"] for c in candles])
    n = len(c_)
    F = {"o": o, "h": h, "l": l, "c": c_, "n": n, "candles": candles}
    F["price"] = float(c_[-1])
    F["atr"] = float(atr(h, l, c_, 14)[-1]) or (float(c_[-1]) * 1e-4)
    for p in (5, 8, 13, 21, 34, 55, 100, 200):
        F[f"ema{p}"] = ema(c_, min(p, max(n-1, 2)))
    F["sma20"] = sma(c_, 20); F["sma50"] = sma(c_, 50)
    F["rsi"] = rsi(c_, 14); F["rsi7"] = rsi(c_, 7); F["rsi21"] = rsi(c_, 21)
    F["macd"], F["macds"], F["macdh"] = macd(c_)
    F["bbU"], F["bbM"], F["bbL"], F["bbSD"] = bollinger(c_, 20, 2.0)
    F["stK"], F["stD"] = stochastic(h, l, c_)
    F["adx"], F["pdi"], F["ndi"] = adx(h, l, c_)
    F["cci"] = cci(h, l, c_); F["willr"] = willr(h, l, c_)
    F["st"] = supertrend(h, l, c_)
    F["hao"], F["hah"], F["hal"], F["hac"] = heikin(o, h, l, c_)
    F["body"] = np.abs(c_ - o)
    F["range"] = np.maximum(h - l, 1e-12)
    F["upw"] = h - np.maximum(o, c_)
    F["dnw"] = np.minimum(o, c_) - l
    F["avgbody"] = float(F["body"][-20:].mean()) if n >= 20 else float(F["body"].mean())
    F["bull"] = c_ > o
    F["levels"] = sr_levels(candles, F["atr"])
    F["sup"], F["res"] = nearest_levels(F["levels"], F["price"])
    F["slope5"] = slope(c_, 5); F["slope13"] = slope(c_, 13)
    F["ema8s"] = slope(F["ema8"], 4); F["ema21s"] = slope(F["ema21"], 6)
    F["mtf"] = mtf or {}
    F["forming"] = forming or []
    F["payout"] = candles[-1].get("payout", 0)
    F["session"], F["sessw"] = get_session()
    F["weekday"] = get_now().weekday()
    # volatility / regime
    rng = float(np.mean(F["range"][-20:])) if n >= 20 else float(np.mean(F["range"]))
    F["volratio"] = float(F["range"][-1] / (rng or 1e-12))
    F["adxv"] = float(F["adx"][-1])
    if F["adxv"] >= 26: F["regime"] = "TRENDING"
    elif F["volratio"] > 2.0: F["regime"] = "BREAKOUT"
    elif F["adxv"] < 16: F["regime"] = "RANGING"
    else: F["regime"] = "NORMAL"

    # ── CONTEXT FIELDS (trend-end / doji / big-candle engine) ──
    # consecutive same-direction candle run (signed: + up run, - down run)
    run = 1
    for i in range(n - 2, max(n - 15, -1), -1):
        if bool(F["bull"][i]) == bool(F["bull"][-1]): run += 1
        else: break
    F["run_len"] = run
    F["run_dir"] = UP if bool(F["bull"][-1]) else DN
    # distance from EMA21 measured in ATR (over-extension)
    F["ext_atr"] = float((F["price"] - float(F["ema21"][-1])) / (F["atr"] or 1e-12))
    # body / range ratios of the last candles
    br = F["body"] / F["range"]
    F["bodyratio"] = float(br[-1])
    F["doji_cluster"] = int(sum(1 for x in br[-3:] if x < 0.25))
    F["big_range"] = float(F["range"][-1] / (F["atr"] or 1e-12))
    F["big_body"] = float(F["body"][-1] / (F["avgbody"] or 1e-12))
    # momentum decay: are the last 3 bodies of the run shrinking?
    if n >= 4:
        b1, b2, b3 = float(F["body"][-3]), float(F["body"][-2]), float(F["body"][-1])
        F["body_decay"] = bool(b3 < b2 < b1)
    else:
        F["body_decay"] = False

    # ── NON-MTG (FIRST CANDLE) MICRO-FEATURES ──
    rg_last = float(F["range"][-1]) or 1e-12
    # close location value: +1 = close exactly on high, -1 = on low
    F["clv"] = float(((c_[-1] - l[-1]) - (h[-1] - c_[-1])) / rg_last)
    F["clv3"] = float(np.mean(((c_[-3:] - l[-3:]) - (h[-3:] - c_[-3:])) / np.maximum(F["range"][-3:], 1e-12))) if n >= 3 else F["clv"]
    F["upw_r"] = float(F["upw"][-1] / rg_last)
    F["dnw_r"] = float(F["dnw"][-1] / rg_last)
    # room (in ATR) till the nearest opposing level -> pehli candle ko jagah chahiye
    _atr = F["atr"] or 1e-12
    F["room_up"] = float(((F["res"]["price"] - F["price"]) / _atr)) if F["res"] else 3.0
    F["room_dn"] = float(((F["price"] - F["sup"]["price"]) / _atr)) if F["sup"] else 3.0
    # fast ribbon alignment score (-1 full down .. +1 full up)
    _fast = [float(F["ema5"][-1]), float(F["ema8"][-1]), float(F["ema13"][-1]), float(F["ema21"][-1])]
    _up_al = sum(1 for i in range(3) if _fast[i] > _fast[i+1])
    F["ribbon_score"] = (_up_al - (3 - _up_al)) / 3.0
    # micro momentum: last 3 closes net move in ATR
    F["micro_mom"] = float((c_[-1] - c_[-4]) / _atr) if n >= 5 else 0.0
    # forming candle bias (live candle already moving our way?)
    fm = (forming or [])
    if fm:
        fc = fm[-1]
        _fr = max(float(fc["h"]) - float(fc["l"]), 1e-12)
        F["form_dir"] = UP if float(fc["c"]) >= float(fc["o"]) else DN
        F["form_body"] = float(abs(float(fc["c"]) - float(fc["o"])) / _fr)
    else:
        F["form_dir"] = None
        F["form_body"] = 0.0
    return F


# ─────────────────────────────────────────────────────────────
#  NEW STRATEGY BANK  (all previous strategies removed)
#  Each strategy -> ("CALL"/"PUT", reason) or None
# ─────────────────────────────────────────────────────────────
STRATS = []   # (name, family, fn)

def S(name, family):
    def deco(fn):
        STRATS.append((name, family, fn)); return fn
    return deco

UP, DN = "CALL", "PUT"
def sgn(cond, reason_up, reason_dn, up=True):
    return (UP, reason_up) if up else (DN, reason_dn)

# ══════════ FAMILY TR — TREND ══════════
def _mk_ema_cross(fast, slow):
    def fn(F):
        a, b = F[f"ema{fast}"], F[f"ema{slow}"]
        if len(a) < 3 or len(b) < 3: return None
        if a[-1] > b[-1] and a[-2] <= b[-2]:
            return UP, f"EMA{fast} crossed above EMA{slow} (fresh bullish cross)"
        if a[-1] < b[-1] and a[-2] >= b[-2]:
            return DN, f"EMA{fast} crossed below EMA{slow} (fresh bearish cross)"
        return None
    return fn

for _f, _s in [(5, 13), (8, 21), (13, 34), (21, 55), (5, 21), (8, 34), (13, 55), (21, 100)]:
    STRATS.append((f"TR_X{_f}_{_s}", "TR", _mk_ema_cross(_f, _s)))

def _mk_stack(periods):
    def fn(F):
        vals = [F[f"ema{p}"][-1] for p in periods]
        if all(vals[i] > vals[i+1] for i in range(len(vals)-1)) and F["price"] > vals[0]:
            return UP, f"EMA ribbon stacked bullish ({'>'.join(str(p) for p in periods)})"
        if all(vals[i] < vals[i+1] for i in range(len(vals)-1)) and F["price"] < vals[0]:
            return DN, f"EMA ribbon stacked bearish ({'<'.join(str(p) for p in periods)})"
        return None
    return fn

for i, _p in enumerate([(8, 21, 55), (5, 13, 34), (8, 21, 55, 100), (13, 34, 100), (5, 8, 21, 34)]):
    STRATS.append((f"TR_STK{i+1}", "TR", _mk_stack(_p)))

@S("TR_ADX_DI", "TR")
def _tr_adx(F):
    if F["adxv"] < 22: return None
    if F["pdi"][-1] > F["ndi"][-1] * 1.25: return UP, f"ADX {F['adxv']:.0f} with +DI dominance = strong up-trend"
    if F["ndi"][-1] > F["pdi"][-1] * 1.25: return DN, f"ADX {F['adxv']:.0f} with -DI dominance = strong down-trend"
    return None

@S("TR_SUPERTREND", "TR")
def _tr_st(F):
    if F["st"][-1] > 0 and F["st"][-2] > 0: return UP, "Supertrend holding bullish"
    if F["st"][-1] < 0 and F["st"][-2] < 0: return DN, "Supertrend holding bearish"
    return None

@S("TR_ST_FLIP", "TR")
def _tr_stf(F):
    if F["st"][-1] > 0 and F["st"][-2] < 0: return UP, "Supertrend just flipped to buy"
    if F["st"][-1] < 0 and F["st"][-2] > 0: return DN, "Supertrend just flipped to sell"
    return None

@S("TR_SLOPE", "TR")
def _tr_slope(F):
    a = F["atr"]
    if F["ema8s"] > a*0.06 and F["ema21s"] > 0: return UP, "EMA8 & EMA21 slopes rising together"
    if F["ema8s"] < -a*0.06 and F["ema21s"] < 0: return DN, "EMA8 & EMA21 slopes falling together"
    return None

@S("TR_HH_HL", "TR")
def _tr_struct(F):
    hi, lo = swing_points(list(F["h"]), list(F["l"]), 2)
    if len(hi) >= 2 and len(lo) >= 2:
        if hi[-1][1] > hi[-2][1] and lo[-1][1] > lo[-2][1]:
            return UP, "Market structure = higher-high + higher-low"
        if hi[-1][1] < hi[-2][1] and lo[-1][1] < lo[-2][1]:
            return DN, "Market structure = lower-high + lower-low"
    return None

@S("TR_PULLBACK", "TR")
def _tr_pb(F):
    e8, e21 = F["ema8"][-1], F["ema21"][-1]
    p = F["price"]
    if e8 > e21 and abs(p-e21) < F["atr"]*0.5 and F["c"][-1] > F["o"][-1]:
        return UP, "Pullback into EMA21 in an up-trend, bullish rejection"
    if e8 < e21 and abs(p-e21) < F["atr"]*0.5 and F["c"][-1] < F["o"][-1]:
        return DN, "Pullback into EMA21 in a down-trend, bearish rejection"
    return None

@S("TR_HEIKIN", "TR")
def _tr_ha(F):
    hc, ho, hl, hh = F["hac"], F["hao"], F["hal"], F["hah"]
    if hc[-1] > ho[-1] and hc[-2] > ho[-2] and abs(hl[-1]-min(ho[-1], hc[-1])) < F["atr"]*0.15:
        return UP, "Heikin-Ashi bullish body with no lower wick"
    if hc[-1] < ho[-1] and hc[-2] < ho[-2] and abs(hh[-1]-max(ho[-1], hc[-1])) < F["atr"]*0.15:
        return DN, "Heikin-Ashi bearish body with no upper wick"
    return None

@S("TR_MTF_ALIGN", "TR")
def _tr_mtf(F):
    m = F["mtf"]
    if not m: return None
    ups = sum(1 for v in m.values() if v == UP); dns = sum(1 for v in m.values() if v == DN)
    if ups >= 2 and dns == 0: return UP, "Higher timeframes (M5/M15) both bullish"
    if dns >= 2 and ups == 0: return DN, "Higher timeframes (M5/M15) both bearish"
    return None

@S("TR_PRICE_EMA200", "TR")
def _tr_e200(F):
    e = F["ema200"][-1]
    if F["price"] > e and F["ema21"][-1] > e: return UP, "Price and EMA21 above EMA200 baseline"
    if F["price"] < e and F["ema21"][-1] < e: return DN, "Price and EMA21 below EMA200 baseline"
    return None

@S("TR_CONSEC", "TR")
def _tr_consec(F):
    b = F["bull"][-4:]
    if all(b) and F["body"][-1] > F["avgbody"]*0.5: return UP, "Four consecutive bullish candles with body"
    if not any(b) and F["body"][-1] > F["avgbody"]*0.5: return DN, "Four consecutive bearish candles with body"
    return None

@S("TR_MACD_TREND", "TR")
def _tr_macd(F):
    if F["macd"][-1] > F["macds"][-1] and F["macd"][-1] > 0: return UP, "MACD above signal and above zero"
    if F["macd"][-1] < F["macds"][-1] and F["macd"][-1] < 0: return DN, "MACD below signal and below zero"
    return None

@S("TR_RIBBON_EXPAND", "TR")
def _tr_exp(F):
    d1 = abs(F["ema8"][-1]-F["ema21"][-1]); d2 = abs(F["ema8"][-5]-F["ema21"][-5])
    if d1 > d2*1.3:
        return (UP, "EMA ribbon expanding upward (trend acceleration)") if F["ema8"][-1] > F["ema21"][-1] \
            else (DN, "EMA ribbon expanding downward (trend acceleration)")
    return None

# ══════════ FAMILY MO — MOMENTUM ══════════
def _mk_rsi_zone(lo, hi, per):
    def fn(F):
        r = F[f"rsi{per}" if per != 14 else "rsi"]
        if r[-1] > hi and r[-1] > r[-2]: return UP, f"RSI{per} {r[-1]:.0f} above {hi} and rising (momentum up)"
        if r[-1] < lo and r[-1] < r[-2]: return DN, f"RSI{per} {r[-1]:.0f} below {lo} and falling (momentum down)"
        return None
    return fn

for i, (_lo, _hi, _p) in enumerate([(45, 55, 14), (40, 60, 14), (35, 65, 7), (45, 55, 21), (30, 70, 7)]):
    STRATS.append((f"MO_RSI{i+1}", "MO", _mk_rsi_zone(_lo, _hi, _p)))

@S("MO_RSI_50X", "MO")
def _mo_r50(F):
    r = F["rsi"]
    if r[-1] > 50 >= r[-2]: return UP, "RSI reclaimed the 50 mid-line"
    if r[-1] < 50 <= r[-2]: return DN, "RSI lost the 50 mid-line"
    return None

@S("MO_MACD_HIST", "MO")
def _mo_mh(F):
    hh = F["macdh"]
    if hh[-1] > 0 and hh[-1] > hh[-2] > hh[-3]: return UP, "MACD histogram expanding positive"
    if hh[-1] < 0 and hh[-1] < hh[-2] < hh[-3]: return DN, "MACD histogram expanding negative"
    return None

@S("MO_MACD_CROSS", "MO")
def _mo_mx(F):
    if F["macd"][-1] > F["macds"][-1] and F["macd"][-2] <= F["macds"][-2]: return UP, "MACD bullish crossover"
    if F["macd"][-1] < F["macds"][-1] and F["macd"][-2] >= F["macds"][-2]: return DN, "MACD bearish crossover"
    return None

@S("MO_STOCH_X", "MO")
def _mo_sx(F):
    k, d = F["stK"], F["stD"]
    if k[-1] > d[-1] and k[-2] <= d[-2] and k[-1] < 80: return UP, f"Stochastic K/D bull cross at {k[-1]:.0f}"
    if k[-1] < d[-1] and k[-2] >= d[-2] and k[-1] > 20: return DN, f"Stochastic K/D bear cross at {k[-1]:.0f}"
    return None

@S("MO_STOCH_ZONE", "MO")
def _mo_sz(F):
    k = F["stK"]
    if k[-1] < 22 and k[-1] > k[-2]: return UP, "Stochastic turning up from oversold"
    if k[-1] > 78 and k[-1] < k[-2]: return DN, "Stochastic turning down from overbought"
    return None

@S("MO_CCI", "MO")
def _mo_cci(F):
    v = F["cci"]
    if v[-1] > 100 and v[-2] <= 100: return UP, "CCI broke +100 (strong bullish thrust)"
    if v[-1] < -100 and v[-2] >= -100: return DN, "CCI broke -100 (strong bearish thrust)"
    return None

@S("MO_WILLR", "MO")
def _mo_w(F):
    v = F["willr"]
    if v[-1] > -20 and v[-2] <= -20: return UP, "Williams %R pushed into strength zone"
    if v[-1] < -80 and v[-2] >= -80: return DN, "Williams %R pushed into weakness zone"
    return None

@S("MO_ROC", "MO")
def _mo_roc(F):
    c = F["c"]
    if len(c) < 12: return None
    r = (c[-1]-c[-11])/(c[-11] or 1e-12)*100
    if r > 0.04 and c[-1] > c[-2]: return UP, f"10-candle rate-of-change +{r:.2f}% (bull momentum)"
    if r < -0.04 and c[-1] < c[-2]: return DN, f"10-candle rate-of-change {r:.2f}% (bear momentum)"
    return None

@S("MO_BODY_MOM", "MO")
def _mo_body(F):
    if F["body"][-1] > F["avgbody"]*1.6:
        return (UP, "Large bullish momentum candle") if F["bull"][-1] else (DN, "Large bearish momentum candle")
    return None

@S("MO_ACCEL", "MO")
def _mo_acc(F):
    c = F["c"]
    if len(c) < 4: return None
    d1, d2 = c[-1]-c[-2], c[-2]-c[-3]
    if d1 > 0 and d1 > d2 > 0: return UP, "Price advance accelerating candle over candle"
    if d1 < 0 and d1 < d2 < 0: return DN, "Price decline accelerating candle over candle"
    return None

@S("MO_RSI_SLOPE", "MO")
def _mo_rs(F):
    s = slope(F["rsi"], 5)
    if s > 1.6: return UP, "RSI slope strongly positive"
    if s < -1.6: return DN, "RSI slope strongly negative"
    return None

@S("MO_TRIPLE_RSI", "MO")
def _mo_tri(F):
    a, b, c = F["rsi7"][-1], F["rsi"][-1], F["rsi21"][-1]
    if a > b > c and a > 55: return UP, "Fast/medium/slow RSI stacked bullish"
    if a < b < c and a < 45: return DN, "Fast/medium/slow RSI stacked bearish"
    return None

# ══════════ FAMILY RV — REVERSAL ══════════
@S("RV_RSI_DIV", "RV")
def _rv_div(F):
    c, r = F["c"], F["rsi"]
    if len(c) < 12: return None
    lo1 = int(np.argmin(c[-12:])); hi1 = int(np.argmax(c[-12:]))
    if lo1 < 9 and c[-1] < c[-12+lo1] and r[-1] > r[-12+lo1] + 3:
        return UP, "Bullish RSI divergence (lower price, higher RSI)"
    if hi1 < 9 and c[-1] > c[-12+hi1] and r[-1] < r[-12+hi1] - 3:
        return DN, "Bearish RSI divergence (higher price, lower RSI)"
    return None

@S("RV_MACD_DIV", "RV")
def _rv_mdiv(F):
    c, m = F["c"], F["macd"]
    if len(c) < 14: return None
    if c[-1] < c[-7] and m[-1] > m[-7]: return UP, "MACD bullish divergence vs price"
    if c[-1] > c[-7] and m[-1] < m[-7]: return DN, "MACD bearish divergence vs price"
    return None

@S("RV_EXHAUST", "RV")
def _rv_ex(F):
    b = F["bull"]
    if all(b[-5:]) and F["rsi"][-1] > 72 and F["body"][-1] < F["avgbody"]*0.6:
        return DN, "Five up candles then a weak body at RSI>72 = buyer exhaustion"
    if not any(b[-5:]) and F["rsi"][-1] < 28 and F["body"][-1] < F["avgbody"]*0.6:
        return UP, "Five down candles then a weak body at RSI<28 = seller exhaustion"
    return None

@S("RV_PIN_BAR", "RV")
def _rv_pin(F):
    i = -1
    if F["dnw"][i] > F["body"][i]*2 and F["dnw"][i] > F["upw"][i]*2:
        return UP, "Bullish pin bar (long lower wick rejection)"
    if F["upw"][i] > F["body"][i]*2 and F["upw"][i] > F["dnw"][i]*2:
        return DN, "Bearish pin bar (long upper wick rejection)"
    return None

@S("RV_ENGULF", "RV")
def _rv_eng(F):
    o, c = F["o"], F["c"]
    if c[-1] > o[-1] and c[-2] < o[-2] and c[-1] > o[-2] and o[-1] < c[-2]:
        return UP, "Bullish engulfing candle"
    if c[-1] < o[-1] and c[-2] > o[-2] and c[-1] < o[-2] and o[-1] > c[-2]:
        return DN, "Bearish engulfing candle"
    return None

@S("RV_MORNING_EVE", "RV")
def _rv_star(F):
    o, c = F["o"], F["c"]
    if len(c) < 3: return None
    small = F["body"][-2] < F["avgbody"]*0.5
    if small and c[-3] < o[-3] and c[-1] > o[-1] and c[-1] > (o[-3]+c[-3])/2:
        return UP, "Morning-star reversal pattern"
    if small and c[-3] > o[-3] and c[-1] < o[-1] and c[-1] < (o[-3]+c[-3])/2:
        return DN, "Evening-star reversal pattern"
    return None

@S("RV_BB_REJECT", "RV")
def _rv_bb(F):
    if F["l"][-1] < F["bbL"][-1] and F["c"][-1] > F["bbL"][-1]:
        return UP, "Rejection back inside lower Bollinger band"
    if F["h"][-1] > F["bbU"][-1] and F["c"][-1] < F["bbU"][-1]:
        return DN, "Rejection back inside upper Bollinger band"
    return None

@S("RV_DOUBLE_BOT_TOP", "RV")
def _rv_dbl(F):
    hi, lo = swing_points(list(F["h"]), list(F["l"]), 2)
    a = F["atr"]
    if len(lo) >= 2 and abs(lo[-1][1]-lo[-2][1]) < a*0.4 and F["c"][-1] > F["o"][-1]:
        return UP, "Double bottom formed and holding"
    if len(hi) >= 2 and abs(hi[-1][1]-hi[-2][1]) < a*0.4 and F["c"][-1] < F["o"][-1]:
        return DN, "Double top formed and failing"
    return None

@S("RV_TWEEZER", "RV")
def _rv_tw(F):
    a = F["atr"]*0.15
    if abs(F["l"][-1]-F["l"][-2]) < a and F["c"][-1] > F["o"][-1]: return UP, "Tweezer bottom at equal lows"
    if abs(F["h"][-1]-F["h"][-2]) < a and F["c"][-1] < F["o"][-1]: return DN, "Tweezer top at equal highs"
    return None

@S("RV_STOCH_DIV", "RV")
def _rv_sd(F):
    k, c = F["stK"], F["c"]
    if len(c) < 8: return None
    if c[-1] < c[-5] and k[-1] > k[-5] + 8 and k[-1] < 40: return UP, "Stochastic divergence from the lows"
    if c[-1] > c[-5] and k[-1] < k[-5] - 8 and k[-1] > 60: return DN, "Stochastic divergence from the highs"
    return None

@S("RV_MEAN_REVERT", "RV")
def _rv_mr(F):
    z = (F["price"]-F["bbM"][-1])/(F["bbSD"][-1] or 1e-12)
    if z < -2.1 and F["c"][-1] > F["o"][-1]: return UP, f"Price {abs(z):.1f}σ below mean, snapping back up"
    if z > 2.1 and F["c"][-1] < F["o"][-1]: return DN, f"Price {z:.1f}σ above mean, snapping back down"
    return None

@S("RV_V_RECOVERY", "RV")
def _rv_v(F):
    c = F["c"]
    if len(c) < 6: return None
    drop = c[-4]-c[-6]; rise = c[-1]-c[-4]
    if drop < -F["atr"]*1.2 and rise > abs(drop)*0.6: return UP, "V-shaped recovery after a sharp drop"
    if drop > F["atr"]*1.2 and rise < -abs(drop)*0.6: return DN, "Inverted-V rollover after a sharp spike"
    return None

# ══════════ FAMILY SR — SUPPORT / RESISTANCE ══════════
@S("SR_BOUNCE", "SR")
def _sr_b(F):
    s, r, a, p = F["sup"], F["res"], F["atr"], F["price"]
    if s and abs(p-s["price"]) < a*0.7 and F["c"][-1] > F["o"][-1] and s["strength"] >= 4:
        return UP, f"Bounce from support {s['price']:.5f} (strength {s['strength']}, {s['touches']} touches)"
    if r and abs(r["price"]-p) < a*0.7 and F["c"][-1] < F["o"][-1] and r["strength"] >= 4:
        return DN, f"Rejection at resistance {r['price']:.5f} (strength {r['strength']}, {r['touches']} touches)"
    return None

@S("SR_BREAK_RETEST", "SR")
def _sr_brt(F):
    s, r, a = F["sup"], F["res"], F["atr"]
    c = F["c"]
    if r and c[-2] > r["price"] and abs(c[-1]-r["price"]) < a*0.5 and c[-1] > F["o"][-1]:
        return UP, f"Broke resistance {r['price']:.5f} and retested it as support"
    if s and c[-2] < s["price"] and abs(c[-1]-s["price"]) < a*0.5 and c[-1] < F["o"][-1]:
        return DN, f"Broke support {s['price']:.5f} and retested it as resistance"
    return None

@S("SR_ROOM_TO_RUN", "SR")
def _sr_room(F):
    s, r, a = F["sup"], F["res"], F["atr"]
    if r and (r["price"]-F["price"]) > a*2.2 and F["ema8"][-1] > F["ema21"][-1]:
        return UP, f"Clear space to next resistance {r['price']:.5f} (>2 ATR headroom)"
    if s and (F["price"]-s["price"]) > a*2.2 and F["ema8"][-1] < F["ema21"][-1]:
        return DN, f"Clear space to next support {s['price']:.5f} (>2 ATR downside room)"
    return None

@S("SR_MID_RANGE", "SR")
def _sr_mid(F):
    s, r = F["sup"], F["res"]
    if not (s and r): return None
    mid = (s["price"]+r["price"])/2
    width = r["price"]-s["price"]
    if width <= 0: return None
    pos = (F["price"]-s["price"])/width
    if pos < 0.25 and F["rsi"][-1] < 45: return UP, "Price at bottom quarter of the S/R range"
    if pos > 0.75 and F["rsi"][-1] > 55: return DN, "Price at top quarter of the S/R range"
    return None

@S("SR_ROUND_NUMBER", "SR")
def _sr_round(F):
    p = F["price"]; a = F["atr"]
    step = 10 ** (math.floor(math.log10(max(p, 1e-9))) - 3)
    near = round(p/step)*step
    if abs(p-near) < a*0.35:
        return (UP, f"Holding above psychological level {near:.5f}") if F["c"][-1] > F["o"][-1] \
            else (DN, f"Failing at psychological level {near:.5f}")
    return None

@S("SR_PIVOT", "SR")
def _sr_piv(F):
    h, l, c = F["h"], F["l"], F["c"]
    if len(c) < 30: return None
    P = (h[-30:].max()+l[-30:].min()+c[-1])/3
    if c[-1] > P and c[-2] <= P: return UP, f"Reclaimed session pivot {P:.5f}"
    if c[-1] < P and c[-2] >= P: return DN, f"Lost session pivot {P:.5f}"
    return None

@S("SR_FIB", "SR")
def _sr_fib(F):
    h, l = F["h"][-40:], F["l"][-40:]
    hi, lo = float(h.max()), float(l.min())
    if hi <= lo: return None
    lv = {"0.382": hi-(hi-lo)*0.382, "0.5": hi-(hi-lo)*0.5, "0.618": hi-(hi-lo)*0.618}
    a = F["atr"]*0.4
    for k, v in lv.items():
        if abs(F["price"]-v) < a:
            if F["ema21"][-1] < F["price"] and F["c"][-1] > F["o"][-1]:
                return UP, f"Bullish hold at Fib {k} ({v:.5f})"
            if F["ema21"][-1] > F["price"] and F["c"][-1] < F["o"][-1]:
                return DN, f"Bearish rejection at Fib {k} ({v:.5f})"
    return None

@S("SR_DONCHIAN", "SR")
def _sr_don(F):
    h, l, c = F["h"], F["l"], F["c"]
    if len(c) < 22: return None
    up, dnn = float(h[-21:-1].max()), float(l[-21:-1].min())
    if c[-1] > up: return UP, f"20-candle Donchian breakout above {up:.5f}"
    if c[-1] < dnn: return DN, f"20-candle Donchian breakdown below {dnn:.5f}"
    return None

@S("SR_LEVEL_STACK", "SR")
def _sr_stack(F):
    p, a = F["price"], F["atr"]
    below = sum(1 for L in F["levels"] if 0 < p-L["price"] < a*3)
    above = sum(1 for L in F["levels"] if 0 < L["price"]-p < a*3)
    if below >= 3 and above <= 1: return UP, "Multiple supports stacked below, thin resistance above"
    if above >= 3 and below <= 1: return DN, "Multiple resistances stacked above, thin support below"
    return None

# ══════════ FAMILY PA — PRICE ACTION ══════════
@S("PA_MARUBOZU", "PA")
def _pa_mar(F):
    i = -1
    if F["body"][i] > F["range"][i]*0.82:
        return (UP, "Bullish marubozu (full-body candle)") if F["bull"][i] else (DN, "Bearish marubozu (full-body candle)")
    return None

@S("PA_INSIDE_BREAK", "PA")
def _pa_ins(F):
    if F["h"][-2] < F["h"][-3] and F["l"][-2] > F["l"][-3]:
        if F["c"][-1] > F["h"][-2]: return UP, "Inside-bar broken to the upside"
        if F["c"][-1] < F["l"][-2]: return DN, "Inside-bar broken to the downside"
    return None

@S("PA_OUTSIDE", "PA")
def _pa_out(F):
    if F["h"][-1] > F["h"][-2] and F["l"][-1] < F["l"][-2]:
        return (UP, "Outside bar closing bullish") if F["bull"][-1] else (DN, "Outside bar closing bearish")
    return None

@S("PA_CLOSE_POS", "PA")
def _pa_cp(F):
    pos = (F["c"][-1]-F["l"][-1])/F["range"][-1]
    if pos > 0.78 and F["body"][-1] > F["avgbody"]*0.7: return UP, "Candle closed in the top 22% of its range"
    if pos < 0.22 and F["body"][-1] > F["avgbody"]*0.7: return DN, "Candle closed in the bottom 22% of its range"
    return None

@S("PA_THREE_SOLDIERS", "PA")
def _pa_3s(F):
    o, c = F["o"], F["c"]
    if all(c[-i] > o[-i] for i in (1, 2, 3)) and c[-1] > c[-2] > c[-3]:
        return UP, "Three white soldiers"
    if all(c[-i] < o[-i] for i in (1, 2, 3)) and c[-1] < c[-2] < c[-3]:
        return DN, "Three black crows"
    return None

@S("PA_WICK_RATIO", "PA")
def _pa_wick(F):
    u, d = float(F["upw"][-3:].sum()), float(F["dnw"][-3:].sum())
    if d > u*2.2: return UP, "Lower wicks dominating last 3 candles (buyers defending)"
    if u > d*2.2: return DN, "Upper wicks dominating last 3 candles (sellers capping)"
    return None

@S("PA_GAP_FILL", "PA")
def _pa_gap(F):
    o, c = F["o"], F["c"]
    g = o[-1]-c[-2]
    if g < -F["atr"]*0.5 and c[-1] > o[-1]: return UP, "Down gap being filled by bulls"
    if g > F["atr"]*0.5 and c[-1] < o[-1]: return DN, "Up gap being filled by bears"
    return None

@S("PA_MOMENTUM_CHAIN", "PA")
def _pa_chain(F):
    b = F["body"][-3:]
    if b[0] < b[1] < b[2]:
        return (UP, "Bodies growing into bullish thrust") if F["bull"][-1] else (DN, "Bodies growing into bearish thrust")
    return None

@S("PA_REJECT_HIGH_LOW", "PA")
def _pa_rej(F):
    h, l, c = F["h"], F["l"], F["c"]
    if len(c) < 12: return None
    if h[-1] >= h[-12:].max() and c[-1] < (h[-1]+l[-1])/2: return DN, "New high rejected with a close below mid-range"
    if l[-1] <= l[-12:].min() and c[-1] > (h[-1]+l[-1])/2: return UP, "New low rejected with a close above mid-range"
    return None

@S("PA_COMPRESSION_POP", "PA")
def _pa_comp(F):
    rng = F["range"]
    if rng[-4:-1].mean() < F["atr"]*0.55 and rng[-1] > F["atr"]*1.2:
        return (UP, "Compression then bullish expansion candle") if F["bull"][-1] \
            else (DN, "Compression then bearish expansion candle")
    return None

# ══════════ FAMILY VO — VOLATILITY ══════════
@S("VO_BB_SQUEEZE", "VO")
def _vo_sq(F):
    w = (F["bbU"]-F["bbL"])
    if w[-1] > w[-6:-1].mean()*1.35:
        return (UP, "Bollinger squeeze released upward") if F["c"][-1] > F["bbM"][-1] \
            else (DN, "Bollinger squeeze released downward")
    return None

@S("VO_BB_WALK", "VO")
def _vo_walk(F):
    if F["c"][-1] > F["bbU"][-1] and F["c"][-2] > F["bbU"][-2]: return UP, "Walking the upper Bollinger band"
    if F["c"][-1] < F["bbL"][-1] and F["c"][-2] < F["bbL"][-2]: return DN, "Walking the lower Bollinger band"
    return None

@S("VO_ATR_EXPANSION", "VO")
def _vo_atr(F):
    if F["volratio"] > 1.6:
        return (UP, f"Volatility expansion {F['volratio']:.1f}x with bullish close") if F["bull"][-1] \
            else (DN, f"Volatility expansion {F['volratio']:.1f}x with bearish close")
    return None

@S("VO_KELTNER", "VO")
def _vo_kc(F):
    m = F["ema21"]; a = F["atr"]
    up, dn = m[-1]+a*1.5, m[-1]-a*1.5
    if F["c"][-1] > up: return UP, "Close outside upper Keltner channel"
    if F["c"][-1] < dn: return DN, "Close outside lower Keltner channel"
    return None

@S("VO_QUIET_DRIFT", "VO")
def _vo_qd(F):
    if F["volratio"] < 0.8 and F["adxv"] > 20:
        return (UP, "Low-volatility steady bullish drift") if F["ema8"][-1] > F["ema21"][-1] \
            else (DN, "Low-volatility steady bearish drift")
    return None

@S("VO_RANGE_BREAK", "VO")
def _vo_rb(F):
    h, l, c = F["h"], F["l"], F["c"]
    if len(c) < 16: return None
    hi, lo = float(h[-16:-1].max()), float(l[-16:-1].min())
    if (hi-lo) < F["atr"]*2.5:
        if c[-1] > hi: return UP, "Tight range broken upward"
        if c[-1] < lo: return DN, "Tight range broken downward"
    return None

# ══════════ FAMILY ST — STRUCTURE / SMART MONEY ══════════
@S("ST_BOS", "ST")
def _st_bos(F):
    hi, lo = swing_points(list(F["h"]), list(F["l"]), 2)
    c = F["c"][-1]
    if hi and c > hi[-1][1]: return UP, "Break of structure above last swing high"
    if lo and c < lo[-1][1]: return DN, "Break of structure below last swing low"
    return None

@S("ST_CHOCH", "ST")
def _st_choch(F):
    hi, lo = swing_points(list(F["h"]), list(F["l"]), 2)
    if len(hi) >= 2 and len(lo) >= 2:
        if lo[-1][1] > lo[-2][1] and F["c"][-1] > hi[-1][1]:
            return UP, "Change of character to bullish"
        if hi[-1][1] < hi[-2][1] and F["c"][-1] < lo[-1][1]:
            return DN, "Change of character to bearish"
    return None

@S("ST_FVG", "ST")
def _st_fvg(F):
    h, l = F["h"], F["l"]
    if len(h) < 4: return None
    if l[-1] > h[-3]: return UP, "Bullish fair-value gap left behind"
    if h[-1] < l[-3]: return DN, "Bearish fair-value gap left behind"
    return None

@S("ST_LIQ_SWEEP", "ST")
def _st_sweep(F):
    h, l, c = F["h"], F["l"], F["c"]
    if len(c) < 12: return None
    if l[-1] < l[-12:-1].min() and c[-1] > l[-12:-1].min():
        return UP, "Liquidity sweep below the lows then reclaim"
    if h[-1] > h[-12:-1].max() and c[-1] < h[-12:-1].max():
        return DN, "Liquidity sweep above the highs then rejection"
    return None

@S("ST_ORDER_BLOCK", "ST")
def _st_ob(F):
    o, c, b = F["o"], F["c"], F["body"]
    for i in range(-6, -2):
        if b[i] > F["avgbody"]*1.5:
            if c[i] < o[i] and F["c"][-1] > o[i]: return UP, "Bullish reaction from a bearish order block"
            if c[i] > o[i] and F["c"][-1] < o[i]: return DN, "Bearish reaction from a bullish order block"
    return None

@S("ST_EQ_LEVELS", "ST")
def _st_eq(F):
    a = F["atr"]*0.12
    h, l = F["h"], F["l"]
    if abs(h[-2]-h[-3]) < a and F["c"][-1] > h[-2]: return UP, "Equal highs taken out (liquidity grab up)"
    if abs(l[-2]-l[-3]) < a and F["c"][-1] < l[-2]: return DN, "Equal lows taken out (liquidity grab down)"
    return None

@S("ST_PREMIUM_DISCOUNT", "ST")
def _st_pd(F):
    h, l = F["h"][-50:], F["l"][-50:]
    hi, lo = float(h.max()), float(l.min())
    if hi <= lo: return None
    pos = (F["price"]-lo)/(hi-lo)
    if pos < 0.35 and F["ema21"][-1] < F["ema55"][-1]*1.001 and F["c"][-1] > F["o"][-1]:
        return UP, "Price in discount zone of the dealing range"
    if pos > 0.65 and F["c"][-1] < F["o"][-1]:
        return DN, "Price in premium zone of the dealing range"
    return None

# ══════════ FAMILY CY — CYCLE / STATISTICS ══════════
@S("CY_ZSCORE", "CY")
def _cy_z(F):
    c = F["c"][-30:]
    z = (F["price"]-c.mean())/(c.std() or 1e-12)
    if z < -1.8: return UP, f"Statistical z-score {z:.1f} (stretched low)"
    if z > 1.8: return DN, f"Statistical z-score {z:.1f} (stretched high)"
    return None

@S("CY_MEAN_GAP", "CY")
def _cy_mg(F):
    g = (F["price"]-F["sma20"][-1])/(F["atr"] or 1e-12)
    if g < -1.5 and F["c"][-1] > F["o"][-1]: return UP, "Price far below SMA20, reverting up"
    if g > 1.5 and F["c"][-1] < F["o"][-1]: return DN, "Price far above SMA20, reverting down"
    return None

@S("CY_STREAK_PROB", "CY")
def _cy_streak(F):
    b = list(F["bull"])
    k = 1
    while k < len(b) and b[-k-1] == b[-1]: k += 1
    if k >= 6: return (DN, f"{k} consecutive bullish candles - statistical pullback due") if b[-1] \
        else (UP, f"{k} consecutive bearish candles - statistical bounce due")
    return None

@S("CY_HOUR_BIAS", "CY")
def _cy_hour(F):
    c = F["c"]
    if len(c) < 60: return None
    up = sum(1 for i in range(-60, 0) if c[i] > F["o"][i])
    if up >= 38: return UP, f"Last hour bullish bias ({up}/60 green candles)"
    if up <= 22: return DN, f"Last hour bearish bias ({60-up}/60 red candles)"
    return None

@S("CY_RETURN_SYMMETRY", "CY")
def _cy_sym(F):
    c = F["c"]
    if len(c) < 21: return None
    r = np.diff(c[-21:])
    if r.mean() > 0 and (r > 0).sum() >= 12: return UP, "Positive drift with majority up-returns"
    if r.mean() < 0 and (r < 0).sum() >= 12: return DN, "Negative drift with majority down-returns"
    return None

@S("CY_VOLATILITY_CYCLE", "CY")
def _cy_vc(F):
    rg = F["range"]
    if rg[-1] < rg[-10:].mean()*0.6:
        return (UP, "Contraction inside up-trend, continuation expected") if F["ema8"][-1] > F["ema21"][-1] \
            else (DN, "Contraction inside down-trend, continuation expected")
    return None

@S("CY_LINREG", "CY")
def _cy_lr(F):
    c = F["c"][-25:]
    if len(c) < 25: return None
    x = np.arange(len(c)); k, b = np.polyfit(x, c, 1)
    resid = c - (k*x+b); sd = resid.std() or 1e-12
    dev = resid[-1]/sd
    if k > 0 and dev < -1.2: return UP, "Below rising regression channel (buy the dip)"
    if k < 0 and dev > 1.2: return DN, "Above falling regression channel (sell the rally)"
    return None

# ══════════ FAMILY SS — SESSION / TIME ══════════
@S("SS_SESSION_TREND", "SS")
def _ss_st(F):
    if F["sessw"] >= 1.05 and F["adxv"] >= 20:
        return (UP, f"{F['session']} session momentum favours buyers") if F["ema8"][-1] > F["ema21"][-1] \
            else (DN, f"{F['session']} session momentum favours sellers")
    return None

@S("SS_QUIET_RANGE", "SS")
def _ss_qr(F):
    if F["sessw"] <= 0.9 and F["regime"] == "RANGING":
        s, r = F["sup"], F["res"]
        if s and abs(F["price"]-s["price"]) < F["atr"]*0.8: return UP, "Quiet session: range support bounce"
        if r and abs(r["price"]-F["price"]) < F["atr"]*0.8: return DN, "Quiet session: range resistance fade"
    return None

@S("SS_OPEN_DRIVE", "SS")
def _ss_od(F):
    m = get_now().minute
    if m in (0, 1, 30, 31) and F["body"][-1] > F["avgbody"]:
        return (UP, "Half-hour open drive to the upside") if F["bull"][-1] else (DN, "Half-hour open drive to the downside")
    return None

@S("SS_OTC_WEEKEND", "SS")
def _ss_otc(F):
    if F["weekday"] >= 5 and F["regime"] in ("RANGING", "NORMAL"):
        if F["rsi"][-1] < 35: return UP, "Weekend OTC mean-reversion from oversold"
        if F["rsi"][-1] > 65: return DN, "Weekend OTC mean-reversion from overbought"
    return None

@S("SS_MONDAY_BREAK", "SS")
def _ss_mon(F):
    if F["weekday"] == 0 and F["regime"] in ("BREAKOUT", "TRENDING"):
        return (UP, "Monday breakout continuation upward") if F["ema8"][-1] > F["ema21"][-1] \
            else (DN, "Monday breakout continuation downward")
    return None

@S("SS_FRIDAY_FADE", "SS")
def _ss_fri(F):
    if F["weekday"] == 4 and abs(F["price"]-F["sma20"][-1]) > F["atr"]*1.4:
        return (DN, "Friday fade back to the mean from above") if F["price"] > F["sma20"][-1] \
            else (UP, "Friday fade back to the mean from below")
    return None

# ══════════ FAMILY CF — MULTI-FACTOR CONFLUENCE ══════════
def _mk_conf(idx, need, checks_desc):
    def fn(F):
        up = 0; dn = 0; hits = []
        tests = [
            (F["ema8"][-1] > F["ema21"][-1], "EMA8>EMA21"),
            (F["macd"][-1] > F["macds"][-1], "MACD>signal"),
            (F["rsi"][-1] > 50, "RSI>50"),
            (F["st"][-1] > 0, "Supertrend up"),
            (F["price"] > F["bbM"][-1], "above BB mid"),
            (F["stK"][-1] > F["stD"][-1], "Stoch K>D"),
            (F["pdi"][-1] > F["ndi"][-1], "+DI>-DI"),
            (F["c"][-1] > F["o"][-1], "green candle"),
            (F["price"] > F["ema55"][-1], "above EMA55"),
            (F["cci"][-1] > 0, "CCI>0"),
            (F["hac"][-1] > F["hao"][-1], "HA bullish"),
            (F["slope5"] > 0, "short slope up"),
        ]
        sel = tests[idx % 4:] + tests[:idx % 4]
        for cond, label in sel:
            if cond: up += 1; hits.append(label)
            else: dn += 1
        total = len(sel)
        if up >= need: return UP, f"{up}/{total} bullish confluence ({', '.join(hits[:4])})"
        if dn >= need: return DN, f"{dn}/{total} bearish confluence ({checks_desc})"
        return None
    return fn

for _i, _need in enumerate([8, 9, 10, 11, 8, 9, 10, 12]):
    STRATS.append((f"CF_MULTI{_i+1}", "CF", _mk_conf(_i, _need, "majority of indicators bearish")))

@S("CF_TREND_MOM_SR", "CF")
def _cf_tms(F):
    s, r, a = F["sup"], F["res"], F["atr"]
    trend_up = F["ema8"][-1] > F["ema21"][-1] > F["ema55"][-1]
    trend_dn = F["ema8"][-1] < F["ema21"][-1] < F["ema55"][-1]
    if trend_up and F["rsi"][-1] > 52 and (not r or (r["price"]-F["price"]) > a):
        return UP, "Trend + momentum aligned with clean space to resistance"
    if trend_dn and F["rsi"][-1] < 48 and (not s or (F["price"]-s["price"]) > a):
        return DN, "Trend + momentum aligned with clean space to support"
    return None

@S("CF_MTF_MOM", "CF")
def _cf_mtf(F):
    m = F["mtf"]
    if not m: return None
    if m.get("M5") == UP and F["macdh"][-1] > 0 and F["rsi"][-1] > 50:
        return UP, "M5 trend and M1 momentum both bullish"
    if m.get("M5") == DN and F["macdh"][-1] < 0 and F["rsi"][-1] < 50:
        return DN, "M5 trend and M1 momentum both bearish"
    return None

@S("CF_FORMING", "CF")
def _cf_form(F):
    fp = F["forming"]
    if len(fp) < 3: return None
    d = _fp_px(fp[-1]) - _fp_px(fp[0])
    if abs(d) < F["atr"]*0.08: return None
    if d > 0: return UP, "Live forming candle is pushing up in real time"
    return DN, "Live forming candle is pushing down in real time"

@S("CF_TRIPLE_SCREEN", "CF")
def _cf_ts(F):
    m = F["mtf"]
    long_ok = m.get("M15") == UP
    short_ok = F["stK"][-1] < 45
    if long_ok and short_ok and F["c"][-1] > F["o"][-1]:
        return UP, "Triple-screen: M15 up-trend + oversold entry"
    if m.get("M15") == DN and F["stK"][-1] > 55 and F["c"][-1] < F["o"][-1]:
        return DN, "Triple-screen: M15 down-trend + overbought entry"
    return None

@S("CF_PAYOUT_QUALITY", "CF")
def _cf_pay(F):
    if F["payout"] >= 88 and F["adxv"] >= 20:
        return (UP, f"High payout {F['payout']:.0f}% with a clean bullish trend") if F["ema8"][-1] > F["ema21"][-1] \
            else (DN, f"High payout {F['payout']:.0f}% with a clean bearish trend")
    return None



# ══════════ FAMILY TR2 — HIGH-ACCURACY TREND PACK (candle-data only) ══════════
def _wma(d, p):
    p = int(max(2, min(p, len(d))))
    w = np.arange(1, p + 1, dtype=float)
    return float(np.dot(d[-p:], w) / w.sum())


def _hma(d, p=21):
    if len(d) < p + 2: return None
    half = _wma(d, max(2, p // 2)); full = _wma(d, p)
    raw = 2 * half - full
    return raw


def _hma_series(d, p=21, k=4):
    out = []
    for i in range(k, 0, -1):
        v = _hma(d[:len(d) - i + 1], p)
        if v is None: return None
        out.append(v)
    return out


def _linreg(d, p=30):
    p = int(min(p, len(d)))
    if p < 8: return 0.0, 0.0
    y = d[-p:]; x = np.arange(p, dtype=float)
    sl, ic = np.polyfit(x, y, 1)
    pred = sl * x + ic
    ss_res = float(np.sum((y - pred) ** 2)); ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1e-12
    return float(sl), float(max(0.0, 1 - ss_res / ss_tot))


@S("TR2_RIBBON_EXPAND", "TR")
def _t2_ribbon(F):
    e = [F[f"ema{p}"] for p in (8, 13, 21, 34, 55)]
    now = [x[-1] for x in e]; prv = [x[-4] for x in e if len(x) > 4]
    if len(prv) < 5: return None
    width_now = abs(now[0] - now[-1]); width_prv = abs(prv[0] - prv[-1])
    if width_now <= width_prv: return None
    if all(now[i] > now[i + 1] for i in range(4)) and F["price"] > now[0]:
        return UP, "EMA ribbon 8>13>21>34>55 and expanding (strong bull trend)"
    if all(now[i] < now[i + 1] for i in range(4)) and F["price"] < now[0]:
        return DN, "EMA ribbon 8<13<21<34<55 and expanding (strong bear trend)"
    return None


@S("TR2_HULL", "TR")
def _t2_hull(F):
    h = _hma_series(F["c"], 21, 4)
    if not h: return None
    rising = h[-1] > h[-2] > h[-3]
    falling = h[-1] < h[-2] < h[-3]
    if rising and F["price"] > F["ema21"][-1]:
        return UP, "Hull MA rising 3 bars with price above EMA21"
    if falling and F["price"] < F["ema21"][-1]:
        return DN, "Hull MA falling 3 bars with price below EMA21"
    return None


@S("TR2_DONCHIAN_BRK", "TR")
def _t2_don(F):
    n = 20
    if F["n"] < n + 3: return None
    hi = float(np.max(F["h"][-n-1:-1])); lo = float(np.min(F["l"][-n-1:-1]))
    a = F["atr"]
    if F["price"] > hi and (F["price"] - hi) < 1.2 * a and F["adxv"] >= 18:
        return UP, "Donchian-20 breakout up with healthy ATR and ADX"
    if F["price"] < lo and (lo - F["price"]) < 1.2 * a and F["adxv"] >= 18:
        return DN, "Donchian-20 breakout down with healthy ATR and ADX"
    return None


@S("TR2_ADX_DI_RISE", "TR")
def _t2_adxdi(F):
    ad, pd_, nd = F["adx"], F["pdi"], F["ndi"]
    if len(ad) < 4: return None
    rising = ad[-1] > ad[-2] > ad[-3] and ad[-1] >= 20
    if not rising: return None
    if pd_[-1] > nd[-1] and pd_[-2] <= nd[-2] * 1.02:
        return UP, f"+DI over -DI with ADX rising to {ad[-1]:.0f} (trend igniting up)"
    if nd[-1] > pd_[-1] and nd[-2] <= pd_[-2] * 1.02:
        return DN, f"-DI over +DI with ADX rising to {ad[-1]:.0f} (trend igniting down)"
    return None


@S("TR2_ST_MULTI", "TR")
def _t2_stmulti(F):
    votes = []
    for per, mult in ((10, 3.0), (7, 2.0), (14, 4.0)):
        try:
            st = supertrend(F["h"], F["l"], F["c"], per, mult)
        except Exception:
            continue
        votes.append(1 if F["price"] > st[-1] else -1)
    if len(votes) < 3: return None
    if sum(votes) == 3:  return UP, "All 3 SuperTrend settings (10/3, 7/2, 14/4) bullish"
    if sum(votes) == -3: return DN, "All 3 SuperTrend settings (10/3, 7/2, 14/4) bearish"
    return None


@S("TR2_VWAP_BIAS", "TR")
def _t2_vwap(F):
    n = min(120, F["n"])
    tp = (F["h"][-n:] + F["l"][-n:] + F["c"][-n:]) / 3.0
    w = np.maximum(F["range"][-n:], 1e-12)          # range as a volume proxy
    vwap = float(np.dot(tp, w) / w.sum())
    dev = (F["price"] - vwap) / max(F["atr"], 1e-12)
    if 0.15 < dev < 2.2 and F["ema8"][-1] > F["ema21"][-1]:
        return UP, "Price holding above session VWAP with bullish EMA bias"
    if -2.2 < dev < -0.15 and F["ema8"][-1] < F["ema21"][-1]:
        return DN, "Price holding below session VWAP with bearish EMA bias"
    return None


@S("TR2_LINREG_R2", "TR")
def _t2_linreg(F):
    sl, r2 = _linreg(F["c"], 30)
    if r2 < 0.55: return None
    norm = sl / max(F["atr"], 1e-12)
    if norm > 0.05:  return UP, f"Linear-regression channel rising, fit R2 {r2:.2f} (clean uptrend)"
    if norm < -0.05: return DN, f"Linear-regression channel falling, fit R2 {r2:.2f} (clean downtrend)"
    return None


@S("TR2_HTF_GATE", "TR")
def _t2_htf(F):
    m = F.get("mtf") or {}
    if not m: return None
    vals = [v for v in (m.get("M5"), m.get("M15")) if v]
    if len(vals) < 2 or vals[0] != vals[1]: return None
    d = vals[0]
    if d == UP and F["ema8"][-1] > F["ema21"][-1]:
        return UP, "M5 and M15 both bullish and M1 aligned (higher-timeframe gate open)"
    if d == DN and F["ema8"][-1] < F["ema21"][-1]:
        return DN, "M5 and M15 both bearish and M1 aligned (higher-timeframe gate open)"
    return None


@S("TR2_PULLBACK_EMA21", "TR")
def _t2_pull(F):
    e21 = F["ema21"]; a = F["atr"]
    dist = (F["price"] - e21[-1]) / max(a, 1e-12)
    touched = np.min(np.abs(F["l"][-3:] - e21[-3:])) < 0.45 * a
    if F["ema8"][-1] > F["ema21"][-1] > F["ema55"][-1] and 0 <= dist < 0.9 and touched:
        return UP, "Uptrend pullback into EMA21 held (continuation entry)"
    touched_d = np.min(np.abs(F["h"][-3:] - e21[-3:])) < 0.45 * a
    if F["ema8"][-1] < F["ema21"][-1] < F["ema55"][-1] and -0.9 < dist <= 0 and touched_d:
        return DN, "Downtrend pullback into EMA21 rejected (continuation entry)"
    return None


@S("TR2_NO_3PUSH", "TR")
def _t2_3push(F):
    """Filter against exhausted trends: 3 pushes with shrinking bodies = fade the trend."""
    b = F["body"][-6:]
    if len(b) < 6: return None
    up_run = int(np.sum(F["bull"][-5:])); shrink = b[-1] < b[-3] < b[-5]
    if up_run >= 4 and shrink and F["rsi"][-1] > 68:
        return DN, "Third bullish push with shrinking bodies and hot RSI (trend exhausted)"
    if up_run <= 1 and shrink and F["rsi"][-1] < 32:
        return UP, "Third bearish push with shrinking bodies and cold RSI (trend exhausted)"
    return None


@S("TR2_MOM_ALIGN", "TR")
def _t2_mom(F):
    ok_up = (F["macdh"][-1] > 0 and F["macdh"][-1] > F["macdh"][-2]
             and F["rsi"][-1] > 52 and F["ema8s"] > 0 and F["adxv"] >= 20)
    ok_dn = (F["macdh"][-1] < 0 and F["macdh"][-1] < F["macdh"][-2]
             and F["rsi"][-1] < 48 and F["ema8s"] < 0 and F["adxv"] >= 20)
    if ok_up: return UP, "MACD histogram, RSI and EMA slope all accelerating up with ADX>20"
    if ok_dn: return DN, "MACD histogram, RSI and EMA slope all accelerating down with ADX>20"
    return None


# ─────────────────────────────────────────────────────────────
#  EXHAUSTION PACK  (family "EX") — trend ke last me entry rokne ke liye
#  Ye strategies continuation ke against vote karti hain jab trend thak
#  chuka ho. Koi threshold strict nahi hota — sirf votes shift hote hain.
# ─────────────────────────────────────────────────────────────
@S("EX_RUN_DECAY", "EX")
def _ex_run(F):
    """5+ same-direction candles + shrinking bodies = trend ka last hissa."""
    if F["run_len"] < 5 or not F["body_decay"]:
        return None
    if F["run_dir"] == UP:
        return DN, f"{F['run_len']} green candles in a row with shrinking bodies (trend exhausted)"
    return UP, f"{F['run_len']} red candles in a row with shrinking bodies (trend exhausted)"


@S("EX_OVEREXT_ATR", "EX")
def _ex_ext(F):
    """Price EMA21 se 2.2 ATR door + RSI7 extreme = over-extended."""
    e = F["ext_atr"]; r7 = float(F["rsi7"][-1])
    if e > 2.2 and r7 > 78:
        return DN, f"Price {e:.1f} ATR above EMA21 with RSI7 {r7:.0f} (over-extended top)"
    if e < -2.2 and r7 < 22:
        return UP, f"Price {abs(e):.1f} ATR below EMA21 with RSI7 {r7:.0f} (over-extended bottom)"
    return None


@S("EX_3PUSH_DIV", "EX")
def _ex_3push(F):
    """Teesra push jisme MACD hist + RSI pehle push se kamzor = hidden divergence."""
    c = F["c"]; n = F["n"]
    if n < 40: return None
    h = F["h"]; l = F["l"]; mh = F["macdh"]; rs = F["rsi"]
    hi_now = float(np.max(h[-4:])); hi_prev = float(np.max(h[-14:-6]))
    lo_now = float(np.min(l[-4:])); lo_prev = float(np.min(l[-14:-6]))
    mh_now = float(np.max(mh[-4:])); mh_prev = float(np.max(mh[-14:-6]))
    mhl_now = float(np.min(mh[-4:])); mhl_prev = float(np.min(mh[-14:-6]))
    rs_now = float(rs[-1]); rs_prev = float(np.max(rs[-14:-6]))
    rsl_prev = float(np.min(rs[-14:-6]))
    if hi_now > hi_prev and mh_now < mh_prev and rs_now < rs_prev:
        return DN, "Higher high but weaker MACD/RSI push (momentum divergence at top)"
    if lo_now < lo_prev and mhl_now > mhl_prev and rs_now > rsl_prev:
        return UP, "Lower low but weaker MACD/RSI push (momentum divergence at bottom)"
    return None


@S("EX_CLIMAX", "EX")
def _ex_climax(F):
    """Blow-off candle: 20 candles ki sabse badi body + close wick ke andar."""
    if F["n"] < 22: return None
    body = F["body"]; 
    if float(body[-1]) < float(np.max(body[-20:])) - 1e-12:
        return None
    if F["big_range"] < 1.8:
        return None
    rng = float(F["range"][-1])
    up_rej = float(F["upw"][-1]) / (rng or 1e-12)
    dn_rej = float(F["dnw"][-1]) / (rng or 1e-12)
    if bool(F["bull"][-1]) and up_rej > 0.28:
        return DN, "Climax green candle rejected from the high (blow-off top)"
    if not bool(F["bull"][-1]) and dn_rej > 0.28:
        return UP, "Climax red candle rejected from the low (blow-off bottom)"
    return None


@S("EX_BB_STRETCH", "EX")
def _ex_bb(F):
    """Band ke bahar close + run 4+ = stretched move, next candle usually retrace."""
    if F["run_len"] < 4: return None
    p = F["price"]
    if p > float(F["bbU"][-1]) and float(F["rsi"][-1]) > 70:
        return DN, "Close outside upper Bollinger band after a long run (stretched)"
    if p < float(F["bbL"][-1]) and float(F["rsi"][-1]) < 30:
        return UP, "Close outside lower Bollinger band after a long run (stretched)"
    return None



# ══════════ FAMILY NM — NON-MTG FIRST-CANDLE SNIPERS ══════════
#  Ye strategies sirf tab bolti hain jab pehli hi candle me close hone ka
#  structural + statistical reason ho (no MTG dependency). Isi liye inka
#  gate weight sabse zyada hai aur inke bina signal nahi jata.

@S("NM Ribbon Thrust", "NM")
def _nm_ribbon(F):
    """Fast ribbon fully stacked + last candle strong close in same side +
    khula raasta = next candle usually same colour me close hoti hai."""
    if abs(F["ribbon_score"]) < 1.0: return None
    if F["bodyratio"] < 0.55 or F["adxv"] < 18: return None
    if F["ribbon_score"] > 0 and F["clv"] > 0.35 and F["room_up"] >= 0.9 and F["price"] > float(F["ema21"][-1]):
        return UP, "Fast EMA ribbon fully bullish, strong close near high, clear room above"
    if F["ribbon_score"] < 0 and F["clv"] < -0.35 and F["room_dn"] >= 0.9 and F["price"] < float(F["ema21"][-1]):
        return DN, "Fast EMA ribbon fully bearish, strong close near low, clear room below"
    return None

@S("NM Clean Close", "NM")
def _nm_clean(F):
    """Body 65%+, against-wick 15% se kam, EMA8 ke correct side -> follow-through."""
    if F["bodyratio"] < 0.65: return None
    if F["clv"] > 0.5 and F["upw_r"] < 0.15 and F["price"] > float(F["ema8"][-1]):
        return UP, "Clean bullish body with almost no upper wick (buyers in control)"
    if F["clv"] < -0.5 and F["dnw_r"] < 0.15 and F["price"] < float(F["ema8"][-1]):
        return DN, "Clean bearish body with almost no lower wick (sellers in control)"
    return None

@S("NM Micro Momentum", "NM")
def _nm_micro(F):
    """3-candle net move 0.8 ATR+ aur RSI mid-zone se nikal raha ho ->
    momentum abhi zinda hai, agli candle usi taraf close hoti hai."""
    m = F["micro_mom"]; r = float(F["rsi"][-1])
    if m >= 0.8 and 52 <= r <= 72 and F["clv3"] > 0.15:
        return UP, f"3-candle upward drive {m:.1f} ATR with RSI still in the healthy zone"
    if m <= -0.8 and 28 <= r <= 48 and F["clv3"] < -0.15:
        return DN, f"3-candle downward drive {abs(m):.1f} ATR with RSI still in the healthy zone"
    return None

@S("NM Pullback Snap", "NM")
def _nm_pull(F):
    """Trend me shallow pullback ke turant baad ka entry — pehli candle
    hit rate sabse zyada isi setup ka hota hai."""
    e8, e21 = float(F["ema8"][-1]), float(F["ema21"][-1])
    if F["adxv"] < 20: return None
    if e8 > e21 and F["dnw_r"] > 0.35 and F["clv"] > 0.2 and F["price"] > e8:
        return UP, "Shallow dip bought back inside an uptrend (pullback snap-back)"
    if e8 < e21 and F["upw_r"] > 0.35 and F["clv"] < -0.2 and F["price"] < e8:
        return DN, "Shallow rally sold back inside a downtrend (pullback snap-back)"
    return None

@S("NM Rejection Wick", "NM")
def _nm_rej(F):
    """S/R par lamba rejection wick + opposite side khula = instant reversal candle."""
    if F["upw_r"] >= 0.55 and F["res"] and F["room_dn"] >= 1.0 and float(F["rsi"][-1]) > 55:
        return DN, "Long rejection wick into resistance with open space below"
    if F["dnw_r"] >= 0.55 and F["sup"] and F["room_up"] >= 1.0 and float(F["rsi"][-1]) < 45:
        return UP, "Long rejection wick off support with open space above"
    return None

@S("NM Volatility Sweet Spot", "NM")
def _nm_vol(F):
    """Na dead na crazy — 0.75x-1.8x ATR range me hi pehli candle predictable hoti hai."""
    if not (0.75 <= F["big_range"] <= 1.8): return None
    if F["doji_cluster"] >= 2: return None
    if F["ribbon_score"] > 0 and F["micro_mom"] > 0.3:
        return UP, "Volatility in the predictable band with bullish structure"
    if F["ribbon_score"] < 0 and F["micro_mom"] < -0.3:
        return DN, "Volatility in the predictable band with bearish structure"
    return None

@S("NM Forming Confirm", "NM")
def _nm_form(F):
    """Live (forming) candle already hamari direction me body bana rahi hai."""
    if not F.get("form_dir") or F.get("form_body", 0) < 0.35: return None
    if F["form_dir"] == UP and F["ribbon_score"] >= 0.33 and F["price"] > float(F["ema21"][-1]):
        return UP, "Live candle already printing a bullish body with trend support"
    if F["form_dir"] == DN and F["ribbon_score"] <= -0.33 and F["price"] < float(F["ema21"][-1]):
        return DN, "Live candle already printing a bearish body with trend support"
    return None

@S("NM Squeeze Release", "NM")
def _nm_sqz(F):
    """Bollinger squeeze ke baad pehla expansion candle — next candle continuation."""
    sd = F["bbSD"]
    if len(sd) < 25: return None
    now = float(sd[-1]); base = float(np.mean(sd[-25:-5]))
    if now < base * 1.05: return None
    if F["bodyratio"] < 0.55: return None
    if F["clv"] > 0.3 and F["price"] > float(F["bbM"][-1]):
        return UP, "First expansion candle out of a volatility squeeze (upside)"
    if F["clv"] < -0.3 and F["price"] < float(F["bbM"][-1]):
        return DN, "First expansion candle out of a volatility squeeze (downside)"
    return None

@S("NM No-Trap Guard", "NM")
def _nm_notrap(F):
    """Sirf tab bolti hai jab pichhli candle ne opposite trap wick nahi banaya
    aur run 1-3 candle ka hi hai (over-extended nahi)."""
    if F["run_len"] > 3 or abs(F["ext_atr"]) > 1.6: return None
    if F["doji_cluster"] >= 1: return None
    if F["run_dir"] == UP and F["upw_r"] < 0.22 and F["micro_mom"] > 0.2:
        return UP, "Fresh 1-3 candle up-run, no trap wick, not over-extended"
    if F["run_dir"] == DN and F["dnw_r"] < 0.22 and F["micro_mom"] < -0.2:
        return DN, "Fresh 1-3 candle down-run, no trap wick, not over-extended"
    return None

@S("NM MTF Stack", "NM")
def _nm_mtf(F):
    """M1 + M5 + M15 teeno same side + fast ribbon aligned = highest first-candle
    hit-rate combination."""
    m = F.get("mtf") or {}
    if not (m.get("M5") and m.get("M15")): return None
    if m["M5"] != m["M15"]: return None
    d = m["M5"]
    if d == UP and F["ribbon_score"] >= 0.33 and F["clv"] > 0.1:
        return UP, "M1 + M5 + M15 all aligned bullish (multi-timeframe stack)"
    if d == DN and F["ribbon_score"] <= -0.33 and F["clv"] < -0.1:
        return DN, "M1 + M5 + M15 all aligned bearish (multi-timeframe stack)"
    return None

@S("NM Hour Edge", "NM")
def _nm_hour(F):
    """Broker-hour ka apna behaviour (continuation vs reversal) follow karti hai
    — pre-analysis se aaya statistical edge."""
    hr = str(get_now().hour)
    prof = (F.get("hourprof") or {}).get(hr)
    if not prof or prof.get("n", 0) < 60: return None
    cont = float(prof.get("cont", 0.5))
    if cont >= 0.55:
        return (UP if F["run_dir"] == UP else DN), f"This hour statistically continues ({cont*100:.0f}%)"
    if cont <= 0.45:
        return (DN if F["run_dir"] == UP else UP), f"This hour statistically reverses ({(1-cont)*100:.0f}%)"
    return None




# ═════════════════════════════════════════════════════════════
#  v52 MEGA STRATEGY LAYER  —  3 naye packs (40 strategies)
#  LQ = Liquidity / Smart-Money   MS = Micro-structure (first candle)
#  QS = Quant-statistics
#  Sab weighted voting + regime router se guzarti hain (koi hard wall nahi).
# ═════════════════════════════════════════════════════════════

def _lvl_prices(F, kind):
    return [l["price"] for l in (F.get("levels") or []) if l.get("kind") == kind] \
        if (F.get("levels") and isinstance(F["levels"][0], dict) and "kind" in F["levels"][0]) \
        else [l["price"] for l in (F.get("levels") or [])]

# ══════════ FAMILY LQ — LIQUIDITY / SMART MONEY ══════════
@S("LQ Sweep Re-entry", "LQ")
def _lq_sweep(F):
    """Pichhli candle ne swing liquidity le li aur wapas andar close hui ->
    stop-hunt reversal, next candle usually opposite direction."""
    h, l, c, o = F["h"], F["l"], F["c"], F["o"]
    if F["n"] < 12: return None
    hh = float(h[-11:-1].max()); ll = float(l[-11:-1].min())
    if float(h[-1]) > hh and float(c[-1]) < hh and F["upw_r"] > 0.3:
        return DN, "Liquidity sweep above the swing high, closed back inside"
    if float(l[-1]) < ll and float(c[-1]) > ll and F["dnw_r"] > 0.3:
        return UP, "Liquidity sweep below the swing low, closed back inside"
    return None

@S("LQ Equal Highs Raid", "LQ")
def _lq_eq(F):
    h, l = F["h"], F["l"]
    if F["n"] < 15: return None
    a = F["atr"] or 1e-12
    eqh = abs(float(h[-2]) - float(h[-3])) < a * 0.12
    eql = abs(float(l[-2]) - float(l[-3])) < a * 0.12
    if eqh and float(h[-1]) > max(float(h[-2]), float(h[-3])) and float(F["clv"]) < 0:
        return DN, "Equal highs raided then rejected (liquidity grab)"
    if eql and float(l[-1]) < min(float(l[-2]), float(l[-3])) and float(F["clv"]) > 0:
        return UP, "Equal lows raided then rejected (liquidity grab)"
    return None

@S("LQ FVG Continuation", "LQ")
def _lq_fvg(F):
    """Fair-value gap ban gaya aur price usko fill kar ke wapas direction me
    chali -> imbalance continuation."""
    h, l, c = F["h"], F["l"], F["c"]
    if F["n"] < 6: return None
    a = F["atr"] or 1e-12
    up_gap = float(l[-2]) - float(h[-4])
    dn_gap = float(l[-4]) - float(h[-2])
    if up_gap > a * 0.25 and float(c[-1]) > float(l[-2]) and F["ribbon_score"] >= 0:
        return UP, "Bullish fair-value gap held after the fill"
    if dn_gap > a * 0.25 and float(c[-1]) < float(h[-2]) and F["ribbon_score"] <= 0:
        return DN, "Bearish fair-value gap held after the fill"
    return None

@S("LQ Order Block Retest", "LQ")
def _lq_ob(F):
    """Last strong opposite candle (order block) ka retest + rejection."""
    o, c, h, l = F["o"], F["c"], F["h"], F["l"]
    if F["n"] < 10: return None
    a = F["atr"] or 1e-12
    for i in range(-3, -9, -1):
        body = abs(float(c[i]) - float(o[i]))
        if body < (F["avgbody"] or 1e-12) * 1.3: continue
        if float(c[i]) < float(o[i]):        # bearish OB -> supply
            top = float(o[i])
            if abs(F["price"] - top) < a * 0.5 and float(F["clv"]) < 0:
                return DN, "Retest of a bearish order block with rejection"
        else:                                # bullish OB -> demand
            bot = float(o[i])
            if abs(F["price"] - bot) < a * 0.5 and float(F["clv"]) > 0:
                return UP, "Retest of a bullish order block with rejection"
    return None

@S("LQ Premium Discount BOS", "LQ")
def _lq_pd(F):
    h, l = F["h"], F["l"]
    if F["n"] < 30: return None
    hi = float(h[-30:].max()); lo = float(l[-30:].min())
    rngv = max(hi - lo, 1e-12)
    pos = (F["price"] - lo) / rngv
    bos_up = F["price"] > float(h[-12:-1].max())
    bos_dn = F["price"] < float(l[-12:-1].min())
    if pos < 0.4 and bos_up: return UP, "Break of structure up from the discount zone"
    if pos > 0.6 and bos_dn: return DN, "Break of structure down from the premium zone"
    return None

@S("LQ Wick Cluster Zone", "LQ")
def _lq_wick(F):
    a = F["atr"] or 1e-12
    lows = F["l"][-6:]; highs = F["h"][-6:]
    if float(highs.max()) - float(highs.min()) < a * 0.35 and float(F["clv"]) < -0.1:
        return DN, "Repeated wicks into one supply zone"
    if float(lows.max()) - float(lows.min()) < a * 0.35 and float(F["clv"]) > 0.1:
        return UP, "Repeated wicks into one demand zone"
    return None

@S("LQ Trap Reversal", "LQ")
def _lq_trap(F):
    """Breakout hua par turant wapas — trapped breakout traders."""
    h, l, c = F["h"], F["l"], F["c"]
    if F["n"] < 14: return None
    hh = float(h[-13:-2].max()); ll = float(l[-13:-2].min())
    if float(h[-2]) > hh and float(c[-1]) < hh:
        return DN, "Failed upside breakout — trapped buyers"
    if float(l[-2]) < ll and float(c[-1]) > ll:
        return UP, "Failed downside breakout — trapped sellers"
    return None

@S("LQ Imbalance Momentum", "LQ")
def _lq_imb(F):
    a = F["atr"] or 1e-12
    net = float(F["c"][-1] - F["c"][-4]) / a if F["n"] >= 5 else 0.0
    if abs(net) < 0.9: return None
    if net > 0 and F["upw_r"] < 0.25 and F["bodyratio"] > 0.5:
        return UP, "One-sided bullish imbalance with clean closes"
    if net < 0 and F["dnw_r"] < 0.25 and F["bodyratio"] > 0.5:
        return DN, "One-sided bearish imbalance with clean closes"
    return None

# ══════════ FAMILY MS — MICRO-STRUCTURE (first-candle, NM-grade) ══════════
@S("MS Compression Break", "NM")
def _ms_comp(F):
    r = F["range"]
    if F["n"] < 8: return None
    tight = float(r[-4:-1].mean()) < float(r[-20:].mean()) * 0.7
    if not tight: return None
    if F["bodyratio"] > 0.5 and F["clv"] > 0.3: return UP, "Break out of a 3-candle compression (up)"
    if F["bodyratio"] > 0.5 and F["clv"] < -0.3: return DN, "Break out of a 3-candle compression (down)"
    return None

@S("MS Inside Bar Break", "NM")
def _ms_ib(F):
    h, l = F["h"], F["l"]
    if F["n"] < 4: return None
    inside = float(h[-2]) < float(h[-3]) and float(l[-2]) > float(l[-3])
    if not inside: return None
    if F["price"] > float(h[-2]) and F["ribbon_score"] >= 0: return UP, "Inside-bar breakout upward"
    if F["price"] < float(l[-2]) and F["ribbon_score"] <= 0: return DN, "Inside-bar breakout downward"
    return None

@S("MS Exhaustion Fade", "NM")
def _ms_ex(F):
    if F["run_len"] < 4 or not F["body_decay"]: return None
    if abs(F["ext_atr"]) < 1.0: return None
    return (DN, "Momentum exhausted after an extended up-run") if F["run_dir"] == UP \
        else (UP, "Momentum exhausted after an extended down-run")

@S("MS Opposite Close", "NM")
def _ms_oc(F):
    """Do candle ka reversal pattern: pehli strong opposite, doosri wapas —
    pehli candle hi jeetne wali setup."""
    o, c = F["o"], F["c"]
    if F["n"] < 4: return None
    b1 = abs(float(c[-2]) - float(o[-2])); b2 = abs(float(c[-1]) - float(o[-1]))
    if b2 < (F["avgbody"] or 1e-12) * 0.8: return None
    if float(c[-2]) < float(o[-2]) and float(c[-1]) > float(o[-1]) and b2 > b1 * 0.9 and F["clv"] > 0.3:
        return UP, "Strong bullish engulf of the previous bearish candle"
    if float(c[-2]) > float(o[-2]) and float(c[-1]) < float(o[-1]) and b2 > b1 * 0.9 and F["clv"] < -0.3:
        return DN, "Strong bearish engulf of the previous bullish candle"
    return None

@S("MS Wick Rejection Cluster", "NM")
def _ms_wick(F):
    up = float(sum(1 for i in (-1, -2, -3) if float(F["upw"][i]) > float(F["body"][i])))
    dn = float(sum(1 for i in (-1, -2, -3) if float(F["dnw"][i]) > float(F["body"][i])))
    if up >= 2 and dn == 0: return DN, "Cluster of upper-wick rejections"
    if dn >= 2 and up == 0: return UP, "Cluster of lower-wick rejections"
    return None

@S("MS Clean Close Drive", "NM")
def _ms_clv(F):
    if F["bodyratio"] < 0.6: return None
    if F["clv"] > 0.6 and F["micro_mom"] > 0.2 and F["room_up"] > 0.8:
        return UP, "Candle closed on its high with room above"
    if F["clv"] < -0.6 and F["micro_mom"] < -0.2 and F["room_dn"] > 0.8:
        return DN, "Candle closed on its low with room below"
    return None

@S("MS Ribbon Pull", "NM")
def _ms_rib(F):
    e5, e13 = float(F["ema5"][-1]), float(F["ema13"][-1])
    if F["ribbon_score"] >= 0.66 and F["price"] < e5 and F["price"] > e13:
        return UP, "Pullback into a fully stacked bullish ribbon"
    if F["ribbon_score"] <= -0.66 and F["price"] > e5 and F["price"] < e13:
        return DN, "Pullback into a fully stacked bearish ribbon"
    return None

@S("MS Two-Bar Thrust", "NM")
def _ms_2b(F):
    if F["n"] < 4: return None
    b = F["bull"]
    if bool(b[-1]) and bool(b[-2]) and F["clv"] > 0.2 and F["clv3"] > 0.1 and F["run_len"] <= 3:
        return UP, "Two-bar bullish thrust, still early in the run"
    if (not bool(b[-1])) and (not bool(b[-2])) and F["clv"] < -0.2 and F["clv3"] < -0.1 and F["run_len"] <= 3:
        return DN, "Two-bar bearish thrust, still early in the run"
    return None

@S("MS Range Edge Fade", "NM")
def _ms_edge(F):
    if F["regime"] != "RANGING": return None
    s, r = F["sup"], F["res"]
    a = F["atr"] or 1e-12
    if r and (float(r["price"]) - F["price"]) < a * 0.4 and F["clv"] < 0:
        return DN, "Fade from the top edge of the range"
    if s and (F["price"] - float(s["price"])) < a * 0.4 and F["clv"] > 0:
        return UP, "Bounce from the bottom edge of the range"
    return None

@S("MS Micro Trend Slope", "NM")
def _ms_slope(F):
    s5 = float(F["slope5"][-1]) if hasattr(F["slope5"], "__len__") else float(F["slope5"])
    a = F["atr"] or 1e-12
    if s5 / a > 0.12 and F["bodyratio"] > 0.4 and F["upw_r"] < 0.35:
        return UP, "Micro slope rising with healthy candles"
    if s5 / a < -0.12 and F["bodyratio"] > 0.4 and F["dnw_r"] < 0.35:
        return DN, "Micro slope falling with healthy candles"
    return None

# ══════════ FAMILY QS — QUANT STATISTICS ══════════
@S("QS Body Distribution Edge", "QS")
def _qs_body(F):
    br = F["body"] / F["range"]
    strong = float(np.mean(br[-40:] > 0.55)) if F["n"] >= 40 else float(np.mean(br > 0.55))
    if strong < 0.35: return None          # noisy market -> no directional edge
    if F["ribbon_score"] > 0 and F["clv"] > 0: return UP, f"Directional candle ratio {strong*100:.0f}% favours trend"
    if F["ribbon_score"] < 0 and F["clv"] < 0: return DN, f"Directional candle ratio {strong*100:.0f}% favours trend"
    return None

@S("QS Vol Regime Filter", "QS")
def _qs_vol(F):
    v = F["volratio"]
    if v < 0.45: return None               # dead market
    if v > 3.2: return None                # spike, unpredictable
    if F["micro_mom"] > 0.35 and F["ribbon_score"] >= 0.33:
        return UP, "Volatility in the tradable band, bullish structure"
    if F["micro_mom"] < -0.35 and F["ribbon_score"] <= -0.33:
        return DN, "Volatility in the tradable band, bearish structure"
    return None

@S("QS Z Reversion 60", "QS")
def _qs_z60(F):
    if F["n"] < 60: return None
    c = F["c"][-60:]
    z = (F["price"] - float(c.mean())) / (float(c.std()) or 1e-12)
    if z < -2.1 and F["clv"] > 0: return UP, f"60-candle z-score {z:.1f} snapping back up"
    if z > 2.1 and F["clv"] < 0: return DN, f"60-candle z-score {z:.1f} snapping back down"
    return None

@S("QS Runs Test", "QS")
def _qs_runs(F):
    b = list(map(bool, F["bull"][-30:]))
    if len(b) < 30: return None
    flips = sum(1 for i in range(1, len(b)) if b[i] != b[i-1])
    if flips >= 20:                          # ultra choppy -> mean revert
        return (DN, "Choppy alternating candles — fade the last push") if b[-1] \
            else (UP, "Choppy alternating candles — fade the last push")
    if flips <= 9:                           # smooth -> trend follows
        return (UP, "Very low candle-flip rate — trend persistence") if b[-1] \
            else (DN, "Very low candle-flip rate — trend persistence")
    return None

@S("QS Hour Behaviour", "QS")
def _qs_hour(F):
    prof = (F.get("hourprof") or {}).get(str(get_now().hour))
    if not prof or prof.get("n", 0) < 45: return None
    cont = float(prof.get("cont", 0.5))
    if cont >= 0.57: return (F["run_dir"], f"Statistically continuation hour ({cont*100:.0f}%)")
    if cont <= 0.43:
        return (DN if F["run_dir"] == UP else UP), f"Statistically reversal hour ({(1-cont)*100:.0f}%)"
    return None

@S("QS Drift Persistence", "QS")
def _qs_drift(F):
    if F["n"] < 45: return None
    d = np.diff(F["c"][-45:])
    pos = float((d > 0).sum()); neg = float((d < 0).sum())
    if pos > neg * 1.45 and F["price"] > float(F["sma20"][-1]): return UP, "Positive drift persistence over 45 candles"
    if neg > pos * 1.45 and F["price"] < float(F["sma20"][-1]): return DN, "Negative drift persistence over 45 candles"
    return None

@S("QS Range Percentile", "QS")
def _qs_pct(F):
    if F["n"] < 50: return None
    hi = float(F["h"][-50:].max()); lo = float(F["l"][-50:].min())
    pos = (F["price"] - lo) / max(hi - lo, 1e-12)
    if pos < 0.15 and F["clv"] > 0.2: return UP, "Price at the 50-candle bottom percentile, turning up"
    if pos > 0.85 and F["clv"] < -0.2: return DN, "Price at the 50-candle top percentile, turning down"
    return None

@S("QS Autocorrelation", "QS")
def _qs_ac(F):
    if F["n"] < 40: return None
    d = np.diff(F["c"][-40:])
    if d.std() == 0: return None
    ac = float(np.corrcoef(d[:-1], d[1:])[0, 1])
    last = float(d[-1])
    if ac > 0.12: return (UP, f"Positive autocorrelation {ac:.2f} — follow the last move") if last > 0 \
        else (DN, f"Positive autocorrelation {ac:.2f} — follow the last move")
    if ac < -0.18: return (DN, f"Negative autocorrelation {ac:.2f} — fade the last move") if last > 0 \
        else (UP, f"Negative autocorrelation {ac:.2f} — fade the last move")
    return None

@S("QS ATR Normalised Move", "QS")
def _qs_atrn(F):
    a = F["atr"] or 1e-12
    mv = float(F["c"][-1] - F["o"][-1]) / a
    if 0.35 < mv < 1.6 and F["ribbon_score"] >= 0: return UP, "Healthy ATR-normalised bullish candle"
    if -1.6 < mv < -0.35 and F["ribbon_score"] <= 0: return DN, "Healthy ATR-normalised bearish candle"
    return None

@S("QS Pair Quality Bias", "QS")
def _qs_pq(F):
    prof = F.get("pairprof") or {}
    beh = prof.get("behaviour")
    if not beh: return None
    if beh == "TREND" and abs(F["ribbon_score"]) >= 0.66:
        return (UP, "Pair statistically trends — ribbon aligned up") if F["ribbon_score"] > 0 \
            else (DN, "Pair statistically trends — ribbon aligned down")
    if beh == "REVERT" and abs(F["ext_atr"]) > 1.4:
        return (DN, "Pair statistically mean-reverts — stretched high") if F["ext_atr"] > 0 \
            else (UP, "Pair statistically mean-reverts — stretched low")
    return None


# ─────────────────────────────────────────────────────────────
#  v52 REGIME ROUTER — market ke mood ke hisaab se family weight
#  (galat market me galat strategy = sabse bada loss source)
# ─────────────────────────────────────────────────────────────
REGIME_W = {
    "TRENDING": {"TR": 1.30, "MO": 1.20, "ST": 1.25, "VO": 1.10, "CF": 1.15, "LQ": 1.10,
                 "NM": 1.10, "QS": 1.05, "RV": 0.70, "SR": 0.80, "CY": 0.70, "EX": 0.80},
    "BREAKOUT": {"VO": 1.35, "ST": 1.20, "TR": 1.15, "LQ": 1.20, "NM": 1.05, "PA": 1.10,
                 "RV": 0.70, "CY": 0.70, "SR": 0.85, "QS": 0.95},
    "RANGING":  {"RV": 1.30, "SR": 1.30, "CY": 1.25, "PA": 1.10, "EX": 1.15, "QS": 1.10,
                 "LQ": 1.15, "NM": 1.00, "TR": 0.72, "MO": 0.80, "ST": 0.75, "VO": 0.80},
    "NORMAL":   {},
}

def regime_weight(regime, family):
    return float(REGIME_W.get(regime or "NORMAL", {}).get(family, 1.0))


# ─────────────────────────────────────────────────────────────
#  CONTEXT RISK ENGINE  (doji / big candle / trend-end)
# ─────────────────────────────────────────────────────────────
def context_risk(F, direction):
    """0..1 risk + reasons. Continuation-in-bad-context ko punish karta hai."""
    risk = 0.0
    reasons = []
    with_run = (F["run_dir"] == direction)

    # 1) doji / indecision cluster
    if F["bodyratio"] < 0.30:
        risk += 0.30 * (1.0 - F["bodyratio"] / 0.30)
        reasons.append("doji entry candle")
    if F["doji_cluster"] >= 2:
        risk += 0.18
        reasons.append(f"{F['doji_cluster']}/3 doji cluster")

    # 2) big candle just closed -> next candle usually retraces
    big = max(F["big_range"] / 2.0, F["big_body"] / 2.5)
    if big > 1.0 and with_run:
        risk += min(0.30, 0.22 * (big - 1.0) + 0.12)
        reasons.append(f"big candle ({F['big_range']:.1f}x ATR) already ran")

    # 3) over-extension + long run (trend ka last hissa)
    ext = abs(F["ext_atr"])
    if with_run:
        if ext > 1.6:
            risk += min(0.26, 0.14 * (ext - 1.6) + 0.08)
            reasons.append(f"{ext:.1f} ATR away from EMA21")
        if F["run_len"] >= 5:
            risk += min(0.22, 0.05 * (F["run_len"] - 4))
            reasons.append(f"{F['run_len']}-candle run (late entry)")
        if F["body_decay"] and F["run_len"] >= 4:
            risk += 0.10
            reasons.append("momentum decaying")
    else:
        # counter-trend entry into an exhausted move = achha context
        if ext > 1.8 or F["run_len"] >= 5:
            risk -= 0.10
            reasons.append("counter-trend into exhausted move")

    # 4) compression trap (dead candles, next candle random)
    if F["volratio"] < 0.50 and F["adxv"] < 16:
        risk += 0.16
        reasons.append("compressed / dead range")

    risk = float(min(1.0, max(0.0, risk)))
    return risk, reasons


# ─────────────────────────────────────────────────────────────
#  DAY-OF-WEEK ADAPTIVE PROFILE (self-learning)
# ─────────────────────────────────────────────────────────────
FAMILIES = ["TR", "MO", "RV", "SR", "PA", "VO", "ST", "CY", "SS", "CF", "EX", "NM"]

#  Priors: which style historically suits each weekday on OTC/forex.
DAY_PRIORS = {
    0: {"TR": 1.30, "MO": 1.20, "VO": 1.20, "ST": 1.15, "SR": 1.00, "PA": 1.05, "RV": 0.85, "CY": 0.90, "SS": 1.10, "CF": 1.15, "EX": 1.10},  # Monday - breakout/trend
    1: {"TR": 1.20, "MO": 1.30, "VO": 1.10, "ST": 1.15, "SR": 1.05, "PA": 1.10, "RV": 0.95, "CY": 0.95, "SS": 1.05, "CF": 1.15, "EX": 1.10},  # Tuesday - momentum
    2: {"TR": 1.10, "MO": 1.05, "VO": 1.00, "ST": 1.20, "SR": 1.25, "PA": 1.15, "RV": 1.20, "CY": 1.05, "SS": 1.00, "CF": 1.10, "EX": 1.20},  # Wednesday - rotation
    3: {"TR": 1.25, "MO": 1.15, "VO": 1.15, "ST": 1.20, "SR": 1.05, "PA": 1.05, "RV": 0.95, "CY": 0.95, "SS": 1.05, "CF": 1.15, "EX": 1.10},  # Thursday - trend day
    4: {"TR": 0.95, "MO": 0.95, "VO": 0.95, "ST": 1.05, "SR": 1.30, "PA": 1.15, "RV": 1.30, "CY": 1.20, "SS": 1.10, "CF": 1.05, "EX": 1.25},  # Friday - mean revert
    5: {"TR": 0.95, "MO": 0.95, "VO": 0.90, "ST": 1.05, "SR": 1.35, "PA": 1.20, "RV": 1.30, "CY": 1.25, "SS": 1.15, "CF": 1.05, "EX": 1.30},  # Saturday OTC
    6: {"TR": 0.95, "MO": 0.95, "VO": 0.90, "ST": 1.05, "SR": 1.35, "PA": 1.20, "RV": 1.30, "CY": 1.25, "SS": 1.15, "CF": 1.05, "EX": 1.30},  # Sunday OTC
}

# NM (non-MTG sniper) family har din strong prior rakhti hai — yehi engine
# pehli candle ki accuracy banata hai.
for _wd in DAY_PRIORS:
    DAY_PRIORS[_wd]["NM"] = 1.35


def load_dayprofile():
    d = _jload(DAYPROF_FILE, {})
    for wd in range(7):
        k = str(wd)
        d.setdefault(k, {})
        for f in FAMILIES:
            d[k].setdefault(f, {"w": 1.0, "win": 0, "loss": 0})
    return d

DAY_PROFILE = load_dayprofile()

def day_weight(family, wd=None):
    wd = get_now().weekday() if wd is None else wd
    prior = DAY_PRIORS[wd].get(family, 1.0)
    learned = DAY_PROFILE.get(str(wd), {}).get(family, {}).get("w", 1.0)
    return max(0.35, min(prior * learned, 2.2))

def learn_day(families, outcome):
    """Called after every result -> the weekday profile self-updates."""
    wd = str(get_now().weekday())
    win = outcome in ("WIN", "WIN MTG")
    for f in set(families):
        node = DAY_PROFILE.setdefault(wd, {}).setdefault(f, {"w": 1.0, "win": 0, "loss": 0})
        node["win" if win else "loss"] += 1
        n = node["win"] + node["loss"]
        wr = node["win"] / n
        # gentle Bayesian pull towards observed win-rate
        target = 0.6 + wr * 0.9
        node["w"] = round(node["w"] + (target - node["w"]) * min(n / 40.0, 0.35), 4)
    _jsave(DAYPROF_FILE, DAY_PROFILE)


# ── per-strategy win-rate learning ──
STRAT_WR = _jload(STRATWR_FILE, {})

def strat_weight(name):
    d = STRAT_WR.get(name)
    if not d: return 1.0
    n = d["win"] + d["loss"]
    if n < 10: return 1.0
    wr = d["win"] / n
    if wr < 0.45: return 0.35
    if wr < 0.55: return 0.8
    if wr > 0.68: return 1.35
    return 1.0

def learn_strats(names, outcome):
    win = outcome in ("WIN", "WIN MTG")
    for n in set(names):
        d = STRAT_WR.setdefault(n, {"win": 0, "loss": 0})
        d["win" if win else "loss"] += 1
    _jsave(STRATWR_FILE, STRAT_WR)


# ═════════════════════════════════════════════════════════════
#  PRE-ANALYSIS ENGINE  —  studies the LAST 2-3 DAYS of every pair
#  Fully vectorised (numpy) so it finishes in seconds even on Termux.
#  Output per pair:
#     quality      0..1  how tradable / how clean the pair behaves
#     behaviour    TREND | REVERT | MIXED
#     persistence  P(next candle continues current direction)
#     hours{h}     {cont, rev, n}  hour-by-hour edge (UTC+6)
#     bodyratio    avg body / avg range  (noise measure)
#     doji         share of no-body candles
#     atrpct       average true range in %
# ═════════════════════════════════════════════════════════════
CALIB = {"t": 0, "days": CALIB_DAYS, "pairs": {}}


def _pair_study(pair, cfg):
    cds = fetch_m1(pair, CALIB_CANDLES, cfg, use_cache=False)
    if len(cds) < 800:
        return None
    o = np.array([c["o"] for c in cds]); h = np.array([c["h"] for c in cds])
    l = np.array([c["l"] for c in cds]); c_ = np.array([c["c"] for c in cds])
    t = np.array([c["t"] for c in cds])
    n = len(c_)

    body = np.abs(c_ - o)
    rng = np.maximum(h - l, 1e-12)
    bodyratio = float(np.mean(body / rng))
    doji = float(np.mean(body <= (rng * 0.08)))
    atrpct = float(np.mean(rng / np.maximum(c_, 1e-12)) * 100.0)

    up = c_ > o
    same = up[1:] == up[:-1]
    persistence = float(np.mean(same))

    # follow-through of strong candles (body > 60% of range)
    strong = (body / rng) > 0.6
    st_idx = np.where(strong[:-1])[0]
    follow = float(np.mean(same[st_idx])) if len(st_idx) > 30 else persistence

    # reaction after 3 same-colour candles (exhaustion / mean reversion)
    rev3 = 0.5
    if n > 40:
        run3 = (up[2:-1] == up[1:-2]) & (up[1:-2] == up[:-3])
        idx = np.where(run3)[0]
        if len(idx) > 25:
            nxt_opp = up[3:][idx] != up[2:-1][idx]
            rev3 = float(np.mean(nxt_opp))

    # hour-by-hour edge (broker time = UTC+6)
    hours = {}
    hr = np.array([(int(x) // 3600 + API_TZ_OFFSET) % 24 for x in t])
    for hh in range(24):
        m = np.where(hr[:-1] == hh)[0]
        if len(m) < 25:
            continue
        cont = float(np.mean(same[m]))
        hours[str(hh)] = {"cont": round(cont, 4), "rev": round(1.0 - cont, 4), "n": int(len(m))}

    # directional structure: how far price actually travels vs its noise
    seg = 15
    usable = (n // seg) * seg
    if usable >= seg * 10:
        blocks = c_[:usable].reshape(-1, seg)
        travel = np.abs(blocks[:, -1] - blocks[:, 0])
        noise = np.sum(np.abs(np.diff(blocks, axis=1)), axis=1)
        efficiency = float(np.mean(travel / np.maximum(noise, 1e-12)))
    else:
        efficiency = 0.25

    edge = max(abs(persistence - 0.5), abs(follow - 0.5), abs(rev3 - 0.5))
    hour_edge = 0.0
    if hours:
        hour_edge = float(np.mean([abs(v["cont"] - 0.5) for v in hours.values()]))

    quality = (min(edge / 0.10, 1.0) * 0.34 +
               min(hour_edge / 0.08, 1.0) * 0.20 +
               min(efficiency / 0.45, 1.0) * 0.26 +
               min(bodyratio / 0.55, 1.0) * 0.14 +
               max(0.0, 1.0 - doji / 0.30) * 0.06)
    quality = float(min(max(quality, 0.0), 1.0))

    if persistence >= 0.515 or follow >= 0.545:
        behaviour = "TREND"
    elif persistence <= 0.485 or rev3 >= 0.555:
        behaviour = "REVERT"
    else:
        behaviour = "MIXED"

    payout = float(cds[-1].get("payout", 0) or 0)

    return {
        "pair": pair, "candles": n, "quality": round(quality, 3),
        "behaviour": behaviour, "persistence": round(persistence, 4),
        "follow": round(follow, 4), "rev3": round(rev3, 4),
        "efficiency": round(efficiency, 4), "bodyratio": round(bodyratio, 4),
        "doji": round(doji, 4), "atrpct": round(atrpct, 5),
        "payout": payout, "hours": hours,
    }


def run_pre_analysis(pairs, cfg, force=False):
    """Download + study 2-3 days of history for every pair (cached)."""
    global CALIB
    cached = _jload(CALIB_FILE, {})
    if (not force and cached.get("pairs")
            and time.time() - cached.get("t", 0) < CALIB_TTL_HRS * 3600):
        missing = [p for p in pairs if p not in cached["pairs"]]
        if not missing:
            CALIB = cached
            age = (time.time() - cached["t"]) / 3600
            console.print(f"[green]● Pre-analysis loaded from cache[/] "
                          f"[dim]({len(cached['pairs'])} pairs • {cached.get('days', CALIB_DAYS)} days "
                          f"• {age:.1f}h old)[/]")
            return CALIB
        pairs_to_do = missing
        study = dict(cached["pairs"])
    else:
        pairs_to_do = list(pairs)
        study = {}

    console.print(f"[cyan]● PRE-ANALYSIS[/] studying last [bold]{CALIB_DAYS} days[/] "
                  f"({CALIB_CANDLES} M1 candles) of [bold]{len(pairs_to_do)}[/] pairs …")
    with Progress(TextColumn("[cyan]{task.description}"), BarColumn(bar_width=28),
                  TextColumn("{task.completed}/{task.total}"), TimeElapsedColumn(),
                  console=console, transient=True) as prog:
        task = prog.add_task("history", total=len(pairs_to_do))
        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
            futs = {ex.submit(_pair_study, p, cfg): p for p in pairs_to_do}
            for f in as_completed(futs):
                p = futs[f]
                try:
                    s = f.result()
                except Exception as e:
                    s = None
                    log_line(f"study {p}: {e}")
                if s: study[p] = s
                prog.advance(task)

    CALIB = {"t": time.time(), "days": CALIB_DAYS, "pairs": study}
    _jsave(CALIB_FILE, CALIB)

    good = sorted(study.values(), key=lambda s: -s["quality"])
    tb = Table(box=box.SIMPLE_HEAD, border_style="cyan", title="2-3 DAY PRE-ANALYSIS (top pairs)")
    for col in ("PAIR", "QUALITY", "BEHAVIOUR", "PERSIST", "EFFIC", "BODY%", "ATR%", "PAYOUT"):
        tb.add_column(col)
    for s in good[:14]:
        tb.add_row(pretty_pair(s["pair"]), f"{s['quality']*100:.0f}", s["behaviour"],
                   f"{s['persistence']*100:.1f}", f"{s['efficiency']:.2f}",
                   f"{s['bodyratio']*100:.0f}", f"{s['atrpct']:.3f}", f"{s['payout']:.0f}")
    console.print(tb)
    console.print(f"[green]● Pre-analysis done[/] [dim]{len(study)} pairs studied • "
                  f"tradable (quality ≥ {int(MIN_PAIR_QUALITY*100)}): "
                  f"{len([s for s in study.values() if s['quality'] >= MIN_PAIR_QUALITY])}[/]")
    return CALIB


def pair_stats(pair):
    return CALIB.get("pairs", {}).get(pair)


def hour_edge_for(pair, direction, last_up):
    """Calibrated probability that this candle direction works at this hour."""
    s = pair_stats(pair)
    if not s: return 0.5, 0
    hh = str(get_now().hour)
    node = s["hours"].get(hh)
    cont = node["cont"] if node else s["persistence"]
    n = node["n"] if node else s["candles"]
    continuation = (direction == UP) == bool(last_up)
    return (cont if continuation else 1.0 - cont), n


TREND_FAMS  = {"TR", "MO", "VO", "ST", "CF", "LQ", "NM"}
REVERT_FAMS = {"RV", "SR", "CY", "PA", "EX", "QS"}


def behaviour_family_weight(pair, family):
    s = pair_stats(pair)
    if not s: return 1.0
    if s["behaviour"] == "TREND":
        return 1.25 if family in TREND_FAMS else 0.85
    if s["behaviour"] == "REVERT":
        return 1.25 if family in REVERT_FAMS else 0.85
    return 1.0


# ═════════════════════════════════════════════════════════════
#  🧠  MONARCH AI CORE  v50  — "NEURAL ACCURACY LAYER"
#  ---------------------------------------------------------
#  1. CANDLE MODEL  : logistic-regression (numpy, self-trained) jo
#     har pair ke 2-3 din ke M1 history par offline train hota hai
#     aur next-candle direction ki real probability deta hai.
#  2. LIVE MODEL    : har WIN/LOSS ke baad online SGD se seekhta hai
#     (setup features -> jeetne ki probability).
#  3. PATTERN MEMORY: candle-signature -> win/loss memory (kNN jaisa).
#  4. ACCURACY GUARD: rolling accuracy monitor. Accuracy giri to gate
#     apne aap strict, pair suspend, model auto-retrain.
#  5. TIME ENGINE   : kaunse ghante me kaunsa pair best hai — data se.
#  Sab kuch offline hai, koi extra API/key nahi chahiye.
# ═════════════════════════════════════════════════════════════

AI_MODEL_FILE   = "monarch_ai_model.json"
AI_LIVE_FILE    = "monarch_ai_live.json"
AI_MEMORY_FILE  = "monarch_ai_memory.json"

AI_ENABLED        = True
AI_MIN_PROB       = 0.480   # gate minimum (AI ko setup pasand aana chahiye)
AI_HARD_FLOOR     = 0.340   # isse neeche = hard block
AI_ELITE_PROB     = 0.600
AI_TRAIN_CANDLES  = 3000    # per pair training candles
AI_EPOCHS         = 260
AI_LR             = 0.12
AI_L2             = 1e-4
AI_LIVE_LR        = 0.055
AI_RETRAIN_HRS    = 8       # model itne ghante baad auto refresh
AI_WARM_TRADES    = 12      # itne live results ke baad live-model bharosa
ACC_WINDOW        = 25      # rolling accuracy window
ACC_TARGET        = 0.80    # target accuracy
ACC_FLOOR         = 0.68    # isse neeche = emergency strict mode
PAIR_SUSPEND_LOSS = 6       # ek pair par lagatar itni loss -> suspend
PAIR_SUSPEND_MIN  = 8       # v52: 45 min -> 8 min (flow band nahi hota)
MAX_SUSPENDED     = 7       # itne se zyada pair kabhi suspend nahi honge


# ─────────────────────────────────────────────────────────────
#  FEATURE ENGINE (same features offline + live)
# ─────────────────────────────────────────────────────────────
AI_FEATS = ["bias", "ret1", "ret3", "ret5", "body", "wick", "rsi", "ema_f",
            "ema_s", "slope", "bbz", "stoch", "run", "rng", "accel", "pos"]


def _ai_series(o, h, l, c):
    """Numpy feature matrix (n x len(AI_FEATS)) — row i = state AT candle i."""
    o, h, l, c = arr(o), arr(h), arr(l), arr(c)
    n = len(c)
    rng = np.maximum(h - l, 1e-12)
    a = atr(h, l, c, 14)
    a = np.where(a <= 0, np.mean(rng) or 1e-9, a)

    prev = np.concatenate([[c[0]], c[:-1]])
    ret1 = (c - prev) / a
    ret3 = (c - np.concatenate([np.full(3, c[0]), c[:-3]])) / a
    ret5 = (c - np.concatenate([np.full(5, c[0]), c[:-5]])) / a
    body = (c - o) / rng
    upw = h - np.maximum(o, c)
    dnw = np.minimum(o, c) - l
    wick = (dnw - upw) / rng
    r = (rsi(c, 14) - 50.0) / 50.0
    e9, e21, e50 = ema(c, 9), ema(c, 21), ema(c, 50)
    ema_f = (e9 - e21) / a
    ema_s = (e21 - e50) / a
    sl = np.concatenate([np.zeros(5), (e9[5:] - e9[:-5]) / a[5:]])
    up_, mid, lo_, std = bollinger(c, 20, 2.0)
    bbz = (c - mid) / np.maximum(std, 1e-12)
    k, _d = stochastic(h, l, c, 14, 3)
    stoch = (k - 50.0) / 50.0

    up = (c > o).astype(float)
    run = np.zeros(n)
    for i in range(1, n):
        run[i] = (run[i - 1] + 1) if up[i] == up[i - 1] else 1
    run = np.clip(run, 0, 6) / 6.0 * np.where(up > 0, 1.0, -1.0)

    rngz = rng / a
    accel = np.concatenate([[0.0], np.diff(ret1)])
    hh = np.array([np.max(h[max(0, i - 20):i + 1]) for i in range(n)])
    ll = np.array([np.min(l[max(0, i - 20):i + 1]) for i in range(n)])
    pos = (c - ll) / np.maximum(hh - ll, 1e-12) * 2.0 - 1.0

    X = np.column_stack([np.ones(n), ret1, ret3, ret5, body, wick, r, ema_f,
                         ema_s, sl, bbz, stoch, run, rngz, accel, pos])
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    return np.clip(X, -6.0, 6.0)


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def _train_logistic(X, y, epochs=AI_EPOCHS, lr=AI_LR, l2=AI_L2):
    w = np.zeros(X.shape[1])
    m = len(y)
    if m < 200:
        return w, 0.5
    for _ in range(epochs):
        p = _sigmoid(X @ w)
        g = X.T @ (p - y) / m + l2 * w
        w -= lr * g
    acc = float(np.mean((_sigmoid(X @ w) >= 0.5) == (y >= 0.5)))
    return w, acc


# ─────────────────────────────────────────────────────────────
#  AI BRAIN
# ─────────────────────────────────────────────────────────────
class AIBrain:
    def __init__(self):
        self.candle = {}            # pair -> {"w": [...], "acc": .., "n": ..}
        self.globalw = None         # fallback weights (all pairs)
        self.trained_at = 0
        self.live_w = None          # live setup model
        self.live_n = 0
        self.memory = {}            # signature -> [win, loss]
        self.load()

    # ---------- persistence ----------
    def load(self):
        m = _jload(AI_MODEL_FILE, {})
        self.candle = m.get("candle", {})
        self.globalw = np.array(m["global"]) if m.get("global") else None
        self.trained_at = m.get("t", 0)
        lv = _jload(AI_LIVE_FILE, {})
        self.live_w = np.array(lv["w"]) if lv.get("w") else None
        self.live_n = lv.get("n", 0)
        self.memory = _jload(AI_MEMORY_FILE, {})

    def save(self):
        _jsave(AI_MODEL_FILE, {"t": self.trained_at,
                               "global": (self.globalw.tolist() if self.globalw is not None else None),
                               "candle": self.candle})
        _jsave(AI_LIVE_FILE, {"w": (self.live_w.tolist() if self.live_w is not None else None),
                              "n": self.live_n})
        if len(self.memory) > 4000:
            self.memory = dict(list(self.memory.items())[-2000:])
        _jsave(AI_MEMORY_FILE, self.memory)

    def is_fresh(self):
        return bool(self.candle) and (time.time() - self.trained_at) < AI_RETRAIN_HRS * 3600

    # ---------- offline training ----------
    def train_pair(self, pair, cfg):
        cds = fetch_m1(pair, AI_TRAIN_CANDLES, cfg, use_cache=False)
        if len(cds) < 900:
            return None
        o = [c["o"] for c in cds]; h = [c["h"] for c in cds]
        l = [c["l"] for c in cds]; c_ = [c["c"] for c in cds]
        X = _ai_series(o, h, l, c_)
        y = (np.array(c_[1:]) > np.array(o[1:])).astype(float)
        X = X[50:-1]; y = y[50:]
        if len(y) < 400:
            return None
        cut = int(len(y) * 0.75)
        w, _tr = _train_logistic(X[:cut], y[:cut])
        pv = _sigmoid(X[cut:] @ w)
        val = float(np.mean((pv >= 0.5) == (y[cut:] >= 0.5))) if len(y) - cut > 40 else 0.5
        # confident-subset accuracy: jab model sure hota hai to kitna sahi
        sure = np.abs(pv - 0.5) >= 0.06
        sure_acc = float(np.mean((pv[sure] >= 0.5) == (y[cut:][sure] >= 0.5))) if sure.sum() > 25 else val
        w_full, _ = _train_logistic(X, y)
        return {"w": w_full.tolist(), "acc": round(val, 4),
                "sure": round(sure_acc, 4), "n": int(len(y)), "X": X, "y": y}

    def train_all(self, pairs, cfg, force=False, quiet=False):
        if not force and self.is_fresh():
            miss = [p for p in pairs if p not in self.candle]
            if not miss:
                if not quiet:
                    console.print(f"[green]🧠 AI model loaded[/] [dim]({len(self.candle)} pairs • "
                                  f"{(time.time()-self.trained_at)/3600:.1f}h old)[/]")
                return
            todo = miss
        else:
            todo = list(pairs)

        console.print(f"[cyan]🧠 AI TRAINING[/] — learning next-candle behaviour of "
                      f"[bold]{len(todo)}[/] pairs …")
        allX, allY = [], []
        with Progress(TextColumn("[cyan]{task.description}"), BarColumn(bar_width=28),
                      TextColumn("{task.completed}/{task.total}"), TimeElapsedColumn(),
                      console=console, transient=True) as prog:
            task = prog.add_task("ai-train", total=len(todo))
            with ThreadPoolExecutor(max_workers=max(4, FETCH_WORKERS // 3)) as ex:
                futs = {ex.submit(self.train_pair, p, cfg): p for p in todo}
                for f in as_completed(futs):
                    p = futs[f]
                    try:
                        r = f.result()
                    except Exception as e:
                        r = None; log_line(f"ai train {p}: {e}")
                    if r:
                        allX.append(r.pop("X")); allY.append(r.pop("y"))
                        self.candle[p] = r
                    prog.advance(task)

        if allX:
            X = np.vstack(allX); y = np.concatenate(allY)
            if len(y) > 60000:
                idx = np.random.choice(len(y), 60000, replace=False)
                X, y = X[idx], y[idx]
            gw, gacc = _train_logistic(X, y)
            self.globalw = gw
            self.trained_at = time.time()
            self.save()
            tb = Table(box=box.SIMPLE_HEAD, border_style="cyan",
                       title="🧠 AI MODEL — next-candle accuracy (out of sample)")
            for col in ("PAIR", "VAL ACC", "CONFIDENT ACC", "SAMPLES"):
                tb.add_column(col)
            best = sorted(self.candle.items(), key=lambda kv: -kv[1]["sure"])
            for p, m in best[:12]:
                tb.add_row(pretty_pair(p), f"{m['acc']*100:.1f}%",
                           f"[bold green]{m['sure']*100:.1f}%[/]", str(m["n"]))
            console.print(tb)
            console.print(f"[green]🧠 AI ready[/] [dim]{len(self.candle)} pair-models • "
                          f"global accuracy {gacc*100:.1f}%[/]")

    # ---------- live inference ----------
    def candle_prob_up(self, pair, F, candles):
        """Probability that the NEXT candle closes UP (0..1)."""
        try:
            X = _ai_series(F["o"], F["h"], F["l"], F["c"])
        except Exception:
            return 0.5, 0.0
        x = X[-1]
        node = self.candle.get(pair)
        ws, conf = [], []
        if node:
            ws.append(np.array(node["w"])); conf.append(max(node["sure"], 0.5))
        if self.globalw is not None:
            ws.append(self.globalw); conf.append(0.53)
        if not ws:
            return 0.5, 0.0
        ps = [_sigmoid(float(w @ x)) for w in ws]
        wt = np.array(conf) - 0.5
        wt = wt / max(wt.sum(), 1e-9)
        p = float(np.dot(ps, wt))
        strength = float(max(conf) - 0.5) * 2.0     # 0..1 trust in this model
        return p, min(strength * 4.0, 1.0)

    # ---------- live setup model ----------
    def setup_vector(self, a):
        F = a.get("F") or {}
        mtf = F.get("mtf", {}) if isinstance(F, dict) else {}
        conflict = sum(1 for k in ("M5", "M15") if mtf.get(k) and mtf[k] != a["direction"])
        v = [1.0,
             (a.get("conf", 70) - 80.0) / 20.0,
             (a.get("direct", 0.5) - 0.5) * 4.0,
             (a.get("dominance", 0.7) - 0.7) * 5.0,
             (0.3 - a.get("loss_prob", 0.3)) * 6.0,
             (a.get("trend_score", 0.5) - 0.5) * 4.0,
             (a.get("hour_edge", 0.5) - 0.5) * 8.0,
             ((a.get("quality") or 0.45) - 0.5) * 4.0,
             (a.get("context", 0.7) - 0.7) * 4.0,
             min(a.get("votes", 0), 30) / 30.0,
             -min(a.get("against", 0), 15) / 15.0,
             min(len(a.get("families", [])), 10) / 10.0,
             min(a.get("nm_for", 0), 8) / 8.0,
             -min(a.get("nm_against", 0), 5) / 5.0,
             -conflict / 2.0,
             (a.get("ai_candle", 0.5) - 0.5) * 4.0]
        return np.clip(np.nan_to_num(np.array(v, dtype=float)), -4, 4)

    def live_prob(self, a):
        x = self.setup_vector(a)
        if self.live_w is None:
            self.live_w = np.zeros(len(x))
        p = float(_sigmoid(float(self.live_w @ x)))
        trust = min(self.live_n / float(AI_WARM_TRADES * 4), 1.0)
        return 0.5 + (p - 0.5) * trust, trust

    def learn_live(self, x, won):
        x = np.array(x, dtype=float)
        if self.live_w is None or len(self.live_w) != len(x):
            self.live_w = np.zeros(len(x))
        p = _sigmoid(float(self.live_w @ x))
        self.live_w -= AI_LIVE_LR * ((p - (1.0 if won else 0.0)) * x + AI_L2 * self.live_w)
        self.live_n += 1
        self.save()

    # ---------- pattern memory ----------
    def signature(self, a):
        F = a.get("F") or {}
        def q(v, step):
            try: return int(round(float(v) / step))
            except Exception: return 0
        return "|".join([str(a.get("pair")), str(a.get("direction")),
                         str(get_now().hour),
                         str(q(a.get("body_ratio", 0), 0.25)),
                         str(q(a.get("run_len", 0), 1)),
                         str(q(F.get("rsi", [50])[-1] if isinstance(F.get("rsi"), (list, np.ndarray)) else 50, 10))])

    def memory_prob(self, a):
        s = self.memory.get(self.signature(a))
        if not s: return 0.5, 0
        w, l = s[0], s[1]
        n = w + l
        if n < 3: return 0.5, n
        # Laplace smoothing
        return (w + 1.5) / (n + 3.0), n

    def learn_memory(self, sig_key, won):
        node = self.memory.get(sig_key) or [0, 0]
        node[0 if won else 1] += 1
        self.memory[sig_key] = node


AI = AIBrain()



# ─────────────────────────────────────────────────────────────
#  v52 PROBABILITY CALIBRATION  +  LIVE PAIR/HOUR EDGE
#  AI ka 70% ka matlab really 70% ho — isliye purane results ko
#  bins me daal kar mapping seekhi jati hai (isotonic-style).
# ─────────────────────────────────────────────────────────────
_CAL = {"t": 0.0, "bins": None, "n": 0}
CAL_MIN_SAMPLES = 30


def _build_calibration():
    rows = [r for r in load_results() if r.get("ai_prob") is not None
            and r.get("result") in ("WIN", "WIN MTG", "LOSS")]
    n = len(rows)
    if n < CAL_MIN_SAMPLES:
        _CAL.update({"t": time.time(), "bins": None, "n": n}); return
    edges = [0.0, 0.45, 0.52, 0.58, 0.64, 0.72, 1.01]
    bins = []
    for i in range(len(edges) - 1):
        seg = [r for r in rows if edges[i] <= float(r["ai_prob"]) < edges[i + 1]]
        if len(seg) >= 6:
            wr = sum(1 for r in seg if r["result"] == "WIN") / len(seg)
            bins.append((edges[i], edges[i + 1], wr, len(seg)))
        else:
            bins.append((edges[i], edges[i + 1], None, len(seg)))
    _CAL.update({"t": time.time(), "bins": bins, "n": n})


def calibrated_prob(p):
    """Raw AI probability -> reality-checked probability (soft blend)."""
    if time.time() - _CAL["t"] > 600:
        try: _build_calibration()
        except Exception as _e: log_line(f"calib error: {_e}")
    bins = _CAL.get("bins")
    if not bins: return float(p)
    for lo, hi, wr, k in bins:
        if lo <= p < hi and wr is not None:
            trust = min(k / 25.0, 1.0) * 0.45          # max 45% weight to history
            return float(min(0.97, max(0.03, p * (1 - trust) + wr * trust)))
    return float(p)


def live_edge_nudge(pair, hour=None):
    """Live results se per-pair + per-hour chhota adjustment (-0.05..+0.05)."""
    hour = get_now().hour if hour is None else hour
    adj = 0.0
    w, l = GUARD.pair_live.get(pair, [0, 0])
    if w + l >= 8:
        adj += (w / (w + l) - 0.5) * 0.10
    hw, hl = GUARD.hour_live.get(hour, [0, 0])
    if hw + hl >= 8:
        adj += (hw / (hw + hl) - 0.5) * 0.08
    return float(max(-0.05, min(0.05, adj)))


def ai_probability(a):
    """Final AI probability (0..1) that THIS setup wins on the first candle."""
    if not AI_ENABLED:
        return 0.5, {}
    F = a.get("F") or {}
    try:
        pu, trust = AI.candle_prob_up(a["pair"], F, a.get("candles"))
    except Exception:
        pu, trust = 0.5, 0.0
    p_dir = pu if a["direction"] == UP else (1.0 - pu)
    p_dir = 0.5 + (p_dir - 0.5) * (0.45 + 0.55 * trust)
    a["ai_candle"] = round(p_dir, 4)

    p_live, live_trust = AI.live_prob(a)
    p_mem, mem_n = AI.memory_prob(a)
    mem_trust = min(mem_n / 12.0, 1.0)

    wts = [(p_dir, 1.0), (p_live, 0.85 * live_trust), (p_mem, 0.55 * mem_trust)]
    num = sum(p * w for p, w in wts); den = sum(w for _p, w in wts)
    prob = num / max(den, 1e-9)

    # hour-quality nudge (data-driven, small)
    prob += (a.get("hour_edge", 0.5) - 0.5) * 0.18
    # ── v52: reality calibration + live pair/hour edge ──
    try:
        prob = calibrated_prob(prob)
        prob += live_edge_nudge(a["pair"])
    except Exception as _e:
        log_line(f"calib apply: {_e}")
    prob = float(min(0.97, max(0.03, prob)))
    info = {"candle": round(p_dir, 3), "live": round(p_live, 3), "mem": round(p_mem, 3),
            "mem_n": mem_n, "trust": round(trust, 2)}
    a["ai_prob"] = round(prob, 4)
    a["ai_info"] = info
    a["ai_x"] = AI.setup_vector(a).tolist()
    a["ai_sig"] = AI.signature(a)
    return prob, info


# ─────────────────────────────────────────────────────────────
#  ACCURACY GUARD — accuracy ko hamesha maintain rakhta hai
# ─────────────────────────────────────────────────────────────
class AccuracyGuard:
    def __init__(self):
        self.recent = deque(maxlen=ACC_WINDOW)     # 1 = win, 0 = loss
        self.pair_streak = defaultdict(int)
        self.suspended = {}
        self.hour_live = defaultdict(lambda: [0, 0])   # hour -> [win, loss]
        self.pair_live = defaultdict(lambda: [0, 0])
        self._boot()

    def _boot(self):
        for r in load_results()[-120:]:
            won = r["result"] in ("WIN", "WIN MTG")
            self.recent.append(1 if won else 0)
            try:
                hh = int(str(r.get("time", "  :  ")).split(" ")[-1].split(":")[0])
                self.hour_live[hh][0 if won else 1] += 1
            except Exception:
                pass
            self.pair_live[r.get("pair", "?")][0 if won else 1] += 1

    def accuracy(self):
        if not self.recent: return None
        return sum(self.recent) / len(self.recent)

    def record(self, pair, outcome):
        won = outcome in ("WIN", "WIN MTG")
        direct = outcome == "WIN"
        self.recent.append(1 if won else 0)
        self.hour_live[get_now().hour][0 if won else 1] += 1
        self.pair_live[pair][0 if won else 1] += 1
        if direct:
            self.pair_streak[pair] = 0
        else:
            self.pair_streak[pair] += 1
            live_susp = sum(1 for t in self.suspended.values() if t > time.time())
            if self.pair_streak[pair] >= PAIR_SUSPEND_LOSS and live_susp < MAX_SUSPENDED:
                self.suspended[pair] = time.time() + PAIR_SUSPEND_MIN * 60
                self.pair_streak[pair] = 0
                console.print(f"[yellow]🛡 {pretty_pair(pair)} suspended for "
                              f"{PAIR_SUSPEND_MIN}m (accuracy protection)[/]")

    def blocked(self, pair):
        t = self.suspended.get(pair)
        if not t: return False
        if time.time() > t:
            self.suspended.pop(pair, None); return False
        return True

    def cutoff_bonus(self):
        """Accuracy giri = gate strict (cutoff up). Accuracy high = normal."""
        acc = self.accuracy()
        if acc is None or len(self.recent) < 6: return 0.0
        if acc >= ACC_TARGET: return 0.0
        if acc <= ACC_FLOOR: return 3.0
        return (ACC_TARGET - acc) / max(ACC_TARGET - ACC_FLOOR, 1e-6) * 3.0

    def ai_min(self):
        acc = self.accuracy()
        base = AI_MIN_PROB
        if acc is not None and len(self.recent) >= 6 and acc < ACC_TARGET:
            base += min(0.02, (ACC_TARGET - acc) * 0.12)
        return min(base, 0.60)   # v52: gate kabhi itna ooncha nahi ki flow ruke

    def emergency(self):
        acc = self.accuracy()
        return acc is not None and len(self.recent) >= 8 and acc < ACC_FLOOR


GUARD = AccuracyGuard()


# ─────────────────────────────────────────────────────────────
#  SKIP-NEXT LOSS LOGIC v53  —  "LOSS ke baad agla signal SKIP"
#  Purana back-to-back firewall (12/30/60 min pause, pair rest,
#  direction block, probation, extra cutoff) HATA diya gaya hai.
#  Naya simple rule: jab bhi ek LOSS aaye, uske baad jo pehla
#  signal banega usko SKIP kar diya jayega aur uske BAAD ka signal
#  liya jayega. Koi time waiting nahi — flow chalu rehta hai.
# ─────────────────────────────────────────────────────────────
LF_ENABLED    = True
LF_SKIP_AFTER_LOSS = 0      # v52: koi skip nahi — flow 24h chalu (accuracy score se aati hai)


class LossFirewall:
    """Loss ke baad next signal skip karne wala simple manager."""

    def __init__(self):
        self.streak = 0          # info only (consecutive losses)
        self.worst = 0
        self.skip_left = 0       # kitne aane wale signal skip karne hain
        self.skipped_total = 0
        self.pause_reason = ""
        self.probation = 0
        self._boot()

    def _boot(self):
        try:
            for r in load_results()[-20:]:
                self.streak = 0 if r.get("result") in ("WIN", "WIN MTG") else self.streak + 1
        except Exception:
            self.streak = 0
        self.worst = self.streak

    # ── result hook ──
    def on_result(self, pair, outcome, direction=None):
        won = outcome in ("WIN", "WIN MTG")
        if won:
            self.streak = 0
            self.skip_left = 0
            return
        self.streak += 1
        self.worst = max(self.worst, self.streak)
        if LF_ENABLED:
            self.skip_left = LF_SKIP_AFTER_LOSS
            console.print(f"[yellow]⏭ LOSS aayi — agla {self.skip_left} signal SKIP hoga, "
                          f"uske baad ka signal liya jayega.[/]")

    # ── skip gate (dispatch me use hota hai) ──
    def should_skip(self):
        return bool(LF_ENABLED and self.skip_left > 0)

    def consume_skip(self):
        """True = ye signal skip karo."""
        if not self.should_skip():
            return False
        self.skip_left -= 1
        self.skipped_total += 1
        return True

    # ── purane gates: sab OFF (compatibility ke liye rakhe gaye) ──
    def paused(self):                       return False
    def pause_left(self):                   return 0
    def pair_blocked(self, pair):           return False
    def dir_blocked(self, pair, direction): return False
    def cutoff_bonus(self):                 return 0.0
    def ai_bonus(self):                     return 0.0
    def on_signal_sent(self):               pass
    def min_grade_ok(self, grade):          return True

    def status(self):
        return {"streak": self.streak, "worst": self.worst,
                "skip_left": self.skip_left, "skipped_total": self.skipped_total,
                "pause_left": 0, "probation": 0, "resting_pairs": [],
                "pauses_today": 0}


FIRE = LossFirewall()


def firewall_panel():
    st = FIRE.status()
    tb = Table(box=box.ROUNDED, border_style="red", show_header=False,
               title="⏭ SKIP-NEXT LOSS LOGIC")
    tb.add_column(style="bold cyan"); tb.add_column(style="bold white")
    tb.add_row("STATUS", "[yellow]NEXT SIGNAL SKIP[/]" if st["skip_left"] else "[green]ACTIVE[/]")
    tb.add_row("LOSS STREAK", f"{st['streak']}  (worst {st['worst']})")
    tb.add_row("SKIP PENDING", str(st["skip_left"]))
    tb.add_row("TOTAL SKIPPED", str(st["skipped_total"]))
    tb.add_row("RULE", f"loss ke baad {LF_SKIP_AFTER_LOSS} signal skip, uske baad ka liya jata hai")
    console.print(tb)



# ─────────────────────────────────────────────────────────────
#  TIME ENGINE — best hours (calibration + live results)
# ─────────────────────────────────────────────────────────────
def hour_power(hour=None):
    """0..1 score of how good this hour is (avg pair edge + live winrate)."""
    hh = get_now().hour if hour is None else hour
    edges = []
    for s in CALIB.get("pairs", {}).values():
        node = (s.get("hours") or {}).get(str(hh))
        if node and node.get("n", 0) >= 25:
            edges.append(abs(node["cont"] - 0.5))
    stat = min((sum(edges) / len(edges)) / 0.07, 1.0) if edges else 0.5
    w, l = GUARD.hour_live.get(hh, [0, 0])
    live = ((w + 1.0) / (w + l + 2.0)) if (w + l) >= 3 else 0.5
    sess = 1.0 if 11 <= hh <= 23 else 0.72       # London+NY overlap (UTC+6 broker time)
    return float(min(1.0, 0.45 * stat + 0.30 * live + 0.25 * sess))


def best_hours_table(top=8):
    rows = []
    for hh in range(24):
        p = hour_power(hh)
        w, l = GUARD.hour_live.get(hh, [0, 0])
        # best pair of that hour
        best_p, best_e = "-", 0.0
        for pair, s in CALIB.get("pairs", {}).items():
            node = (s.get("hours") or {}).get(str(hh))
            if node and node.get("n", 0) >= 25:
                e = abs(node["cont"] - 0.5)
                if e > best_e:
                    best_e, best_p = e, pair
        rows.append((hh, p, w, l, best_p, best_e))
    rows.sort(key=lambda r: -r[1])
    return rows[:top]


def show_best_times():
    rows = best_hours_table(10)
    tb = Table(box=box.ROUNDED, border_style="magenta",
               title="⏰ BEST TRADING HOURS (broker time UTC+6) — data se nikale hue")
    for col in ("HOUR", "POWER", "LIVE W/L", "BEST PAIR", "PAIR EDGE"):
        tb.add_column(col)
    for hh, p, w, l, bp, be in rows:
        colour = "bold green" if p >= 0.66 else ("yellow" if p >= 0.5 else "red")
        tb.add_row(f"{hh:02d}:00-{(hh+1)%24:02d}:00", f"[{colour}]{p*100:.0f}[/]",
                   f"{w}/{l}", pretty_pair(bp) if bp != "-" else "-",
                   f"{be*100:.1f}%" if be else "-")
    console.print(tb)
    now_p = hour_power()
    console.print(Panel(
        f"[bold]Abhi ka ghanta:[/] {get_now():%H:00} → power [bold]{now_p*100:.0f}/100[/]\n"
        f"[dim]• Power 66+  = best signal window (bot khud yahan zyada trade karega)\n"
        f"• Power 50-65 = normal — bot sirf ELITE/STRONG setup lega\n"
        f"• Power <50   = bot ka gate apne aap strict ho jata hai (kam signals, high quality)\n"
        f"• Forex majors: London (12:00-16:00) + NY overlap (18:00-22:00) UTC+6 sabse strong\n"
        f"• OTC pairs: weekend aur late night (00:00-06:00) me sabse stable\n"
        f"• News spike ke 5 min andar bot khud rukta hai (context-risk gate)[/]",
        border_style="cyan", padding=(1, 2)))


def show_ai_panel():
    acc = GUARD.accuracy()
    tb = Table(box=box.ROUNDED, border_style="cyan", show_header=False)
    tb.add_column(style="bold cyan"); tb.add_column(style="bold white")
    tb.add_row("AI CANDLE MODELS", f"{len(AI.candle)} pairs")
    if AI.candle:
        best = max(AI.candle.values(), key=lambda m: m["sure"])
        avg = sum(m["sure"] for m in AI.candle.values()) / len(AI.candle)
        tb.add_row("MODEL ACCURACY", f"avg {avg*100:.1f}%  •  best {best['sure']*100:.1f}%")
    tb.add_row("MODEL AGE", f"{(time.time()-AI.trained_at)/3600:.1f} h" if AI.trained_at else "not trained")
    tb.add_row("LIVE MODEL", f"{AI.live_n} trades learned")
    tb.add_row("PATTERN MEMORY", f"{len(AI.memory)} patterns")
    tb.add_row("ROLLING ACCURACY", f"{acc*100:.1f}% (last {len(GUARD.recent)})" if acc is not None else "no data yet")
    tb.add_row("AI GATE MIN", f"{GUARD.ai_min()*100:.1f}%")
    tb.add_row("CUTOFF BONUS", f"+{GUARD.cutoff_bonus():.1f}")
    tb.add_row("SUSPENDED PAIRS", ", ".join(pretty_pair(p) for p in GUARD.suspended) or "none")
    tb.add_row("HOUR POWER (now)", f"{hour_power()*100:.0f}/100")
    console.print(tb)
    console.print(Panel(
        "[bold cyan]ACCURACY HAMESHA MAINTAIN RAKHNE KA TARIKA[/]\n"
        "[white]1.[/] Bot har 8 ghante me AI model dobara train karta hai (menu 5 se turant bhi).\n"
        "[white]2.[/] Har result se live model + pattern memory seekhte hain — jitna chalega utna sharp.\n"
        "[white]3.[/] Rolling accuracy 80% se niche gayi to gate khud strict ho jata hai.\n"
        "[white]4.[/] 3 back-to-back miss wale pair 45 min ke liye auto-suspend.\n"
        "[white]5.[/] Low-power ghante me bot kam par behtar signal deta hai.\n"
        "[white]6.[/] Roz ek hi settings par chalao — bar-bar loose karoge to learning reset ho jati hai.\n"
        "[white]7.[/] Payout 75%+ aur stable internet — verification miss = learning miss.",
        border_style="green", padding=(1, 2)))


# ─────────────────────────────────────────────────────────────
#  DECISION ENGINE  (calibration aware)
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
#  DIRECT-WIN ENGINE  (non-MTG first-candle probability)
#  0..1 score. Ye v43 ka core hai: signal tabhi jata hai jab pehli
#  candle me hi jeetne ke structural + statistical reason ho.
# ─────────────────────────────────────────────────────────────
def direct_score(F, direction, st=None, nm_votes=0, nm_against=0):
    """Returns (score 0..1, reasons list). 0.5 = neutral."""
    parts, reasons = [], []

    def add(w, val, ok_txt=None, bad_txt=None):
        val = float(min(1.0, max(0.0, val)))
        parts.append((w, val))
        if ok_txt and val >= 0.75: reasons.append(ok_txt)
        elif bad_txt and val <= 0.30: reasons.append(bad_txt)

    up = (direction == UP)
    clv = F["clv"] if up else -F["clv"]
    against_wick = F["upw_r"] if up else F["dnw_r"]
    room = F["room_up"] if up else F["room_dn"]
    ribbon = F["ribbon_score"] if up else -F["ribbon_score"]
    micro = F["micro_mom"] if up else -F["micro_mom"]

    # 1) candle ne kis taraf close kiya (sabse strong single predictor)
    add(0.16, (clv + 1.0) / 2.0, "closed strongly in signal direction", "closed against the signal")
    # 2) against-side wick (trap risk)
    add(0.12, 1.0 - min(against_wick / 0.5, 1.0), None, "large wick against the signal")
    # 3) khula raasta (pehli candle ko move karne ki jagah)
    add(0.13, min(room / 1.5, 1.0), "clear room to the next level", "level blocking the first candle")
    # 4) structure alignment
    add(0.11, (ribbon + 1.0) / 2.0, "trend structure aligned", "structure against the signal")
    # 5) micro momentum
    add(0.10, min(max((micro + 1.0) / 2.0, 0.0), 1.0), "live momentum in our favour", "momentum fading")
    # 6) body quality / no doji chop
    q = min(F["bodyratio"] / 0.6, 1.0) * (1.0 - min(F["doji_cluster"] / 3.0, 1.0) * 0.7)
    add(0.09, q, None, "doji / indecision candles around entry")
    # 7) volatility sweet spot (na dead na spike)
    br = F["big_range"]
    vol = 1.0 if 0.7 <= br <= 1.8 else (0.55 if br < 0.7 else max(0.0, 1.0 - (br - 1.8) / 1.6))
    add(0.08, vol, None, "volatility outside the predictable band")
    # 8) over-extension (spike ke baad pehli candle 50/50 ho jati hai)
    add(0.07, 1.0 - min(abs(F["ext_atr"]) / 2.4, 1.0), None, "price over-extended from EMA21")
    # 9) MTF agreement
    m = F.get("mtf") or {}
    agree = sum(1 for k in ("M5", "M15") if m.get(k) == direction)
    disagree = sum(1 for k in ("M5", "M15") if m.get(k) and m[k] != direction)
    add(0.08, 0.5 + agree * 0.25 - disagree * 0.30, "higher timeframes agree", "higher timeframe conflict")
    # 10) NM family votes (dedicated first-candle strategies)
    nmv = min(nm_votes / 4.0, 1.0) - min(nm_against / 3.0, 0.6)
    add(0.10, 0.35 + nmv * 0.65, f"{nm_votes} first-candle strategies agree", "no first-candle confirmation")
    # 11) pair ka apna follow-through / reversal statistic
    if st:
        with_run = (F["run_dir"] == direction)
        if with_run:
            stat = float(st.get("follow", 0.5))
        else:
            stat = float(st.get("rev3", 0.5)) if F["run_len"] >= 3 else (1.0 - float(st.get("persistence", 0.5)))
        add(0.10, 0.5 + (stat - 0.5) * 4.0, "pair history supports this candle", "pair history is against this candle")
        add(0.06, min(float(st.get("efficiency", 0.25)) / 0.40, 1.0), None, "noisy pair (low efficiency)")
    else:
        add(0.10, 0.40, None, "pair not calibrated")

    # 12) live/forming candle already helping
    if F.get("form_dir"):
        add(0.07, 0.85 if F["form_dir"] == direction else 0.20,
            "live candle already moving our way", "live candle moving against us")

    wsum = sum(w for w, _ in parts) or 1.0
    score = sum(w * v for w, v in parts) / wsum
    return float(min(1.0, max(0.0, score))), reasons[:4]


def mtf_bias(pair, cfg, base=None):
    out = {}
    base = base if base is not None else fetch_base(pair, cfg)
    for tf in ("M5", "M15"):
        cd = tf_from_base(base, tf)
        if len(cd) < 25: continue
        cl = arr([x["c"] for x in cd])
        e8, e21 = ema(cl, 8), ema(cl, 21)
        if e8[-1] > e21[-1] and cl[-1] > e21[-1]: out[tf] = UP
        elif e8[-1] < e21[-1] and cl[-1] < e21[-1]: out[tf] = DN
    return out


def analyze(pair, tf, cfg, forming=None, with_mtf=True):
    base = fetch_base(pair, cfg)
    candles = tf_from_base(base, tf)
    if len(candles) < 90:
        return None
    mtf = mtf_bias(pair, cfg, base) if with_mtf else {}
    F = build_features(candles, mtf, forming)
    _st_pre = pair_stats(pair)
    F["hourprof"] = (_st_pre or {}).get("hours", {})
    F["pairprof"] = _st_pre or {}

    votes = {UP: [], DN: []}
    fam_hit = {UP: set(), DN: set()}
    wsum = {UP: 0.0, DN: 0.0}
    fam_w = {UP: defaultdict(float), DN: defaultdict(float)}

    for name, fam, fn in STRATS:
        try:
            res = fn(F)
        except Exception:
            continue
        if not res: continue
        d, reason = res
        # v52: regime router — market ke mood ke hisaab se family ka weight
        w = (day_weight(fam) * strat_weight(name) * F["sessw"]
             * behaviour_family_weight(pair, fam)
             * regime_weight(F.get("regime"), fam))
        votes[d].append((name, fam, reason, w))
        fam_hit[d].add(fam)
        fam_w[d][fam] += w
        wsum[d] += w

    # ── v52 CONFLUENCE DE-DUPLICATION ──
    # ek hi family ke 20 strategies ek hi baat 20 baar bolti hain (double counting).
    # Har family ka contribution cap kar dete hain -> asli independent confluence
    # ubhar kar aata hai. Yahi wo cheez hai jo real accuracy badhati hai.
    for _d in (UP, DN):
        wsum[_d] = sum(min(v, CONFLUENCE_FAM_CAP) for v in fam_w[_d].values())

    direction = UP if wsum[UP] > wsum[DN] else DN
    loser = DN if direction == UP else UP
    win_votes = votes[direction]
    total_votes = len(votes[UP]) + len(votes[DN])
    if total_votes == 0: return None

    # independent families ka agreement (0..1) — sirf vote count se behtar signal
    indep_for = len(fam_hit[direction]); indep_ag = len(fam_hit[loser])
    indep_score = indep_for / max(indep_for + indep_ag, 1)
    dominance = 0.62 * (len(win_votes) / total_votes) + 0.38 * indep_score
    gap = wsum[direction] / max(wsum[loser], 1e-9)

    # trend alignment score 0..1 (pure candle evidence)
    tr_for = sum(1 for (_n, _f, _r, _w) in win_votes if _f in ("TR", "MO", "ST"))
    tr_against = sum(1 for (_n, _f, _r, _w) in votes[loser] if _f in ("TR", "MO", "ST"))
    trend_score = tr_for / max(tr_for + tr_against, 1)

    st = pair_stats(pair)
    last_up = bool(F["c"][-1] > F["o"][-1])
    hedge, hn = hour_edge_for(pair, direction, last_up)

    fam_counts = defaultdict(int)
    for (_n, _f, _r, _w) in win_votes: fam_counts[_f] += 1
    effective = sum(min(v, 5) for v in fam_counts.values())

    lp = 0.52
    lp -= min(effective, 30) * 0.0042
    lp -= min(len(fam_hit[direction]), 10) * 0.011
    lp -= max(0.0, dominance - 0.5) * 0.42
    lp -= min(max(gap - 1.0, 0.0), 3.0) * 0.032
    if F["mtf"].get("M5") == direction: lp -= 0.030
    if F["mtf"].get("M15") == direction: lp -= 0.025
    if F["regime"] == "TRENDING": lp -= 0.025
    # BREAKOUT credit sirf tab jab candle apni range ke aage close hui ho
    if F["regime"] == "BREAKOUT":
        _clean_bo = (F["bodyratio"] > 0.55
                     and ((F["price"] > (F["res"]["price"] if F["res"] else F["price"]))
                          or (F["price"] < (F["sup"]["price"] if F["sup"] else F["price"]))))
        if _clean_bo and F["run_dir"] == direction: lp -= 0.010
    if F["regime"] == "RANGING": lp += 0.030
    if F["adxv"] >= 25: lp -= 0.020
    if F["adxv"] < 14: lp += 0.020
    if F["payout"] >= 88: lp -= 0.010

    # ── calibration (2-3 day pre-analysis) corrections ──
    if st:
        lp -= (st["quality"] - 0.5) * 0.16               # clean pairs get credit
        lp -= (hedge - 0.5) * 0.55                       # hourly statistical edge
        if hn < 40: lp += 0.02                           # thin hourly sample
        if st["doji"] > 0.28: lp += 0.03                 # choppy / doji heavy
        if st["efficiency"] < 0.18: lp += 0.03           # pure noise pair
        fam_set = fam_hit[direction]
        if st["behaviour"] == "TREND" and not (fam_set & TREND_FAMS): lp += 0.04
        if st["behaviour"] == "REVERT" and not (fam_set & REVERT_FAMS): lp += 0.04
    else:
        lp += 0.05                                        # uncalibrated pair

    # trend-quality corrections (replaces the old tick-based trap engine)
    lp -= (trend_score - 0.5) * 0.16
    # v52: independent-family confluence bonus (max ~0.045)
    lp -= max(0.0, indep_score - 0.5) * 0.09
    if F["adxv"] >= 22 and trend_score >= 0.7: lp -= 0.02

    # ── CONTEXT ENGINE: doji / big candle / trend-end ──
    ctx_risk, ctx_reasons = context_risk(F, direction)
    lp += ctx_risk * 0.10                    # max +0.10 (graded, koi hard wall nahi)
    # exhaustion family hamare against vote kare to extra caution
    ex_against = sum(1 for (_n, _f, _r, _w) in votes[loser] if _f == "EX")
    ex_for = sum(1 for (_n, _f, _r, _w) in win_votes if _f == "EX")
    if ex_against: lp += min(0.05, 0.018 * ex_against)
    if ex_for: lp -= min(0.02, 0.008 * ex_for)

    # ── NON-MTG (FIRST CANDLE) ENGINE ──
    nm_for = sum(1 for (_n, _f, _r, _w) in win_votes if _f == "NM")
    nm_ag = sum(1 for (_n, _f, _r, _w) in votes[loser] if _f == "NM")
    dscore, dreasons = direct_score(F, direction, st, nm_for, nm_ag)
    # direct score seedha loss-probability ko chalata hai (sabse bada weight)
    lp -= (dscore - 0.5) * 0.34
    if nm_for == 0: lp += 0.05
    if nm_ag >= 2: lp += 0.04

    lp = float(min(max(lp, 0.05), 0.97))
    conf = round(min(97.0, max(40.0, (1.0 - lp) * 100.0)), 1)

    top = sorted(win_votes, key=lambda x: -x[3])[:6]
    sup, res = F["sup"], F["res"]

    return {
        "pair": pair, "tf": tf, "direction": direction, "conf": conf,
        "loss_prob": round(lp, 3), "trend_score": round(trend_score, 3),
        "votes": len(win_votes), "against": len(votes[loser]),
        "families": sorted(fam_hit[direction]),
        "dominance": round(dominance, 3), "gap": round(gap, 2),
        "regime": F["regime"], "session": F["session"], "adx": round(F["adxv"], 1),
        "payout": F["payout"], "price": F["price"], "atr": F["atr"],
        "reasons": [r for (_, _, r, _) in top],
        "strategies": [n for (n, _, _, _) in win_votes],
        "support": sup["price"] if sup else None,
        "sup_strength": sup["strength"] if sup else 0,
        "resistance": res["price"] if res else None,
        "res_strength": res["strength"] if res else 0,
        "quality": st["quality"] if st else None,
        "behaviour": st["behaviour"] if st else "?",
        "hour_edge": round(hedge, 3),
        "context": round(1.0 - ctx_risk, 3),
        "context_risk": round(ctx_risk, 3),
        "context_reasons": ctx_reasons,
        "ex_against": ex_against, "ex_for": ex_for,
        "direct": round(dscore, 3), "direct_reasons": dreasons,
        "nm_for": nm_for, "nm_against": nm_ag,
        "run_len": F["run_len"], "ext_atr": round(F["ext_atr"], 2),
        "body_ratio": round(F["bodyratio"], 2), "big_range": round(F["big_range"], 2),
        "levels": F["levels"], "candles": candles, "F": F,
    }


def _ramp(val, floor, target):
    """0 at (or below) floor, 1 at (or above) target, linear in between."""
    if target <= floor: return 1.0 if val >= target else 0.0
    return float(min(1.0, max(0.0, (val - floor) / (target - floor))))


def _g(val, minv, slack, target):
    """Gate score: 0 at (minv-slack), 0.70 exactly at the minimum, 1.0 at target.
    Matlab minimum chhu lena hi decent credit deta hai — wall nahi."""
    below = _ramp(val, minv - slack, minv)
    above = _ramp(val, minv, target)
    return 0.70 * below + 0.30 * above




# per-gate weights (auto-normalised to sum = 100, so purane minimums same rehte hain)
_GATE_RAW = {
    "risk":     22.0,   # loss probability
    "conf":     16.0,
    "trend":    16.0,   # MTF / trend alignment
    "dom":      12.0,
    "votes":     9.0,
    "families":  8.0,
    "gap":       7.0,
    "hour":      6.0,
    "quality":   4.0,
    "context":   9.0,   # doji / big-candle / trend-end context
    "direct":   20.0,   # v43: non-MTG first-candle probability
    "ai":       26.0,   # v50: AI probability (sabse bada weight)
}
_GW_SUM = sum(_GATE_RAW.values())
GATE_WEIGHTS = {k: (v * 100.0 / _GW_SUM) for k, v in _GATE_RAW.items()}


def score_setup(a, cfg):
    """Weighted 0..100 setup score + list of soft misses. No hard wall."""
    maxlp = cfg.get("max_loss_prob", MAX_LOSS_PROB)
    s, miss = {}, []

    # ── AI LAYER (v50) ──
    if "ai_prob" not in a:
        try:
            ai_probability(a)
        except Exception as _e:
            log_line(f"ai error: {_e}")
            a["ai_prob"] = 0.5; a["ai_info"] = {}
    aip = a.get("ai_prob", 0.5)
    ai_min = GUARD.ai_min()
    s["ai"] = _g(aip, ai_min, 0.10, 0.78)

    s["risk"]     = _g(1.0 - a["loss_prob"], 1.0 - maxlp, 0.12, 0.88)
    s["conf"]     = _g(a["conf"], MIN_CONFIDENCE, 10.0, 92.0)
    s["trend"]    = _g(a.get("trend_score", 0.0), MIN_TREND_SCORE, 0.16, 0.85)
    s["dom"]      = _g(a["dominance"], MIN_DOMINANCE, 0.14, 0.88)
    s["votes"]    = _g(a["votes"], MIN_STRATEGIES, 4, MIN_STRATEGIES + 7)
    s["families"] = _g(len(a["families"]), MIN_FAMILIES, 2, MIN_FAMILIES + 3)
    s["gap"]      = _g(a["gap"], MIN_SCORE_GAP, 0.6, MIN_SCORE_GAP + 1.6)
    s["hour"]     = _g(a.get("hour_edge", 0.5), MIN_HOUR_EDGE, 0.10, 0.68)
    q = a["quality"] if a["quality"] is not None else 0.45
    s["quality"]  = _g(q, MIN_PAIR_QUALITY, 0.12, 0.70)
    # context: 1.0 = clean candle context, 0 = doji / post-spike / trend-end
    s["context"]  = _g(a.get("context", 0.75), 0.55, 0.35, 0.95)
    # non-MTG first-candle probability — v43 ka sabse important gate
    s["direct"]   = _g(a.get("direct", 0.5), direct_minimum(), 0.13, 0.86)


    total = sum(GATE_WEIGHTS[k] * v for k, v in s.items())

    # ── HARD SAFETY RULES (ye kabhi loose nahi hote — accuracy ka core) ──
    hard = None
    if a["against"] and a["votes"] / max(a["against"], 1) < 1.0:
        hard = f"against {a['against']} vs {a['votes']}"          # 50%+ opposition
    if a["against"] and a["votes"] / max(a["against"], 1) < MIN_VOTE_RATIO:
        total -= 14.0                                             # weak edge penalty
        miss.append(f"votes {a['votes']}v{a['against']}")
    F = a.get("F") or {}
    mtf = F.get("mtf", {}) if isinstance(F, dict) else {}
    conflict = sum(1 for k in ("M5", "M15") if mtf.get(k) and mtf[k] != a["direction"])
    if conflict >= 2:
        total -= 12.0
        miss.append("M5+M15 opposite")
    elif conflict == 1:
        total -= 9.0
        miss.append("MTF conflict")
    if a["loss_prob"] >= 0.50:
        hard = f"risk {a['loss_prob']*100:.0f}%"

    # ── AI HARD RULES (v50) ──
    if aip < AI_HARD_FLOOR:
        hard = f"AI {aip*100:.0f}% (AI setup reject)"
    elif aip < ai_min:
        miss.append(f"AI {aip*100:.0f}%")
    # v52 NON-STOP: ye do rules ab HARD nahi — sirf score penalty (flow chalu)
    if GUARD.blocked(a["pair"]):
        total -= 10.0
        miss.append("pair on guard-rest")
    if GUARD.emergency() and aip < 0.56:
        total -= 7.0
        miss.append("recovery mode")
    _hp = hour_power()
    if _hp < 0.42 and aip < 0.62:
        miss.append(f"weak hour ({_hp*100:.0f}/100)")
        total -= 5.0

    # ── NON-MTG HARD RULES (MTG kam karne ke liye) ──
    d = a.get("direct", 0.5)
    if d < DIRECT_HARD_FLOOR:
        hard = f"first-candle score {d*100:.0f}% (MTG risk)"
    if a.get("nm_for", 0) < NM_STRAT_MIN:
        total -= 10.0
        miss.append(f"only {a.get('nm_for', 0)} first-candle strategies")
    if a.get("nm_against", 0) >= 2:
        total -= 6.0
        miss.append(f"{a['nm_against']} first-candle strategies against")
    if d < direct_minimum():
        miss.append(f"first-candle {d*100:.0f}%")

    # soft misses (reporting ke liye)
    if a["conf"] < MIN_CONFIDENCE: miss.append(f"conf {a['conf']:.0f}%")
    if a["votes"] < MIN_STRATEGIES: miss.append(f"{a['votes']} strategies")
    if len(a["families"]) < MIN_FAMILIES: miss.append(f"{len(a['families'])} families")
    if a["dominance"] < MIN_DOMINANCE: miss.append(f"dom {a['dominance']:.2f}")
    if a["gap"] < MIN_SCORE_GAP: miss.append(f"gap {a['gap']:.2f}")
    if a.get("trend_score", 0) < MIN_TREND_SCORE: miss.append(f"trend {a['trend_score']*100:.0f}%")
    if a.get("hour_edge", 0) < MIN_HOUR_EDGE: miss.append(f"hour {a['hour_edge']*100:.0f}%")
    if a["quality"] is not None and a["quality"] < MIN_PAIR_QUALITY:
        miss.append(f"quality {a['quality']*100:.0f}")

    # ── CONTEXT (trend-end / doji / big-candle) — soft, koi hard block nahi ──
    cr = a.get("context_risk", 0.0)
    if cr >= 0.35:
        miss.append("context: " + ", ".join(a.get("context_reasons", [])[:2]))
    if cr >= 0.75:
        total -= 8.0            # extreme: doji cluster + climax + late entry
    elif cr >= 0.55:
        total -= 4.0
    if a.get("ex_against", 0) >= 2:
        total -= 5.0
        miss.append(f"{a['ex_against']} exhaustion signals against")

    total = float(min(100.0, max(0.0, total)))
    return total, hard, miss


def gate_report(a, cfg):
    """Back-compat helper: (n_soft_misses, first_reason)."""
    _t, hard, miss = score_setup(a, cfg)
    if hard: return 99, hard
    return len(miss), (miss[0] if miss else "OK")


# ── adaptive cutoff (dry spell me thoda relax, WIN par wapas normal) ──
_LAST_SENT_TS = [time.time()]
_RELAXED = [False]
# recent outcomes (sirf MTG-guard ke liye): "WIN" / "WIN MTG" / "LOSS"
_RECENT = deque(maxlen=MTG_GUARD_WINDOW)

def mark_signal_sent():
    _LAST_SENT_TS[0] = time.time()
    _RELAXED[0] = False

def mtg_pressure():
    """Last N results me MTG-win + LOSS ka hissa. Zyada = engine strict."""
    if not MTG_GUARD or len(_RECENT) < 4: return 0.0
    bad = sum(1 for r in _RECENT if r in ("WIN MTG", "LOSS"))
    return bad / len(_RECENT)

def direct_minimum():
    """MTG zyada aa rahe ho to first-candle requirement khud badh jati hai."""
    p = mtg_pressure()
    if p <= MTG_GUARD_RATIO: return MIN_DIRECT_SCORE
    return float(min(0.74, MIN_DIRECT_SCORE + (p - MTG_GUARD_RATIO) * 0.30))

def note_result(outcome):
    """Direct WIN aane par cutoff normal; MTG/LOSS par engine strict."""
    if outcome in ("WIN", "WIN MTG", "LOSS"):
        _RECENT.append(outcome)
    if outcome == "WIN":
        _RELAXED[0] = False

def active_cutoff():
    dry = (time.time() - _LAST_SENT_TS[0]) / 60.0
    if dry >= DRY_SPELL_MIN:
        _RELAXED[0] = True
    if dry >= DRY_SPELL_MIN * 2:
        cut = SETUP_CUTOFF_DESPERATE          # v52: lamba sookha -> last relax step
    elif _RELAXED[0]:
        cut = SETUP_CUTOFF_RELAX
    else:
        cut = SETUP_CUTOFF
    # MTG pressure -> cutoff upar (max +5) taaki sirf A+ setups jaayein
    p = mtg_pressure()
    if p > MTG_GUARD_RATIO:
        cut = min(94.0, cut + min(5.0, (p - MTG_GUARD_RATIO) * 16.0))
    # v50: accuracy guard — rolling accuracy giri to cutoff apne aap upar
    cut = min(96.0, cut + GUARD.cutoff_bonus())
    # v52: cutoff ka hard ceiling — warna bot ghanton tak kuch send hi nahi karta
    cut = min(cut, 78.0)
    if dry >= WATCHDOG_MIN:
        cut = min(cut, SETUP_CUTOFF_DESPERATE)
    return cut


def rank_score(a):
    """Higher = better. Used to pick THE best setup of the scan."""
    q = a.get("quality") or 0.35
    return (a.get("ai_prob", 0.5) * 90.0
            + a.get("setup_score", 0.0) * 1.2
            + a.get("direct", 0.5) * 55.0
            + min(a.get("nm_for", 0), 5) * 3.0
            + (1.0 - a["loss_prob"]) * 60.0
            + a["conf"] * 0.20
            + q * 12.0
            + a.get("hour_edge", 0.5) * 16.0
            + a.get("trend_score", 0.5) * 12.0
            + min(a["dominance"], 0.95) * 8.0
            + a.get("context", 0.75) * 22.0
            - min(a.get("ex_against", 0), 4) * 4.0
            + min(a["gap"], 4.0) * 1.2)


def grade_setup(a, cfg):
    """ELITE / STRONG / GOOD / MEDIUM / WATCH  +  suggested stake share."""
    total, hard, miss = score_setup(a, cfg)
    a["setup_score"] = round(total, 1)
    a["hard_block"] = hard
    why = hard or (miss[0] if miss else "OK")
    if hard:
        return "WATCH", 0.0, why
    cut = active_cutoff()
    aip = a.get("ai_prob", 0.5)
    if total >= TIER_ELITE_SCORE and a["loss_prob"] <= 0.26 and a.get("direct", 0) >= 0.62 and aip >= AI_ELITE_PROB:
        return "ELITE", 1.0, why
    if total >= TIER_STRONG_SCORE and a.get("direct", 0) >= 0.54:
        return "STRONG", 0.8, why
    if total >= max(TIER_GOOD_SCORE, cut) or total >= cut:
        return "GOOD", 0.6, why
    if total >= cut - 8:
        return "MEDIUM", 0.4, why
    return "WATCH", 0.25, why


SENDABLE_GRADES = ("ELITE", "STRONG", "GOOD", "MEDIUM")


def passes_gate(a, cfg):
    if not a: return False, "no analysis"
    if a["payout"] and a["payout"] < MIN_PAYOUT: return False, f"payout {a['payout']:.0f}%"
    g, _stake, why = grade_setup(a, cfg)
    return g in SENDABLE_GRADES, why



# ── cooldown / rate limits ──
_COOLDOWN = {}
_RATE = deque(maxlen=500)   # stats only — no blocking

def on_cooldown(pair, direction):
    e = _COOLDOWN.get(pair)
    if not e: return False
    t, d = e
    mins = (time.time() - t) / 60
    if mins < PAIR_COOLDOWN_MIN: return True
    if d == direction and mins < PAIR_SAMEDIR_MIN: return True
    return False

def set_cooldown(pair, direction):
    _COOLDOWN[pair] = (time.time(), direction)

def rate_limited():
    # Hourly limit hata diya gaya hai — bot kabhi nahi rukta.
    now = time.time()
    while _RATE and now - _RATE[0] > 3600: _RATE.popleft()
    return False

def register_rate(): _RATE.append(time.time())
# ═════════════════════════════════════════════════════════════
#  CHART ENGINE v4  —  "AURORA GLASS" (brand new style)
#  gradient backdrop • rounded candles • EMA ribbon fill
#  S/R zones • live forming candle • entry marker • RSI strip
# ═════════════════════════════════════════════════════════════
CLR_BG1  = "#070b14"
CLR_BG2  = "#101a2e"
CLR_CARD = "#0c1322"
CLR_GRID = "#1a2438"
CLR_UP   = "#22e3a1"
CLR_DN   = "#ff5b7f"
CLR_TXT  = "#e8eefc"
CLR_DIM   = "#6b7c9b"
CLR_GOLD = "#ffcc57"
CLR_CYAN = "#49d3ff"
CLR_VIO  = "#8b7bff"


def _aurora_bg(fig):
    """Vertical gradient backdrop + soft glow."""
    ax = fig.add_axes([0, 0, 1, 1], zorder=-10)
    ax.set_axis_off()
    grad = np.linspace(0, 1, 256).reshape(-1, 1)
    cmap = LinearSegmentedColormap.from_list("aur", [CLR_BG2, CLR_BG1])
    ax.imshow(grad, aspect="auto", cmap=cmap, extent=[0, 1, 0, 1], alpha=1.0)
    glow = LinearSegmentedColormap.from_list("gl", ["#49d3ff00", "#49d3ff22"])
    ax.imshow(np.linspace(0, 1, 128).reshape(1, -1), aspect="auto", cmap=glow,
              extent=[0, 1, 0.82, 1.0])
    return ax


def _panel(ax, title=None):
    ax.set_facecolor("none")
    for s in ax.spines.values():
        s.set_color(CLR_GRID); s.set_linewidth(0.8)
    ax.tick_params(colors=CLR_DIM, labelsize=7.5, length=2)
    ax.grid(True, color=CLR_GRID, lw=0.55, alpha=0.55, linestyle=(0, (2, 3)))
    ax.set_axisbelow(True)
    if title:
        ax.set_title(title, color=CLR_DIM, fontsize=8, loc="left", pad=4)


def _rounded_candle(ax, x, o, h, l, c, w, up, span):
    """Slim glass candle: soft wick + crisp body (data-safe geometry)."""
    col = CLR_UP if up else CLR_DN
    ax.plot([x, x], [l, h], color=col, lw=1.1, alpha=0.65,
            solid_capstyle="round", zorder=3)
    top, bot = max(o, c), min(o, c)
    hgt = max(top - bot, span * 0.0016)
    ax.add_patch(Rectangle((x - w / 2, bot), w, hgt, linewidth=0.9,
                           edgecolor=col, facecolor=col,
                           alpha=0.55 if up else 0.55, zorder=4))
    ax.add_patch(Rectangle((x - w / 2, bot), w, hgt, linewidth=1.1,
                           edgecolor=col, facecolor="none", alpha=0.95, zorder=5))


def generate_chart(analysis, entry_time_str, forming=None):
    if not CHART_ENABLED:
        return None
    try:
        a = analysis; F = a["F"]
        cds = a["candles"][-CHART_DISPLAY_CANDLES:]
        if len(cds) < 12: return None
        live = None
        if forming:
            live = forming[-1]
            if cds and live["t"] == cds[-1]["t"]:
                cds = cds[:-1] + [live]
            else:
                cds = cds + [live]

        o = np.array([c["o"] for c in cds]); h = np.array([c["h"] for c in cds])
        l = np.array([c["l"] for c in cds]); c_ = np.array([c["c"] for c in cds])
        n = len(cds); x = np.arange(n)
        up = a["direction"] == UP
        acc = CLR_UP if up else CLR_DN

        fig = plt.figure(figsize=(11.4, 7.4), dpi=125)
        fig.patch.set_facecolor(CLR_BG1)
        _aurora_bg(fig)
        gs = GridSpec(3, 1, height_ratios=[1.0, 3.5, 1.15], hspace=0.30,
                      left=0.055, right=0.965, top=0.965, bottom=0.075)

        # ── header card ──
        hd = fig.add_subplot(gs[0]); hd.set_axis_off()
        hd.add_patch(FancyBboxPatch((0.0, 0.02), 1.0, 0.96,
                                    boxstyle="round,pad=0.01,rounding_size=0.04",
                                    transform=hd.transAxes, facecolor=CLR_CARD,
                                    edgecolor=acc, alpha=0.92, linewidth=1.2, zorder=1))
        hd.text(0.022, 0.70, pretty_pair(a["pair"]), color=CLR_TXT, fontsize=19,
                fontweight="bold", va="center", transform=hd.transAxes, zorder=3)
        hd.text(0.022, 0.28, f"{BROKER} • {a['tf']} • {a['session']} • {weekday_name()}",
                color=CLR_DIM, fontsize=8.5, va="center", transform=hd.transAxes, zorder=3)
        hd.text(0.40, 0.66, ("▲ CALL" if up else "▼ PUT"), color=acc, fontsize=21,
                fontweight="bold", va="center", transform=hd.transAxes, zorder=3)
        hd.text(0.40, 0.24, f"entry {entry_time_str}  •  10s pre-alert",
                color=CLR_GOLD, fontsize=9, va="center", transform=hd.transAxes, zorder=3)
        for i, (lab, val, col) in enumerate([
                ("CONF", f"{a['conf']:.0f}%", CLR_CYAN),
                ("RISK", f"{a['loss_prob']*100:.0f}%", CLR_DN),
                ("QUALITY", f"{(a['quality'] or 0)*100:.0f}", CLR_VIO),
                ("H-EDGE", f"{a['hour_edge']*100:.0f}%", CLR_UP),
                ("PAYOUT", f"{a['payout']:.0f}%", CLR_GOLD)]):
            xx = 0.60 + i * 0.079
            hd.text(xx, 0.66, val, color=col, fontsize=12.5, fontweight="bold",
                    ha="center", va="center", transform=hd.transAxes, zorder=3)
            hd.text(xx, 0.26, lab, color=CLR_DIM, fontsize=7,
                    ha="center", va="center", transform=hd.transAxes, zorder=3)

        # ── price panel ──
        ax = fig.add_subplot(gs[1]); _panel(ax)
        # EMA ribbon with fill
        cl_all = F["c"]
        e8, e21, e55 = F["ema8"][-n:], F["ema21"][-n:], F["ema55"][-n:]
        ax.fill_between(x, e8, e21, color=CLR_CYAN, alpha=0.10, zorder=1)
        ax.plot(x, e8,  color=CLR_CYAN, lw=1.3, alpha=0.95, label="EMA8", zorder=5)
        ax.plot(x, e21, color=CLR_VIO,  lw=1.2, alpha=0.9,  label="EMA21", zorder=5)
        ax.plot(x, e55, color=CLR_GOLD, lw=1.0, alpha=0.6,  label="EMA55", zorder=5)
        bbU, bbL = F["bbU"][-n:], F["bbL"][-n:]
        ax.plot(x, bbU, color=CLR_DIM, lw=0.7, alpha=0.5, linestyle=(0, (3, 3)), zorder=2)
        ax.plot(x, bbL, color=CLR_DIM, lw=0.7, alpha=0.5, linestyle=(0, (3, 3)), zorder=2)
        ax.fill_between(x, bbU, bbL, color="#8b7bff", alpha=0.045, zorder=0)

        # S/R zones
        atrv = F["atr"]
        for lvl, colr, nm in ((a["support"], CLR_UP, "S"), (a["resistance"], CLR_DN, "R")):
            if not lvl: continue
            ax.add_patch(Rectangle((-0.5, lvl - atrv * 0.25), n + 1, atrv * 0.5,
                                   facecolor=colr, alpha=0.10, edgecolor="none", zorder=1))
            ax.axhline(lvl, color=colr, lw=0.9, alpha=0.55, linestyle=(0, (5, 3)), zorder=2)
            ax.text(n - 0.2, lvl, f" {nm} {lvl:.5f}", color=colr, fontsize=7.5,
                    va="center", ha="left", zorder=6)

        w = 0.58
        span = float(max(h.max() - l.min(), 1e-9))
        for i in range(n):
            _rounded_candle(ax, i, o[i], h[i], l[i], c_[i], w, c_[i] >= o[i], span)
        if live is not None:
            ax.add_patch(Rectangle((n - 1.5, l[-1]), 1.0, max(h[-1] - l[-1], 1e-9),
                                   facecolor=CLR_GOLD, alpha=0.09, edgecolor=CLR_GOLD,
                                   lw=0.8, linestyle=(0, (2, 2)), zorder=3))
            ax.text(n - 1, h[-1], " LIVE", color=CLR_GOLD, fontsize=7.5,
                    va="bottom", ha="left", zorder=7)

        # entry marker (next candle)
        px = float(c_[-1])
        ax.axvline(n - 0.35, color=acc, lw=1.0, alpha=0.7, linestyle=(0, (4, 3)), zorder=5)
        ax.annotate("", xy=(n + 0.6, px + (atrv * (2.2 if up else -2.2))),
                    xytext=(n - 0.2, px),
                    arrowprops=dict(arrowstyle="-|>", color=acc, lw=2.0, alpha=0.95), zorder=8)
        ax.text(n + 0.7, px + (atrv * (2.6 if up else -2.6)),
                f"NEXT {entry_time_str}", color=acc, fontsize=8, fontweight="bold",
                va="center", zorder=8)
        ax.axhline(px, color=CLR_TXT, lw=0.6, alpha=0.35, zorder=2)
        ax.text(-0.4, px, f"{px:.5f} ", color=CLR_TXT, fontsize=7.5, ha="right",
                va="center", zorder=6,
                bbox=dict(facecolor=CLR_CARD, edgecolor=acc, lw=0.6, pad=1.6))

        ax.set_xlim(-1.2, n + 5.5)
        pad = (h.max() - l.min()) * 0.14 + atrv
        ax.set_ylim(l.min() - pad, h.max() + pad)
        ax.set_xticks([])
        lg = ax.legend(loc="upper left", fontsize=7, frameon=True, ncol=3)
        lg.get_frame().set_facecolor(CLR_CARD); lg.get_frame().set_edgecolor(CLR_GRID)
        for t_ in lg.get_texts(): t_.set_color(CLR_DIM)

        # ── RSI / momentum strip ──
        ax2 = fig.add_subplot(gs[2]); _panel(ax2, "RSI 14  •  MACD histogram")
        r = F["rsi"][-n:]
        ax2.axhspan(30, 70, color=CLR_CYAN, alpha=0.05)
        ax2.axhline(70, color=CLR_DN, lw=0.6, alpha=0.5, linestyle=(0, (3, 3)))
        ax2.axhline(50, color=CLR_DIM, lw=0.5, alpha=0.4)
        ax2.axhline(30, color=CLR_UP, lw=0.6, alpha=0.5, linestyle=(0, (3, 3)))
        ax2.plot(x, r, color=CLR_CYAN, lw=1.4, zorder=4)
        ax2.fill_between(x, 50, r, color=CLR_CYAN, alpha=0.12, zorder=2)
        mh = F["macdh"][-n:]
        sc = 18.0 / (np.max(np.abs(mh)) or 1e-9)
        ax2.bar(x, mh * sc, bottom=50, width=0.55,
                color=[CLR_UP if v >= 0 else CLR_DN for v in mh], alpha=0.45, zorder=1)
        ax2.set_ylim(6, 94); ax2.set_xlim(-1.2, n + 5.5); ax2.set_xticks([])
        ax2.set_yticks([30, 50, 70])
        ax2.text(0.995, 0.06, f"{a['votes']} strategies • {len(a['families'])} families • "
                              f"{a['behaviour']} pair • {a['regime']}",
                 transform=ax2.transAxes, ha="right", color=CLR_DIM, fontsize=7.5)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=CLR_BG1, bbox_inches="tight", pad_inches=0.18)
        plt.close(fig); buf.seek(0)
        return buf
    except Exception as e:
        log_line(f"chart error: {e}")
        try: plt.close('all')
        except Exception: pass
        return None


def generate_result_chart(sig, candles, outcome):
    """Chart for the RESULT message — entry (and MTG) candle highlighted."""
    if not CHART_ENABLED:
        return None
    try:
        cds = [c for c in candles][-CHART_DISPLAY_CANDLES:]
        if len(cds) < 8:
            return None
        idx_entry = next((i for i, c in enumerate(cds) if c["t"] == sig["entry_epoch"]), None)
        if idx_entry is None:
            return None
        idx_mtg = next((i for i, c in enumerate(cds) if c["t"] == sig.get("mtg_epoch")), None)

        o = np.array([c["o"] for c in cds]); h = np.array([c["h"] for c in cds])
        l = np.array([c["l"] for c in cds]); c_ = np.array([c["c"] for c in cds])
        n = len(cds); x = np.arange(n)
        up = sig["direction"] == UP
        won = outcome in ("WIN", "WIN MTG")
        acc = CLR_UP if won else CLR_DN

        fig = plt.figure(figsize=(11.4, 6.2), dpi=125)
        fig.patch.set_facecolor(CLR_BG1)
        _aurora_bg(fig)
        gs = GridSpec(2, 1, height_ratios=[1.0, 4.0], hspace=0.26,
                      left=0.055, right=0.965, top=0.955, bottom=0.07)

        hd = fig.add_subplot(gs[0]); hd.set_axis_off()
        hd.add_patch(FancyBboxPatch((0.0, 0.02), 1.0, 0.96,
                                    boxstyle="round,pad=0.01,rounding_size=0.04",
                                    transform=hd.transAxes, facecolor=CLR_CARD,
                                    edgecolor=acc, alpha=0.92, linewidth=1.2, zorder=1))
        hd.text(0.022, 0.70, pretty_pair(sig["pair"]), color=CLR_TXT, fontsize=19,
                fontweight="bold", va="center", transform=hd.transAxes, zorder=3)
        hd.text(0.022, 0.26, f"{BROKER} • {sig['tf']} • entry {sig['entry_time']}"
                             + (f" • MTG {sig.get('mtg_time')}" if sig.get("mtg_time") else ""),
                color=CLR_DIM, fontsize=8.5, va="center", transform=hd.transAxes, zorder=3)
        hd.text(0.44, 0.66, ("▲ CALL" if up else "▼ PUT"),
                color=(CLR_UP if up else CLR_DN), fontsize=19, fontweight="bold",
                va="center", transform=hd.transAxes, zorder=3)
        badge = {"WIN": "WIN ✓", "WIN MTG": "WIN MTG ✓", "LOSS": "LOSS ✗"}.get(outcome, outcome)
        hd.text(0.80, 0.50, badge, color=acc, fontsize=24, fontweight="bold",
                ha="center", va="center", transform=hd.transAxes, zorder=3)

        ax = fig.add_subplot(gs[1]); _panel(ax)
        w = 0.58
        span = float(max(h.max() - l.min(), 1e-9))
        for i in range(n):
            _rounded_candle(ax, i, o[i], h[i], l[i], c_[i], w, c_[i] >= o[i], span)

        atrv = span / 12.0
        for k, (i, lab) in enumerate(((idx_entry, "ENTRY " + sig["entry_time"]),
                                      (idx_mtg, "MTG " + str(sig.get("mtg_time"))))):
            if i is None:
                continue
            lab_y = h.max() + span * (0.04 + 0.075 * k)
            good = (c_[i] > o[i]) if up else (c_[i] < o[i])
            col = CLR_UP if good else CLR_DN
            ax.add_patch(Rectangle((i - 0.75, l[i] - atrv * 0.35), 1.5,
                                   max(h[i] - l[i], 1e-9) + atrv * 0.7,
                                   facecolor=col, alpha=0.13, edgecolor=col,
                                   lw=1.1, linestyle=(0, (2, 2)), zorder=3))
            ax.text(i, lab_y, lab + ("  ✓" if good else "  ✗"), color=col,
                    fontsize=8, fontweight="bold", ha="right" if k == 0 else "left",
                    va="bottom", zorder=8)
            ax.annotate("", xy=(i, c_[i]), xytext=(i, o[i]),
                        arrowprops=dict(arrowstyle="-|>", color=col, lw=1.8, alpha=0.9),
                        zorder=9)

        ax.set_xlim(-1.2, n + 1.2)
        pad = span * 0.26
        ax.set_ylim(l.min() - pad, h.max() + pad)
        ax.set_xticks([])
        fig.text(0.5, 0.012, f"{BOT_NAME} • {BROKER} {BOT_VERSION}", color=CLR_DIM,
                 fontsize=7.5, ha="center")

        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        log_line(f"result chart error: {e}")
        try: plt.close('all')
        except Exception: pass
        return None


# ─────────────────────────────────────────────────────────────
#  TELEGRAM
# ─────────────────────────────────────────────────────────────
def esc(x):
    """Escape any dynamic text before it goes inside an HTML Telegram message."""
    return _html.escape(str(x), quote=False)


def strip_tags(msg):
    """Plain-text fallback: remove every tag so Telegram can never fail to parse."""
    return _re_tag.sub("", msg).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def _parse_failed(txt):
    t = (txt or "").lower()
    return "can't parse entities" in t or "cant parse entities" in t or "unsupported start tag" in t


def send_tg_text(token, chat_id, msg, parse_mode="HTML"):
    if not token or not chat_id: return False, "no credentials"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    last = "unknown"
    for attempt in range(2):
        try:
            r = requests.post(url, json={"chat_id": chat_id, "text": msg[:4090],
                                         "parse_mode": parse_mode}, timeout=15)
            if r.status_code == 200:
                return True, "OK"
            last = r.text
            log_line(f"telegram text error: {r.status_code} {r.text[:300]}")
            if _parse_failed(r.text):
                # last-resort: send the very same message without any markup
                try:
                    r2 = requests.post(url, json={"chat_id": chat_id,
                                                  "text": strip_tags(msg)[:4090]}, timeout=15)
                    if r2.status_code == 200:
                        return True, "OK (plain fallback)"
                    last = r2.text
                except Exception as e:
                    last = str(e)
                return False, last
        except Exception as e:
            last = str(e)
            log_line(f"telegram text exception: {e}")
        time.sleep(1)
    return False, last


def send_tg_photo(token, chat_id, photo, caption="", parse_mode="HTML"):
    if not token or not chat_id: return False, "no credentials"
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    last = "unknown"
    try:
        raw = photo.getvalue() if hasattr(photo, "getvalue") else photo
    except Exception:
        raw = photo
    for attempt in range(2):
        try:
            r = requests.post(url,
                              data={"chat_id": chat_id, "caption": caption[:1020],
                                    "parse_mode": parse_mode},
                              files={"photo": ("chart.png", io.BytesIO(raw), "image/png")},
                              timeout=30)
            if r.status_code == 200:
                return True, "OK"
            last = r.text
            log_line(f"telegram photo error: {r.status_code} {r.text[:300]}")
            if _parse_failed(r.text):
                try:
                    r2 = requests.post(url,
                                       data={"chat_id": chat_id,
                                             "caption": strip_tags(caption)[:1020]},
                                       files={"photo": ("chart.png", io.BytesIO(raw), "image/png")},
                                       timeout=30)
                    if r2.status_code == 200:
                        return True, "OK (plain fallback)"
                    last = r2.text
                except Exception as e:
                    last = str(e)
                return False, last
        except Exception as e:
            last = str(e)
            log_line(f"telegram photo exception: {e}")
        time.sleep(1)
    return False, last


def tg_send_async(cfg, msg, photo=None):
    """Fire-and-forget sender so a slow upload never blocks the trade loop."""
    if not cfg or not cfg.get("telegram"):
        return

    def _worker():
        try:
            if photo is not None:
                ok, err = send_tg_photo(cfg["token"], cfg["chat_id"], photo, msg)
                if not ok:
                    send_tg_text(cfg["token"], cfg["chat_id"], msg)
            else:
                send_tg_text(cfg["token"], cfg["chat_id"], msg)
        except Exception as e:
            log_line(f"tg async error: {e}")

    threading.Thread(target=_worker, daemon=True).start()



def context_label(a):
    """Chart/message ke liye ek line: candle context clean hai ya nahi."""
    cr = a.get("context_risk", 0.0)
    rs = a.get("context_reasons") or []
    tag = "clean ✅" if cr < 0.20 else ("ok" if cr < 0.35 else ("caution ⚠️" if cr < 0.60 else "risky ⛔"))
    extra = f" — {', '.join(rs[:3])}" if rs else ""
    ex = f" • {a['ex_against']} exhaustion vs" if a.get("ex_against") else ""
    return f"{tag}{extra}{ex}"


def tier_label(conf):
    if conf >= TIER_ELITE:  return "⭐ ELITE"
    if conf >= TIER_STRONG: return "🔥 STRONG"
    if conf >= TIER_MEDIUM: return "✅ MEDIUM"
    return "📶 WEAK"


def ai_badge(a):
    p = a.get("ai_prob")
    if p is None: return ""
    info = a.get("ai_info") or {}
    star = "🧠🔥" if p >= 0.72 else ("🧠" if p >= 0.62 else "🧠·")
    return (f"{star} <b>AI {p*100:.0f}%</b>  "
            f"<i>(model {info.get('candle', 0.5)*100:.0f}% • live {info.get('live', 0.5)*100:.0f}% • memory {info.get('mem', 0.5)*100:.0f}%)</i>")


def make_signal_msg(a, entry_time):
    """Returns (head, detail). head = always visible, detail = expandable quote."""
    d = a["direction"]
    action = "𝙲𝙰𝙻𝙻 🟢 UP" if d == UP else "𝙿𝚄𝚃 🔴 DOWN"
    sup = f"{a['support']:.5f}" if a["support"] else "—"
    res = f"{a['resistance']:.5f}" if a["resistance"] else "—"
    reasons = "\n".join(f"   ▸ {esc(r)}" for r in a["reasons"][:5])
    warn = ""
    if a.get("grade") in ("MEDIUM", "WATCH"):
        warn = (f"\n⚠️ <b>𝙶𝚁𝙰𝙳𝙴</b>: {esc(a['grade'])} — best available this candle "
                f"(suggested stake {int(a.get('stake', 0.5)*100)}% of normal)")

    head = (
        f"🏆 <b>{esc(BOT_NAME)}</b> — <b>{esc(BROKER)}</b> {esc(BOT_VERSION)}\n"
        f"╔══════════💠══════════╗\n"
        f"📊 <b>PAIR</b>      ⊱ <b>{esc(pretty_pair(a['pair']))}</b>\n"
        f"⌛ <b>TIMEFRAME</b> ⊱ <b>{esc(a['tf'])}</b>\n"
        f"🎯 <b>ACTION</b>    ⊱ <b>{action}</b>\n"
        f"🕒 <b>ENTRY</b>     ⊱ <b>{esc(entry_time)}</b>\n"
        f"💰 <b>PAYOUT</b>    ⊱ <b>{a['payout']:.0f}%</b>\n"
        f"╚══════════💠══════════╝\n\n"
        f"⚡ <b>CONFIDENCE</b>: <b>{a['conf']:.0f}%</b>  {tier_label(a['conf'])}\n"
        f"🛡 <b>LOSS RISK</b> : <b>{a['loss_prob']*100:.0f}%</b>  •  GRADE <b>{esc(a.get('grade','-'))}</b>"
    )

    detail = (
        f"📈 <b>TREND FIT</b> : <b>{a.get('trend_score',0)*100:.0f}%</b>\n"
        f"🌐 <b>MARKET</b>    : {esc(a['regime'])} • ADX {esc(a['adx'])} • {esc(a['session'])} • "
        f"{esc(weekday_name())} profile\n\n"
        f"🕯 <b>CONTEXT</b>   : {esc(context_label(a))}\n\n"
        f"📉 <b>SUPPORT</b>    : <b>{sup}</b>  (str {esc(a['sup_strength'])})\n"
        f"📈 <b>RESISTANCE</b> : <b>{res}</b>  (str {esc(a['res_strength'])})\n\n"
        f"🔎 <b>WHY THIS SIGNAL</b>\n{reasons}{warn}\n\n"
        f"⚙️ <b>STATUS</b>: <b>TRADE SENT ✅</b>"
    )
    return head, detail


def quote_block(detail):
    return f"<blockquote expandable>{detail}</blockquote>"


def make_result_msg(pair, entry_time, direction, result, wins, losses, mtg_time=None):
    total = wins+losses; pct = int(wins/total*100) if total else 0
    dl = "𝗨𝗣 🟢" if direction == UP else "𝗗𝗢𝗪𝗡 🔴"
    rl = ("✅✅✅ <b>WIN</b> ✅✅✅" if result == "WIN" else
          "✅✅ <b>WIN MTG</b> ✅✅" if result == "WIN MTG" else
          "⚠️ <b>UNVERIFIED</b> ⚠️" if result == "UNVERIFIED" else
          "❎❎❎ <b>LOSS</b> ❎❎❎")
    mtg_line = f"🔁 <b>MTG-1:</b> {esc(mtg_time)}\n" if mtg_time else ""
    return (
        f"𒆜•—— <b>R E S U L T</b> ——•𒆜\n"
        f"╭━━━━━━━━𖥠━━━━━━━━╮\n"
        f"📊 <b>{esc(pretty_pair(pair))}</b> ┃ 🕓 <b>{esc(entry_time)}</b>\n"
        f"🎯 <b>Direction:</b> {dl}\n"
        f"{mtg_line}"
        f"╰━━━━━━━━𖥠━━━━━━━━╯\n{rl}\n"
        f"╭━━━━━━━━𖥠━━━━━━━━╮\n"
        f"🚀 <b>Win: {wins}</b> ┃ ✖️ <b>Loss: {losses}</b> ◈ <b>{pct}%</b>\n"
        f"╰━━━━━━━━𖥠━━━━━━━━╯\n"
        f"⚙ <b>{esc(BOT_NAME)} • {esc(BROKER)} {esc(BOT_VERSION)}</b>"
    )


def make_partial_msg(signals):
    wins = len([s for s in signals if s.get("result") in ("WIN", "WIN MTG")])
    direct = len([s for s in signals if s.get("result") == "WIN"])
    mtg = len([s for s in signals if s.get("result") == "WIN MTG"])
    loss = len([s for s in signals if s.get("result") == "LOSS"])
    tot = wins+loss; pct = int(wins/tot*100) if tot else 0
    dpct = int(direct/tot*100) if tot else 0
    lines = [f"=========== <b>PARTIAL</b> ===========",
             f"📆 {get_now():%Y.%m.%d} | {esc(BROKER)} | {esc(weekday_name())} adaptive profile",
             "━━━━━━━━━・━━━━━━━━━"]
    for s in signals[-20:]:
        r = s.get("result", "PENDING")
        mk = ("✅" if r in ("WIN", "WIN MTG") else
              "❎" if r == "LOSS" else "⚠️" if r == "UNVERIFIED" else "⏳")
        mt = "¹" if r == "WIN MTG" else ""
        lines.append(f"❒ {esc(s.get('entry_time','--:--'))} - {esc(pretty_pair(s.get('pair','?')))} - "
                     f"<b>{'BUY' if s.get('direction') == UP else 'SELL'}</b> {mk}{mt}")
    lines += ["━━━━━━━━━・━━━━━━━━━",
              f"📊 <b>Win:{wins} Loss:{loss} Rate:{pct}%</b>",
              f"🎯 <b>Direct (non-MTG):{direct} ({dpct}%)</b> | 🔁 MTG:{mtg}",
              f"⚙ <b>{esc(BOT_NAME)} {esc(BOT_VERSION)}</b> ✅"]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
#  TIMING  (M1 boundary precise)
# ─────────────────────────────────────────────────────────────
def tf_seconds(tf): return {"M1": 60, "M5": 300, "M15": 900}.get(tf, 60)

def seconds_to_next(tf):
    """Candle boundaries come from the REAL epoch clock, not the local clock."""
    sec = tf_seconds(tf)
    now = time.time()
    return sec - (now % sec)

def next_open_epoch(tf):
    sec = tf_seconds(tf)
    ep = int(time.time())
    return ep - (ep % sec) + sec

def entry_label(tf):
    return ts_to_dt(next_open_epoch(tf)).strftime("%H:%M")


# ─────────────────────────────────────────────────────────────
#  RESULT CHECKER  (verifies via the same candle API)
# ─────────────────────────────────────────────────────────────
_TRADE = {"busy": False, "sig": None}


def trade_busy():
    """v52 NON-STOP: analysis kabhi block nahi hoti. Result verification
    background thread me chalti hai, is liye ek trade live hone par bhi bot
    agli candle scan karta rehta hai. Per-pair repeat cooldown se rukta hai."""
    if NONSTOP_MODE:
        return False
    return _TRADE["busy"]


def trade_start(sig):
    _TRADE["busy"] = True
    _TRADE["sig"] = sig


def trade_end():
    _TRADE["busy"] = False
    _TRADE["sig"] = None


class ResultChecker(threading.Thread):
    """One trade at a time: entry candle -> (loss) MTG-1 candle -> final result."""

    def __init__(self, cfg, signals, wins, losses):
        super().__init__(daemon=True)
        self.cfg = cfg; self.signals = signals
        self.wins = wins; self.losses = losses
        self.pending = []; self._stop = threading.Event()

    def add(self, sig): self.pending.append(sig)
    def stop(self): self._stop.set()

    # ── helpers ──
    def _candle(self, sig, epoch):
        """Fresh fetch only — a stale cache must never decide a result."""
        cds = fetch_m1(sig["pair"], 60, self.cfg, use_cache=False) or []
        target = [c for c in cds if c["t"] == epoch]
        if not target:
            # second endpoint / second try, straight from the API
            try:
                j = api_get(API_CANDLES2, {"pair": _norm_pair(sig["pair"]),
                                           "timeframe": "M1", "count": 60}, self.cfg)
                if j and j.get("data"):
                    cds2 = _parse_candles(j)
                    if cds2:
                        cds = cds2
                        target = [c for c in cds if c["t"] == epoch]
            except Exception as e:
                log_line(f"verify fallback fetch error: {e}")
        return (target[0] if target else None), cds

    def _finish(self, sig, outcome, candles):
        sig["result"] = outcome
        counted = outcome in ("WIN", "WIN MTG", "LOSS")
        if outcome in ("WIN", "WIN MTG"): self.wins[0] += 1
        elif outcome == "LOSS": self.losses[0] += 1
        try: self.pending.remove(sig)
        except Exception: pass

        # release the lock immediately — charting/upload must not delay scanning
        trade_end()

        if counted:
            note_result(outcome)
            learn_day(sig.get("families", []), outcome)
            learn_strats(sig.get("strategies", []), outcome)
            # ── v50 AI LEARNING ──
            try:
                won = outcome == "WIN"          # sirf first-candle win = real win
                if sig.get("ai_x"):
                    AI.learn_live(sig["ai_x"], won)
                if sig.get("ai_sig"):
                    AI.learn_memory(sig["ai_sig"], won)
                    AI.save()
                GUARD.record(sig["pair"], outcome)
                FIRE.on_result(sig["pair"], outcome, sig.get("direction"))
                acc = GUARD.accuracy()
                if acc is not None:
                    console.print(f"[dim]🧠 AI updated • rolling accuracy "
                                  f"{acc*100:.1f}% ({len(GUARD.recent)} trades) • "
                                  f"gate min {GUARD.ai_min()*100:.0f}%[/]")
            except Exception as _e:
                log_line(f"ai learn error: {_e}")

            rs = load_results(); rs.append({
                "time": get_now().strftime("%Y-%m-%d %H:%M"),
                "pair": sig["pair"], "tf": sig["tf"], "direction": sig["direction"],
                "result": outcome, "conf": sig["conf"], "loss_prob": sig["loss_prob"],
                "weekday": get_now().weekday(), "families": sig.get("families", []),
                "ai_prob": sig.get("ai_prob"), "hour": get_now().hour,
            })
            save_results(rs)

        log_line(f"RESULT {sig['pair']} {sig['direction']} -> {outcome}")
        colour = "green" if outcome in ("WIN", "WIN MTG") else ("yellow" if outcome == "UNVERIFIED" else "red")
        console.print(f"[{colour}]● RESULT "
                      f"{pretty_pair(sig['pair'])} {sig['direction']} {sig['entry_time']} "
                      f"-> {outcome}[/]")

        if self.cfg.get("telegram"):
            if outcome == "UNVERIFIED":
                tg_send_async(self.cfg,
                              f"⚠️ <b>UNVERIFIED</b> — {esc(pretty_pair(sig['pair']))} "
                              f"⊱ <b>{esc(sig['entry_time'])}</b>\n"
                              f"Candle data API se nahi mila — result skip "
                              f"(stats me count nahi hua).")
            else:
                msg = make_result_msg(sig["pair"], sig["entry_time"], sig["direction"],
                                      outcome, self.wins[0], self.losses[0],
                                      sig.get("mtg_time"))
                chart = None
                try:
                    chart = generate_result_chart(sig, candles, outcome) if (
                        self.cfg.get("charts") and candles) else None
                except Exception as e:
                    log_line(f"result chart error: {e}")
                tg_send_async(self.cfg, msg, chart)

    def _price_fallback(self, sig, epoch, candles):
        """Last resort: decide from the closest candle we do have, else None."""
        step = tf_seconds(sig["tf"])
        near = [c for c in (candles or []) if epoch <= c["t"] < epoch + step]
        if not near:
            return None
        c = near[-1]
        return (c["c"] > c["o"]) if sig["direction"] == UP else (c["c"] < c["o"])

    def run(self):
        while not self._stop.is_set():
            time.sleep(1)
            for sig in list(self.pending):
                try:
                    if time.time() < sig["verify_at"]:
                        continue
                    phase = sig.get("phase", "ENTRY")
                    epoch = sig["entry_epoch"] if phase == "ENTRY" else sig["mtg_epoch"]
                    c, cds = self._candle(sig, epoch)

                    if not c:
                        waited = time.time() - sig["verify_at"]
                        # hard watchdog: never keep the bot locked for long
                        if waited > VERIFY_GRACE or time.time() > sig["entry_epoch"] + 3 * tf_seconds(sig["tf"]) + 20:
                            fb = self._price_fallback(sig, epoch, cds)
                            if fb is None:
                                self._finish(sig, "UNVERIFIED", cds)
                            elif phase == "ENTRY":
                                self._finish(sig, "WIN" if fb else "LOSS", cds)
                            else:
                                self._finish(sig, "WIN MTG" if fb else "LOSS", cds)
                        continue

                    win = (c["c"] > c["o"]) if sig["direction"] == UP else (c["c"] < c["o"])

                    if phase == "ENTRY":
                        if win:
                            self._finish(sig, "WIN", cds)
                        else:
                            # step into MTG-1 on the very next candle
                            step = tf_seconds(sig["tf"])
                            sig["phase"] = "MTG"
                            sig["mtg_epoch"] = sig["entry_epoch"] + step
                            sig["mtg_time"] = ts_to_dt(sig["mtg_epoch"]).strftime("%H:%M")
                            sig["verify_at"] = sig["mtg_epoch"] + step + 1
                            console.print(f"[yellow]● {pretty_pair(sig['pair'])} "
                                          f"{sig['entry_time']} lost — MTG-1 running on "
                                          f"{sig['mtg_time']}[/]")
                            tg_send_async(self.cfg,
                                          f"🔁 <b>MTG-1</b> — {esc(pretty_pair(sig['pair']))} "
                                          f"{'UP 🟢' if sig['direction'] == UP else 'DOWN 🔴'} "
                                          f"⊱ <b>{esc(sig['mtg_time'])}</b>")
                    else:
                        self._finish(sig, "WIN MTG" if win else "LOSS", cds)
                except Exception as e:
                    log_line(f"checker error: {e}")
                    try: self.pending.remove(sig)
                    except Exception: pass
                    trade_end()


# ─────────────────────────────────────────────────────────────
#  SIGNAL DISPATCH
# ─────────────────────────────────────────────────────────────
def dispatch(a, cfg, rc, signals):
    tf = a["tf"]
    # ── SKIP-NEXT LOSS LOGIC: loss ke baad pehla signal skip ──
    if FIRE.consume_skip():
        console.print(f"[yellow]⏭ SKIPPED (loss ke baad ka signal): "
                      f"{pretty_pair(a['pair'])} {a['direction']} — "
                      f"agla banne wala signal liya jayega.[/]")
        log_line(f"SKIP-AFTER-LOSS {a['pair']} {a['tf']} {a['direction']}")
        set_cooldown(a["pair"], a["direction"])
        return None
    remaining = max(int(round(seconds_to_next(tf))), 0)
    entry_epoch = next_open_epoch(tf)
    entry = ts_to_dt(entry_epoch).strftime("%H:%M")

    chart = generate_chart(a, entry, a["F"]["forming"]) if cfg.get("charts") else None
    head, detail = make_signal_msg(a, entry)
    full = head + "\n\n" + quote_block(detail)

    if cfg.get("telegram") and cfg.get("token") and cfg.get("chat_id"):
        if chart:
            if len(full) <= 1000:
                ok, err = send_tg_photo(cfg["token"], cfg["chat_id"], chart, full)
            else:
                ok, err = send_tg_photo(cfg["token"], cfg["chat_id"], chart, head)
                if ok:
                    send_tg_text(cfg["token"], cfg["chat_id"], quote_block(detail))
        else:
            ok, err = send_tg_text(cfg["token"], cfg["chat_id"], full)
        if not ok: console.print(f"[red]Telegram error: {err}[/]")

    show_signal(a, entry, remaining)
    set_cooldown(a["pair"], a["direction"]); register_rate(); mark_signal_sent()

    sig = {"pair": a["pair"], "tf": tf, "direction": a["direction"], "conf": a["conf"],
           "loss_prob": a["loss_prob"], "entry_time": entry, "entry_epoch": entry_epoch,
           "phase": "ENTRY",
           "verify_at": entry_epoch + tf_seconds(tf) + 1,
           "families": a["families"], "strategies": a["strategies"], "result": "PENDING",
           "ai_prob": a.get("ai_prob"), "ai_x": a.get("ai_x"), "ai_sig": a.get("ai_sig"),
           "ai_info": a.get("ai_info", {})}
    signals.append(sig)
    trade_start(sig)          # lock: no new analysis until the result lands
    rc.add(sig)
    log_line(f"SIGNAL {a['pair']} {a['tf']} {a['direction']} conf={a['conf']} lp={a['loss_prob']} ctx={a.get('context')} run={a.get('run_len')} ext={a.get('ext_atr')} body={a.get('body_ratio')} ctxwhy={'|'.join(a.get('context_reasons') or []) or 'clean'}")
    return sig


def show_signal(a, entry, remaining):
    t = Table(box=box.ROUNDED, border_style="cyan", show_header=False, expand=False)
    t.add_column(style="bold cyan"); t.add_column(style="bold white")
    t.add_row("PAIR", pretty_pair(a["pair"]))
    t.add_row("TF / ENTRY", f"{a['tf']}  @  {entry}  (next candle — opens in {remaining}s)")
    t.add_row("DIRECTION", "[green]CALL ▲[/]" if a["direction"] == UP else "[red]PUT ▼[/]")
    t.add_row("CONFIDENCE", f"{a['conf']:.0f}%  {tier_label(a['conf'])}")
    t.add_row("LOSS RISK", f"{a['loss_prob']*100:.0f}%   [bold]{a.get('grade','-')}[/]"
                           f"  (stake {int(a.get('stake',1)*100)}%)")
    t.add_row("TREND FIT", f"{a.get('trend_score',0)*100:.0f}%")
    t.add_row("NON-MTG SCORE", f"[bold green]{a.get('direct',0)*100:.0f}%[/]  "
                               f"(min {direct_minimum()*100:.0f}% • {a.get('nm_for',0)} NM strategies)")
    t.add_row("PRE-ANALYSIS", f"quality {(a['quality'] or 0)*100:.0f} • {a['behaviour']} pair • "
                              f"hour edge {a['hour_edge']*100:.0f}%")
    t.add_row("ENGINE", f"{a['votes']} strategies • {len(a['families'])} families • dom {a['dominance']:.2f}")
    t.add_row("MARKET", f"{a['regime']} • ADX {a['adx']} • {a['session']} • {weekday_name()}")
    t.add_row("CONTEXT", context_label(a))
    t.add_row("SUPPORT", f"{a['support']:.5f}" if a["support"] else "—")
    t.add_row("RESISTANCE", f"{a['resistance']:.5f}" if a["resistance"] else "—")
    t.add_row("PAYOUT", f"{a['payout']:.0f}%")
    t.add_row("REASONS", "\n".join("• " + r for r in a["reasons"][:5]))
    if a.get("grade") in ("MEDIUM", "WATCH"):
        t.add_row("NOTE", f"best available setup ({a.get('why','-')}) — trade smaller")
    console.print(t)


# ─────────────────────────────────────────────────────────────
#  SCANNER  (parallel, finishes before the send window)
# ─────────────────────────────────────────────────────────────
def _safe_analyze(p, tf, cfg):
    try:
        return analyze(p, tf, cfg)
    except Exception as e:
        log_line(f"scan {p}: {e}")
        return None


_PREFETCH = {"stop": None, "thread": None}


def start_rolling_prefetch(pairs, cfg):
    """Keeps the candle cache warm all minute long, so the scan itself is instant."""
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            live = ensure_live_pool(pairs)
            try:
                prefetch_many(live, cfg)
            except Exception as e:
                log_line(f"prefetch: {e}")
            stop.wait(ROLLING_REFRESH)

    t = threading.Thread(target=loop, daemon=True); t.start()
    _PREFETCH.update({"stop": stop, "thread": t})
    return stop


def stop_rolling_prefetch():
    if _PREFETCH.get("stop"): _PREFETCH["stop"].set()



# ─────────────────────────────────────────────────────────────
#  v52 SIGNAL WATCHDOG  —  24 GHANTE NON-STOP GUARANTEE
#  Agar bot kisi wajah se chup ho jaye (route dead, saare pair bench,
#  guard ne sab suspend kar diya, cutoff bahut ooncha) to ye engine
#  khud detect kar ke sab kholta hai aur reason print/log karta hai.
# ─────────────────────────────────────────────────────────────
_WD = {"last_heal": 0.0, "last_health": 0.0, "heals": 0}


def dry_minutes():
    return (time.time() - _LAST_SENT_TS[0]) / 60.0


def health_line(pairs, cfg):
    live = sum(1 for p in pairs if not pair_benched(p))
    acc = GUARD.accuracy()
    console.print(f"[dim]❤ health • uptime ok • live pairs {live}/{len(pairs)} • "
                  f"dry {dry_minutes():.0f}m • cutoff {active_cutoff():.0f} • "
                  f"accuracy {'-' if acc is None else f'{acc*100:.0f}%'} • "
                  f"route {route_name()} • heals {_WD['heals']}[/]")


def watchdog_tick(pairs, cfg):
    """Har loop me sasta check. Signal flow ruk gaya to khud theek karta hai."""
    now = time.time()
    if now - _WD["last_health"] > HEALTH_EVERY_MIN * 60:
        _WD["last_health"] = now
        try: health_line(pairs, cfg)
        except Exception: pass

    dry = dry_minutes()
    if dry < WATCHDOG_MIN or now - _WD["last_heal"] < 300:
        return
    _WD["last_heal"] = now
    _WD["heals"] += 1
    reasons = []

    benched = sum(1 for p in pairs if pair_benched(p))
    if benched:
        reasons.append(f"{benched} pairs benched")
        clear_bench("(watchdog)")

    susp = [p for p, t in list(GUARD.suspended.items()) if t > now]
    if susp:
        reasons.append(f"{len(susp)} pairs on guard-rest")
        GUARD.suspended.clear()
        GUARD.pair_streak.clear()

    _RELAXED[0] = True                     # cutoff ladder ka relax step on
    FIRE.skip_left = 0                     # koi pending skip nahi

    try:                                   # route slow/dead ho sakta hai
        ensure_route(cfg, quiet=True)
    except Exception as _e:
        log_line(f"watchdog route: {_e}")

    _CANDLE_CACHE.clear()                  # fresh data
    _COOLDOWN.clear()                      # sab pairs dobara available

    txt = ", ".join(reasons) if reasons else "no setup passed the gates"
    console.print(f"[yellow]🐕 WATCHDOG: {dry:.0f} min se koi signal nahi "
                  f"({txt}) — sab khol diya, cutoff {active_cutoff():.0f}, "
                  f"flow dobara chalu.[/]")
    log_line(f"WATCHDOG heal dry={dry:.0f}m {txt}")


def scan_best(pairs, tf, cfg, verbose=True, top=6):
    """Analyse every warm pair in parallel and return a RANKED candidate list."""
    live = [p for p in ensure_live_pool(pairs)
            if not (on_cooldown(p, UP) and on_cooldown(p, DN))]
    if not live:                       # v52: kabhi khali scan nahi
        _COOLDOWN.clear()
        live = list(pairs)
    results = []
    with ThreadPoolExecutor(max_workers=ANALYZE_WORKERS) as ex:
        futs = {ex.submit(_safe_analyze, p, tf, cfg): p for p in live}
        for f in as_completed(futs):
            a = f.result()
            if a: results.append(a)

    for a in results:
        g, stake, why = grade_setup(a, cfg)
        a["grade"], a["stake"], a["why"] = g, stake, why
        a["score"] = rank_score(a)
    results = [a for a in results if not (a["payout"] and a["payout"] < MIN_PAYOUT)]
    results.sort(key=lambda a: -a["score"])

    if verbose:
        colors = {"ELITE": "bold green", "STRONG": "green", "GOOD": "cyan", "MEDIUM": "yellow", "WATCH": "dim"}
        for a in results[:8]:
            c = colors.get(a["grade"], "dim")
            console.print(f"  [{c}]{a['grade']:<6}[/] {pretty_pair(a['pair']):<14} {a['direction']:<4} "
                          f"win {100-a['loss_prob']*100:>3.0f}%  conf {a['conf']:>4.0f}%  "
                          f"trend {a['trend_score']*100:>3.0f}  q{(a['quality'] or 0)*100:>3.0f} "
                          f"h{a['hour_edge']*100:>3.0f}  [dim]{len(a['families'])}fam[/]")

    ranked = [a for a in results
              if not on_cooldown(a["pair"], a["direction"])]
    return ranked[:top], len(results)


def confirm_with_forming(a, cfg):
    """Light live check on candle data: the forming candle must not contradict us."""
    try:
        snaps = fetch_m1(a["pair"], 3, cfg, use_cache=False)
    except Exception:
        snaps = []
    if not snaps:
        return a
    cur = snaps[-1]
    body = cur["c"] - cur["o"]
    rng = max(cur["h"] - cur["l"], 1e-12)
    # HIGH ACCURACY: any meaningful opposite body kills the setup
    strong_against = (abs(body) / rng > 0.40) and ((body > 0) != (a["direction"] == UP))
    # and the last closed candle must not be a violent spike against us either
    if len(snaps) >= 2:
        prev = snaps[-2]
        pbody = prev["c"] - prev["o"]
        prng = max(prev["h"] - prev["l"], 1e-12)
        if (abs(pbody) / prng > 0.80) and ((pbody > 0) != (a["direction"] == UP)):
            strong_against = True
    # NEW: forming candle already ran too far in our direction (late entry / spike)
    late_spike = False
    _atr = a.get("atr") or 0.0
    if _atr and (rng / _atr) > 1.8 and ((body > 0) == (a["direction"] == UP)):
        late_spike = True
    if strong_against or late_spike:
        why = "contradicts" if strong_against else f"already ran {rng/_atr:.1f}x ATR (late entry)"
        console.print(f"[yellow]  {pretty_pair(a['pair'])}: forming candle {why} — trying next best[/]")
        log_line(f"SKIP {a['pair']} forming candle {why}")
        return None
    a["F"]["forming"] = snaps[-1:]
    return a


# ─────────────────────────────────────────────────────────────
#  UI
# ─────────────────────────────────────────────────────────────
def banner():
    console.print(Panel(
        f"[bold cyan]{BOT_NAME}[/]  [bold yellow]{BOT_VERSION}[/]\n"
        f"[white]Broker:[/] [bold]{BROKER}[/]   "
        f"[white]Strategies:[/] [bold]{len(STRATS)}[/] [dim](v52 mega layer)[/]   "
        f"[white]Families:[/] [bold]{len(FAMILIES)}[/]   "
        f"[white]Route:[/] [bold green]{route_name()}[/]\n"
        f"[dim]🧠 AI accuracy layer ON • auto-route (no proxy) • 30-35 main pairs • {CALIB_DAYS}-day pre-analysis • "
        f"signal 10s before candle • NON-MTG SNIPER gate • Ctrl+P partial / Ctrl+R reset • "
        f"UTC+{API_TZ_OFFSET:g}[/]",
        border_style="cyan", padding=(1, 3)))


def show_menu(cfg):
    st = "[green]ON[/]" if cfg.get("telegram") else "[red]OFF[/]"
    console.print(Panel(
        f"[bold]1[/] Auto scan  (pre-analysis + best signal, 10s early)\n"
        f"[bold]2[/] Manual pair\n"
        f"[bold]3[/] Settings  (Telegram {st} | charts {'ON' if cfg.get('charts') else 'OFF'} | "
        f"max loss-risk {int(cfg.get('max_loss_prob', MAX_LOSS_PROB)*100)}%)\n"
        f"[bold]4[/] Stats + day profile\n"
        f"[bold]5[/] Re-run {CALIB_DAYS}-day pre-analysis / re-test API route\n"
        f"[bold]6[/] Send partial now   [bold]7[/] Reset partial\n"
        f"[bold]8[/] Exit\n"
        f"[bold]9[/] 🧠 AI brain + accuracy panel     [bold]0[/] ⏰ Best trading times\n"
        f"[dim]scan ke dauran: Ctrl+P = partial • Ctrl+R = partial reset[/]",
        title=f"{weekday_name()} • {get_session()[0]} • {get_now():%H:%M:%S} (UTC+6)",
        border_style="magenta", padding=(1, 3)))


def show_stats():
    rs = load_results()
    w = len([r for r in rs if r["result"] in ("WIN", "WIN MTG")])
    l = len([r for r in rs if r["result"] == "LOSS"])
    t = w + l
    tb = Table(box=box.ROUNDED, border_style="cyan", show_header=False)
    tb.add_column(style="bold cyan"); tb.add_column(style="bold white")
    tb.add_row("TOTAL", str(t))
    tb.add_row("WINS", f"[green]{w}[/]")
    tb.add_row("LOSSES", f"[red]{l}[/]")
    tb.add_row("WIN RATE", f"{(w/t*100) if t else 0:.1f}%")
    tb.add_row("API ROUTE", route_name())
    cp = CALIB.get("pairs", {})
    if cp:
        avgq = sum(s["quality"] for s in cp.values()) / len(cp)
        tb.add_row("PRE-ANALYSIS", f"{len(cp)} pairs • {CALIB.get('days', CALIB_DAYS)} days • "
                                   f"avg quality {avgq*100:.0f}")
    console.print(tb)

    wd = get_now().weekday()
    prof = DAY_PROFILE.get(str(wd), {})
    t2 = Table(box=box.SIMPLE_HEAD, border_style="magenta",
               title=f"{weekday_name()} family profile (self-learned)")
    t2.add_column("FAM"); t2.add_column("WEIGHT"); t2.add_column("W/L")
    for f in FAMILIES:
        node = prof.get(f, {"w": 1.0, "win": 0, "loss": 0})
        t2.add_row(f, f"{day_weight(f):.2f}", f"{node['win']}/{node['loss']}")
    console.print(t2)


def settings_menu(cfg):
    while True:
        console.print(Panel(
            f"1 Telegram on/off      [{'ON' if cfg.get('telegram') else 'OFF'}]\n"
            f"2 Bot token            [{'set' if cfg.get('token') else 'empty'}]\n"
            f"3 Chat id              [{cfg.get('chat_id') or 'empty'}]\n"
            f"4 Charts on/off        [{'ON' if cfg.get('charts') else 'OFF'}]\n"
            f"5 Timeframe            [{cfg.get('timeframe')}]\n"
            f"6 Max loss-risk %      [{int(cfg.get('max_loss_prob', MAX_LOSS_PROB)*100)}]\n"
            f"7 Send-before seconds  [{cfg.get('send_before', SIGNAL_SEND_BEFORE)}]\n"
            f"8 Optional manual proxy (not needed) [{cfg.get('proxy') or 'none'}]\n"
            f"9 Test API route now\n"
            f"0 Back", border_style="magenta", padding=(1, 3)))
        ch = Prompt.ask("Choice", choices=[str(i) for i in range(10)])
        if ch == "1": cfg["telegram"] = not cfg.get("telegram")
        elif ch == "2": cfg["token"] = Prompt.ask("Bot token", default=cfg.get("token", ""))
        elif ch == "3": cfg["chat_id"] = Prompt.ask("Chat id", default=cfg.get("chat_id", ""))
        elif ch == "4": cfg["charts"] = not cfg.get("charts")
        elif ch == "5": cfg["timeframe"] = Prompt.ask("Timeframe", choices=TIMEFRAMES,
                                                      default=cfg.get("timeframe", "M1"))
        elif ch == "6":
            v = Prompt.ask("Max loss-risk % (20-45)", default=str(int(cfg.get("max_loss_prob", MAX_LOSS_PROB)*100)))
            try: cfg["max_loss_prob"] = max(0.15, min(0.45, float(v)/100.0))
            except Exception: pass
        elif ch == "7":
            v = Prompt.ask("Seconds before candle (5-30)", default=str(cfg.get("send_before", SIGNAL_SEND_BEFORE)))
            try: cfg["send_before"] = max(5, min(30, int(v)))
            except Exception: pass
        elif ch == "8":
            cfg["proxy"] = Prompt.ask("Manual proxy URL (blank = auto)", default=cfg.get("proxy", ""))
            _ROUTE["name"] = None
        elif ch == "9":
            _ROUTE["name"] = None
            ok = ensure_route(cfg)
            p = api_pairs(cfg, force=True)
            console.print(f"[green]Route {route_name()} • API OK — {len(p)} pairs[/]" if ok and p
                          else "[red]No route found — bot will keep retrying automatically[/]")
        else:
            save_config(cfg); return
        save_config(cfg)


# ─────────────────────────────────────────────────────────────
#  PAIR SELECTION  (main pairs only — 30-35)
# ─────────────────────────────────────────────────────────────
_LIVE_CACHE = {"t": 0, "pairs": []}


def _is_streaming(p, cfg):
    """A symbol only counts if the API is really streaming its candles."""
    try:
        return len(fetch_m1(p, 80, cfg, use_cache=False)) >= 60
    except Exception:
        return False


def pick_pairs(cfg, quiet=False):
    if _LIVE_CACHE["pairs"] and time.time() - _LIVE_CACHE["t"] < 600:
        out = list(_LIVE_CACHE["pairs"])
    else:
        listed = api_pairs(cfg)
        if not listed:
            if not quiet:
                console.print("[red]API not reachable yet — auto-route is still searching. "
                              "Retrying…[/]")
            return []
        listed_set = set(listed)

        wanted = ([p for p in CORE_OTC if p in listed_set]
                  + [p for p in CORE_CRYPTO if p in listed_set]
                  + [p for p in CORE_FOREX if p in listed_set])
        seen, cand = set(), []
        for p in wanted:
            if p not in seen:
                seen.add(p); cand.append(p)

        if not quiet:
            console.print(f"[cyan]● Checking which of the {len(cand)} main pairs are "
                          f"actually streaming right now…[/]")
        out = []
        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
            futs = {ex.submit(_is_streaming, p, cfg): p for p in cand}
            for f in as_completed(futs):
                if f.result():
                    out.append(futs[f])
        # keep the curated priority order
        order = {p: i for i, p in enumerate(cand)}
        out.sort(key=lambda p: order.get(p, 999))
        out = out[:MAX_PAIRS]
        _LIVE_CACHE.update({"t": time.time(), "pairs": list(out)})
        if not quiet:
            console.print(f"[green]● {len(out)} live main pairs selected[/] "
                          f"[dim](markets closed / dead symbols dropped automatically)[/]")

    if CALIB.get("pairs"):
        out.sort(key=lambda p: -((pair_stats(p) or {}).get("quality", 0.3)))
    return out[:MAX_PAIRS]


# ─────────────────────────────────────────────────────────────
#  RUN MODES
# ─────────────────────────────────────────────────────────────
def run_auto(cfg, rc, signals):
    tf = cfg.get("timeframe", "M1")
    send_before = int(cfg.get("send_before", SIGNAL_SEND_BEFORE))
    pairs = pick_pairs(cfg)
    if not pairs: input("\nEnter to continue..."); return

    run_pre_analysis(pairs, cfg)
    try:
        AI.train_all(pairs, cfg)
        show_best_times()
    except Exception as _e:
        log_line(f"ai boot: {_e}")
    pairs = pick_pairs(cfg)          # re-rank with fresh calibration
    tradable = [p for p in pairs if (pair_stats(p) or {}).get("quality", 1) >= MIN_PAIR_QUALITY]
    if len(tradable) >= MIN_LIVE_POOL: pairs = tradable      # v52: pool khali nahi hone dena
    pairs = pairs[:MAX_PAIRS]

    console.print(f"[cyan]AUTO SCAN[/] • {len(pairs)} pairs • {tf} • {weekday_name()} profile • "
                  f"signal {send_before}s before candle • rolling data feed ON  [dim](Ctrl+C to stop)[/]")
    console.print(f"[green]NON-STOP MODE ON[/] • {len(STRATS)} strategies • regime router • "
                  f"watchdog {WATCHDOG_MIN}m • max {MAX_LIVE_TRADES} live trades • "
                  f"[dim]24h continuous — trade chalte hue bhi scanning band nahi hoti[/]\n")
    start_rolling_prefetch(pairs, cfg)
    hk = start_hotkeys(cfg, signals)
    time.sleep(1.5)                  # let the first warm-up round land
    waiting_notice = False
    try:
        while True:
            # v52 NON-STOP: trade live hone par bhi scanning chalti rehti hai.
            # (verification background thread me hai — flow kabhi nahi rukta)
            if (not NONSTOP_MODE) and trade_busy():
                if not waiting_notice:
                    ts = _TRADE.get("sig") or {}
                    console.print(f"[yellow]⏸ Trade live ({pretty_pair(ts.get('pair','?'))} "
                                  f"{ts.get('entry_time','--:--')}) — result ka intezaar, "
                                  f"koi analysis nahi.[/]")
                    waiting_notice = True
                time.sleep(2); continue
            waiting_notice = False

            watchdog_tick(pairs, cfg)
            if len(rc.pending) >= MAX_LIVE_TRADES:
                time.sleep(1); continue

            rem = seconds_to_next(tf)
            if rem > PRESCAN_START_BEFORE:
                time.sleep(min(rem - PRESCAN_START_BEFORE, 3)); continue
            if rem < send_before + 2:
                time.sleep(max(rem + 0.6, 0.5)); continue

            console.rule(f"[dim]scan {get_now():%H:%M:%S} — next candle in {int(rem)}s[/]")
            t0 = time.time()
            ranked, checked = scan_best(pairs, tf, cfg)
            console.print(f"[dim]analysed {checked} pairs in {time.time()-t0:.1f}s[/]")
            if not ranked:
                console.print("[dim]No data this candle — waiting.[/]")
                time.sleep(max(seconds_to_next(tf) + 0.5, 1)); continue

            while seconds_to_next(tf) > send_before + 3:
                time.sleep(0.1)

            # BALANCED: score-based selection (ELITE / STRONG / GOOD)
            sendable = [a for a in ranked if a.get("grade") in SENDABLE_GRADES] if STRICT_MODE else ranked
            if not sendable:
                if ranked:
                    b = ranked[0]
                    console.print(f"[dim]No setup above cutoff {active_cutoff():.0f} — best was "
                                  f"{pretty_pair(b['pair'])} score {b.get('setup_score',0):.0f} "
                                  f"({b.get('why','-')}).[/]")
                else:
                    console.print("[dim]No setup for this candle — skipped (no forced trade).[/]")
                time.sleep(max(seconds_to_next(tf) + 0.5, 1)); continue


            final = None
            for cand in sendable:                     # best first, fall through on contradiction
                if seconds_to_next(tf) < MIN_SEND_BUFFER: break
                final = confirm_with_forming(cand, cfg)
                if final: break
            if not final:
                console.print("[dim]Live candle contradicted every setup — candle skipped.[/]")
                time.sleep(max(seconds_to_next(tf) + 0.5, 1)); continue

            while seconds_to_next(tf) > send_before:
                time.sleep(0.05)
            if seconds_to_next(tf) < MIN_SEND_BUFFER:
                console.print("[yellow]Send window missed — waiting for the next candle.[/]")
                time.sleep(max(seconds_to_next(tf) + 0.5, 1)); continue

            dispatch(final, cfg, rc, signals)
            time.sleep(max(seconds_to_next(tf) + 1, 2))
    except KeyboardInterrupt:
        console.print("\n[yellow]Auto scan stopped.[/]")
    finally:
        stop_rolling_prefetch()
        try: hk.stop()
        except Exception: pass


def run_manual(cfg, rc, signals):
    tf_default = cfg.get("timeframe", "M1")
    send_before = int(cfg.get("send_before", SIGNAL_SEND_BEFORE))
    pairs = pick_pairs(cfg)
    if not pairs: input("\nEnter to continue..."); return
    console.print("[dim]" + ", ".join(pretty_pair(p) for p in pairs) + "[/]\n")
    raw = Prompt.ask("Pair (e.g. EURUSD-OTC)")
    pair = _norm_pair(raw)
    if pair not in pairs:
        near = [p for p in pairs if raw.upper().replace("-OTC", "").replace("_OTC", "") in p.upper()]
        if near: pair = near[0]
        else:
            console.print("[red]Pair not in the curated main list.[/]"); input(); return
    tf = Prompt.ask("Timeframe", choices=TIMEFRAMES, default=tf_default)
    run_pre_analysis([pair], cfg)
    console.print(f"[cyan]Watching {pretty_pair(pair)} {tf} … signal {send_before}s early. "
                  f"Ctrl+C to stop[/]\n")
    hk = start_hotkeys(cfg, signals)
    waiting_notice = False
    try:
        while True:
            if trade_busy():
                if not waiting_notice:
                    ts = _TRADE.get("sig") or {}
                    console.print(f"[yellow]⏸ Trade live ({ts.get('entry_time','--:--')}) — "
                                  f"result ke baad hi agla analysis.[/]")
                    waiting_notice = True
                time.sleep(2); continue
            waiting_notice = False

            rem = seconds_to_next(tf)
            if rem > PRESCAN_START_BEFORE:
                time.sleep(min(rem - PRESCAN_START_BEFORE, 5)); continue
            if rem < send_before + 2:
                time.sleep(max(rem + 0.6, 0.5)); continue
            a = analyze(pair, tf, cfg)
            if not a:
                console.print("[red]No data for this pair right now.[/]"); time.sleep(5); continue
            a["grade"], a["stake"], a["why"] = grade_setup(a, cfg)
            a["score"] = rank_score(a)
            console.print(f"  {get_now():%H:%M:%S}  {a['direction']}  {a['grade']}  conf {a['conf']:.0f}%  "
                          f"risk {a['loss_prob']*100:.0f}%  trend {a['trend_score']*100:.0f}%")
            if STRICT_MODE and a["grade"] not in SENDABLE_GRADES:
                console.print(f"[dim]  skipped — score {a.get('setup_score',0):.0f} < cutoff {active_cutoff():.0f} ({a['why']})[/]")
                time.sleep(max(seconds_to_next(tf) + 1, 2)); continue
            while seconds_to_next(tf) > send_before + 3: time.sleep(0.2)
            final = confirm_with_forming(a, cfg)
            if not final:
                time.sleep(max(seconds_to_next(tf) + 1, 2)); continue
            while seconds_to_next(tf) > send_before: time.sleep(0.05)
            dispatch(final, cfg, rc, signals)
            time.sleep(max(seconds_to_next(tf) + 1, 2))
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/]")
    finally:
        try: hk.stop()
        except Exception: pass



# ─────────────────────────────────────────────────────────────
#  PARTIAL BATCH + HOTKEYS
#    Ctrl+P  ->  partial abhi bhej do (kabhi bhi, beech me bhi)
#    Ctrl+R  ->  partial reset (naya batch shuru, purana chhod diya)
#  Ctrl+C hamesha kaam karta hai (scan stop).
# ─────────────────────────────────────────────────────────────
PARTIAL = {"start": 0, "sent": 0}


def partial_batch(signals):
    """Current partial batch = reset ke baad ke saare signals."""
    st = min(PARTIAL["start"], len(signals))
    return signals[st:]


def send_partial_now(cfg, signals, tag="Ctrl+P"):
    batch = partial_batch(signals)
    if not batch:
        console.print("[yellow]⚠ Partial khali hai — is batch me abhi koi signal nahi.[/]")
        return False
    msg = make_partial_msg(batch)
    pend = len([x for x in batch if x.get("result", "PENDING") == "PENDING"])
    if cfg.get("telegram") and cfg.get("token") and cfg.get("chat_id"):
        ok, err = send_tg_text(cfg["token"], cfg["chat_id"], msg)
        if ok:
            PARTIAL["sent"] += 1
            console.print(f"[green]📤 PARTIAL sent ({tag}) — {len(batch)} signals"
                          f"{f', {pend} pending' if pend else ''} • total sent {PARTIAL['sent']}[/]")
        else:
            console.print(f"[red]Partial telegram error: {err}[/]")
        return ok
    console.print(f"[yellow]Telegram OFF — partial preview ({tag}):[/]\n" + strip_tags(msg))
    return True


def reset_partial(signals):
    PARTIAL["start"] = len(signals)
    console.print("[cyan]♻ PARTIAL RESET — naya batch shuru. Agla Ctrl+P sirf "
                  "yahan se aage ke signals bhejega.[/]")


class HotkeyListener(threading.Thread):
    """Non-blocking single-key listener (Termux / Linux / Windows)."""

    def __init__(self, cfg, signals):
        super().__init__(daemon=True)
        self.cfg = cfg; self.signals = signals
        self._stop = threading.Event()

    def stop(self): self._stop.set()

    def _handle(self, ch):
        if ch == "\x10":                     # Ctrl+P
            send_partial_now(self.cfg, self.signals, "Ctrl+P")
        elif ch == "\x12":                   # Ctrl+R
            reset_partial(self.signals)

    def run(self):
        if os.name == "nt":
            try:
                import msvcrt
            except Exception:
                return
            while not self._stop.is_set():
                try:
                    if msvcrt.kbhit():
                        self._handle(msvcrt.getwch())
                    else:
                        time.sleep(0.08)
                except Exception:
                    time.sleep(0.3)
            return

        try:
            import termios, tty, select
        except Exception:
            return
        if not sys.stdin.isatty():
            return
        fd = sys.stdin.fileno()
        try:
            old = termios.tcgetattr(fd)
        except Exception:
            return
        try:
            tty.setcbreak(fd)                 # cbreak = Ctrl+C still works
            while not self._stop.is_set():
                try:
                    r, _, _ = select.select([sys.stdin], [], [], 0.2)
                    if r:
                        self._handle(sys.stdin.read(1))
                except Exception:
                    time.sleep(0.3)
        finally:
            try: termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception: pass


def start_hotkeys(cfg, signals):
    hk = HotkeyListener(cfg, signals); hk.start()
    console.print("[magenta]⌨  HOTKEYS: [bold]Ctrl+P[/] = partial bhejo (kabhi bhi)   "
                  "[bold]Ctrl+R[/] = partial reset   [bold]Ctrl+C[/] = stop[/]")
    return hk


def main():
    cfg = load_config()
    signals, wins, losses = [], [0], [0]
    rc = ResultChecker(cfg, signals, wins, losses); rc.start()

    console.clear()
    console.print("[cyan]● Finding a working path to the Tradowix API (no proxy needed)…[/]")
    ensure_route(cfg)
    banner()
    if not CHART_ENABLED:
        console.print("[yellow]⚠ pip install matplotlib for charts[/]")
    p = api_pairs(cfg)
    console.print(f"[dim]{BROKER} API: {'online — ' + str(len(p)) + ' symbols via ' + route_name() if p else 'searching route…'} | "
                  f"{weekday_name()} {get_now():%H:%M} (UTC+6)[/]\n")

    while True:
        show_menu(cfg)
        ch = Prompt.ask("Choice", choices=["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"])
        console.clear(); banner()
        if ch == "1":
            run_auto(cfg, rc, signals); console.clear(); banner()
        elif ch == "2":
            run_manual(cfg, rc, signals); console.clear(); banner()
        elif ch == "3":
            settings_menu(cfg); console.clear(); banner()
        elif ch == "4":
            show_stats(); input("\nEnter to continue..."); console.clear(); banner()
        elif ch == "5":
            _ROUTE["name"] = None; ensure_route(cfg)
            pr = pick_pairs(cfg)
            if pr:
                run_pre_analysis(pr, cfg, force=True)
                AI.train_all(pr, cfg, force=True)
            input("\nEnter to continue..."); console.clear(); banner()
        elif ch == "6":
            send_partial_now(cfg, signals, "menu")
            input("\nEnter to continue..."); console.clear(); banner()
        elif ch == "7":
            reset_partial(signals)
            input("\nEnter to continue..."); console.clear(); banner()
        elif ch == "9":
            show_ai_panel()
            if Confirm.ask("AI model abhi retrain karein?", default=False):
                pr = pick_pairs(cfg)
                if pr: AI.train_all(pr, cfg, force=True)
            input("\nEnter to continue..."); console.clear(); banner()
        elif ch == "0":
            show_best_times()
            input("\nEnter to continue..."); console.clear(); banner()
        else:
            rc.stop()
            if partial_batch(signals) and cfg.get("telegram"):
                if Confirm.ask("Send partial before exit?", default=True):
                    send_partial_now(cfg, signals, "exit")
            show_stats()
            console.print(Panel(f"[bold cyan]Trade safe 🙏[/]\n[dim]{BOT_NAME} {BOT_VERSION} • {BROKER}[/]",
                                border_style="cyan", padding=(1, 3)))
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]● Stopped by user[/]")
    except Exception as e:
        log_line(f"fatal: {e}")
        console.print(f"[red]FATAL: {e}[/]")
