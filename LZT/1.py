from playwright.sync_api import sync_playwright, TimeoutError
from kameleo.local_api_client import KameleoLocalApiClient
from kameleo.local_api_client.models import CreateProfileRequest, ProxyChoice, Server
import os
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

# CAPTCHA Config (optional)
CAPTCHA_API_KEY = "852675d7f72a99e3047e8ba106177696"  # 2Captcha API key
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
    try:
        # Сначала дождемся пока Turnstile загрузится (может быть несколько iframe'ов на странице)
        logger.info("[SITEKEY] Waiting for Turnstile to load...")
        try:
            page.wait_for_function(
                "() => document.querySelectorAll('iframe').length > 0",
                timeout=10000
            )
            logger.info("[SITEKEY] Turnstile iframe detected - proceeding with extraction")
            time.sleep(1)  # Give it extra time to fully initialize
        except:
            logger.warning("[SITEKEY] Timeout waiting for iframe - continuing anyway")

        sitekey = page.evaluate("""
            () => {
                // Способ 1: data-sitekey атрибут
                let el = document.querySelector('[data-sitekey]');
                if (el) return el.getAttribute('data-sitekey');

                // Способ 2: cf-turnstile контейнер
                let turnstile = document.querySelector('[data-sitekey], .cf-turnstile, #cf-turnstile, [id*="turnstile"]');
                if (turnstile && turnstile.getAttribute('data-sitekey')) {
                    return turnstile.getAttribute('data-sitekey');
                }

                // Способ 3: проверить все iframes (все, не только с turnstile)
                let iframes = document.querySelectorAll('iframe');
                for (let iframe of iframes) {
                    let src = iframe.src;
                    let match = src.match(/key=([A-Za-z0-9_-]+)/);
                    if (match) return match[1];
                    match = src.match(/sitekey=([A-Za-z0-9_-]+)/);
                    if (match) return match[1];
                }

                // Способ 4: window объект и глобальные переменные
                if (window.turnstileKey) return window.turnstileKey;
                if (window.challengeSitekey) return window.challengeSitekey;
                if (window._cf_chl_opt && window._cf_chl_opt.websiteKey) return window._cf_chl_opt.websiteKey;
                if (window._cf_chl_opt && window._cf_chl_opt.sitekey) return window._cf_chl_opt.sitekey;

                // Способ 5: поискать в скриптах - АГРЕССИВНЫЙ ПОИСК
                let scripts = document.querySelectorAll('script');
                for (let script of scripts) {
                    let text = script.textContent;
                    // Cloudflare IThaC9 (websiteKey в конфиге)
                    let match = text.match(/IThaC9['\"]?\\s*:\\s*['\"]([^'\"]+)['\"]/);
                    if (match) return match[1];
                    // Общий поиск sitekey
                    match = text.match(/['\"]sitekey['\"]\\s*:\\s*['\"]([^'\"]+)['\"]/);
                    if (match) return match[1];
                    match = text.match(/websiteKey['\"]?\\s*:\\s*['\"]([^'\"]+)['\"]/);
                    if (match) return match[1];
                    // Поиск hex строк которые выглядят как sitekey
                    match = text.match(/['\"]([0-9a-f]{32,})['\"]|['\"]([0-9]{1}x[A-Za-z0-9]{27,})['\"]|IThaC9['\"]\\s*:\\s*['\"]([^'\"]+)['\"]/);
                    if (match) {
                        let potential = match[1] || match[2] || match[3];
                        if (potential && potential.length > 20) return potential;
                    }
                }

                // Способ 6: использовать стандартный Cloudflare sitekey если ничего не найдено
                return '0x4AAAAAAAAjq6WYeRDKmebM';
            }
        """)
        if sitekey:
            logger.info(f"Sitekey найден: {sitekey}")
            return sitekey
        else:
            # Добавим диагностику если sitekey не найден
            logger.warning("[SITEKEY] Not found - dumping page structure for debugging")
            try:
                page_info = page.evaluate("""
                    () => {
                        let info = {
                            elements_with_data_sitekey: document.querySelectorAll('[data-sitekey]').length,
                            cf_turnstile_divs: document.querySelectorAll('.cf-turnstile').length,
                            turnstile_iframes: document.querySelectorAll('iframe[src*="turnstile"]').length,
                            challenge_iframes: document.querySelectorAll('iframe[src*="challenges"]').length,
                            all_iframes: document.querySelectorAll('iframe').length,
                            all_divs_with_id: document.querySelectorAll('div[id]').length,
                            page_html_length: document.documentElement.outerHTML.length,
                            body_html_length: document.body.outerHTML.length
                        };

                        // Получить первые несколько iframe src для логирования
                        let iframes = document.querySelectorAll('iframe');
                        info.iframe_srcs = [];
                        for (let i = 0; i < Math.min(3, iframes.length); i++) {
                            info.iframe_srcs.push(iframes[i].src.substring(0, 100));
                        }

                        // Check for Cloudflare cData in scripts
                        let scripts = document.querySelectorAll('script');
                        info.cloudflare_scripts = 0;
                        for (let script of scripts) {
                            if (script.src.includes('challenges.cloudflare.com') ||
                                script.textContent.includes('cData') ||
                                script.textContent.includes('cRay')) {
                                info.cloudflare_scripts++;
                            }
                        }

                        return info;
                    }
                """)
                logger.warning(f"[SITEKEY] Page structure: {page_info}")
            except Exception as e:
                logger.debug(f"[SITEKEY] Could not dump structure: {e}")
    except Exception as e:
        logger.debug(f"Error extracting sitekey: {e}")

    return None

