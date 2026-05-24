from playwright.sync_api import sync_playwright, TimeoutError
from kameleo.local_api_client import KameleoLocalApiClient
from kameleo.local_api_client.models import CreateProfileRequest, ProxyChoice, Server
import os
import time
import random
import sys
import logging
import json
import urllib.request

SPEED_FACTOR = 1
RESULTS_FOLDER = r"C:\Users\gogog\Downloads\Xivora\LZT\results"

FORM_REACH_TIMEOUT = 240   # seconds before failsafe triggers
AUTO_CLOSE_DELAY   = 10    # seconds to wait after ticket sent

# ---- Telegram notifications ----------------------------------------
_TG_TOKEN = os.getenv("TG_BOT_TOKEN", "")
_TG_OWNER = os.getenv("TG_OWNER_ID", "")

def notify_telegram(text: str):
    if not _TG_TOKEN or not _TG_OWNER:
        return
    try:
        url = f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage"
        payload = json.dumps({
            "chat_id": int(_TG_OWNER),
            "text": text,
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


# ---- Logging setup -------------------------------------------------
def setup_logging(file_number: int):
    log_file = os.path.join(RESULTS_FOLDER, f"log_{file_number}.txt")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    return logging.getLogger(__name__)


# ---- Timing helpers ------------------------------------------------
def random_delay(multiplier=2.5, base_min=0.1, base_max=0.4):
    time.sleep(random.uniform(base_min * multiplier, base_max * multiplier) * SPEED_FACTOR)

def button_delay():
    time.sleep(random.uniform(2.0, 5.0) * SPEED_FACTOR)

def field_pause():
    time.sleep(random.uniform(0.6, 1.6) * SPEED_FACTOR)

def think_pause():
    time.sleep(random.uniform(0.3, 0.8) * SPEED_FACTOR)

def human_type(page, selector, text, click_first=True):
    if not text:
        return
    if click_first:
        page.click(selector)
        time.sleep(random.uniform(0.15, 0.45) * SPEED_FACTOR)
    for ch in text:
        page.keyboard.type(ch)
        if ch in " .@_-":
            time.sleep(random.uniform(0.10, 0.25) * SPEED_FACTOR)
        else:
            time.sleep(random.uniform(0.04, 0.14) * SPEED_FACTOR)
    time.sleep(random.uniform(0.2, 0.5) * SPEED_FACTOR)

def random_scroll(page, pixels=150):
    try:
        page.evaluate(f"window.scrollBy(0, {pixels})")
        time.sleep(random.uniform(0.5, 1.5) * SPEED_FACTOR)
    except Exception:
        pass


# ---- Date pickers --------------------------------------------------
def pick_creation_and_membership_for_username_login():
    months = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]
    cy = random.randint(2005, 2007)
    cm = random.randint(1, 12)
    my = random.randint(2009, 2010)
    mm = random.randint(1, 12)
    return months[cm-1], str(cy), months[mm-1], str(my)

def pick_creation_and_membership_for_email_like_username():
    months = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]
    cy = random.randint(2013, 2014)
    cm = random.randint(1, 12)
    my = random.randint(2015, 2016)
    mm = random.randint(1, 12)
    return months[cm-1], str(cy), months[mm-1], str(my)


# ---- Read account file ---------------------------------------------
def read_account_file(file_number=1):
    file_path = os.path.join(RESULTS_FOLDER, f"{file_number}.txt")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} not found.")

    with open(file_path, "r", encoding="utf-8") as f:
        lines = [l.rstrip() for l in f.read().splitlines()]

    proxy_line = next((l for l in reversed(lines) if l.count(".") == 3 and ":" in l), None)
    if not proxy_line:
        raise ValueError("No valid proxy found in file.")

    account_lines = lines[:lines.index(proxy_line)]
    while len(account_lines) < 11:
        account_lines.append("")

    ph, pp, pu, ppass = proxy_line.split(":")
    return {
        "stored_username":        account_lines[0],
        "mail_account":           account_lines[1],
        "password1":              account_lines[2],
        "password2":              account_lines[3],
        "payment_email_address":  account_lines[4],
        "postcode":               account_lines[5],
        "creation_month":         account_lines[6],
        "creation_year":          account_lines[7],
        "country":                account_lines[8],
        "state":                  account_lines[9],
        "isp":                    account_lines[10],
        "proxy_host": ph,
        "proxy_port": int(pp),
        "proxy_user": pu,
        "proxy_pass": ppass,
    }


