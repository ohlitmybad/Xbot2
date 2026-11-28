import base64
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# --- sampling / config (inlined; loads JSON beside this file) ---
from typing import Iterable, Mapping, Sequence, Union

Key = Union[str, int]
_BOT_DIR = os.path.dirname(os.path.abspath(__file__))

AGE_OPTIONS = ["Age", "U21", "U23"]
SINGLE_LEAGUES = {"Premier League", "La Liga"}
PERFORMANCE_INDEX = "Performance Index"
# Metrics with an Index up/down sort toggle (negative vs positive ranking).
SORT_TOGGLE_METRICS = frozenset(
    {
        "Possessions lost per 90",
        "Shots conceded per 90",
        "xG conceded per 90",
        "Assists - xA per 90",
        "Goals - xG per 90",
    }
)
LEAGUES = [
    "Top 7 Leagues",
    "Top 5 Leagues",
    "All Leagues",
    "Premier League",
    "La Liga",
]
LEAGUES_TEAM = [lg for lg in LEAGUES if lg != "All Leagues"]
POSITIONS_PLAYER = [
    "Goalkeeper",
    "Centre-back",
    "Full-back",
    "Midfielder",
    "Winger",
    "Striker",
    "All positions",
]
POSITIONS_PLOT = POSITIONS_PLAYER + ["Teams"]
VENN_POSITION_TO_VALUE = {"All positions": "All"}
VENN_VALUE_TO_LABEL = {"All": "All positions"}
THRESHOLD_LEVELS = [80, 85, 90, 95, 99]
PLOT_DOTS_MIN = 35
PLOT_DOTS_MAX = 800
PLOT_DOTS_MAX_ALL_POSITIONS = 2500
VENN_MIN_IN_ALL = 1
VENN_MAX_IN_ALL = 4
VENN_MIN_IN_ANY = 8


def load_weights(bot_dir: Optional[str] = None) -> Dict[str, Any]:
    bot_dir = bot_dir or _BOT_DIR
    prior: Dict[str, Any] = {}
    learned: Dict[str, Any] = {}
    prior_path = os.path.join(bot_dir, "prior_weights.json")
    learned_path = os.path.join(bot_dir, "learned_weights.json")
    for path, dest_name in ((prior_path, "prior"), (learned_path, "learned")):
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                if dest_name == "prior":
                    prior = data
                else:
                    learned = data
        except Exception:
            continue
    out: Dict[str, Any] = {}
    for key in ("position", "league", "age"):
        if isinstance(prior.get(key), dict):
            out[key] = prior[key]
    if isinstance(prior.get("metric"), dict):
        out["metric"] = prior["metric"]
    for key in (
        "metric_by_position",
        "metric_pair_by_position",
        "metric_trio_by_position",
        "metric_pair",
        "metric_trio",
    ):
        if isinstance(learned.get(key), dict) and learned[key]:
            out[key] = learned[key]
    return out


def metric_weights_for_position(weights: Mapping[str, Any], position: str) -> Optional[Dict[str, float]]:
    by_pos = weights.get("metric_by_position") or {}
    if isinstance(by_pos, dict) and position in by_pos:
        return by_pos[position]
    if position == "All" and "All positions" in by_pos:
        return by_pos["All positions"]
    if position == "All positions" and "All" in by_pos:
        return by_pos["All"]
    flat = weights.get("metric")
    return flat if isinstance(flat, dict) else None


def pair_weights_for_position(weights: Mapping[str, Any], position: str) -> Optional[Dict[str, float]]:
    by_pos = weights.get("metric_pair_by_position") or {}
    if isinstance(by_pos, dict) and position in by_pos:
        return by_pos[position]
    if position == "All" and "All positions" in by_pos:
        return by_pos["All positions"]
    if position == "All positions" and "All" in by_pos:
        return by_pos["All"]
    flat = weights.get("metric_pair")
    return flat if isinstance(flat, dict) else None


def _weight_for(table: Optional[Mapping[str, float]], key: Key, default: float = 1.0) -> float:
    if not table:
        return default
    raw = table.get(str(key), table.get(key, default))  # type: ignore[arg-type]
    try:
        w = float(raw)
    except (TypeError, ValueError):
        return default
    return w if w > 0 else default


def weighted_choice(
    options: Sequence[Any],
    weights_table: Optional[Mapping[str, float]] = None,
    *,
    key_fn=None,
) -> Any:
    opts = list(options)
    if not opts:
        raise ValueError("weighted_choice: empty options")
    if len(opts) == 1:
        return opts[0]
    keys = [key_fn(o) if key_fn else o for o in opts]
    weights = [_weight_for(weights_table, k) for k in keys]
    return random.choices(opts, weights=weights, k=1)[0]


def pair_key(a: str, b: str) -> str:
    return "||".join(sorted((a, b)))


def age_to_max(age_label: str) -> Optional[int]:
    if not age_label or age_label == "Age":
        return None
    if age_label.startswith("U") and age_label[1:].isdigit():
        return int(age_label[1:])
    return None


def load_metrics_config(path: Optional[str] = None) -> Dict[str, Any]:
    p = path or os.path.join(_BOT_DIR, "metrics_config.json")
    if not os.path.isfile(p):
        return {"index": {}, "plot": {}, "venn": {}, "exclude_groups": {"plot": [], "venn": []}}
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def exclude_groups_for(bot: str, cfg: Optional[Dict[str, Any]] = None) -> List[List[str]]:
    cfg = cfg if cfg is not None else load_metrics_config()
    key = "plot" if bot.lower() == "plot" else "venn"
    eg = cfg.get("exclude_groups")
    if isinstance(eg, dict):
        return [list(g) for g in (eg.get(key) or []) if g and len(g) >= 2]
    if isinstance(eg, list):
        return [list(g) for g in eg if g and len(g) >= 2]
    return []


def pick_age(position: str, league: str, weights: Optional[Dict[str, float]] = None) -> str:
    forced = (os.environ.get("XBOT_FORCE_AGE") or "").strip()
    if forced:
        if forced not in AGE_OPTIONS:
            raise ValueError(f"XBOT_FORCE_AGE={forced!r} not in {AGE_OPTIONS}")
        return forced
    if position == "Goalkeeper" or league in SINGLE_LEAGUES:
        return "Age"
    return weighted_choice(AGE_OPTIONS, weights)


def pick_league(
    weights: Optional[Dict[str, float]] = None,
    *,
    options: Optional[Sequence[str]] = None,
) -> str:
    pool = list(options) if options is not None else list(LEAGUES)
    if not pool:
        raise ValueError("pick_league: empty options")
    forced = (os.environ.get("XBOT_FORCE_LEAGUE") or "").strip()
    if forced:
        if forced not in pool:
            raise ValueError(f"XBOT_FORCE_LEAGUE={forced!r} not in {pool}")
        return forced
    return weighted_choice(pool, weights)


_METRICS_QUEUE_CACHE: Dict[str, Any] = {"path": None, "items": None, "i": 0}


def trial_queue_active() -> bool:
    return bool(
        (os.environ.get("XBOT_METRICS_QUEUE") or "").strip()
        or (os.environ.get("XBOT_FORCE_METRICS") or "").strip()
    )


def unpop_metrics_queue() -> None:
    i = int(_METRICS_QUEUE_CACHE.get("i") or 0)
    if i > 0:
        _METRICS_QUEUE_CACHE["i"] = i - 1


def forced_metrics_from_env() -> Optional[List[str]]:
    qpath = (os.environ.get("XBOT_METRICS_QUEUE") or "").strip()
    if qpath:
        if _METRICS_QUEUE_CACHE["path"] != qpath or _METRICS_QUEUE_CACHE["items"] is None:
            with open(qpath, encoding="utf-8") as fh:
                items = json.load(fh)
            if not isinstance(items, list) or not items:
                raise ValueError(f"XBOT_METRICS_QUEUE empty/invalid: {qpath}")
            _METRICS_QUEUE_CACHE["path"] = qpath
            _METRICS_QUEUE_CACHE["items"] = items
            _METRICS_QUEUE_CACHE["i"] = 0
        i = int(_METRICS_QUEUE_CACHE["i"])
        items = _METRICS_QUEUE_CACHE["items"]
        if i >= len(items):
            raise RuntimeError(f"XBOT_METRICS_QUEUE exhausted ({len(items)} items): {qpath}")
        combo = items[i]
        _METRICS_QUEUE_CACHE["i"] = i + 1
        if not isinstance(combo, list) or not combo:
            raise ValueError(f"Bad queue item at {i}: {combo!r}")
        return [str(x) for x in combo]
    raw = (os.environ.get("XBOT_FORCE_METRICS") or "").strip()
    if not raw:
        return None
    data = json.loads(raw)
    if not isinstance(data, list) or not data:
        raise ValueError(f"XBOT_FORCE_METRICS must be a non-empty JSON list, got {raw!r}")
    return [str(x) for x in data]


