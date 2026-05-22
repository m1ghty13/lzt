from playwright.sync_api import sync_playwright, TimeoutError
from kameleo.local_api_client import KameleoLocalApiClient
from kameleo.local_api_client.models import CreateProfileRequest, ProxyChoice, Server
import os
import re
import time
import random
import sys
import logging
import requests

# ---- Global speed factor for delays ----
# IMPORTANT: Session expires in 20 minutes, so speed matters!
# 1.0 = normal speed (slower, more human-like)
# 0.5 = 2x faster (recommended to stay within 20 min limit)
SPEED_FACTOR = 1
RESULTS_FOLDER = r"C:\Users\gogog\Downloads\Xivora\LZT\results"

# CAPTCHA Config
CAPTCHA_API_KEY   = "852675d7f72a99e3047e8ba106177696"  # 2Captcha key (не решает managed CF)
ANTICAPTCHA_KEY   = ""   # anti-captcha.com — вставь сюда свой ключ
CAPSOLVER_API_KEY = ""   # capsolver.com — опционально
PROXY_STRING = "38.49.216.136:34181:DVS6xh9vgn:pVa387P"  # SOCKS5 proxy

# ---- Logging setup ----
def setup_logging(file_number: int):
    """Setup logging for this instance"""
    log_file = os.path.join(RESULTS_FOLDER, f"log_{file_number}.txt")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ],
        force=True
    )
    return logging.getLogger(__name__)

# ---- Timing functions ----
def random_delay(multiplier=2.5, base_min=0.1, base_max=0.4):
    time.sleep(random.uniform(base_min * multiplier, base_max * multiplier) * SPEED_FACTOR)

def button_delay():
    base_min, base_max = 2.0, 5.0
    time.sleep(random.uniform(base_min, base_max) * SPEED_FACTOR)

def field_pause():
    """Pause between filling fields, like a human moving to the next input."""
    time.sleep(random.uniform(0.6, 1.6) * SPEED_FACTOR)

def think_pause():
    """Longer pause, like a human reading or thinking before typing."""
    # Reduced - session expires in 20 minutes!
    time.sleep(random.uniform(0.3, 0.8) * SPEED_FACTOR)

def human_type(page, selector, text, click_first=True):
    """Type text one character at a time with small randomized delays."""
    if not text:
        return
    if click_first:
        page.click(selector)
        time.sleep(random.uniform(0.15, 0.45) * SPEED_FACTOR)
    for ch in text:
        page.keyboard.type(ch)
        # Slightly longer pause after spaces / punctuation
        if ch in ' .@_-':
            time.sleep(random.uniform(0.10, 0.25) * SPEED_FACTOR)
        else:
            time.sleep(random.uniform(0.04, 0.14) * SPEED_FACTOR)
    time.sleep(random.uniform(0.2, 0.5) * SPEED_FACTOR)

def random_scroll(page, pixels=150):
    """Random page scrolling (humanization)"""
    try:
        page.evaluate(f"window.scrollBy(0, {pixels})")
        time.sleep(random.uniform(0.5, 1.5) * SPEED_FACTOR)
    except:
        pass

# ---- Date picking functions ----
def pick_creation_and_membership_for_username_login():
    month_names = [
        'January','February','March','April','May','June',
        'July','August','September','October','November','December'
    ]
    # Creation date: 2005-2007
    creation_year = random.randint(2005, 2007)
    creation_month_index = random.randint(1, 12)
    creation_month = month_names[creation_month_index - 1]
    creation_year_str = str(creation_year)

    # Membership date: 2009-2010, ensuring it's after creation date
    membership_year = random.randint(2009, 2010)
    if membership_year == creation_year:
        membership_month_index = random.randint(creation_month_index + 1, 12)
        if membership_month_index > 12:
            membership_month_index = 1
            membership_year = creation_year + 1
    else:
        membership_month_index = random.randint(1, 12)

    membership_month = month_names[membership_month_index - 1]
    membership_year_str = str(membership_year)

    return creation_month, creation_year_str, membership_month, membership_year_str

def pick_creation_and_membership_for_email_like_username():
    month_names = [
        'January','February','March','April','May','June',
        'July','August','September','October','November','December'
    ]
    # Creation date: 2013-2014
    creation_year = random.randint(2013, 2014)
    creation_month_index = random.randint(1, 12)
    creation_month = month_names[creation_month_index - 1]
    creation_year_str = str(creation_year)

    # Membership date: 2015-2016, ensuring it's after creation date
    membership_year = random.randint(2015, 2016)
    if membership_year == creation_year:
        membership_month_index = random.randint(creation_month_index + 1, 12)
        if membership_month_index > 12:
            membership_month_index = 1
            membership_year = creation_year + 1
    else:
        membership_month_index = random.randint(1, 12)

    membership_month = month_names[membership_month_index - 1]
    membership_year_str = str(membership_year)

    return creation_month, creation_year_str, membership_month, membership_year_str

# ---- Read account file ----
def read_account_file(file_number=1):
    file_path = os.path.join(RESULTS_FOLDER, f"{file_number}.txt")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} not found.")

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.rstrip() for line in f.read().splitlines()]

    proxy_line = next((l for l in reversed(lines) if l.count('.') == 3 and ':' in l), None)
    if not proxy_line:
        raise ValueError("No valid proxy found in file.")

    account_lines = lines[:lines.index(proxy_line)]
    while len(account_lines) < 11:
        account_lines.append("")

    parts = proxy_line.split(":")
    proxy_host, proxy_port_str, proxy_user, proxy_pass = parts

    return {
        "stored_username": account_lines[0],
        "mail_account": account_lines[1],
        "password1": account_lines[2],
        "password2": account_lines[3],
        "payment_email_address": account_lines[4],
        "postcode": account_lines[5],
        "creation_month": account_lines[6],
        "creation_year": account_lines[7],
        "country": account_lines[8],
        "state": account_lines[9],
        "isp": account_lines[10],
        "proxy_host": proxy_host,
        "proxy_port": int(proxy_port_str),
        "proxy_user": proxy_user,
        "proxy_pass": proxy_pass
    }