# ---- Cloudflare helpers --------------------------------------------
def is_challenge_page(page) -> bool:
    try:
        if any(t in page.title() for t in ("Just a moment", "Checking your Browser", "Are you a robot")):
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
    try:
        return any(c["name"] == "cf_clearance" for c in page.context.cookies())
    except Exception:
        return False


CHECKBOX_SELECTORS = [
    'input[type="checkbox"]',
    '[role="checkbox"]',
    'label > input',
    '.ctp-checkbox-label',
    'label',
]

def _try_click_checkbox(page) -> bool:
    # S1: label text
    try:
        lbl = page.locator("text=Verify you are human")
        if lbl.count() > 0:
            parent = lbl.locator(
                'xpath=./ancestor::*[contains(@class,"checkboxLabel") or contains(@class,"mark")]'
            )
            if parent.count() > 0:
                parent.click()
                return True
    except Exception:
        pass

    # S2: enumerate iframes by index
    try:
        iframes = page.query_selector_all("iframe")
        for i in range(len(iframes)):
            frame = page.frame_locator(f"iframe >> nth={i}")
            for sel in CHECKBOX_SELECTORS:
                try:
                    cb = frame.locator(sel)
                    if cb.count() > 0:
                        cb.click(timeout=2000)
                        return True
                except Exception:
                    continue
    except Exception:
        pass

    # S3: page.frames by URL
    try:
        for frame in page.frames:
            if "challenges.cloudflare.com" in frame.url or "turnstile" in frame.url:
                for sel in CHECKBOX_SELECTORS:
                    try:
                        el = frame.query_selector(sel)
                        if el:
                            el.click()
                            return True
                    except Exception:
                        continue
    except Exception:
        pass

    # S4: JS click
    try:
        result = page.evaluate("""
            () => {
                let cb = document.querySelector('input[type="checkbox"]');
                if (cb) { cb.click(); cb.dispatchEvent(new Event('change',{bubbles:true})); return true; }
                let aria = document.querySelector('[aria-label*="Verify"]');
                if (aria) { aria.click(); return true; }
                return false;
            }
        """)
        if result:
            return True
    except Exception:
        pass

    # S5: Tab+Space
    try:
        page.keyboard.press("Tab")
        time.sleep(0.3)
        page.keyboard.press("Space")
        return True
    except Exception:
        pass

    # S6: coordinate clicks
    try:
        vp = page.viewport_size or {"width": 1280, "height": 800}
        w, h = vp["width"], vp["height"]
        for x, y in [
            (int(w * 0.5),  int(h * 0.5)),
            (int(w * 0.75), int(h * 0.5)),
            (int(w * 0.5),  int(h * 0.45)),
            (int(w * 0.5),  int(h * 0.55)),
            (int(w * 0.25), int(h * 0.5)),
        ]:
            try:
                page.mouse.click(x, y)
                time.sleep(0.5)
                if not is_challenge_page(page):
                    return True
            except Exception:
                continue
    except Exception:
        pass

    return False


def handle_cloudflare_turnstile(page, logger, **_) -> bool:
    if not is_challenge_page(page):
        return True

    logger.info("🔒 Cloudflare challenge — waiting for checkbox...")

    try:
        page.wait_for_function(
            '() => document.querySelectorAll("iframe").length > 0 '
            '|| !!document.querySelector("input[type=\\"checkbox\\"]")',
            timeout=15000,
        )
        time.sleep(1.5)
    except Exception:
        pass

    start = time.time()
    timeout = 90
    clicked = False

    while time.time() - start < timeout:
        try:
            has_clearance = _has_cf_clearance(page)
            on_challenge  = is_challenge_page(page)

            if has_clearance and not on_challenge:
                logger.info("✅ Cloudflare passed!")
                return True

            if not clicked:
                if _try_click_checkbox(page):
                    clicked = True
                    logger.info("☑️  Checkbox clicked — waiting for clearance...")

        except Exception:
            pass

        time.sleep(0.5)

    logger.warning("⚠️  CF not solved in 90s — switching to manual mode")
    return _wait_manual_captcha(page, logger)