def solve_cloudflare_api(page_url: str, sitekey: str, logger, proxy_str: str = None, captcha_params: dict = None) -> str:
    """Отправить задачу в 2Captcha для решения Cloudflare Turnstile"""
    if not CAPTCHA_API_KEY:
        logger.warning("CAPTCHA_API_KEY не установлен")
        return None

    try:
        final_sitekey = sitekey if sitekey else "0x4AAAAAAAAjq6WYeRDKmebM"
        logger.info(f"Отправка задачи в 2Captcha (TurnstileTaskProxyless, sitekey={final_sitekey[:20]}...)")

        # Шаг 1: Создать задачу TurnstileTaskProxyless в 2Captcha
        task_data = {
            "clientKey": CAPTCHA_API_KEY,
            "task": {
                "type": "TurnstileTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": final_sitekey
            }
        }

        # Добавить дополнительные параметры для Cloudflare Challenge если есть
        if captcha_params:
            if captcha_params.get("action"):
                task_data["task"]["action"] = captcha_params["action"]
                logger.info(f"  Added action: {captcha_params['action']}")
            if captcha_params.get("cData"):
                task_data["task"]["data"] = captcha_params["cData"]
                logger.info(f"  Added cData: {captcha_params['cData'][:40]}...")
            if captcha_params.get("chlPageData"):
                task_data["task"]["pagedata"] = captcha_params["chlPageData"]
                logger.info(f"  Added chlPageData: {captcha_params['chlPageData'][:40]}...")

        logger.debug(f"JSON для 2Captcha: {task_data}")
        resp = requests.post("https://api.2captcha.com/createTask", json=task_data, timeout=30)

        result = resp.json()
        task_id = result.get("taskId")
        error_id = result.get("errorId")

        if error_id and error_id != 0:
            error_desc = result.get("errorDescription") or str(result)
            logger.warning(f"2Captcha ошибка (errorId={error_id}): {error_desc}")
            return None

        if not task_id:
            logger.warning(f"2Captcha: нет taskId в ответе: {result}")
            return None

        logger.info(f"Задача создана: ID={task_id}")

        # Шаг 2: Ждать результат (до 2 минут)
        for attempt in range(24):
            time.sleep(5)

            try:
                result = requests.post("https://api.2captcha.com/getTaskResult", json={
                    "clientKey": CAPTCHA_API_KEY,
                    "taskId": task_id
                }, timeout=30).json()

                if result.get("status") == "ready":
                    solution = result.get("solution", {})
                    # 2Captcha TurnstileTaskProxyless возвращает token
                    token = solution.get("token")
                    if token:
                        logger.info(f"✓ Turnstile решена! Токен получен")
                        return token
                    else:
                        logger.warning(f"2Captcha: нет токена в решении: {solution}")
                        return None

                if attempt % 5 == 0:
                    logger.info(f"Ожидание результата... ({attempt*5}s)")

            except Exception as poll_error:
                logger.debug(f"Ошибка при опросе результата (attempt {attempt}): {poll_error}")
                if attempt > 20:
                    break
                continue

        logger.warning("2Captcha: таймаут (2 минуты)")
        return None

    except Exception as e:
        logger.error(f"Ошибка в solve_cloudflare_api: {e}")
        return None