# ---- CAPTCHA Handling ----
def get_turnstile_sitekey(page, logger) -> str:
    """Извлечь sitekey со страницы"""
    # Метод 1: _cf_chl_opt.IThaC9 — самый надёжный для Cloudflare WAF
    try:
        page.wait_for_function("!!window._cf_chl_opt?.IThaC9", timeout=3000)
        key = page.evaluate("window._cf_chl_opt.IThaC9")
        if key:
            logger.info(f"[SITEKEY] Found via _cf_chl_opt.IThaC9: {key}")
            return key
    except Exception:
        pass

    # Метод 2: regex на URL фреймов challenges.cloudflare.com
    try:
        for frame in page.frames:
            if "challenges.cloudflare.com" in frame.url:
                m = re.search(r"/(0x[A-Za-z0-9]{10,})/", frame.url)
                if m:
                    logger.info(f"[SITEKEY] Found via frame URL: {m.group(1)}")
                    return m.group(1)
    except Exception:
        pass

    # Метод 3: ждём iframe и ищем через JS
    try:
        page.wait_for_function(
            "() => document.querySelectorAll('iframe').length > 0",
            timeout=10000
        )
        time.sleep(1)
    except Exception:
        logger.warning("[SITEKEY] Timeout waiting for iframe - continuing anyway")

    try:
        sitekey = page.evaluate("""
            () => {
                // data-sitekey атрибут
                let el = document.querySelector('[data-sitekey]');
                if (el) return el.getAttribute('data-sitekey');

                // iframe src атрибут
                for (let iframe of document.querySelectorAll('iframe')) {
                    let src = iframe.src || '';
                    let m = src.match(/(0x[A-Za-z0-9]{10,})/);
                    if (m) return m[1];
                    m = src.match(/[?&]k=([A-Za-z0-9_-]+)/);
                    if (m) return m[1];
                }

                // window globals
                if (window._cf_chl_opt) {
                    let o = window._cf_chl_opt;
                    return o.IThaC9 || o.websiteKey || o.sitekey || null;
                }

                return null;
            }
        """)
        if sitekey:
            logger.info(f"[SITEKEY] Found via JS: {sitekey}")
            return sitekey
    except Exception as e:
        logger.debug(f"[SITEKEY] JS extraction error: {e}")

    logger.warning("[SITEKEY] Sitekey not found")
    return None

def check_2captcha_balance(logger) -> float | None:
    """Проверить баланс и валидность API-ключа. Возвращает баланс или None."""
    try:
        resp = requests.post(
            "https://api.2captcha.com/getBalance",
            json={"clientKey": CAPTCHA_API_KEY},
            timeout=10,
        ).json()
        if resp.get("errorId"):
            logger.error(f"[2captcha] Ключ невалиден: {resp.get('errorDescription')} (errorId={resp.get('errorId')})")
            return None
        balance = resp.get("balance", 0)
        logger.info(f"[2captcha] Баланс: ${balance:.4f}")
        return balance
    except Exception as e:
        logger.error(f"[2captcha] Не удалось проверить баланс: {e}")
        return None


def _submit_2captcha_task(task: dict, logger) -> str | None:
    """Submit task to 2captcha and poll until ready. Returns token or None."""
    import json as _json
    body = {"clientKey": CAPTCHA_API_KEY, "task": task}
    logger.info(f"[2captcha] Запрос: {_json.dumps(body, ensure_ascii=False)}")
    resp = requests.post(
        "https://api.2captcha.com/createTask",
        json=body,
        timeout=30,
    ).json()
    logger.info(f"[2captcha] Ответ createTask: {resp}")

    if resp.get("errorId"):
        logger.warning(f"[2captcha] Submit error ({resp.get('errorId')}): {resp.get('errorDescription')}")
        return None

    task_id = resp.get("taskId")
    if not task_id:
        logger.warning(f"[2captcha] Нет taskId в ответе: {resp}")
        return None

    logger.info(f"[2captcha] Task {task_id} — ожидание решения...")
    for attempt in range(36):
        time.sleep(5)
        result = requests.post(
            "https://api.2captcha.com/getTaskResult",
            json={"clientKey": CAPTCHA_API_KEY, "taskId": task_id},
            timeout=30,
        ).json()

        if result.get("errorId"):
            logger.warning(f"[2captcha] Poll error: {result.get('errorDescription')}")
            return None

        if result.get("status") == "ready":
            token = result.get("solution", {}).get("token")
            if token:
                logger.info(f"[2captcha] Токен получен: {token[:40]}...")
                return token
            logger.warning(f"[2captcha] Нет токена в решении: {result}")
            return None

        if attempt % 6 == 0:
            logger.info(f"[2captcha] Ожидание... {attempt * 5}s")

    logger.warning("[2captcha] Таймаут (3 минуты)")
    return None


