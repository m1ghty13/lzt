from playwright.sync_api import sync_playwright, TimeoutError
from kameleo.local_api_client import KameleoLocalApiClient
from kameleo.local_api_client.models import CreateProfileRequest, ProxyChoice, Server
import os
import time
import random
import sys
import logging

# ---- Global speed factor for delays ----
# IMPORTANT: Session expires in 20 minutes, so speed matters!
# 1.0 = normal speed (slower, more human-like)
# 0.5 = 2x faster (recommended to stay within 20 min limit)
SPEED_FACTOR = 1
RESULTS_FOLDER = r"C:\Users\gogog\Downloads\Xivora\LZT\results"

# ---- Failsafe / auto-close timings ----
# If recovery_form is not reached within this many seconds → proxy too slow / bad trust score → auto-close
FORM_REACH_TIMEOUT = 240   # 4 minutes
# Seconds to wait after ticket is submitted before auto-closing the browser
AUTO_CLOSE_DELAY = 10


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


def _has_cf_clearance(page) -> bool:
    """cf_clearance cookie — единственный надёжный признак прохождения CF managed challenge."""
    try:
        return any(c["name"] == "cf_clearance" for c in page.context.cookies())
    except Exception:
        return False


def wait_kameleo_autopass(page, logger, timeout=90) -> bool:
    """Ждём авто-прохождения Cloudflare challenge через Kameleo fingerprinting.

    Надёжный признак — cf_clearance cookie + страница не challenge.
    Заголовок ненадёжен: CF перезагружает страницу внутри challenge несколько раз.
    """
    already_had = _has_cf_clearance(page)
    logger.info(f"[KAMELEO] Ждём cf_clearance ({timeout}s) [уже был: {already_had}]...")
    start = time.time()
    last_log = 0

    while time.time() - start < timeout:
        try:
            got_clearance = _has_cf_clearance(page)
            not_challenge = not is_challenge_page(page)

            if got_clearance and not_challenge:
                logger.info("[KAMELEO] cf_clearance получен + challenge пройден!")
                return True

            elapsed = int(time.time() - start)
            if elapsed - last_log >= 10:
                logger.info(
                    f"[KAMELEO] {elapsed}s/{timeout}s | "
                    f"cf_clearance={'да' if got_clearance else 'нет'} | "
                    f"challenge={'да' if not not_challenge else 'нет'}"
                )
                last_log = elapsed

        except Exception:
            return True

        time.sleep(1)

    logger.warning("[KAMELEO] cf_clearance не получен за 90s — ручной режим")
    logger.warning("[KAMELEO] Для авто-прохождения нужны residential прокси.")
    return wait_manual_captcha(page, logger)


def wait_manual_captcha(page, logger) -> bool:
    """Ждём ручного решения CAPTCHA пользователем в браузере."""
    logger.info("=" * 60)
    logger.info("[MANUAL] Реши CAPTCHA вручную в браузере Kameleo")
    logger.info("=" * 60)

    start_time = time.time()
    timeout = 300
    last_log = 0

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            logger.error("[MANUAL] Таймаут — CAPTCHA не решена за 5 минут")
            return False

        try:
            if not is_challenge_page(page):
                logger.info("[MANUAL] CAPTCHA решена!")
                time.sleep(2)
                return True

            if int(elapsed) - int(last_log) >= 10:
                logger.info(f"[MANUAL] Ожидание... {int(elapsed)}s")
                last_log = int(elapsed)

            time.sleep(1)

        except Exception as e:
            logger.debug(f"[MANUAL] Ошибка: {e}")
            time.sleep(1)

    return False


CHECKBOX_SELECTORS = [
    'input[type="checkbox"]',
    '[role="checkbox"]',
    'label > input',
    '.ctp-checkbox-label',
    'label',
]