def inject_turnstile_token(page, token: str, logger) -> bool:
    """Вставить токен Turnstile или cf_clearance cookie в контекст браузера"""
    try:
        # Проверим, это cookie или Turnstile токен
        if len(token) > 100:  # cf_clearance cookies обычно длинные
            logger.info("Вставляем cf_clearance cookie в контекст браузера...")
            try:
                # Получить domain из текущего URL
                current_url = page.url
                domain = ".secure.runescape.com" if "runescape.com" in current_url else "secure.runescape.com"

                # Вставить cookie в контекст браузера
                page.context.add_cookies([{
                    "name": "cf_clearance",
                    "value": token,
                    "domain": domain,
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "None"
                }])
                logger.info("✓ cf_clearance cookie вставлен в контекст")
                return True
            except Exception as e:
                logger.error(f"Error injecting cf_clearance cookie: {e}")
                return False
        else:
            # Это Turnstile токен - старый метод
            logger.info("Инжектируем Turnstile токен в страницу...")
            page.evaluate(f"""
                () => {{
                    let input = document.querySelector('[name="cf-turnstile-response"]');
                    if (input) {{
                        input.value = '{token}';
                    }}
                    if (window.turnstile && window.turnstile.getResponse) {{
                        window.turnstile.reset();
                    }}
                    if (window.tsCallback) {{
                        window.tsCallback('{token}');
                    }}
                }}
            """)
            logger.info("✓ Turnstile токен инжектирован")
            return True

    except Exception as e:
        logger.error(f"Error in inject_turnstile_token: {e}")
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