def _solve_via_anticaptcha(page_url: str, sitekey: str, logger,
                            pagedata=None) -> str | None:
    """Решить Cloudflare Turnstile/Managed Challenge через Anti-Captcha."""
    if not ANTICAPTCHA_KEY:
        return None
    try:
        task = {
            "type": "TurnstileTaskProxyless",
            "websiteURL": page_url,
            "websiteKey": sitekey,
        }
        if pagedata:
            task["pagedata"] = pagedata

        logger.info(f"[AntiCaptcha] Отправка задачи sitekey={sitekey[:20]}...")
        resp = requests.post(
            "https://api.anti-captcha.com/createTask",
            json={"clientKey": ANTICAPTCHA_KEY, "task": task},
            timeout=30,
        ).json()
        logger.info(f"[AntiCaptcha] Ответ createTask: {resp}")

        if resp.get("errorId"):
            logger.warning(f"[AntiCaptcha] Ошибка: {resp.get('errorDescription')}")
            return None

        task_id = resp.get("taskId")
        if not task_id:
            logger.warning(f"[AntiCaptcha] Нет taskId: {resp}")
            return None

        logger.info(f"[AntiCaptcha] Task {task_id} — ожидание...")
        for attempt in range(36):
            time.sleep(5)
            result = requests.post(
                "https://api.anti-captcha.com/getTaskResult",
                json={"clientKey": ANTICAPTCHA_KEY, "taskId": task_id},
                timeout=30,
            ).json()
            if result.get("errorId"):
                logger.warning(f"[AntiCaptcha] Poll error: {result.get('errorDescription')}")
                return None
            if result.get("status") == "ready":
                token = result.get("solution", {}).get("token")
                if token:
                    logger.info(f"[AntiCaptcha] Токен получен: {token[:40]}...")
                    return token
                logger.warning(f"[AntiCaptcha] Нет токена: {result}")
                return None
            if attempt % 6 == 0:
                logger.info(f"[AntiCaptcha] Ожидание... {attempt * 5}s")
        logger.warning("[AntiCaptcha] Таймаут")
        return None
    except Exception as e:
        logger.error(f"[AntiCaptcha] Ошибка: {e}")
        return None


def _clean_cf_url(page_url: str) -> str:
    """Убрать CF-challenge токены из URL перед отправкой в сервис решения."""
    from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
    parsed = urlparse(page_url)
    drop = {"__cf_chl_rt_tk", "__cf_chl_f_tk", "cf_chl_captcha_tk"}
    qs = {k: v for k, v in parse_qs(parsed.query).items() if k not in drop}
    return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))


def _solve_via_capsolver(page_url: str, sitekey: str, logger,
                         pagedata=None) -> str | None:
    """Решить managed Cloudflare challenge через CapSolver."""
    if not CAPSOLVER_API_KEY:
        return None
    try:
        task = {
            "type": "AntiTurnstileTaskProxyLess",
            "websiteURL": page_url,
            "websiteKey": sitekey,
            "metadata": {"action": "managed"},
        }
        if pagedata:
            task["metadata"]["chlPageData"] = pagedata

        logger.info(f"[CapSolver] Отправка задачи sitekey={sitekey[:20]}...")
        resp = requests.post(
            "https://api.capsolver.com/createTask",
            json={"clientKey": CAPSOLVER_API_KEY, "task": task},
            timeout=30,
        ).json()

        if resp.get("errorId"):
            logger.warning(f"[CapSolver] Ошибка: {resp.get('errorDescription')}")
            return None

        task_id = resp.get("taskId")
        if not task_id:
            logger.warning(f"[CapSolver] Нет taskId: {resp}")
            return None

        logger.info(f"[CapSolver] Task {task_id} — ожидание...")
        for attempt in range(36):
            time.sleep(5)
            result = requests.post(
                "https://api.capsolver.com/getTaskResult",
                json={"clientKey": CAPSOLVER_API_KEY, "taskId": task_id},
                timeout=30,
            ).json()
            if result.get("errorId"):
                logger.warning(f"[CapSolver] Poll error: {result.get('errorDescription')}")
                return None
            if result.get("status") == "ready":
                token = result.get("solution", {}).get("token")
                if token:
                    logger.info(f"[CapSolver] Токен получен: {token[:40]}...")
                    return token
                return None
            if attempt % 6 == 0:
                logger.info(f"[CapSolver] Ожидание... {attempt * 5}s")
        logger.warning("[CapSolver] Таймаут")
        return None
    except Exception as e:
        logger.error(f"[CapSolver] Ошибка: {e}")
        return None


def _solve_via_2captcha_form(page_url: str, sitekey: str, logger) -> str | None:
    """Попытка через старый form-encoded API 2captcha (другой путь валидации)."""
    try:
        logger.info("[2captcha-form] Отправка через in.php...")
        resp = requests.post(
            "https://2captcha.com/in.php",
            data={
                "key": CAPTCHA_API_KEY,
                "method": "turnstile",
                "sitekey": sitekey,
                "pageurl": page_url,
                "json": "1",
            },
            timeout=30,
        ).json()
        logger.info(f"[2captcha-form] Ответ: {resp}")

        if resp.get("status") != 1:
            logger.warning(f"[2captcha-form] Ошибка: {resp.get('request')}")
            return None

        task_id = resp["request"]
        logger.info(f"[2captcha-form] Task {task_id} — ожидание...")
        for attempt in range(36):
            time.sleep(5)
            result = requests.get(
                "https://2captcha.com/res.php",
                params={"key": CAPTCHA_API_KEY, "action": "get", "id": task_id, "json": "1"},
                timeout=30,
            ).json()
            if result.get("status") == 1:
                token = result.get("request")
                logger.info(f"[2captcha-form] Токен: {token[:40]}...")
                return token
            if result.get("request") == "CAPCHA_NOT_READY":
                if attempt % 6 == 0:
                    logger.info(f"[2captcha-form] Ожидание... {attempt * 5}s")
                continue
            logger.warning(f"[2captcha-form] Ошибка: {result}")
            return None
        logger.warning("[2captcha-form] Таймаут")
        return None
    except Exception as e:
        logger.error(f"[2captcha-form] Ошибка: {e}")
        return None