def pick_position(options: Sequence[str], weights: Optional[Dict[str, float]] = None) -> str:
    forced = (os.environ.get("XBOT_FORCE_POSITION") or "").strip()
    if forced:
        opts = list(options)
        if forced in opts:
            return forced
        if forced == "All" and "All positions" in opts:
            return "All positions"
        if forced == "All positions" and "All" in opts:
            return "All"
        raise ValueError(f"XBOT_FORCE_POSITION={forced!r} not in options {opts}")
    return weighted_choice(list(options), weights)


def filter_index_metrics(pool: Sequence[str], position: str, league: str) -> List[str]:
    allow_pi = league in SINGLE_LEAGUES and position != "All positions"
    if allow_pi:
        return list(pool)
    return [m for m in pool if m != PERFORMANCE_INDEX]


def is_percent_metric(name: str) -> bool:
    """True for rate metrics like 'Pass completion %' (not 'per 100 touches')."""
    return bool(name) and str(name).rstrip().endswith("%")


def parse_metric_number(text: str) -> Optional[float]:
    if text is None:
        return None
    cleaned = re.sub(r"[^0-9.\-]+", "", str(text).strip())
    if not cleaned or cleaned in {".", "-", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def reaches_100_percent(value: Optional[float]) -> bool:
    return value is not None and value >= 99.995


def index_has_player_at_100_percent(driver) -> bool:
    """Any ranked Index row at 100 on the current (percent) metric."""
    values = driver.execute_script(
        """
        return Array.from(document.querySelectorAll('#playerTable .player-value'))
            .map(el => (el.textContent || '').replace(/\\s+/g, ' ').trim());
        """
    ) or []
    return any(reaches_100_percent(parse_metric_number(v)) for v in values)


def _blocked_by_excludes(metric: str, groups: Sequence[Sequence[str]]) -> set:
    out = set()
    for g in groups:
        if metric in g:
            out.update(g)
    return out


def sample_metrics_excluded(
    pool: Sequence[str],
    k: int,
    exclude_groups: Optional[Sequence[Sequence[str]]] = None,
    metric_weights: Optional[Dict[str, float]] = None,
    pair_weights: Optional[Dict[str, float]] = None,
) -> List[str]:
    groups = list(exclude_groups or [])
    remaining = list(dict.fromkeys(pool))
    if len(remaining) < k:
        raise ValueError(f"Need {k} metrics, pool has {len(remaining)}")
    picked: List[str] = []
    blocked: set = set()
    for _ in range(k):
        candidates = [m for m in remaining if m not in blocked]
        if not candidates:
            candidates = list(remaining)
        if not candidates:
            raise ValueError(f"Could not pick {k} metrics under exclude rules")
        weights = []
        for m in candidates:
            w = _weight_for(metric_weights, m)
            if picked and pair_weights:
                pair_factor = 1.0
                for p in picked:
                    pair_factor *= _weight_for(pair_weights, pair_key(p, m))
                w *= pair_factor ** (1.0 / len(picked))
            weights.append(max(w, 1e-9))
        choice = random.choices(candidates, weights=weights, k=1)[0]
        picked.append(choice)
        remaining = [m for m in remaining if m != choice]
        blocked |= _blocked_by_excludes(choice, groups) - set(picked)
    return picked


# --- end sampling / config ---


_WEIGHTS = load_weights(os.path.dirname(os.path.abspath(__file__)))
_METRICS_CFG = load_metrics_config()
_INDEX_METRICS = _METRICS_CFG.get("index", {})

import pytest
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DATAMB_EMAIL = os.getenv("DATAMB_EMAIL")
DATAMB_PASSWORD = os.getenv("DATAMB_PASSWORD")


def _kill_stale_chrome() -> None:
    if sys.platform == "darwin":
        for proc in ("chromedriver", "Google Chrome for Testing"):
            try:
                subprocess.run(["pkill", "-9", "-f", proc], capture_output=True, timeout=5)
            except Exception:
                pass
    elif sys.platform.startswith("linux"):
        for proc in ("chromedriver", "chrome", "chromium"):
            try:
                subprocess.run(["pkill", "-9", "-f", proc], capture_output=True, timeout=5)
            except Exception:
                pass
    time.sleep(0.5)


def _make_fresh_driver(*, headless: bool = True, window_size: Tuple[int, int] = (1200, 900)) -> webdriver.Chrome:
    _kill_stale_chrome()
    tmp_profile = tempfile.mkdtemp(prefix="selenium_buffer_")
    chrome_options = Options()
    chrome_options.add_argument(f"--user-data-dir={tmp_profile}")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--force-device-scale-factor=2")
    if headless:
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(60)
    driver.set_window_size(*window_size)
    driver._tmp_profile = tmp_profile
    return driver


def _quit_driver(driver) -> None:
    try:
        driver.quit()
    except Exception:
        pass
    tmp = getattr(driver, "_tmp_profile", None)
    if tmp and os.path.isdir(tmp):
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


def buffer_schedule_datetime_plus_two_minutes() -> Tuple[str, str]:
    now = datetime.now() + timedelta(minutes=2)
    schedule_date = now.strftime("%Y-%m-%d")
    hours = now.hour
    minutes = now.strftime("%M")
    ampm = "PM" if hours >= 12 else "AM"
    h12 = hours % 12
    if h12 == 0:
        h12 = 12
    schedule_time = f"{h12}:{minutes} {ampm}"
    return schedule_date, schedule_time


def check_post_scheduled_success(driver, timeout: int = 90) -> Tuple[bool, Optional[str]]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = driver.execute_script(
                """
                var body = document.body ? document.body.innerText.toLowerCase() : '';
                var keywords = ['are scheduled', 'is scheduled', 'has been sent',
                                'has been shared', 'has been published',
                                'added to queue', 'all done', 'hooray',
                                'post scheduled', 'post sent', 'post shared', 'post published',
                                'successfully scheduled', 'successfully sent',
                                'successfully shared', 'successfully published'];
                for (var i = 0; i < keywords.length; i++) {
                    if (body.indexOf(keywords[i]) !== -1) {
                        var link = document.querySelector('a[href*="/posts/"]');
                        var url = link ? link.getAttribute('href') : null;
                        return {success: true, url: url};
                    }
                }
                return null;
                """
            )
            if result and result.get("success"):
                view_post_url = result.get("url")
                if view_post_url and not view_post_url.startswith("http"):
                    view_post_url = "https://publish.buffer.com" + view_post_url
                return True, view_post_url
        except Exception:
            pass
        time.sleep(0.5)
    return False, None


def set_buffer_schedule_time_combobox_input(driver, time_input_el, time_str: str) -> None:
    cmd_key = Keys.COMMAND if sys.platform == "darwin" else Keys.CONTROL
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", time_input_el)
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable(time_input_el))
    time_input_el.click()
    time.sleep(0.2)
    try:
        driver.execute_script(
            """
            var el = arguments[0];
            el.focus();
            var v = el.value || '';
            try { el.setSelectionRange(v.length, v.length); } catch (e) {}
            """,
            time_input_el,
        )
        prev = time_input_el.get_attribute("value") or ""
        n_erase = max(len(prev) + 12, 32)
        actions = ActionChains(driver)
        for _ in range(min(n_erase, 64)):
            actions.send_keys(Keys.BACKSPACE)
        actions.perform()
    except Exception:
        pass
    time.sleep(0.1)
    try:
        leftover = (time_input_el.get_attribute("value") or "").strip()
        if leftover:
            ac = ActionChains(driver)
            ac.click(time_input_el)
            ac.key_down(cmd_key).send_keys("a").key_up(cmd_key)
            for _ in range(48):
                ac.send_keys(Keys.BACKSPACE)
            ac.perform()
    except Exception:
        pass
    time.sleep(0.05)
    try:
        driver.execute_script(
            """
            var el = arguments[0];
            el.focus();
            try {
                var desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                if (desc && desc.set) { desc.set.call(el, ''); }
                else { el.value = ''; }
            } catch (e) { el.value = ''; }
            try {
                el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'deleteContentBackward', data: null }));
            } catch (e) {
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }
            el.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            time_input_el,
        )
    except Exception:
        pass
    time.sleep(0.1)
    time_input_el.click()
    time_input_el.send_keys(time_str)
    time.sleep(0.3)
    try:
        listbox_id = time_input_el.get_attribute("aria-controls") or ""
        option_clicked = False
        if listbox_id:
            try:
                options = driver.find_elements(By.CSS_SELECTOR, f"#{listbox_id} [role='option']")
                for opt in options:
                    if opt.is_displayed() and opt.text.strip() == time_str.strip():
                        opt.click()
                        option_clicked = True
                        break
            except Exception:
                pass
        if not option_clicked:
            options = driver.find_elements(By.CSS_SELECTOR, "[role='option']")
            for opt in options:
                if opt.is_displayed() and opt.text.strip() == time_str.strip():
                    opt.click()
                    option_clicked = True
                    break
        if not option_clicked:
            time_input_el.send_keys(Keys.ENTER)
    except Exception:
        try:
            time_input_el.send_keys(Keys.ENTER)
        except Exception:
            pass
    time.sleep(0.2)


_BUFFER_VERIFY_LINK_RE = re.compile(
    r"https://login\.buffer\.com/verify-login\?jwt=[^\s\"'<>]+",
    re.IGNORECASE,
)


def _buffer_gmail_token_path() -> str:
    return (
        os.environ.get("BUFFER_GMAIL_TOKEN", "").strip()
        or os.environ.get("GMAIL_TOKEN_PATH", "").strip()
    )


def _buffer_gmail_search_query() -> str:
    return os.environ.get(
        "BUFFER_GMAIL_QUERY",
        'from:hello@youraccount.buffer.com subject:"Confirm your recent login attempt"',
    ).strip()


# Desktop OAuth client (Gmail API) — same as client_secret_111773946468-....json in Downloads.
_BUFFER_GMAIL_INSTALLED_CLIENT: Dict[str, Any] = {
    "installed": {
        "client_id": os.getenv("CLIENT_ID"),
        "project_id": "xbot-496214",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": os.getenv("CLIENT_SECRET"),
        "redirect_uris": ["http://localhost"],
    }
}


def _gmail_service_for_buffer():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
    token_path = _buffer_gmail_token_path()
    creds: Optional[Any] = None
    if token_path and os.path.isfile(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            if token_path:
                with open(token_path, "w", encoding="utf-8") as fh:
                    fh.write(creds.to_json())
        else:
            flow = InstalledAppFlow.from_client_config(_BUFFER_GMAIL_INSTALLED_CLIENT, scopes)
            creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
            if token_path:
                with open(token_path, "w", encoding="utf-8") as fh:
                    fh.write(creds.to_json())
    if not creds:
        raise RuntimeError("Buffer email verification: Gmail OAuth failed (no credentials).")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _gmail_collect_text_parts(payload: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    mime = (payload.get("mimeType") or "").lower()
    if "parts" in payload:
        for part in payload["parts"]:
            out.extend(_gmail_collect_text_parts(part))
        return out
    body = payload.get("body") or {}
    data = body.get("data")
    if data and mime in ("text/html", "text/plain"):
        try:
            raw = base64.urlsafe_b64decode(data.encode("ascii"))
            out.append(raw.decode("utf-8", errors="replace"))
        except Exception:
            pass
    return out


def _extract_buffer_verify_link_from_bodies(bodies: List[str]) -> Optional[str]:
    joined = "\n".join(bodies)
    m = _BUFFER_VERIFY_LINK_RE.search(joined)
    if m:
        return m.group(0).rstrip(").,]}>'\"")
    m2 = re.search(
        r"https://login\.buffer\.com/verify-login\?[^\s\"'<>]+", joined, re.IGNORECASE
    )
    if m2:
        return m2.group(0).rstrip(").,]}>'\"")
    return None


def fetch_buffer_verify_link_from_gmail() -> Optional[str]:
    """Latest Buffer 'confirm login' email: extract https://login.buffer.com/verify-login?jwt=..."""
    service = _gmail_service_for_buffer()
    newer = os.environ.get("BUFFER_GMAIL_NEWER_THAN", "2h").strip() or "2h"
    base_q = _buffer_gmail_search_query()
    queries = [
        f"{base_q} newer_than:{newer}",
        f'from:buffer.com subject:"Confirm your recent login" newer_than:{newer}',
        f'from:buffer.com subject:"login attempt" newer_than:{newer}',
    ]
    messages: List[Dict[str, str]] = []
    for q in queries:
        result = service.users().messages().list(userId="me", q=q, maxResults=25).execute()
        messages = result.get("messages") or []
        if messages:
            break
    if not messages:
        return None
    best: Optional[Dict[str, Any]] = None
    best_ts = -1
    for ref in messages:
        mid = ref["id"]
        msg = service.users().messages().get(userId="me", id=mid, format="full").execute()
        ts = int(msg.get("internalDate") or 0)
        if ts >= best_ts:
            best_ts = ts
            best = msg
    if not best:
        return None
    bodies = _gmail_collect_text_parts(best["payload"])
    return _extract_buffer_verify_link_from_bodies(bodies)


def _complete_buffer_login_after_submit(driver) -> None:
    """Wait for Buffer publish, or resolve email MFA via Gmail API and open the verify link."""
    initial_wait = float(os.environ.get("BUFFER_LOGIN_PUBLISH_WAIT", "18"))
    try:
        WebDriverWait(driver, initial_wait).until(EC.url_contains("publish.buffer.com"))
        return
    except Exception:
        pass

    token_path = _buffer_gmail_token_path()
    if not token_path or not os.path.isfile(token_path):
        WebDriverWait(driver, 50).until(EC.url_contains("publish.buffer.com"))
        return

    poll_seconds = float(os.environ.get("BUFFER_GMAIL_POLL_SECONDS", "150"))
    interval = max(2, int(os.environ.get("BUFFER_GMAIL_POLL_INTERVAL", "4")))
    deadline = time.time() + poll_seconds

    while time.time() < deadline:
        try:
            if "publish.buffer.com" in driver.current_url:
                return
        except Exception:
            pass

        try:
            link = fetch_buffer_verify_link_from_gmail()
        except Exception as exc:
            raise RuntimeError(f"Buffer MFA: Gmail API failed: {exc}") from exc
        if link:
            driver.get(link)
            try:
                WebDriverWait(driver, 40).until(EC.url_contains("publish.buffer.com"))
                return
            except Exception:
                pass
        time.sleep(interval)

    WebDriverWait(driver, 20).until(EC.url_contains("publish.buffer.com"))


def _login_buffer(driver, email: str, password: str) -> None:
    driver.get("https://login.buffer.com/login")
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body, input[name='email'], button"))
        )
    except Exception:
        pass
    try:
        accept = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Accept All') or contains(text(), 'Accept')]")
            )
        )
        accept.click()
        time.sleep(0.3)
    except Exception:
        pass

    email_field = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.NAME, "email")))
    email_field.clear()
    email_field.click()
    email_field.send_keys(email)

    password_field = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.NAME, "password")))
    password_field.clear()
    password_field.click()
    password_field.send_keys(password)

    login_button = None
    for xpath in (
        "//button[@type='submit']",
        "//button[contains(text(), 'Log In')]",
        "//button[contains(text(), 'Log in')]",
    ):
        try:
            login_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            if login_button:
                break
        except Exception:
            continue
    if not login_button:
        raise RuntimeError("Buffer login button not found")
    login_button.click()
    _complete_buffer_login_after_submit(driver)