def _wait_manual_captcha(page, logger) -> bool:
    logger.info("👋 Solve CAPTCHA manually in the Kameleo browser")
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > 300:
            msg = "❌ CAPTCHA not solved in 5 min — giving up"
            logger.error(msg)
            notify_telegram(msg)
            return False
        try:
            if not is_challenge_page(page):
                logger.info("✅ CAPTCHA solved manually!")
                time.sleep(2)
                return True
            time.sleep(1)
        except Exception:
            time.sleep(1)


# ---- Contact button ------------------------------------------------
def click_contact_button(page, logger, retry_count=0):
    time.sleep(2)
    selectors = [
        "a:has-text('contact jagex')",
        "a:has-text('Contact Jagex')",
        "button:has-text('contact')",
        "//a[contains(text(), 'contact Jagex support')]",
        "//a[contains(text(), 'Contact Jagex')]",
    ]
    button = None
    for sel in selectors:
        try:
            button = page.query_selector(sel)
            if button:
                break
        except Exception:
            continue

    if not button or not button.is_visible():
        return False

    try:
        button.scroll_into_view_if_needed()
        time.sleep(1)
        button.click()
        button_delay()
        logger.info("🔗 Contact Jagex button clicked")
        return True
    except TimeoutError:
        logger.error("❌ Timeout on contact button")
        return False
    except Exception:
        if retry_count < 2:
            time.sleep(2)
            return click_contact_button(page, logger, retry_count + 1)
        return False


# ---- State machine helpers -----------------------------------------
def wait_for_page(page, logger, timeout=30000):
    try:
        page.wait_for_load_state("domcontentloaded", timeout=timeout)
    except Exception:
        pass
    time.sleep(random.uniform(0.4, 0.8) * SPEED_FACTOR)


def get_page_state(page, logger) -> str:
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
    creation_month, creation_year, membership_month, membership_year = dates
    logger.info("📝 Filling recovery form...")

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
            pass

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
    except Exception:
        pass

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

    logger.info("📤 Submitting form...")
    time.sleep(random.uniform(1, 2) * SPEED_FACTOR)
    page.click('//*[@id="submit_button"]')
    logger.info("✅ Form submitted!")