def solve_cloudflare_api(page_url: str, sitekey: str, logger,
                         proxy_host: str = None, proxy_port: int = None,
                         proxy_user: str = None, proxy_pass: str = None,
                         pagedata: str = None) -> str:
    """Решить Cloudflare Turnstile/Managed Challenge.

    Порядок попыток:
    1. CapSolver (AntiTurnstileTaskProxyLess) — лучший для managed challenge
    2. 2captcha JSON API (TurnstileTask http → socks5 → ProxyLess)
    3. 2captcha form API (in.php) — другой путь валидации
    """
    clean_url = _clean_cf_url(page_url)
    logger.info(f"[captcha] URL: {clean_url}  sitekey: {sitekey[:20]}  pagedata: {'да' if pagedata else 'нет'}")

    # 1. Anti-Captcha (лучший для managed CF challenge)
    if ANTICAPTCHA_KEY:
        token = _solve_via_anticaptcha(clean_url, sitekey, logger, pagedata)
        if token:
            return token
        logger.info("[captcha] Anti-Captcha не сработал — пробуем следующий...")

    # 2. CapSolver
    if CAPSOLVER_API_KEY:
        token = _solve_via_capsolver(clean_url, sitekey, logger, pagedata)
        if token:
            return token
        logger.info("[captcha] CapSolver не сработал — пробуем 2captcha JSON...")

    # 2. 2captcha JSON API
    if CAPTCHA_API_KEY:
        balance = check_2captcha_balance(logger)
        if balance and balance >= 0.001:
            common = {"websiteURL": clean_url, "websiteKey": sitekey}
            if pagedata:
                common["pagedata"] = pagedata

            json_attempts = []
            if proxy_host and proxy_port:
                px = {"proxyAddress": proxy_host, "proxyPort": int(proxy_port)}
                if proxy_user: px["proxyLogin"] = proxy_user
                if proxy_pass: px["proxyPassword"] = proxy_pass
                json_attempts.append({"type": "TurnstileTask", "proxyType": "http",   **common, **px})
                json_attempts.append({"type": "TurnstileTask", "proxyType": "socks5", **common, **px})
            json_attempts.append({"type": "TurnstileTaskProxyless", **common})

            for task in json_attempts:
                try:
                    token = _submit_2captcha_task(task, logger)
                    if token:
                        return token
                    logger.info(f"[2captcha] {task['type']} не сработал")
                except Exception as e:
                    logger.error(f"[2captcha] {task.get('type')}: {e}")

        # 3. 2captcha form API
        token = _solve_via_2captcha_form(clean_url, sitekey, logger)
        if token:
            return token

    logger.warning("[captcha] Все сервисы исчерпаны")
    return None

def inject_turnstile_token(page, token: str, logger) -> bool:
    """Вставить Turnstile токен в страницу и отправить форму"""
    try:
        logger.info("[inject] Вставляем токен...")
        result = page.evaluate(f"""
            (() => {{
                const token = {repr(token)};

                // Метод 1: hidden input с native setter (обходит React/Vue проверку)
                const input = document.querySelector('input[name="cf-turnstile-response"]');
                if (input) {{
                    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')
                        .set.call(input, token);
                    input.dispatchEvent(new Event('input', {{bubbles: true}}));
                    input.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}

                // Метод 2: именованный callback на виджете
                const widget = document.querySelector('[data-sitekey][data-callback]');
                if (widget) {{
                    const cb = widget.dataset.callback;
                    if (typeof window[cb] === 'function') {{
                        window[cb](token);
                        return 'callback:' + cb;
                    }}
                }}

                // Метод 3: window.tsCallback / глобальный callback
                if (typeof window.tsCallback === 'function') {{
                    window.tsCallback(token);
                    return 'tsCallback';
                }}

                // Метод 4: submit формы
                const form = document.querySelector('form');
                if (form) {{
                    form.submit();
                    return 'form_submitted';
                }}

                return input ? 'input_set' : 'no_action';
            }})()
        """)
        logger.info(f"[inject] Результат: {result}")
        return True
    except Exception as e:
        logger.error(f"[inject] Ошибка: {e}")
        return False

def diagnose_page_structure(page, logger):
    """Examine the page structure to help diagnose CAPTCHA issues"""
    try:
        logger.info("[CAPTCHA] ===== PAGE DIAGNOSTIC START =====")

        # Check title
        try:
            title = page.title()
            logger.info(f"[CAPTCHA] Page title: {title}")
        except:
            pass

        # Check URL
        try:
            url = page.url
            logger.info(f"[CAPTCHA] Current URL: {url}")
        except:
            pass

        # Check for iframes
        try:
            iframes_count = page.evaluate("() => document.querySelectorAll('iframe').length")
            logger.info(f"[CAPTCHA] Iframes on page: {iframes_count}")

            # List iframe sources
            iframe_srcs = page.evaluate("""
                () => {
                    let iframes = document.querySelectorAll('iframe');
                    return Array.from(iframes).map((f, i) => ({
                        index: i,
                        id: f.id || 'NO_ID',
                        src: f.src || f.getAttribute('src') || 'NO_SRC'
                    }));
                }
            """)
            for iframe_info in iframe_srcs:
                logger.info(f"[CAPTCHA]   Iframe {iframe_info['index']} (id={iframe_info['id']}): {iframe_info['src'][:80]}")
        except Exception as e:
            logger.debug(f"[CAPTCHA] Could not enumerate iframes: {e}")

        # Check for visible text containing "verify" or "human"
        try:
            body_text = page.evaluate("""
                () => document.body.innerText.toLowerCase()
            """)
            has_verify = 'verify' in body_text
            has_human = 'human' in body_text
            logger.info(f"[CAPTCHA] Page text check: has_verify={has_verify}, has_human={has_human}")
            if has_verify or has_human:
                # Show some of the text
                text_preview = body_text[:200]
                logger.info(f"[CAPTCHA] Text preview: {text_preview}")
        except:
            pass

        # Check for checkbox elements
        try:
            checkbox_info = page.evaluate("""
                () => {
                    let checks = document.querySelectorAll('input[type="checkbox"]');
                    return {
                        count: checks.length,
                        details: Array.from(checks).map(c => ({
                            id: c.id || 'no-id',
                            class: c.className || 'no-class',
                            parent: c.parentElement?.className || 'no-parent'
                        }))
                    };
                }
            """)
            logger.info(f"[CAPTCHA] Checkbox inputs: {checkbox_info['count']}")
            if checkbox_info['count'] > 0:
                for detail in checkbox_info['details']:
                    logger.info(f"[CAPTCHA]   Checkbox: id={detail['id']}, class={detail['class']}")
        except:
            pass

        # Check for visible elements
        try:
            visible_elements = page.evaluate("""
                () => {
                    let divs = document.querySelectorAll('div[style*="display"], div[class*="show"], div[role="dialog"]');
                    return divs.length;
                }
            """)
            logger.info(f"[CAPTCHA] Visible containers: {visible_elements}")
        except:
            pass

        logger.info("[CAPTCHA] ===== PAGE DIAGNOSTIC END =====")

    except Exception as e:
        logger.debug(f"[CAPTCHA] Diagnostic error: {e}")