def _try_click_checkbox(page, logger) -> bool:
    """Попытаться кликнуть чекбокс Turnstile всеми доступными методами."""

    # Стратегия 1: поиск по тексту "Verify you are human"
    try:
        verify_label = page.locator('text=Verify you are human')
        if verify_label.count() > 0:
            parent = verify_label.locator(
                'xpath=./ancestor::*[contains(@class,"checkboxLabel") or contains(@class,"mark")]'
            )
            if parent.count() > 0:
                parent.click()
                logger.info("[CLICK] S1: клик по родителю label 'Verify you are human'")
                return True
    except Exception:
        pass

    # Стратегия 2: перебор всех iframe по индексу (nth) — самый надёжный способ
    try:
        iframes = page.query_selector_all('iframe')
        logger.info(f"[CLICK] S2: найдено iframe: {len(iframes)}")
        for i, iframe_el in enumerate(iframes):
            src = iframe_el.get_attribute('src') or ''
            logger.debug(f"[CLICK] S2 iframe[{i}]: {src[:80]}")
            frame = page.frame_locator(f'iframe >> nth={i}')
            for sel in CHECKBOX_SELECTORS:
                try:
                    cb = frame.locator(sel)
                    if cb.count() > 0:
                        cb.click(timeout=2000)
                        logger.info(f"[CLICK] S2: iframe[{i}] → {sel}")
                        return True
                except Exception:
                    continue
    except Exception as e:
        logger.debug(f"[CLICK] S2 error: {e}")

    # Стратегия 3: page.frames по URL
    try:
        for frame in page.frames:
            if "challenges.cloudflare.com" in frame.url or "turnstile" in frame.url:
                for sel in CHECKBOX_SELECTORS:
                    try:
                        el = frame.query_selector(sel)
                        if el:
                            el.click()
                            logger.info(f"[CLICK] S3: page.frames → {sel}")
                            return True
                    except Exception:
                        continue
    except Exception as e:
        logger.debug(f"[CLICK] S3 error: {e}")

    # Стратегия 4: JavaScript клик напрямую на странице
    try:
        result = page.evaluate("""
            () => {
                let cb = document.querySelector('input[type="checkbox"]');
                if (cb) { cb.click(); cb.dispatchEvent(new Event('change',{bubbles:true})); return 'checkbox'; }
                let aria = document.querySelector('[aria-label*="Verify"]');
                if (aria) { aria.click(); return 'aria'; }
                return null;
            }
        """)
        if result:
            logger.info(f"[CLICK] S4: JS click → {result}")
            return True
    except Exception as e:
        logger.debug(f"[CLICK] S4 error: {e}")

    # Стратегия 5: Tab + Space (клавиатурная активация)
    try:
        page.keyboard.press('Tab')
        time.sleep(0.3)
        page.keyboard.press('Space')
        logger.info("[CLICK] S5: Tab+Space")
        return True
    except Exception as e:
        logger.debug(f"[CLICK] S5 error: {e}")

    # Стратегия 6: клик по координатам (центр и типичные позиции виджета)
    try:
        vp = page.viewport_size or {"width": 1280, "height": 800}
        w, h = vp["width"], vp["height"]
        positions = [
            (int(w * 0.5),  int(h * 0.5)),
            (int(w * 0.75), int(h * 0.5)),
            (int(w * 0.5),  int(h * 0.45)),
            (int(w * 0.5),  int(h * 0.55)),
            (int(w * 0.25), int(h * 0.5)),
        ]
        for x, y in positions:
            try:
                page.mouse.click(x, y)
                time.sleep(0.5)
                if not is_challenge_page(page):
                    logger.info(f"[CLICK] S6: координаты ({x},{y}) — challenge ушёл!")
                    return True
            except Exception:
                continue
        logger.info("[CLICK] S6: координаты не помогли")
    except Exception as e:
        logger.debug(f"[CLICK] S6 error: {e}")

    return False