# ---- Main ----------------------------------------------------------
def main(file_number=1):
    logger = setup_logging(file_number)
    profile = None
    client  = None

    try:
        account_data   = read_account_file(file_number)
        email_username = "@" in account_data["stored_username"]
        dates = (
            pick_creation_and_membership_for_email_like_username()
            if email_username else
            pick_creation_and_membership_for_username_login()
        )

        logger.info(
            f"🚀 Starting recovery #{file_number} — "
            f"{account_data['stored_username']} "
            f"({'email' if email_username else 'username'})"
        )

        client = KameleoLocalApiClient()
        fps    = client.fingerprint.search_fingerprints(device_type="desktop", browser_product="chrome")
        fp     = random.choice(fps)

        profile = client.profile.create_profile(
            CreateProfileRequest(
                fingerprint_id=fp.id,
                name=f"Recovery_{file_number}_{int(time.time())}",
                proxy=ProxyChoice(
                    value="socks5",
                    extra=Server(
                        host=account_data["proxy_host"],
                        port=account_data["proxy_port"],
                        id=account_data["proxy_user"],
                        secret=account_data["proxy_pass"],
                    ),
                ),
            )
        )

        logger.info("🌐 Launching browser...")
        with sync_playwright() as p:
            try:
                kameleo_port = os.getenv("KAMELEO_PORT", "5050")
                browser = p.chromium.connect_over_cdp(
                    f"ws://localhost:{kameleo_port}/playwright/{profile.id}"
                )
                page = browser.contexts[0].new_page()
                page.set_default_timeout(120000)
                logger.info("✅ Browser ready")

                page.goto(
                    "https://secure.runescape.com/m=accountappeal/passwordrecovery",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )

                form_submits   = 0
                contact_clicked = False
                state_hits     = {}
                session_start  = time.time()
                form_reached   = False

                for _ in range(30):
                    if not form_reached and (time.time() - session_start) > FORM_REACH_TIMEOUT:
                        msg = (
                            f"⚠️ <b>Failsafe #{file_number}</b> — "
                            f"form not reached in {FORM_REACH_TIMEOUT}s "
                            f"(proxy too slow / low trust score)"
                        )
                        logger.warning(
                            f"⏱️  Timeout: form not reached in {FORM_REACH_TIMEOUT}s — "
                            "proxy too slow or low trust score. Closing."
                        )
                        notify_telegram(msg)
                        break

                    state = get_page_state(page, logger)
                    state_hits[state] = state_hits.get(state, 0) + 1

                    if state_hits[state] > 4:
                        msg = f"❌ <b>Stuck #{file_number}</b> — state <code>{state}</code> looping"
                        logger.error(f"❌ Stuck in '{state}' — aborting")
                        notify_telegram(msg)
                        break

                    if state == "closed":
                        logger.error("❌ Browser closed unexpectedly")
                        notify_telegram(f"❌ <b>Browser crash #{file_number}</b>")
                        break

                    elif state == "captcha":
                        handle_cloudflare_turnstile(page, logger, account_data=account_data)
                        wait_for_page(page, logger)

                    elif state == "username_entry":
                        logger.info("⌨️  Entering username...")
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
                            logger.info(f"✅ Form submitted twice — closing in {AUTO_CLOSE_DELAY}s")
                            time.sleep(AUTO_CLOSE_DELAY)
                            break
                        fill_and_submit_recovery_form(page, account_data, dates, logger)
                        form_submits += 1
                        wait_for_page(page, logger)

                    elif state == "confirmation":
                        if contact_clicked:
                            logger.info(f"🎉 Recovery complete! Closing in {AUTO_CLOSE_DELAY}s...")
                            notify_telegram(
                                f"🎉 <b>Done #{file_number}</b> — "
                                f"{account_data['stored_username']}"
                            )
                            time.sleep(AUTO_CLOSE_DELAY)
                            break
                        if click_contact_button(page, logger):
                            contact_clicked = True
                            wait_for_page(page, logger)
                        else:
                            logger.info(f"🎉 Ticket sent! Closing in {AUTO_CLOSE_DELAY}s...")
                            notify_telegram(
                                f"🎉 <b>Done #{file_number}</b> — "
                                f"{account_data['stored_username']}"
                            )
                            time.sleep(AUTO_CLOSE_DELAY)
                            break

                    elif state == "rejected":
                        msg = (
                            f"⛔ <b>Rejected #{file_number}</b> — "
                            f"{account_data['stored_username']}\n"
                            f"<code>{page.url}</code>"
                        )
                        logger.warning(f"⛔ Rejected by Runescape — {page.url}")
                        notify_telegram(msg)
                        break

                    elif state == "unknown":
                        logger.info(f"❓ Unknown page — waiting for redirect...")
                        resolved = False
                        for _ in range(15):
                            time.sleep(1)
                            if get_page_state(page, logger) != "unknown":
                                resolved = True
                                break
                        if not resolved:
                            logger.info("⏱️  No state change in 15s — exiting")
                            break

                logger.info(f"🏁 Session #{file_number} finished")

            finally:
                try:
                    browser.close()
                except Exception:
                    pass

    except FileNotFoundError as e:
        msg = f"❌ <b>File error #{file_number}</b>: {e}"
        logger.error(f"❌ File not found: {e}")
        notify_telegram(msg)
    except ValueError as e:
        msg = f"❌ <b>Data error #{file_number}</b>: {e}"
        logger.error(f"❌ Data error: {e}")
        notify_telegram(msg)
    except Exception as e:
        import traceback
        msg = f"❌ <b>Error #{file_number}</b>: {e}"
        logger.error(f"❌ Error: {e}\n{traceback.format_exc()}")
        notify_telegram(msg)
    finally:
        if profile and client:
            try:
                client.profile.stop_profile(profile.id)
            except Exception:
                pass
            try:
                client.profile.delete_profile(profile.id)
            except Exception:
                pass


if __name__ == "__main__":
    file_number = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    main(file_number)