def try_click_turnstile_checkbox(page, logger) -> bool:
    """Try to find and click the Turnstile checkbox using multiple strategies"""
    try:
        logger.info("[CAPTCHA] Attempting to find and click Turnstile checkbox...")

        # Strategy 1: Try to find checkbox by label text "Verify you are human"
        try:
            logger.debug("[CAPTCHA] Trying to find by label text...")
            verify_label = page.locator('text=Verify you are human')
            if verify_label.count() > 0:
                logger.info("[CAPTCHA] Found 'Verify you are human' label")
                # The actual checkbox is usually right before the text
                parent = verify_label.locator('xpath=./ancestor::*[contains(@class, "cds-checkboxControl-checkboxLabel") or contains(@class, "mark")]')
                if parent.count() > 0:
                    logger.info("[CAPTCHA] Found parent container, clicking...")
                    parent.click()
                    time.sleep(2)
                    return True
        except Exception as e:
            logger.debug(f"[CAPTCHA] Label text strategy failed: {e}")

        # Strategy 2: Try all iframes with Cloudflare content
        try:
            logger.debug("[CAPTCHA] Trying iframe search...")
            iframes = page.query_selector_all('iframe')
            logger.info(f"[CAPTCHA] Found {len(iframes)} iframes")

            for i, iframe in enumerate(iframes):
                try:
                    src = iframe.get_attribute('src') or ''
                    logger.debug(f"[CAPTCHA] Iframe {i}: {src[:60]}")

                    # Look for checkbox in this iframe
                    try:
                        frame = page.frame_locator(f'iframe >> nth={i}')

                        # Try different selectors
                        selectors = [
                            'input[type="checkbox"]',
                            '[role="checkbox"]',
                            'label > input',
                            '.cds-checkboxWrapper__checkboxInput',
                        ]

                        for selector in selectors:
                            try:
                                checkbox = frame.locator(selector)
                                if checkbox.count() > 0:
                                    logger.info(f"[CAPTCHA] Found checkbox in iframe {i} with selector: {selector}")
                                    checkbox.click()
                                    time.sleep(2)
                                    return True
                            except:
                                continue
                    except:
                        continue

                except Exception as e:
                    logger.debug(f"[CAPTCHA] Iframe {i} error: {e}")
                    continue

        except Exception as e:
            logger.debug(f"[CAPTCHA] Iframe strategy error: {e}")

        # Strategy 3: Try JavaScript-based clicking
        try:
            logger.debug("[CAPTCHA] Trying JavaScript-based click...")
            result = page.evaluate("""
                () => {
                    // Try to find and click checkbox
                    let checkbox = document.querySelector('input[type="checkbox"]');
                    if (checkbox) {
                        checkbox.click();
                        checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                        return 'checkbox_found';
                    }

                    // Try finding by aria-label
                    let ariaCheckbox = document.querySelector('[aria-label*="Verify"]');
                    if (ariaCheckbox) {
                        ariaCheckbox.click();
                        return 'aria_found';
                    }

                    return 'not_found';
                }
            """)
            logger.info(f"[CAPTCHA] JavaScript click result: {result}")
            time.sleep(2)
            if result != 'not_found':
                return True
        except Exception as e:
            logger.debug(f"[CAPTCHA] JavaScript click error: {e}")

        # Strategy 4: Try keyboard-based interaction (Tab + Space to activate checkbox)
        try:
            logger.debug("[CAPTCHA] Trying keyboard-based activation...")
            # Tab to focus on checkbox
            page.keyboard.press('Tab')
            time.sleep(0.5)
            # Space to check
            page.keyboard.press('Space')
            logger.info("[CAPTCHA] Keyboard activation attempted")
            time.sleep(2)
            return True
        except Exception as e:
            logger.debug(f"[CAPTCHA] Keyboard activation error: {e}")

        logger.info("[CAPTCHA] Could not find checkbox with any method")
        return False

    except Exception as e:
        logger.debug(f"[CAPTCHA] Error in try_click_turnstile_checkbox: {e}")
        return False


def try_click_by_coordinates(page, logger) -> bool:
    """Try to click the checkbox by approximate coordinates"""
    try:
        logger.info("[CAPTCHA] Attempting to click by coordinates...")

        viewport = page.viewport_size
        if not viewport:
            logger.debug("[CAPTCHA] Could not get viewport size")
            return False

        logger.info(f"[CAPTCHA] Viewport: {viewport['width']}x{viewport['height']}")

        # Cloudflare widget appears on the right side of the page
        # The checkbox is typically positioned at:
        # X: 70-80% from left (right side of page)
        # Y: 40-60% from top (vertically centered)

        positions_to_try = [
            # Right side positions (where Cloudflare widget usually is)
            (int(viewport['width'] * 0.75), int(viewport['height'] * 0.5)),  # Right-center
            (int(viewport['width'] * 0.8), int(viewport['height'] * 0.5)),   # Further right
            (int(viewport['width'] * 0.7), int(viewport['height'] * 0.5)),   # Slightly right
            (int(viewport['width'] * 0.5), int(viewport['height'] * 0.5)),   # Center

            # Center area (fallback)
            (int(viewport['width'] * 0.5), int(viewport['height'] * 0.45)),
            (int(viewport['width'] * 0.5), int(viewport['height'] * 0.55)),

            # Left side (less likely but try)
            (int(viewport['width'] * 0.25), int(viewport['height'] * 0.5)),
        ]

        for attempt, (x, y) in enumerate(positions_to_try):
            logger.info(f"[CAPTCHA] Click attempt {attempt + 1}: coordinates ({x}, {y})...")
            try:
                page.mouse.click(x, y)
                time.sleep(1.5)

                # Check if page advanced
                title = page.title()
                url = page.url

                title_ok = "Just a moment" not in title
                url_ok = "cf_chl_rt_tk" not in url

                logger.debug(f"[CAPTCHA] After click: title_ok={title_ok}, url_ok={url_ok}")

                if title_ok and url_ok:
                    logger.info(f"[CAPTCHA] Success! Page advanced at coordinates ({x}, {y})")
                    return True
            except Exception as e:
                logger.debug(f"[CAPTCHA] Click attempt {attempt + 1} error: {e}")
                continue

        logger.info("[CAPTCHA] No coordinates worked")
        return False

    except Exception as e:
        logger.debug(f"[CAPTCHA] Error in try_click_by_coordinates: {e}")
        return False