def handle_cloudflare_turnstile(page, logger, captured_sitekey_dict=None) -> bool:
    """Enhanced Cloudflare Challenge handler with multiple click strategies"""
    try:
        # DETECT: Check if CAPTCHA present
        logger.info("[CAPTCHA] Checking for Cloudflare Challenge...")
        try:
            current_title = page.title()
        except:
            logger.info("[CAPTCHA] Page closed")
            return True

        if "Just a moment" not in current_title:
            logger.info("[CAPTCHA] No challenge - page loaded normally")
            return True

        logger.info("[CAPTCHA] Cloudflare Challenge detected")

        # Diagnose page structure
        diagnose_page_structure(page, logger)

        # CRITICAL: Wait for Cloudflare Challenge UI to render (iframes/checkboxes to appear)
        logger.info("[CAPTCHA] Waiting for challenge UI to render...")
        try:
            # Wait for either iframes or checkbox to appear
            page.wait_for_function(
                "() => document.querySelectorAll('iframe').length > 0 || document.querySelector('input[type=\"checkbox\"]')",
                timeout=15000
            )
            logger.info("[CAPTCHA] Challenge UI detected")
        except:
            logger.warning("[CAPTCHA] Challenge UI didn't render in time - trying anyway")

        # Small delay to let UI fully render
        time.sleep(2)

        # Re-diagnose after waiting
        logger.info("[CAPTCHA] Re-diagnosing page after UI render...")
        diagnose_page_structure(page, logger)

        # Try multiple strategies to click the checkbox
        logger.info("[CAPTCHA] Strategy 1: Attempting iframe-based click...")
        if try_click_turnstile_checkbox(page, logger):
            return True

        logger.info("[CAPTCHA] Strategy 2: Attempting coordinate-based click...")
        if try_click_by_coordinates(page, logger):
            return True

        # Fallback: Wait for Kameleo's fingerprinting to auto-pass
        logger.info("[CAPTCHA] Strategy 3: Waiting for Kameleo fingerprinting to auto-pass...")
        logger.info("[CAPTCHA] Kameleo will handle browser verification - waiting...")

        # Extended wait for browser verification
        time.sleep(20)

        # WAIT: Wait for challenge to pass - BOTH conditions must be true
        logger.info("[CAPTCHA] Monitoring for challenge bypass...")
        start_time = time.time()
        timeout = 120  # 120 seconds for auto-pass

        while time.time() - start_time < timeout:
            try:
                current_title = page.title()
                current_url = page.url

                title_ok = "Just a moment" not in current_title
                url_ok = "cf_chl_rt_tk" not in current_url

                logger.debug(f"[CAPTCHA] Title OK: {title_ok}, URL OK: {url_ok}")

                # Both conditions must be true
                if title_ok and url_ok:
                    logger.info(f"[CAPTCHA] Challenge auto-passed! Title: {current_title}")
                    time.sleep(2)
                    return True

                # Still on challenge page
                elapsed = int(time.time() - start_time)
                if elapsed % 15 == 0:
                    logger.info(f"[CAPTCHA] Still waiting... {elapsed}s")

                time.sleep(2)
            except Exception as e:
                logger.debug(f"[CAPTCHA] Check error: {e}")
                time.sleep(2)

        logger.warning("[CAPTCHA] Challenge timeout - could not bypass")
        logger.warning("[CAPTCHA] Please solve CAPTCHA manually if browser is still open")
        return False

    except Exception as e:
        logger.error(f"[CAPTCHA] Error: {e}")
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
        email_username = '@' in account_data['stored_username']

        logger.info(f"Username: {account_data['stored_username']}")
        logger.info(f"Account type: {'Email-based' if email_username else 'Username-based'}")

        if email_username:
            creation_month, creation_year, membership_month, membership_year = pick_creation_and_membership_for_email_like_username()
        else:
            creation_month, creation_year, membership_month, membership_year = pick_creation_and_membership_for_username_login()

        logger.info(f"Dates: Created {creation_month} {creation_year}, Member since {membership_month} {membership_year}")

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
                browser = p.chromium.connect_over_cdp(f"ws://localhost:{kameleo_port}/playwright/{profile.id}")
                page = browser.contexts[0].new_page()
                page.set_default_timeout(120000)

                logger.info("Browser launched")

                # ---- STEP 1: Navigate to recovery page ----
                logger.info("")
                logger.info("=" * 60)
                logger.info("STEP 1: Navigate to recovery page")
                logger.info("=" * 60)

                # Setup network listener to capture real Turnstile sitekey from CDN request
                page.goto('https://secure.runescape.com/m=accountappeal/passwordrecovery', wait_until="networkidle")
                logger.info("Recovery page loaded")

                think_pause()

                # ---- STEP 2: Submit username ----
                logger.info("")
                logger.info("=" * 60)
                logger.info("STEP 2: Submit username")
                logger.info("=" * 60)
                human_type(page, '#email', account_data['stored_username'])
                field_pause()
                page.click('#passwordRecovery')
                logger.info("Username submitted, waiting for page to load...")

                # IMPORTANT: Wait for page to fully load before proceeding
                # The next page will either have recovery form or CAPTCHA
                try:
                    page.wait_for_load_state('domcontentloaded', timeout=30000)
                    logger.info("Page loaded successfully")
                except:
                    logger.warning("Page load timeout, continuing anyway")

                # Log where we are
                current_url_after_submit = page.url
                logger.info(f"Current URL after username submit: {current_url_after_submit}")

                button_delay()

                # ---- STEP 3: Handle login loop ----
                logger.info("")
                logger.info("=" * 60)
                logger.info("STEP 3: Check for login loop")
                logger.info("=" * 60)
                if not handle_login_loop(page, account_data, logger):
                    logger.error("Login loop recovery failed")
                    raise Exception("Login loop recovery failed")

                # ---- STEP 4: Handle CAPTCHA ----
                logger.info("")
                logger.info("=" * 60)
                logger.info("STEP 4: Handle CAPTCHA")
                logger.info("=" * 60)
                handle_cloudflare_turnstile(page, logger)

                # ---- STEP 5: Fill recovery form ----
                logger.info("")
                logger.info("=" * 60)
                logger.info("STEP 5: Fill recovery form")
                logger.info("=" * 60)

                # Debug: Check what's on the page
                logger.info(f"Current URL: {page.url}")
                logger.info(f"Page title: {page.title()}")

                # Debug: Show all elements on page
                try:
                    all_elements = page.query_selector_all('input, textarea, select, label, form, div[id], button, a[href]')
                    logger.info(f"DEBUG: Found {len(all_elements)} total elements")

                    # Show IDs of input fields
                    inputs = page.query_selector_all('input')
                    logger.info(f"Total input fields: {len(inputs)}")
                    for inp in inputs[:10]:
                        inp_id = inp.get_attribute('id') or 'no-id'
                        inp_type = inp.get_attribute('type') or 'no-type'
                        inp_placeholder = inp.get_attribute('placeholder') or 'no-placeholder'
                        logger.info(f"  Input: id={inp_id}, type={inp_type}")

                    # Show buttons
                    buttons = page.query_selector_all('button')
                    logger.info(f"Total buttons: {len(buttons)}")
                    for btn in buttons[:5]:
                        btn_id = btn.get_attribute('id') or 'no-id'
                        btn_text = btn.text_content() or 'no-text'
                        logger.info(f"  Button: id={btn_id}, text={btn_text[:30]}")

                except Exception as e:
                    logger.debug(f"Error debugging: {e}")

                # Wait for navigation to complete after CAPTCHA
                try:
                    page.wait_for_load_state('domcontentloaded', timeout=15000)
                    logger.info("Page load completed after CAPTCHA")
                except:
                    logger.warning("Page load timeout after CAPTCHA - continuing")
                    time.sleep(3)

                # Check if we have the recovery form
                try:
                    form_field = page.query_selector('#reg_email')
                except Exception as e:
                    logger.warning(f"Error accessing page after CAPTCHA: {e}")
                    form_field = None

                if not form_field:
                    # Check if we're back at the initial recovery page (with just email + Recover button)
                    try:
                        recover_button = page.query_selector('#passwordRecovery')
                        initial_email = page.query_selector('#email')
                    except Exception as e:
                        logger.warning(f"Error querying page elements: {e}")
                        recover_button = None
                        initial_email = None

                    if recover_button and initial_email:
                        logger.info("Back at initial recovery page - need to click Recover again")
                        # Fill the email field and click Recover to advance
                        human_type(page, '#email', account_data['stored_username'], click_first=False)
                        field_pause()
                        page.click('#passwordRecovery')
                        logger.info("Clicked Recover - waiting for actual recovery form...")
                        button_delay()
                        time.sleep(3)

                    # Now wait for the recovery form to appear
                    logger.info("Waiting for recovery form fields...")
                    form_wait_start = time.time()
                    while (time.time() - form_wait_start) < 15:
                        try:
                            form_field = page.query_selector('#reg_email')
                            if form_field:
                                logger.info("Recovery form now visible!")
                                break
                        except Exception as e:
                            logger.debug(f"Error checking for form: {e}")
                            form_field = None
                        time.sleep(0.5)

                if form_field:
                    human_type(page, '#reg_email', account_data['mail_account'])
                    field_pause()
                    human_type(page, '#reg_email_conf', account_data['mail_account'])
                    field_pause()
                    human_type(page, '#password1', account_data['password1'])
                    field_pause()
                    if account_data['password2']:
                        try:
                            page.click('#add-password')
                            button_delay()
                            human_type(page, '#password2', account_data['password2'])
                            random_delay()
                        except:
                            logger.warning("Could not add second password")

                    # Skip recovery questions
                    try:
                        skip_button = page.query_selector('#recoveries_not_recognised')
                        if skip_button:
                            skip_button.click()
                            button_delay()
                            checkbox = page.query_selector('label.m-show-password__check-holder:nth-child(1) > input:nth-child(1)')
                            if checkbox:
                                checkbox.click()
                                button_delay()
                                logger.info("Skipped recovery questions")
                    except Exception as e:
                        logger.warning(f"Error skipping recovery questions: {e}")

                    think_pause()
                    human_type(page, '#email', account_data['payment_email_address'])
                    field_pause()
                    human_type(page, '#postcode', account_data['postcode'])
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

                    fill_dropdown('#paymenttype', 'credit')
                    fill_dropdown('#subslength', '1 month recurring')
                    fill_dropdown('#earliestsubsmonth', membership_month)
                    fill_dropdown('#earliestsubsyear', membership_year)

                    think_pause()
                    fill_dropdown('#creationmonth', creation_month)
                    fill_dropdown('#creationyear', creation_year)
                    fill_dropdown('#country_otherinfo', account_data['country'])
                    fill_dropdown('#state_otherinfo', account_data['state'])
                    human_type(page, '#isp', account_data['isp'])
                    field_pause()

                    random_scroll(page, 150)

                    logger.info("Submitting recovery form...")
                    # Reduced pause - 20 minute session limit!
                    time.sleep(random.uniform(1, 2))
                    page.click('//*[@id="submit_button"]')
                    logger.info("Form submitted")
                else:
                    logger.info("Form already submitted")

                # ---- STEP 6: Wait and check for contact button ----
                logger.info("")
                logger.info("=" * 60)
                logger.info("STEP 6: Wait for confirmation page")
                logger.info("=" * 60)

                time.sleep(3)
                current_url = page.url
                logger.info(f"Current URL: {current_url}")

                if "email-confirmation" in current_url:
                    logger.info("On email-confirmation page")
                    if click_contact_button(page, logger):
                        logger.info("Contact button clicked successfully")
                        logger.info("Waiting for page to update after contact button click...")
                        time.sleep(3)

                        # Check if recovery form appears again after contact button click
                        form_field_after_contact = page.query_selector('#reg_email')
                        if form_field_after_contact:
                            logger.info("Recovery form appeared again after contact button - filling it")

                            human_type(page, '#reg_email', account_data['mail_account'])
                            field_pause()
                            human_type(page, '#reg_email_conf', account_data['mail_account'])
                            field_pause()
                            human_type(page, '#password1', account_data['password1'])
                            field_pause()
                            if account_data['password2']:
                                try:
                                    page.click('#add-password')
                                    button_delay()
                                    human_type(page, '#password2', account_data['password2'])
                                    random_delay()
                                except:
                                    logger.warning("Could not add second password")

                            # Skip recovery questions
                            try:
                                skip_button = page.query_selector('#recoveries_not_recognised')
                                if skip_button:
                                    skip_button.click()
                                    button_delay()
                                    checkbox = page.query_selector('label.m-show-password__check-holder:nth-child(1) > input:nth-child(1)')
                                    if checkbox:
                                        checkbox.click()
                                        button_delay()
                                        logger.info("Skipped recovery questions")
                            except Exception as e:
                                logger.warning(f"Error skipping recovery questions: {e}")

                            think_pause()
                            human_type(page, '#email', account_data['payment_email_address'])
                            field_pause()
                            human_type(page, '#postcode', account_data['postcode'])
                            field_pause()

                            def fill_dropdown_post_contact(sel, val):
                                page.click(sel)
                                time.sleep(random.uniform(0.3, 0.7) * SPEED_FACTOR)
                                for ch in str(val):
                                    page.keyboard.type(ch)
                                    time.sleep(random.uniform(0.05, 0.15) * SPEED_FACTOR)
                                time.sleep(random.uniform(0.3, 0.7) * SPEED_FACTOR)
                                page.keyboard.press("Enter")
                                field_pause()

                            fill_dropdown_post_contact('#paymenttype', 'credit')
                            fill_dropdown_post_contact('#subslength', '1 month recurring')
                            fill_dropdown_post_contact('#earliestsubsmonth', membership_month)
                            fill_dropdown_post_contact('#earliestsubsyear', membership_year)

                            think_pause()
                            fill_dropdown_post_contact('#creationmonth', creation_month)
                            fill_dropdown_post_contact('#creationyear', creation_year)
                            fill_dropdown_post_contact('#country_otherinfo', account_data['country'])
                            fill_dropdown_post_contact('#state_otherinfo', account_data['state'])
                            human_type(page, '#isp', account_data['isp'])
                            field_pause()

                            random_scroll(page, 150)

                            logger.info("Submitting recovery form (post-contact)...")
                            time.sleep(random.uniform(1, 2))
                            page.click('//*[@id="submit_button"]')
                            logger.info("Form submitted after contact button")
                        else:
                            logger.info("No recovery form found after contact button click")
                    else:
                        logger.info("Contact button not found or could not click")
                else:
                    logger.info(f"Not on email-confirmation page")

                # ---- Success ----
                logger.info("")
                logger.info("=" * 60)
                logger.info("RECOVERY COMPLETED SUCCESSFULLY!")
                logger.info("=" * 60)

                time.sleep(3)

            finally:
                if browser:
                    try:
                        browser.close()
                        logger.info("Browser closed")
                    except:
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
        # Clean up Kameleo profile
        try:
            if profile and client:
                logger.info("Cleaning up Kameleo profile...")
                try:
                    if hasattr(client.profile, 'delete_profile'):
                        client.profile.delete_profile(profile.id)
                    logger.info("Profile cleaned up")
                except:
                    logger.info("Profile cleanup skipped")
        except:
            pass

if __name__ == "__main__":
    file_number = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    main(file_number)