def _open_composer(driver) -> None:
    if "publish.buffer.com" not in driver.current_url:
        driver.get("https://publish.buffer.com")
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "body, button, [data-testid*='new-post'], .new-post-button")
            )
        )
    except Exception:
        pass
    try:
        new_post = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'New Post')]"))
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", new_post
        )
        time.sleep(0.3)
        new_post.click()
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button.publish_channelItem_BUVOd"))
        )
    except Exception:
        driver.get("https://publish.buffer.com/composer")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "button.publish_channelItem_BUVOd, textarea, .composer")
            )
        )


def _select_twitter_only(driver) -> None:
    for btn in driver.find_elements(By.CSS_SELECTOR, "button.publish_channelItem_BUVOd[aria-pressed='true']"):
        try:
            btn.click()
        except Exception:
            pass
    time.sleep(0.2)
    channel_buttons = driver.find_elements(By.CSS_SELECTOR, "button.publish_channelItem_BUVOd")
    for button in channel_buttons:
        try:
            button.find_element(By.CSS_SELECTOR, "div[data-channel='twitter']")
            if button.get_attribute("aria-pressed") != "true":
                button.click()
                try:
                    WebDriverWait(driver, 2).until(
                        lambda d, b=button: b.get_attribute("aria-pressed") == "true"
                    )
                except Exception:
                    pass
            return
        except Exception:
            continue
    try:
        alt_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label='twitter channel']")
        if alt_btn.get_attribute("aria-pressed") != "true":
            alt_btn.click()
    except Exception as exc:
        raise RuntimeError("Could not select Twitter channel in Buffer") from exc