def is_challenge_page(page) -> bool:
    """Проверить, открыта ли страница Cloudflare Challenge"""
    try:
        title = page.title()
        if any(t in title for t in ("Just a moment", "Checking your Browser", "Are you a robot")):
            return True
    except Exception:
        pass
    try:
        if page.locator("iframe[src*='challenges.cloudflare.com']").count() > 0:
            return True
        if any("challenges.cloudflare.com" in f.url for f in page.frames):
            return True
    except Exception:
        pass
    return False


def handle_cloudflare_turnstile(page, logger, account_data: dict = None) -> bool:
    """Решить Cloudflare Turnstile через 2captcha (с fallback на ручное решение)"""
    try:
        logger.info("[CAPTCHA] Проверка Cloudflare Challenge...")
        if not is_challenge_page(page):
            logger.info("[CAPTCHA] Челлендж не обнаружен")
            return True

        logger.info("[CAPTCHA] Челлендж обнаружен — запускаем 2captcha...")
        diagnose_page_structure(page, logger)

        # Ждём пока Cloudflare JS загрузит _cf_chl_opt (нужен для pagedata и sitekey)
        try:
            page.wait_for_function(
                "() => !!(window._cf_chl_opt?.chlPageData || window._cf_chl_opt?.IThaC9 "
                "|| document.querySelectorAll('iframe').length > 0)",
                timeout=15000,
            )
            logger.info("[CAPTCHA] _cf_chl_opt / iframes готовы")
        except Exception:
            logger.warning("[CAPTCHA] Ждать дальше некуда — пробуем с тем что есть")
        time.sleep(1)

        # Извлекаем sitekey + pagedata из _cf_chl_opt одним вызовом
        cf_params = {}
        try:
            cf_params = page.evaluate("""
                () => {
                    const o = window._cf_chl_opt || {};
                    return {
                        sitekey:  o.IThaC9      || null,
                        pagedata: o.chlPageData  || null,
                        action:   o.cType        || null,
                        cdata:    o.cData        || null,
                    };
                }
            """) or {}
            logger.info(f"[CAPTCHA] _cf_chl_opt: sitekey={bool(cf_params.get('sitekey'))} "
                        f"pagedata={bool(cf_params.get('pagedata'))} "
                        f"action={cf_params.get('action')}")
        except Exception as e:
            logger.debug(f"[CAPTCHA] Не удалось прочитать _cf_chl_opt: {e}")

        sitekey = cf_params.get("sitekey") or get_turnstile_sitekey(page, logger)
        pagedata = cf_params.get("pagedata")

        if not sitekey:
            logger.warning("[CAPTCHA] Sitekey не найден — ждём ручного решения")
            return wait_manual_captcha(page, logger)

        logger.info(f"[CAPTCHA] sitekey={sitekey}  pagedata={'да' if pagedata else 'нет'}")

        # Прокси из account_data
        proxy_host = proxy_port = proxy_user = proxy_pass = None
        if account_data:
            proxy_host = account_data.get("proxy_host")
            proxy_port = account_data.get("proxy_port")
            proxy_user = account_data.get("proxy_user")
            proxy_pass = account_data.get("proxy_pass")

        token = solve_cloudflare_api(
            page.url, sitekey, logger,
            proxy_host=proxy_host, proxy_port=proxy_port,
            proxy_user=proxy_user, proxy_pass=proxy_pass,
            pagedata=pagedata,
        )

        if not token:
            logger.warning("[CAPTCHA] 2captcha не вернул токен — ждём ручного решения")
            return wait_manual_captcha(page, logger)

        inject_turnstile_token(page, token, logger)

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        time.sleep(2)

        if not is_challenge_page(page):
            logger.info("[CAPTCHA] Челлендж пройден!")
            return True

        logger.warning("[CAPTCHA] Страница всё ещё на челлендже после инжекта — ждём ручного")
        return wait_manual_captcha(page, logger)

    except Exception as e:
        logger.error(f"[CAPTCHA] Ошибка: {e}")
        return False

def wait_manual_captcha(page, logger) -> bool:
    """Manual CAPTCHA solve - wait for user to solve it"""
    logger.info("=" * 60)
    logger.info("[MANUAL] Waiting for CAPTCHA to be solved manually")
    logger.info("[MANUAL] Click the 'Verify you are human' checkbox in browser")
    logger.info("=" * 60)

    start_time = time.time()
    timeout = 300  # 5 минут
    last_log = 0

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            logger.error("[MANUAL] Timeout - CAPTCHA not solved in 5 minutes")
            return False

        try:
            current_title = page.title()

            # Check if title changed
            if "Just a moment" not in current_title:
                logger.info(f"[MANUAL] CAPTCHA SOLVED! Title: {current_title}")
                time.sleep(2)
                return True

            # Log progress
            if int(elapsed) - int(last_log) >= 5:
                logger.info(f"[MANUAL] Waiting... ({int(elapsed)}s) - Solve CAPTCHA checkbox in browser")
                last_log = int(elapsed)

            time.sleep(0.5)

        except Exception as e:
            logger.debug(f"[MANUAL] Error: {e}")
            time.sleep(0.5)

    return False

