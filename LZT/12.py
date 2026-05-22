from playwright.sync_api import sync_playwright, TimeoutError
from kameleo.local_api_client import KameleoLocalApiClient
from kameleo.local_api_client.models import CreateProfileRequest, ProxyChoice, Server
import os
import time
import random

# ---- Global speed factor for delays ----
SPEED_FACTOR = 1.0



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
    time.sleep(random.uniform(1.2, 2.8) * SPEED_FACTOR)

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

def read_account_file(file_number=1):
    results_folder = r"C:\Users\gogog\Downloads\Xivora\LZT\results"
    file_path = os.path.join(results_folder, f"{file_number}.txt")
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



def main():
    try:
        account_data = read_account_file(1)
        email_username = '@' in account_data['stored_username']

        creation_month = account_data['creation_month']
        creation_year = account_data['creation_year']

        if email_username:
            creation_month, creation_year, membership_month, membership_year = pick_creation_and_membership_for_email_like_username()
        else:
            creation_month, creation_year, membership_month, membership_year = pick_creation_and_membership_for_username_login()

        kameleo_port = os.getenv("KAMELEO_PORT", "5050")
        client = KameleoLocalApiClient()
        fps = client.fingerprint.search_fingerprints(device_type="desktop", browser_product="chrome")
        fp = random.choice(fps)

        profile = client.profile.create_profile(
            CreateProfileRequest(
                fingerprint_id=fp.id,
                name="Runescape Recovery",
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

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"ws://localhost:{kameleo_port}/playwright/{profile.id}")
            page = browser.contexts[0].new_page()
            page.set_default_timeout(120000)

            # ---- Go to recovery page ----
            page.goto('https://secure.runescape.com/m=accountappeal/passwordrecovery', wait_until="domcontentloaded")
            think_pause()
            human_type(page, '#email', account_data['stored_username'])
            field_pause()
            page.click('#passwordRecovery')
            button_delay()

            human_type(page, '#reg_email', account_data['mail_account'])
            field_pause()
            human_type(page, '#reg_email_conf', account_data['mail_account'])
            field_pause()
            human_type(page, '#password1', account_data['password1'])
            field_pause()
            if account_data['password2']:
                page.click('#add-password')
                button_delay()
                human_type(page, '#password2', account_data['password2'])
                random_delay()

            # ---- START: Skip recovery questions logic exactly as in your second code ----
            try:
                skip_button = page.query_selector('#recoveries_not_recognised')
                if skip_button:
                    skip_button.click()
                    button_delay()
                    checkbox = page.query_selector('label.m-show-password__check-holder:nth-child(1) > input:nth-child(1)')
                    if checkbox:
                        checkbox.click()
                        button_delay()
                        print("✅ Skipped recovery questions successfully")
                    else:
                        print("⚠️ Recovery checkbox not found, skipping...")
                else:
                    print("⚠️ Skip recovery button not found, skipping...")
            except Exception as e:
                print(f"⚠️ Exception while attempting to skip recovery questions: {e}")
            # ---- END skip recovery logic ----

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

            time.sleep(random.uniform(5, 7))
            page.click('//*[@id="submit_button"]')

            input("Press Enter to close the browser manually...")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