def handle_cloudflare_turnstile(page, logger, **_) -> bool:
    """Обработка Cloudflare Challenge.

    Реактивный цикл (каждые 0.5s):
    - Пробуем кликнуть чекбокс всеми методами
    - Если cf_clearance появился И challenge ушёл → готово
    - Через 90s → ручной fallback
    """
    if not is_challenge_page(page):
        return True

    logger.info("[CAPTCHA] Cloudflare Challenge — ждём рендера и кликаем чекбокс...")

    # Ждём появления iframe или чекбокса (до 15s)
    try:
        page.wait_for_function(
            '() => document.querySelectorAll("iframe").length > 0 '
            '|| !!document.querySelector("input[type=\\"checkbox\\"]")',
            timeout=15000,
        )
        logger.info("[CAPTCHA] UI готов")
        time.sleep(1.5)
    except Exception:
        logger.info("[CAPTCHA] iframe не появился за 15s — пробуем всё равно")

    start = time.time()
    timeout = 90
    checkbox_clicked = False
    last_log = 0
    clearance_before = _has_cf_clearance(page)

    while time.time() - start < timeout:
        try:
            has_clearance = _has_cf_clearance(page)
            on_challenge = is_challenge_page(page)

            # Считаем пройденным только если получили НОВЫЙ clearance или ушли со страницы
            if has_clearance and not on_challenge:
                logger.info("[CAPTCHA] Challenge пройден!")
                return True

            # Получили новый clearance — страница сейчас перегружается
            if has_clearance and not clearance_before:
                logger.info("[CAPTCHA] Новый cf_clearance получен, ждём редиректа...")

            # Пробуем кликнуть чекбокс
            if not checkbox_clicked:
                if _try_click_checkbox(page, logger):
                    checkbox_clicked = True
                    logger.info("[CLICK] Клик выполнен — ждём cf_clearance...")

        except Exception:
            pass

        elapsed = int(time.time() - start)
        if elapsed - last_log >= 10:
            logger.info(
                f"[CAPTCHA] {elapsed}s/{timeout}s | "
                f"clearance={'да' if _has_cf_clearance(page) else 'нет'} | "
                f"clicked={'да' if checkbox_clicked else 'нет'}"
            )
            last_log = elapsed

        time.sleep(0.5)

    logger.warning("[CAPTCHA] 90s истекло — переходим в ручной режим")
    return wait_manual_captcha(page, logger)


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

    if "email-confirmation" in url or "appealformresult" in url:
        return "confirmation"

    if "message.ws" in url or "account-identified" in url:
        return "rejected"

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
                session_start = time.time()
                form_reached = False   # tracks whether recovery_form was ever seen

                for step in range(30):
                    # Failsafe: if recovery form not reached within timeout → bad proxy / low trust score
                    if not form_reached and (time.time() - session_start) > FORM_REACH_TIMEOUT:
                        logger.warning(
                            f"[FAILSAFE] Recovery form not reached within {FORM_REACH_TIMEOUT}s "
                            f"(current state: {get_page_state(page, logger)}) — "
                            f"proxy too slow or low trust score. Auto-closing."
                        )
                        break

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
                        form_reached = True
                        if form_submits >= 2:
                            logger.info("Форма заполнена дважды — завершение")
                            logger.info(f"[DONE] Авто-закрытие через {AUTO_CLOSE_DELAY}s...")
                            time.sleep(AUTO_CLOSE_DELAY)
                            break
                        fill_and_submit_recovery_form(page, account_data, dates, logger)
                        form_submits += 1
                        wait_for_page(page, logger)

                    elif state == "confirmation":
                        if contact_clicked:
                            logger.info("Recovery завершён!")
                            logger.info(f"[DONE] Авто-закрытие через {AUTO_CLOSE_DELAY}s...")
                            time.sleep(AUTO_CLOSE_DELAY)
                            break
                        if click_contact_button(page, logger):
                            contact_clicked = True
                            wait_for_page(page, logger)
                        else:
                            logger.info("Contact button не найдена — тикет отправлен!")
                            logger.info(f"[DONE] Авто-закрытие через {AUTO_CLOSE_DELAY}s...")
                            time.sleep(AUTO_CLOSE_DELAY)
                            break

                    elif state == "rejected":
                        logger.warning(f"[REJECTED] Runescape отклонил запрос: {page.url}")
                        logger.warning("[REJECTED] Возможные причины: аккаунт не найден, слишком много попыток, аккаунт заблокирован")
                        break

                    elif state == "unknown":
                        # Форма могла загрузиться через JS без смены URL.
                        # Ждём до 15s пока состояние изменится через DOM.
                        logger.info(f"Неизвестная страница ({page.url}) — ждём изменения DOM...")
                        resolved = False
                        for _ in range(15):
                            time.sleep(1)
                            new_state = get_page_state(page, logger)
                            if new_state != "unknown":
                                logger.info(f"Состояние изменилось: {new_state}")
                                resolved = True
                                break
                        if not resolved:
                            logger.info("Состояние не изменилось за 15s — завершение")
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
                logger.info("Stopping Kameleo browser...")
                try:
                    client.profile.stop_profile(profile.id)
                    logger.info("Browser stopped")
                except Exception as e:
                    logger.debug(f"stop_profile: {e}")
                try:
                    client.profile.delete_profile(profile.id)
                    logger.info("Profile deleted")
                except Exception:
                    pass
        except Exception:
            pass

if __name__ == "__main__":
    file_number = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    main(file_number)