# ---- Login Loop Detection ----
def is_on_login_page(page, logger):
    """Check if we're back on the login/recover page"""
    try:
        email_field = page.query_selector('#email')
        recover_button = page.query_selector('#passwordRecovery')
        if email_field and recover_button:
            logger.warning("Detected login loop - back on recovery page")
            return True
    except:
        pass
    return False

def handle_login_loop(page, account_data, logger):
    """Handle login loops - retry username submission if looped back"""
    for attempt in range(3):
        logger.info(f"Checking for login loop (attempt {attempt + 1}/3)...")
        time.sleep(3)

        if not is_on_login_page(page, logger):
            logger.info("No login loop detected - proceeding")
            return True

        if attempt < 2:
            logger.info("Retrying username submission...")
            try:
                human_type(page, '#email', account_data['stored_username'])
                field_pause()
                page.click('#passwordRecovery', timeout=60000)
                logger.info("Resubmitted username and clicked recover")
                button_delay()
            except Exception as e:
                logger.error(f"Error retrying: {e}")
                return False
        else:
            logger.error("Too many login loop retries")
            return False

    return False

# ---- Contact Button Clicking ----
def click_contact_button(page, logger, retry_count=0):
    """Detect and click the Contact button"""
    max_retries = 2

    try:
        logger.info("Looking for Contact button...")
        time.sleep(2)

        # Multiple selector strategies
        selectors = [
            "a:has-text('contact jagex')",
            "a:has-text('Contact Jagex')",
            "button:has-text('contact')",
            "//a[contains(text(), 'contact Jagex support')]",
            "//a[contains(text(), 'Contact Jagex')]",
        ]

        button = None
        for selector in selectors:
            try:
                button = page.query_selector(selector)
                if button:
                    logger.info(f"Contact button found with selector: {selector}")
                    break
            except:
                continue

        if not button:
            logger.warning("Contact button not found on page")
            return False

        # Check if button is visible
        if not button.is_visible():
            logger.warning("Contact button not visible")
            return False

        # Scroll into view
        button.scroll_into_view_if_needed()
        time.sleep(1)

        logger.info("Clicking contact button...")
        button.click()
        button_delay()

        logger.info("Contact button clicked successfully")
        return True

    except TimeoutError:
        logger.error("Timeout waiting for contact button")
        return False
    except Exception as e:
        logger.error(f"Error clicking contact button: {e}")
        if retry_count < max_retries:
            logger.info(f"Retrying... ({retry_count + 1}/{max_retries})")
            time.sleep(2)
            return click_contact_button(page, logger, retry_count + 1)
        return False

# ---- State machine helpers ----

def wait_for_page(page, logger, timeout=30000):
    """Wait for page DOM to settle after navigation or form submit"""
    try:
        page.wait_for_load_state("domcontentloaded", timeout=timeout)
    except Exception:
        pass
    time.sleep(random.uniform(0.4, 0.8) * SPEED_FACTOR)


def get_page_state(page, logger) -> str:
    """Detect current page state by URL and DOM.

    Returns one of:
      'captcha'        — Cloudflare challenge page
      'username_entry' — initial recovery page (#email + #passwordRecovery)
      'recovery_form'  — the full recovery form (#reg_email)
      'confirmation'   — email-confirmation in URL
      'closed'         — page / browser gone
      'unknown'        — any other page (redirect in progress, final success, etc.)
    """
    try:
        url = page.url
    except Exception:
        return "closed"

    if is_challenge_page(page):
        return "captcha"

    if "email-confirmation" in url:
        return "confirmation"

    try:
        if page.query_selector("#reg_email"):
            return "recovery_form"
        if page.query_selector("#email") and page.query_selector("#passwordRecovery"):
            return "username_entry"
    except Exception:
        pass

    return "unknown"


def fill_and_submit_recovery_form(page, account_data, dates, logger):
    """Fill and submit the account recovery form (reusable for both passes)"""
    creation_month, creation_year, membership_month, membership_year = dates

    logger.info("Заполняем форму восстановления...")

    human_type(page, "#reg_email", account_data["mail_account"])
    field_pause()
    human_type(page, "#reg_email_conf", account_data["mail_account"])
    field_pause()
    human_type(page, "#password1", account_data["password1"])
    field_pause()

    if account_data["password2"]:
        try:
            page.click("#add-password")
            button_delay()
            human_type(page, "#password2", account_data["password2"])
            random_delay()
        except Exception:
            logger.warning("Не удалось добавить второй пароль")

    try:
        skip_btn = page.query_selector("#recoveries_not_recognised")
        if skip_btn:
            skip_btn.click()
            button_delay()
            checkbox = page.query_selector(
                "label.m-show-password__check-holder:nth-child(1) > input:nth-child(1)"
            )
            if checkbox:
                checkbox.click()
                button_delay()
                logger.info("Вопросы восстановления пропущены")
    except Exception as e:
        logger.warning(f"Ошибка при пропуске вопросов: {e}")

    think_pause()
    human_type(page, "#email", account_data["payment_email_address"])
    field_pause()
    human_type(page, "#postcode", account_data["postcode"])
    field_pause()

    def fill_dropdown(sel, val):
        page.click(sel)
        time.sleep(random.uniform(0.3, 0.7) * SPEED_FACTOR)
        for ch in str(val):
            page.keyboard.type(ch)
            time.sleep(random.uniform(0.05, 0.15) * SPEED_FACTOR)
        time.sleep(random.uniform(0.3, 0.7) * SPEED_FACTOR)
        page.keyboard.press("Enter")
        field_pause()

    fill_dropdown("#paymenttype", "credit")
    fill_dropdown("#subslength", "1 month recurring")
    fill_dropdown("#earliestsubsmonth", membership_month)
    fill_dropdown("#earliestsubsyear", membership_year)

    think_pause()
    fill_dropdown("#creationmonth", creation_month)
    fill_dropdown("#creationyear", creation_year)
    fill_dropdown("#country_otherinfo", account_data["country"])
    fill_dropdown("#state_otherinfo", account_data["state"])
    human_type(page, "#isp", account_data["isp"])
    field_pause()

    random_scroll(page, 150)

    logger.info("Отправляем форму...")
    time.sleep(random.uniform(1, 2) * SPEED_FACTOR)
    page.click('//*[@id="submit_button"]')
    logger.info("Форма отправлена")