def _copy_text_to_clipboard(text: str, driver=None) -> bool:
    """
    Set clipboard contents so Ctrl+V triggers a real paste event.
    Primary: CDP command (works in headless CI with no OS clipboard).
    Fallback: OS clipboard tools (pbcopy/xclip/xsel).
    """
    if driver is not None:
        try:
            driver.execute_cdp_cmd(
                "Browser.setPermission",
                {"permission": {"name": "clipboard-read"}, "setting": "granted",
                 "origin": driver.execute_script("return window.location.origin")},
            )
            driver.execute_cdp_cmd(
                "Browser.setPermission",
                {"permission": {"name": "clipboard-write"}, "setting": "granted",
                 "origin": driver.execute_script("return window.location.origin")},
            )
        except Exception:
            pass
        try:
            driver.execute_script(
                "await navigator.clipboard.writeText(arguments[0]);", text
            )
            return True
        except Exception:
            pass
        try:
            driver.execute_cdp_cmd(
                "Runtime.evaluate",
                {"expression": f"navigator.clipboard.writeText({repr(text)})",
                 "awaitPromise": True},
            )
            return True
        except Exception:
            pass
    try:
        raw = text.encode("utf-8")
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=raw, check=True)
        elif sys.platform == "win32":
            subprocess.run(["clip"], input=text, text=True, shell=True, check=True)
        else:
            for argv in (["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
                try:
                    subprocess.run(argv, input=raw, check=True)
                    return True
                except FileNotFoundError:
                    continue
            return False
        return True
    except Exception:
        return False


def _composer_read_text(driver, el) -> str:
    return (
        driver.execute_script(
            """
            const root = arguments[0];
            function read(n) {
                if (!n) return '';
                if (n.tagName === 'TEXTAREA' || n.tagName === 'INPUT') return (n.value || '').trim();
                return (n.innerText || n.textContent || '').trim();
            }
            let t = read(root);
            if (t.length > 0) return t;
            const a = document.activeElement;
            if (a && root && (root === a || root.contains(a))) {
                const u = read(a);
                if (u.length > 0) return u;
            }
            return t;
            """,
            el,
        )
        or ""
    )


def _composer_text_looks_ok(driver, el, expected: str) -> bool:
    got = _composer_read_text(driver, el).strip()
    exp = expected.strip()
    if not exp:
        return True
    if len(exp) <= 12:
        return got == exp
    return len(got) >= max(12, int(0.35 * len(exp)))


def _find_primary_composer(driver):
    """Largest editable in/near composer; pierces shadow roots; prefers composer/editor ancestors."""
    el = driver.execute_script(
        """
        function badHint(el) {
            var p = ((el.getAttribute('placeholder') || '') + ' ' + (el.getAttribute('aria-label') || ''))
                .toLowerCase();
            return p.indexOf('search') >= 0 || p.indexOf('filter') >= 0;
        }
        function composerWeight(el) {
            var n = el;
            for (var i = 0; i < 18 && n; i++) {
                var cls = (n.className && String(n.className).toLowerCase()) || '';
                var tid = ((n.getAttribute && n.getAttribute('data-testid')) || '').toLowerCase();
                if (tid.indexOf('composer') >= 0 || cls.indexOf('composer') >= 0) return 4;
                if (cls.indexOf('draft') >= 0 || cls.indexOf('editor') >= 0 || cls.indexOf('slate') >= 0) return 3;
                if (cls.indexOf('publish') >= 0) return 2;
                n = n.parentElement;
            }
            return 1;
        }
        var nodes = [];
        document.querySelectorAll('textarea, [contenteditable="true"]').forEach(function(el) {
            if (badHint(el)) return;
            var r = el.getBoundingClientRect();
            if (r.width < 40 || r.height < 16) return;
            var st = window.getComputedStyle(el);
            if (st.display === 'none' || st.visibility === 'hidden' || parseFloat(st.opacity || '1') === 0) return;
            if (r.bottom <= 2 || r.top >= window.innerHeight - 2) return;
            var area = r.width * r.height;
            if (area < 300) return;
            var w = composerWeight(el);
            nodes.push({ el: el, score: area * w });
        });
        nodes.sort(function(a, b) { return b.score - a.score; });
        return nodes.length ? nodes[0].el : null;
        """
    )
    if el is not None:
        return el
    scored = []
    for sel in ("textarea", "[contenteditable='true']"):
        for cand in driver.find_elements(By.CSS_SELECTOR, sel):
            try:
                if not cand.is_displayed():
                    continue
                r = cand.rect
                area = r.get("height", 0) * r.get("width", 0)
                if area < 800:
                    continue
                scored.append((area, cand))
            except Exception:
                continue
    if not scored:
        raise RuntimeError("Buffer: could not find main composer text field")
    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


def _set_native_textarea_react(driver, el, text: str) -> None:
    """React-controlled textareas ignore raw .value unless _valueTracker is synced."""
    driver.execute_script(
        """
        const el = arguments[0], value = arguments[1];
        const last = el.value;
        const desc = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
        if (desc && desc.set) { desc.set.call(el, value); }
        else { el.value = value; }
        try {
            const tracker = el._valueTracker;
            if (tracker) { tracker.setValue(last); }
        } catch (e) {}
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        el,
        text,
    )


def _js_synthetic_paste(driver, el, text: str) -> bool:
    """Fire a synthetic paste event with DataTransfer — works in headless without OS clipboard."""
    try:
        driver.execute_script(
            """
            const el = arguments[0], text = arguments[1];
            el.focus();
            const dt = new DataTransfer();
            dt.setData('text/plain', text);
            const pe = new ClipboardEvent('paste', {
                bubbles: true, cancelable: true, clipboardData: dt
            });
            el.dispatchEvent(pe);
            """,
            el,
            text,
        )
        return True
    except Exception:
        return False


def _set_composer_text(driver, post_text: str) -> None:
    el = _find_primary_composer(driver)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable(el))
    cmd = Keys.COMMAND if sys.platform == "darwin" else Keys.CONTROL

    def focus_clear() -> None:
        el.click()
        time.sleep(0.35)
        ActionChains(driver).click(el).key_down(cmd).send_keys("a").key_up(cmd).pause(0.1).send_keys(Keys.BACKSPACE).perform()
        time.sleep(0.2)

    focus_clear()

    # Method 1: CDP clipboard + Ctrl/Cmd+V
    if _copy_text_to_clipboard(post_text, driver=driver):
        driver.execute_script("arguments[0].focus(); arguments[0].click();", el)
        time.sleep(0.15)
        ActionChains(driver).key_down(cmd).send_keys("v").key_up(cmd).perform()
        time.sleep(0.55)
        if _composer_text_looks_ok(driver, el, post_text):
            return

    # Method 2: synthetic paste event (headless-friendly, no OS clipboard needed)
    focus_clear()
    _js_synthetic_paste(driver, el, post_text)
    time.sleep(0.4)
    if _composer_text_looks_ok(driver, el, post_text):
        return

    # Method 3: execCommand insertText (works for contenteditable)
    focus_clear()
    driver.execute_script(
        """
        const el = arguments[0], t = arguments[1];
        el.focus();
        document.execCommand('selectAll', false, null);
        document.execCommand('insertText', false, t);
        """,
        el,
        post_text,
    )
    time.sleep(0.3)
    if _composer_text_looks_ok(driver, el, post_text):
        return

    # Method 4: React textarea setter
    tag = (el.tag_name or "").lower()
    if tag == "textarea":
        focus_clear()
        _set_native_textarea_react(driver, el, post_text)
        time.sleep(0.3)
        if _composer_text_looks_ok(driver, el, post_text):
            return

    # Method 5: direct send_keys
    focus_clear()
    el.send_keys(post_text)
    time.sleep(0.35)
    if not _composer_text_looks_ok(driver, el, post_text):
        raise RuntimeError(
            "Buffer: main composer text did not stick after all methods; "
            "check composer selectors or run with visible Chrome to see focus."
        )


def _upload_single_image(driver, image_path: str) -> None:
    abs_path = os.path.abspath(image_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(abs_path)
    file_input = None
    for sel in (
        "input[type='file']",
        "[data-testid*='media-upload'] input[type='file']",
        "[data-testid*='image-upload'] input[type='file']",
    ):
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                if el.get_attribute("type") == "file":
                    file_input = el
                    break
            if file_input:
                break
        except Exception:
            continue
    if not file_input:
        raise RuntimeError("Buffer: no file input found for image upload")
    file_input.send_keys(abs_path)
    time.sleep(2.5)
    try:
        WebDriverWait(driver, 20).until(
            EC.any_of(
                EC.presence_of_element_located((By.XPATH, "//button[.//span[contains(text(), 'Add description')]]")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "img[src*='blob'], img[src*='buffer']")),
            )
        )
    except Exception:
        pass


def _add_alt_text(driver, alt_text: str) -> None:
    if not alt_text.strip():
        return
    try:
        target_image = None
        for selector in (
            "img[src*='blob']", "img[src*='data:']", "img[src*='buffer']",
            ".publish_mediaContainer img", "[class*='media'] img", "img",
        ):
            try:
                for img in driver.find_elements(By.CSS_SELECTOR, selector):
                    if img.is_displayed() and img.size.get("width", 0) > 50 and img.size.get("height", 0) > 50:
                        target_image = img
                        break
                if target_image:
                    break
            except Exception:
                continue
        if not target_image:
            return

        driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", target_image)
        time.sleep(0.3)

        driver.execute_script(
            """
            var img = arguments[0];
            var container = img.closest('[class*="media"], [class*="Media"], [class*="publish_media"]');
            if (!container) container = img.parentElement;
            ['mouseenter','mouseover','mousemove'].forEach(function(t){
                var ev = new MouseEvent(t,{bubbles:true,cancelable:true,view:window});
                container.dispatchEvent(ev);
                img.dispatchEvent(ev);
            });
            """,
            target_image,
        )
        time.sleep(0.5)

        alt_button = driver.execute_script(
            """
            var allButtons = document.querySelectorAll('button.publish_action_ZlY7D');
            for (var i = 0; i < allButtons.length; i++) {
                var btn = allButtons[i];
                var span = btn.querySelector('span.publish_base_D9VRM');
                if (span && span.textContent.includes('Add description')) {
                    var st = window.getComputedStyle(btn);
                    if (st.display !== 'none' && st.visibility !== 'hidden' && st.opacity !== '0') return btn;
                }
            }
            return null;
            """
        )
        if not alt_button:
            for b in driver.find_elements(By.XPATH, "//button[.//span[contains(text(), 'Add description')]]"):
                try:
                    vis = driver.execute_script(
                        "var s=window.getComputedStyle(arguments[0]);"
                        "return s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0';",
                        b,
                    )
                    if vis:
                        alt_button = b
                        break
                except Exception:
                    continue
        if not alt_button:
            for b in driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='Alt'], button[aria-label*='alt'], button.publish_actionButton_hpIK-"):
                if b.is_displayed():
                    alt_button = b
                    break
        if not alt_button:
            return

        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", alt_button)
        try:
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable(alt_button))
            alt_button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", alt_button)
        time.sleep(0.5)

        cmd = Keys.COMMAND if sys.platform == "darwin" else Keys.CONTROL
        alt_input = None
        try:
            alt_input = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "textarea[placeholder*='description'], textarea[placeholder*='alt'], "
                    "input[placeholder*='description'], input[placeholder*='alt'], "
                    "[aria-label*='alt'] textarea, [aria-label*='description'] textarea"
                ))
            )
        except Exception:
            pass
        if not alt_input:
            try:
                alt_input = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//div[@role='dialog']//textarea | "
                        "//div[@role='dialog']//*[@contenteditable='true']"
                    ))
                )
            except Exception:
                pass

        if alt_input:
            alt_input.click()
            time.sleep(0.15)
            try:
                alt_input.clear()
            except Exception:
                pass
            typed = False
            if _copy_text_to_clipboard(alt_text, driver=driver):
                driver.execute_script("arguments[0].focus(); arguments[0].click();", alt_input)
                time.sleep(0.1)
                ActionChains(driver).key_down(cmd).send_keys("v").key_up(cmd).perform()
                time.sleep(0.4)
                typed = True
            if not typed:
                _js_synthetic_paste(driver, alt_input, alt_text)
                time.sleep(0.3)
                typed = True
            got = driver.execute_script(
                "return (arguments[0].value || arguments[0].textContent || '').trim();",
                alt_input,
            )
            if not got:
                _set_native_textarea_react(driver, alt_input, alt_text)
                time.sleep(0.2)
            got = driver.execute_script(
                "return (arguments[0].value || arguments[0].textContent || '').trim();",
                alt_input,
            )
            if not got:
                alt_input.send_keys(alt_text)
        else:
            ActionChains(driver).send_keys(alt_text).perform()

        time.sleep(0.3)

        for selector_type, selector in (
            (By.CSS_SELECTOR, "button.publish_saveButton_iFO4s"),
            (By.CSS_SELECTOR, "button[class*='publish_saveButton']"),
            (By.XPATH, "//button[contains(text(), 'Save')]"),
        ):
            try:
                save_btn = WebDriverWait(driver, 4).until(EC.element_to_be_clickable((selector_type, selector)))
                if save_btn and save_btn.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", save_btn)
                    save_btn.click()
                    time.sleep(0.5)
                    return
            except Exception:
                continue
        ActionChains(driver).send_keys(Keys.ENTER).perform()
    except Exception:
        pass


def _add_thread_reply(driver, reply_text: str) -> None:
    if not reply_text.strip():
        return
    thread_button = None
    for sel in (
        (By.CSS_SELECTOR, "button[data-testid='add-post-to-thread-button']"),
        (By.XPATH, "//button[contains(., 'Start Thread')]"),
        (By.XPATH, "//button[contains(., 'Add another post')]"),
    ):
        try:
            thread_button = driver.find_element(sel[0], sel[1])
            if thread_button.is_displayed():
                break
        except Exception:
            thread_button = None
    if not thread_button:
        return
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", thread_button)
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(thread_button))
    try:
        thread_button.click()
    except Exception:
        driver.execute_script("arguments[0].click();", thread_button)
    time.sleep(0.65)
    tboxes = [t for t in driver.find_elements(By.CSS_SELECTOR, "textarea") if t.is_displayed()]
    if len(tboxes) >= 2:
        thread_el = tboxes[-1]
    elif tboxes:
        thread_el = tboxes[0]
    else:
        boxes = [b for b in driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']") if b.is_displayed()]
        thread_el = boxes[-1] if boxes else None
    if not thread_el:
        return
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", thread_el)
    thread_el.click()
    time.sleep(0.2)
    thread_el.send_keys(reply_text)
    time.sleep(0.2)


def _publish_now(driver) -> None:
    """Click 'Next Available' dropdown → 'Now' → then 'Publish Now' button."""
    dd = driver.execute_script(
        """
        var btns = document.querySelectorAll('button');
        for (var i = 0; i < btns.length; i++) {
            var t = (btns[i].innerText || '').trim();
            if (t.indexOf('Next Available') >= 0) {
                var r = btns[i].getBoundingClientRect();
                if (r.width > 0 && r.height > 0) return btns[i];
            }
        }
        return null;
        """
    )
    if not dd:
        for xp in (
            "//button[contains(., 'Next Available')]",
            "//*[@role='button'][contains(., 'Next Available')]",
        ):
            try:
                for el in driver.find_elements(By.XPATH, xp):
                    if el.is_displayed():
                        dd = el
                        break
                if dd:
                    break
            except Exception:
                continue
    if not dd:
        raise RuntimeError("Buffer: 'Next Available' dropdown not found")
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", dd)
    dd.click()
    time.sleep(0.6)

    now_btn = None
    for xp in (
        "//button[normalize-space(.)='Now']",
        "//div[normalize-space(.)='Now' and not(descendant::div)]",
        "//span[normalize-space(.)='Now']",
        "//*[normalize-space(.)='Now' and string-length(normalize-space(.))<=4]",
        "//button[contains(., 'Share now')]",
        "//button[contains(., 'right away')]",
    ):
        try:
            for el in driver.find_elements(By.XPATH, xp):
                if el.is_displayed():
                    now_btn = el
                    break
            if now_btn:
                break
        except Exception:
            continue
    if not now_btn:
        raise RuntimeError("Buffer: 'Now' option not found in schedule dropdown")
    now_btn.click()
    time.sleep(0.6)

    pub = driver.execute_script(
        """
        var btns = document.querySelectorAll('button');
        var targets = ['Publish Now', 'Share Now', 'Send Now', 'Post Now'];
        for (var i = 0; i < btns.length; i++) {
            var t = (btns[i].innerText || '').trim();
            for (var j = 0; j < targets.length; j++) {
                if (t === targets[j]) {
                    var r = btns[i].getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) return btns[i];
                }
            }
        }
        return null;
        """
    )
    if not pub:
        for xp in (
            "//button[contains(text(), 'Publish Now')]",
            "//button[contains(text(), 'Share Now')]",
            "//button[contains(text(), 'Send Now')]",
            "//button[contains(text(), 'Post Now')]",
            "//button[contains(text(), 'Publish')]",
        ):
            try:
                el = driver.find_element(By.XPATH, xp)
                if el and el.is_displayed():
                    pub = el
                    break
            except Exception:
                continue
    if not pub:
        raise RuntimeError("Buffer: 'Publish Now' button not found")
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", pub)
    try:
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(pub))
        pub.click()
    except Exception:
        driver.execute_script("arguments[0].click();", pub)
    time.sleep(1)


def _resolve_channel_ids(api_key: str) -> Dict[str, str]:
    """Return Buffer channel IDs for twitter + instagram (both required)."""
    import requests as _requests

    org_q = "query { account { organizations { id } } }"
    resp = _requests.post(
        "https://api.buffer.com",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={"query": org_q},
        timeout=30,
    )
    org_id = resp.json()["data"]["account"]["organizations"][0]["id"]

    ch_q = """query GetChannels($orgId: OrganizationId!) {
      channels(input: { organizationId: $orgId }) { id service }
    }"""
    resp = _requests.post(
        "https://api.buffer.com",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={"query": ch_q, "variables": {"orgId": org_id}},
        timeout=30,
    )
    out: Dict[str, str] = {}
    for ch in resp.json()["data"]["channels"]:
        service = ch.get("service")
        if service in ("twitter", "instagram") and service not in out:
            out[service] = ch["id"]
    missing = [s for s in ("twitter", "instagram") if s not in out]
    if missing:
        raise RuntimeError(f"Buffer channel(s) not found: {', '.join(missing)}")
    return out


def _upload_image_to_host(local_path: str) -> str:
    """Upload a local image to ImgBB and return a stable public HTTPS URL.

    Buffer fetches media at publish time, so the host must stay publicly
    reachable. Litterbox/catbox returns 412 and drops scheduled posts.
    Requires IMGBB_API_KEY env var (same host as Content Creator).
    """
    import requests as _requests

    api_key = os.environ.get("IMGBB_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Set IMGBB_API_KEY env var")

    abs_path = os.path.abspath(local_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"Image not found: {abs_path}")

    with open(abs_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("ascii")

    resp = _requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": api_key, "image": image_b64},
        timeout=120,
    )
    try:
        payload = resp.json()
    except ValueError:
        resp.raise_for_status()
        raise RuntimeError(
            f"ImgBB upload failed: unexpected response ({resp.status_code})"
        )

    if resp.status_code >= 400 or not payload.get("success"):
        err = (
            payload.get("error")
            or payload.get("status_txt")
            or payload.get("data")
            or resp.text
        )
        if isinstance(err, dict):
            err = err.get("message") or err.get("error") or err
        raise RuntimeError(f"ImgBB upload failed: {err}")

    data = payload.get("data") or {}
    url = (
        (data.get("image") or {}).get("url")
        or data.get("url")
        or data.get("display_url")
        or ""
    )
    url = url.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"ImgBB upload failed: no public URL in response ({payload})")
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    return url


def schedule_twitter_post_via_buffer(
    driver,
    post_text: str,
    image_path: str,
    alt_text: Optional[str] = None,
    reply_text: Optional[str] = None,
    schedule_minutes: int = 180,
) -> None:
    """Post to Twitter + Instagram via Buffer GraphQL API (scheduled N minutes from now)."""
    if os.environ.get("XBOT_LOCAL", "").strip().lower() in ("1", "true", "yes"):
        raise RuntimeError(
            "XBOT_LOCAL is set — refusing Buffer upload. Use INDEX/run_local.py instead."
        )

    import requests as _requests
    from datetime import timezone

    api_key = os.environ.get("BUFFER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Set BUFFER_API_KEY env var")

    channels = _resolve_channel_ids(api_key)

    image_url = _upload_image_to_host(image_path)
    print(f"Image uploaded: {image_url}")

    image_asset = {"image": {"url": image_url}}
    if alt_text:
        image_asset["image"]["metadata"] = {"altText": alt_text}
    assets = [image_asset]

    due_at = (datetime.now(tz=timezone.utc) + timedelta(minutes=schedule_minutes)).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )

    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id text dueAt } }
        ... on MutationError { message }
      }
    }
    """

    def _create(channel_id: str, service: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        input_var: Dict[str, Any] = {
            "text": post_text,
            "channelId": channel_id,
            "schedulingType": "automatic",
            "mode": "customScheduled",
            "dueAt": due_at,
            "assets": assets,
        }
        if metadata:
            input_var["metadata"] = metadata
        resp = _requests.post(
            "https://api.buffer.com",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={"query": query, "variables": {"input": input_var}},
            timeout=30,
        )
        result = resp.json()
        if result.get("errors"):
            err = result["errors"][0]
            raise RuntimeError(
                f"Buffer API error ({service}): {err.get('message', 'Unknown')}"
            )
        cp = result.get("data", {}).get("createPost", {})
        if cp.get("post"):
            print(
                f"Buffer API ({service}): post created "
                f"(id={cp['post']['id']}, dueAt={cp['post'].get('dueAt')})"
            )
        elif cp.get("message"):
            raise RuntimeError(f"Buffer API error ({service}): {cp['message']}")
        else:
            raise RuntimeError(f"Buffer API ({service}): unexpected response: {result}")

    twitter_meta: Dict[str, Any] = {}
    if reply_text:
        twitter_meta["twitter"] = {
            "thread": [
                {"text": post_text, "assets": assets},
                {"text": reply_text, "assets": []},
            ]
        }
    _create(channels["twitter"], "twitter", twitter_meta or None)
    _create(
        channels["instagram"],
        "instagram",
        {"instagram": {"type": "post", "shouldShareToFeed": True}},
    )


def _select_index_dropdown(
    driver,
    trigger_id,
    options_id,
    label,
    extra_matches=None,
    search_input_id=None,
    timeout=10,
):
    """Pick one option in the Index custom-select UI (multi-select + search).

    Clicks the option label, not the combine checkbox. Matches data-value or
    the option's span text. Raises if the trigger does not show the choice.
    """
    candidates = [label, *(extra_matches or [])]
    script = """
        const triggerId = arguments[0];
        const optionsId = arguments[1];
        const candidates = arguments[2];
        const searchInputId = arguments[3];

        function norm(s) {
            return (s || '').replace(/\\s+/g, ' ').trim();
        }
        function optionLabel(option) {
            const span = option.querySelector('span:not(.option-check)');
            return span || option;
        }
        function optionText(option) {
            return norm(optionLabel(option).textContent);
        }
        function matches(option) {
            const value = option.getAttribute('data-value') || '';
            const text = optionText(option);
            return candidates.some(function (c) {
                return c === value || c === text;
            });
        }

        const trigger = document.getElementById(triggerId);
        const options = document.getElementById(optionsId);
        if (!trigger || !options) return { ok: false, reason: 'missing-ui' };

        document.querySelectorAll('.custom-select-trigger.open').forEach(function (openTrigger) {
            if (openTrigger !== trigger) {
                openTrigger.classList.remove('open');
                if (openTrigger.nextElementSibling) openTrigger.nextElementSibling.style.display = 'none';
            }
        });
        if (!trigger.classList.contains('open')) trigger.click();

        if (searchInputId) {
            const search = document.getElementById(searchInputId);
            if (search) {
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(search, candidates[0]);
                search.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }

        let found = null;
        options.querySelectorAll('.custom-select-option').forEach(function (option) {
            if (found || option.hidden) return;
            if (matches(option)) found = option;
        });
        if (!found) {
            return {
                ok: false,
                reason: 'not-found',
                open: trigger.classList.contains('open'),
                count: options.querySelectorAll('.custom-select-option').length
            };
        }

        optionLabel(found).click();
        trigger.classList.remove('open');
        options.style.display = 'none';

        const triggerSpan = trigger.querySelector('span');
        return {
            ok: true,
            shown: norm(triggerSpan ? triggerSpan.textContent : trigger.textContent)
        };
    """

    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = driver.execute_script(script, trigger_id, options_id, candidates, search_input_id)
        shown = (last or {}).get("shown") or ""
        if last and last.get("ok") and any(c == shown or c in shown for c in candidates):
            return shown
        time.sleep(0.2)

    raise RuntimeError(
        f"Could not select {label!r} in #{options_id} "
        f"(candidates={candidates}, last={last})"
    )


class TestUntitled:
    def setup_method(self, method):
        self.driver = _make_fresh_driver(headless=True)

    def teardown_method(self):
        _quit_driver(self.driver)
        
    def capture_first_five_lines(self):
        """Top 5 Index rows from the DOM (not body text — threshold UI shifted line offsets)."""
        rows = self.driver.execute_script(
            """
            const out = [];
            document.querySelectorAll('#playerTable .player-row').forEach(function (row) {
                if (out.length >= 5) return;
                const nameEl = row.querySelector('.player-name');
                const valueEl = row.querySelector('.player-value');
                if (!nameEl) return;
                out.push({
                    name: (nameEl.textContent || '').replace(/\\s+/g, ' ').trim(),
                    value: valueEl ? (valueEl.textContent || '').replace(/\\s+/g, ' ').trim() : ''
                });
            });
            return out;
            """
        )
        if not rows:
            # Fallback: find first ranked player line in body text
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            lines = [ln.strip() for ln in body_text.splitlines() if ln.strip()]
            start = 0
            for i, line in enumerate(lines):
                if line.startswith("1.") or line.startswith("1 "):
                    start = i
                    break
            lines = lines[start : start + 5]
            specific_lines = "\n".join(lines)
        else:
            formatted = []
            for row in rows:
                name = row.get("name") or ""
                # Strip leading "1. " / "2. " etc. — medals added below
                name = re.sub(r"^\d+\.\s*", "", name).strip()
                value = row.get("value") or ""
                if value:
                    formatted.append(f"{name} — {value}")
                else:
                    formatted.append(name)
            # Re-add rank prefixes so medal replacements work
            ranked = []
            for i, line in enumerate(formatted, start=1):
                ranked.append(f"{i}. {line}")
            specific_lines = "\n".join(ranked)

        replacements = {
            "1. ": "🥇 ",
            "2. ": "🥈 ",
            "3. ": "🥉 ",
            "4. ": "🏅 ",
            "5. ": "🏅 ",
        }
        for old, new in replacements.items():
            specific_lines = specific_lines.replace(old, new)

        return specific_lines

    
    def test_untitled(self):
        for attempt in range(3):
            try:
                self.driver.get("https://datamb.football/proindex/")
                break
            except Exception:
                if attempt < 2:
                    print(f"Page load failed (attempt {attempt+1}/3), retrying with fresh browser...")
                    _quit_driver(self.driver)
                    self.driver = _make_fresh_driver(headless=True)
                else:
                    raise
        time.sleep(1)
        self.driver.set_window_size(976, 860)
        assert DATAMB_EMAIL and DATAMB_PASSWORD, (
            "Set DATAMB_EMAIL and DATAMB_PASSWORD (e.g. GitHub repo secrets)."
        )

        def _index_ready(d):
            return d.execute_script(
                """
                function isVisible(el) {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity || '1') === 0) return false;
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                }
                if (isVisible(document.querySelector('input[name="eml"]'))) return false;
                if (isVisible(document.querySelector('.SFfrm button'))) return false;
                return isVisible(document.getElementById('metric-select-trigger'));
                """
            )

        # Only skip login when Index UI is actually visible (trigger can exist behind overlay)
        needs_login = True
        try:
            needs_login = not bool(_index_ready(self.driver))
        except Exception:
            needs_login = True
        if needs_login:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "eml"))
            ).send_keys(DATAMB_EMAIL)
            self.driver.find_element(By.NAME, "pwd").send_keys(DATAMB_PASSWORD)
            self.driver.find_element(By.CSS_SELECTOR, ".SFfrm button").click()
        WebDriverWait(self.driver, 45).until(_index_ready)
        WebDriverWait(self.driver, 15).until(
            lambda d: d.execute_script(
                "return document.querySelectorAll('#metric-select-list .custom-select-option, "
                "#metric-select-options .custom-select-option').length > 0"
                " && document.querySelectorAll('#position-select-options .custom-select-option').length > 0"
                " && document.querySelectorAll('#league-select-options .custom-select-option').length > 0"
            )
        )

        max_retries = 8
        tweet_text = None
        alt_text = None
        follow_up_text = None
        screenshot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshot.png")
        _FORCE_PER90 = {
            "Assists per 90",
            "Goals + Assists per 90",
            "NPG+A per 90",
            "Goals per 90",
            "Non-penalty goals per 90",
            "Headed goals per 90",
        }

        for attempt in range(max_retries):
            if attempt > 0:
                self.driver.get("https://datamb.football/proindex/")
                time.sleep(1)
                self.driver.set_window_size(976, 860)
                WebDriverWait(self.driver, 45).until(_index_ready)
                WebDriverWait(self.driver, 15).until(
                    lambda d: d.execute_script(
                        "return document.querySelectorAll('#metric-select-list .custom-select-option, "
                        "#metric-select-options .custom-select-option').length > 0"
                        " && document.querySelectorAll('#position-select-options .custom-select-option').length > 0"
                        " && document.querySelectorAll('#league-select-options .custom-select-option').length > 0"
                    )
                )

            selected_position = pick_position(POSITIONS_PLAYER, _WEIGHTS.get("position"))
            selected_league = pick_league(_WEIGHTS.get("league"))
            selected_age = pick_age(selected_position, selected_league, _WEIGHTS.get("age"))

            # Performance Index only for Premier League / La Liga + a specific position
            metric_options = filter_index_metrics(
                _INDEX_METRICS.get(selected_position) or [],
                selected_position,
                selected_league,
            )
            if not metric_options:
                raise RuntimeError(f"No index metrics configured for {selected_position}")
            forced = forced_metrics_from_env()
            if forced:
                if len(forced) != 1:
                    raise RuntimeError(f"INDEX expects 1 forced metric, got {forced}")
                selected_metric = forced[0]
            else:
                selected_metric = sample_metrics_excluded(
                    metric_options,
                    1,
                    metric_weights=metric_weights_for_position(_WEIGHTS, selected_position),
                )[0]

            _select_index_dropdown(
                self.driver,
                "metric-select-trigger",
                "metric-select-options",
                selected_metric,
                search_input_id="metricSearch",
            )
            _select_index_dropdown(
                self.driver,
                "position-select-trigger",
                "position-select-options",
                selected_position,
                extra_matches=["All"] if selected_position == "All positions" else None,
            )
            league_aliases = ["No Top 7"] if selected_league == "Outside Top 7" else None
            _select_index_dropdown(
                self.driver,
                "league-select-trigger",
                "league-select-options",
                selected_league,
                extra_matches=league_aliases,
            )
            if selected_age != "Age":
                age_value = selected_age[1:] if selected_age.startswith("U") else selected_age
                _select_index_dropdown(
                    self.driver,
                    "age-select-trigger",
                    "age-select-options",
                    selected_age,
                    extra_matches=[age_value],
                )

            # Metrics with an up/down sort toggle: 50/50 whether to flip direction.
            sort_flipped = False
            if selected_metric in SORT_TOGGLE_METRICS and random.choice([True, False]):
                try:
                    toggle_sort = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.ID, "toggleSort"))
                    )
                    self.driver.execute_script("arguments[0].click();", toggle_sort)
                    sort_flipped = True
                except Exception as e:
                    print(f"Could not click toggle sort: {e}")

            # Default UI is per 90; click toggleMetrics to switch to season totals.
            # Keep these counting metrics on per 90 for the screenshot.
            if selected_metric not in _FORCE_PER90:
                toggle_metrics_btn = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.ID, "toggleMetrics"))
                )
                self.driver.execute_script("arguments[0].scrollIntoView(true);", toggle_metrics_btn)
                self.driver.execute_script("arguments[0].click();", toggle_metrics_btn)
                time.sleep(0.5)

            self.driver.execute_script("""
    document.documentElement.style.overflow = 'hidden';  // Hide horizontal and vertical scroll bars
    document.body.style.overflow = 'hidden';  // Hide scroll bars on body
    var resultContainer = document.querySelector('.result-container');
    if (resultContainer) {
        resultContainer.style.overflow = 'hidden';  // Hide scroll bars on result-container div
    }
""")

            # Inject a dummy div at the top left and move mouse to it to avoid hover effect
            self.driver.execute_script("""
                if (!document.getElementById('dummy-mouse-target')) {
                    var d = document.createElement('div');
                    d.id = 'dummy-mouse-target';
                    d.style.position = 'fixed';
                    d.style.left = '0px';
                    d.style.top = '0px';
                    d.style.width = '1px';
                    d.style.height = '1px';
                    d.style.zIndex = '99999';
                    d.style.background = 'transparent';
                    document.body.appendChild(d);
                }
            """)
            dummy = self.driver.find_element(By.ID, "dummy-mouse-target")
            ActionChains(self.driver).move_to_element(dummy).perform()

            # Hide the dark-mode-toggle before taking the screenshot
            self.driver.execute_script("""
                var dmt = document.querySelector('.dark-mode-toggle');
                if (dmt) dmt.style.display = 'none';
            """)

            # Ensure login overlay is gone and ranked rows are painted before capture
            WebDriverWait(self.driver, 20).until(
                lambda d: d.execute_script(
                    """
                    function isVisible(el) {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden') return false;
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    }
                    if (isVisible(document.querySelector('input[name="eml"]'))) return false;
                    return document.querySelectorAll('#playerTable .player-row').length > 0;
                    """
                )
            )

            if is_percent_metric(selected_metric) and index_has_player_at_100_percent(self.driver):
                print(
                    f"  reject: player at 100% on {selected_metric!r} "
                    f"(attempt {attempt + 1}/{max_retries})",
                    flush=True,
                )
                continue

            # Save screenshot
            self.driver.save_screenshot('screenshot.png')
            specific_text = self.capture_first_five_lines()
            self._selection = {
                "bot": "index",
                "position": selected_position,
                "league": selected_league,
                "age": selected_age,
                "metric": selected_metric,
                "metrics": [selected_metric],
                "sort_flipped": sort_flipped,
                "top5": specific_text,
            }

            # Crop 5px from top, left, and right
            img = Image.open('screenshot.png')
            width, height = img.size
            cropped = img.crop((11, 0, width - 11, height - 5))
            cropped.save('screenshot.png')

            metric_label = selected_metric.replace(" per 90", "")
            position_label = selected_position.replace("er", "ers")
            position_label = position_label.replace("ack", "acks")
            position_label = position_label.replace("All positions", "Players")
            age_label = selected_age.replace("Age", "")
            tweet_text = f"{selected_league} {age_label} {position_label} : {metric_label}\n\n{specific_text}\n\n📊 Free trial: datamb.football"
            tweet_text = tweet_text.replace("  ", " ")
            tweet_text = tweet_text.replace(" Wanderers", "")
            tweet_text = tweet_text.replace("Borussia ", "")
            tweet_text = tweet_text.replace("Deportivo ", "")
            tweet_text = tweet_text.replace("Manchester", "Man")
            tweet_text = tweet_text.replace(" Hotspur", "")
            tweet_text = tweet_text.replace("West Ham United", "West Ham")
            tweet_text = tweet_text.replace("Celta de", "Celta")
            tweet_text = tweet_text.replace("Olympique Lyonnais", "Lyon")
            tweet_text = tweet_text.replace("Olympique Marseille", "Marseille")
            tweet_text = tweet_text.replace("Fortuna ", "")
            tweet_text = tweet_text.replace("Eintracht ", "")
            tweet_text = tweet_text.replace("Newcastle United", "Newcastle")
            tweet_text = tweet_text.replace("Wingers", "Wingers & Att Mid")
            tweet_text = tweet_text.replace("Goals - xG", "Goals minus xG")
            tweet_text = tweet_text.replace("Assists - xA", "Assists minus xA")
            tweet_text = tweet_text.replace("All Leagues", "🌍 All Leagues")
            tweet_text = tweet_text.replace("Outside Top 7", "🌍 Outside Top 7")
            tweet_text = tweet_text.replace("South America", "🌎 South America")
            tweet_text = tweet_text.replace("Top 7 Leagues", "🇪🇺 Top 7 League")
            tweet_text = tweet_text.replace("Top 5 Leagues", "🇪🇺 Top 5 League")
            tweet_text = tweet_text.replace("Premier League", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League")
            tweet_text = tweet_text.replace("La Liga", "🇪🇸 La Liga")
            tweet_text = tweet_text.replace("Bundesliga", "🇩🇪 Bundesliga")
            tweet_text = tweet_text.replace("Serie A", "🇮🇹 Serie A")

            alt_text = (
                "This is an automated tweet 🤖\n\nPosition, league, age and metrics were chosen randomly in the 2026/27 dataset.\n\n"
                "Player age and team refer to their age and team during the season.\n\nPositions are determined via the player's average heat map.\n\n"
                "Join the free trial for more leagues and tools!"
            )
            follow_up_text = "Compare Top 7 League players, or join the free trial for more leagues, metrics, and tools ⤵️ datamb.football"
            self._buffer_post_text = tweet_text
            self._buffer_image_path = screenshot_path
            self._buffer_alt_text = alt_text
            self._buffer_reply_text = follow_up_text
            break
        else:
            raise RuntimeError(
                f"Failed after {max_retries} attempts (player at 100% on a % metric)"
            )

        schedule_twitter_post_via_buffer(
            None,
            tweet_text,
            screenshot_path,
            alt_text=alt_text,
            reply_text=follow_up_text,
            schedule_minutes=180,
        )
        print("Post scheduled via Buffer API (~3 hours from now).")

        


if __name__ == "__main__":
    pytest.main()