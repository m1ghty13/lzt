#!/usr/bin/env python3
"""Test script to verify Kameleo connection stability"""

from kameleo.local_api_client import KameleoLocalApiClient
from kameleo.local_api_client.models import CreateProfileRequest
from playwright.sync_api import sync_playwright
import time

try:
    client = KameleoLocalApiClient()
    print("OK: Connected to Kameleo API")

    fps = client.fingerprint.search_fingerprints(device_type='desktop', browser_product='chrome')
    print(f"OK: Found {len(fps)} fingerprints")

    profile = client.profile.create_profile(
        CreateProfileRequest(
            fingerprint_id=fps[0].id,
            name='Test'
        )
    )
    print(f"OK: Created profile: {profile.id}")

    print("Waiting for profile to initialize...")
    time.sleep(3)

    print("Starting Playwright...")
    with sync_playwright() as p:
        print(f"Connecting to browser on ws://localhost:5050/playwright/{profile.id}")
        browser = p.chromium.connect_over_cdp(f"ws://localhost:5050/playwright/{profile.id}")
        print("OK: Connected to browser")

        time.sleep(2)

        page = browser.contexts[0].new_page()
        print("OK: Created page")

        print("Navigating to example.com...")
        page.goto('https://example.com', wait_until='domcontentloaded', timeout=30000)
        print("OK: Page loaded")

        print("Testing page.title()...")
        title = page.title()
        print(f"OK: Page title: {title}")

        time.sleep(2)

        browser.close()
        print("OK: Browser closed")

    print("\nTest passed!")

except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