# ---- Main function ----
def main(file_number=1):
    logger = setup_logging(file_number)
    browser = None
    profile = None
    client = None

    try:
        logger.info("=" * 60)
        logger.info(f"Starting recovery for file #{file_number}")
        logger.info("=" * 60)

        account_data = read_account_file(file_number)
        email_username = "@" in account_data["stored_username"]

        logger.info(f"Username: {account_data['stored_username']}")
        logger.info(f"Account type: {'Email-based' if email_username else 'Username-based'}")

        if email_username:
            dates = pick_creation_and_membership_for_email_like_username()
        else:
            dates = pick_creation_and_membership_for_username_login()

        logger.info(f"Dates: Created {dates[0]} {dates[1]}, Member since {dates[2]} {dates[3]}")

        kameleo_port = os.getenv("KAMELEO_PORT", "5050")
        client = KameleoLocalApiClient()

        logger.info("Getting Kameleo fingerprints...")
        fps = client.fingerprint.search_fingerprints(device_type="desktop", browser_product="chrome")
        fp = random.choice(fps)
        logger.info(f"Using fingerprint: {fp.id}")

        logger.info("Creating Kameleo profile...")
        profile = client.profile.create_profile(
            CreateProfileRequest(
                fingerprint_id=fp.id,
                name=f"Recovery_{file_number}_{int(time.time())}",
                proxy=ProxyChoice(
                    value="socks5",
                    extra=Server(
                        host=account_data['proxy_host'],
                        port=account_data['proxy_port'],
                        id=account_data['proxy_user'],
                        secret=account_data['proxy_pass']
                    )
                )
            )
        )
        logger.info(f"Profile created: {profile.id}")

        logger.info("Launching browser...")
        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp(
                    f"ws://localhost:{kameleo_port}/playwright/{profile.id}"
                )
                page = browser.contexts[0].new_page()
                page.set_default_timeout(120000)
                logger.info("Browser launched")

                page.goto(
                    "https://secure.runescape.com/m=accountappeal/passwordrecovery",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )

                # ---- State machine ----
                # Each iteration detects the current page state and acts on it.
                # No blind sleeps — we wait for DOM/URL events after every action.
                form_submits = 0    # how many times recovery form was submitted
                contact_clicked = False
                state_hits = {}     # loop-detection counter per state

                for step in range(30):
                    state = get_page_state(page, logger)
                    state_hits[state] = state_hits.get(state, 0) + 1
                    logger.info(f"[Step {step + 1}] state={state}  url={page.url}")

                    if state_hits[state] > 4:
                        logger.error(f"Залип в состоянии '{state}' — прерываем")
                        break

                    if state == "closed":
                        logger.error("Браузер закрылся неожиданно")
                        break

                    elif state == "captcha":
                        handle_cloudflare_turnstile(page, logger, account_data=account_data)
                        wait_for_page(page, logger)

                    elif state == "username_entry":
                        logger.info("Вводим username и нажимаем Recover...")
                        try:
                            page.fill("#email", "")
                        except Exception:
                            pass
                        human_type(page, "#email", account_data["stored_username"])
                        field_pause()
                        page.click("#passwordRecovery")
                        wait_for_page(page, logger)

                    elif state == "recovery_form":
                        if form_submits >= 2:
                            logger.info("Форма заполнена дважды — завершение")
                            break
                        fill_and_submit_recovery_form(page, account_data, dates, logger)
                        form_submits += 1
                        wait_for_page(page, logger)

                    elif state == "confirmation":
                        if contact_clicked:
                            logger.info("Recovery завершён!")
                            break
                        if click_contact_button(page, logger):
                            contact_clicked = True
                            wait_for_page(page, logger)
                        else:
                            logger.info("Contact button не найдена — recovery завершён!")
                            break

                    elif state == "unknown":
                        # Redirect still loading, or final success page
                        logger.info(f"Неизвестная страница ({page.url}) — ждём навигации...")
                        try:
                            old_url = page.url
                            page.wait_for_function(
                                f"() => window.location.href !== {repr(old_url)}",
                                timeout=10000,
                            )
                            wait_for_page(page, logger)
                        except Exception:
                            logger.info("Навигации не было — завершение")
                            break

                logger.info("=" * 60)
                logger.info("RECOVERY COMPLETED!")
                logger.info("=" * 60)

            finally:
                if browser:
                    try:
                        browser.close()
                        logger.info("Browser closed")
                    except Exception:
                        pass

    except FileNotFoundError as e:
        logger.error(f"File error: {e}")
    except ValueError as e:
        logger.error(f"Data error: {e}")
    except TimeoutError as e:
        logger.error(f"Timeout error: {e}")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        try:
            if profile and client:
                logger.info("Cleaning up Kameleo profile...")
                try:
                    if hasattr(client.profile, "delete_profile"):
                        client.profile.delete_profile(profile.id)
                    logger.info("Profile cleaned up")
                except Exception:
                    logger.info("Profile cleanup skipped")
        except Exception:
            pass

if __name__ == "__main__":
    file_number = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    main(file_number)
