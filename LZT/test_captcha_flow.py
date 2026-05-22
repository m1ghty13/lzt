#!/usr/bin/env python3
"""
Minimal test script for CAPTCHA handling flow WITHOUT Kameleo
Tests: add_init_script interceptor, parameter capture, 2Captcha integration
"""

import os
import sys
import logging
from playwright.sync_api import sync_playwright
import requests
import time

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_captcha_flow.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Environment
CAPTCHA_API_KEY = os.getenv("CAPTCHA_API_KEY", "852675d7f72a99e3047e8ba106177696")

def solve_cloudflare_api(page_url: str, sitekey: str, captcha_params: dict = None) -> str:
    """Send task to 2Captcha for Cloudflare Turnstile solving"""
    if not CAPTCHA_API_KEY:
        logger.warning("CAPTCHA_API_KEY not set")
        return None

    try:
        final_sitekey = sitekey if sitekey else "0x4AAAAAAAAjq6WYeRDKmebM"
        logger.info(f"Sending task to 2Captcha (sitekey={final_sitekey[:20]}...)")

        task_data = {
            "clientKey": CAPTCHA_API_KEY,
            "task": {
                "type": "TurnstileTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": final_sitekey
            }
        }

        # Add extra parameters for Cloudflare Challenge
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

        logger.debug(f"Sending to 2Captcha: {task_data}")
        resp = requests.post("https://api.2captcha.com/createTask", json=task_data, timeout=30)
        result = resp.json()

        logger.info(f"2Captcha response: {result}")

        task_id = result.get("taskId")
        error_id = result.get("errorId")

        if error_id and error_id != 0:
            error_desc = result.get("errorDescription") or str(result)
            logger.warning(f"2Captcha error (errorId={error_id}): {error_desc}")
            return None

        if not task_id:
            logger.warning(f"2Captcha: no taskId in response: {result}")
            return None

        logger.info(f"Task created: ID={task_id}")

        # Poll for result (up to 2 minutes)
        for attempt in range(24):
            time.sleep(5)

            try:
                result = requests.post("https://api.2captcha.com/getTaskResult", json={
                    "clientKey": CAPTCHA_API_KEY,
                    "taskId": task_id
                }, timeout=30).json()

                logger.debug(f"Poll attempt {attempt}: {result}")

                if result.get("status") == "ready":
                    solution = result.get("solution", {})
                    token = solution.get("token")
                    if token:
                        logger.info(f"[OK] CAPTCHA solved! Token length: {len(token)}")
                        return token
                    else:
                        logger.warning(f"2Captcha: no token in solution: {solution}")
                        return None

                if attempt % 5 == 0:
                    logger.info(f"Waiting for result... ({attempt*5}s)")

            except Exception as poll_error:
                logger.debug(f"Poll error (attempt {attempt}): {poll_error}")
                if attempt > 20:
                    break
                continue

        logger.warning("2Captcha: timeout (2 minutes)")
        return None

    except Exception as e:
        logger.error(f"Error in solve_cloudflare_api: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def test_captcha_flow():
    """Test the CAPTCHA handling flow with add_init_script interceptor"""
    logger.info("=" * 70)
    logger.info("TEST: CAPTCHA Flow with add_init_script Interceptor")
    logger.info("=" * 70)

    with sync_playwright() as p:
        # Use regular Chrome (no Kameleo)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(120000)

        logger.info("Browser launched (headless=False so you can see what's happening)")

        # Prepare interceptor state
        captured_sitekey_dict = {
            "value": None,
            "action": None,
            "cData": None,
            "chlPageData": None,
            "callback": None
        }

        try:
            # SETUP: Inject interceptor BEFORE page.goto()
            logger.info("")
            logger.info("=" * 70)
            logger.info("STEP 1: Setup add_init_script interceptor")
            logger.info("=" * 70)

            logger.info("Installing Turnstile.render interceptor with add_init_script...")
            page.add_init_script("""
                const i = setInterval(() => {
                    if (window.turnstile && window.turnstile.render) {
                        clearInterval(i);
                        const originalRender = window.turnstile.render;
                        window.turnstile.render = function(element, options) {
                            window._tsParams = {
                                sitekey: options.sitekey,
                                action: options.action,
                                data: options.cData,
                                pagedata: options.chlPageData,
                                userAgent: navigator.userAgent
                            };
                            console.log('[INTERCEPT] Turnstile params captured:', window._tsParams);
                            window.tsCallback = options.callback;
                            return originalRender.apply(this, arguments);
                        };
                    }
                }, 10);
            """)
            logger.info("[OK] Interceptor injected via add_init_script")

            # Navigate to recovery page
            logger.info("")
            logger.info("=" * 70)
            logger.info("STEP 2: Navigate to recovery page")
            logger.info("=" * 70)

            logger.info("Navigating to: https://secure.runescape.com/m=accountappeal/passwordrecovery")
            page.goto('https://secure.runescape.com/m=accountappeal/passwordrecovery', wait_until="networkidle")
            logger.info("[OK] Recovery page loaded")

            # Check if CAPTCHA is present
            logger.info("")
            logger.info("=" * 70)
            logger.info("STEP 3: Detect CAPTCHA")
            logger.info("=" * 70)

            title = page.title()
            logger.info(f"Page title: {title}")

            if "Just a moment" in title:
                logger.info("[OK] CAPTCHA DETECTED - proceeding with solving")
            else:
                logger.info("No CAPTCHA detected (unexpected)")
                return

            # Try to get intercepted params
            logger.info("")
            logger.info("=" * 70)
            logger.info("STEP 4: Wait for interceptor to capture params")
            logger.info("=" * 70)

            logger.info("Waiting for window._tsParams to be defined...")
            try:
                page.wait_for_function("() => window._tsParams !== undefined", timeout=15000)
                params = page.evaluate("() => window._tsParams")

                if params:
                    logger.info("[OK] Intercepted Turnstile params:")
                    logger.info(f"  - sitekey: {params.get('sitekey')}")
                    logger.info(f"  - action: {params.get('action')}")
                    logger.info(f"  - data: {params.get('data')[:40] if params.get('data') else 'N/A'}...")
                    logger.info(f"  - pagedata: {params.get('pagedata')[:40] if params.get('pagedata') else 'N/A'}...")

                    # Save for 2Captcha
                    captured_sitekey_dict["value"] = params.get("sitekey")
                    captured_sitekey_dict["action"] = params.get("action")
                    captured_sitekey_dict["cData"] = params.get("data")
                    captured_sitekey_dict["chlPageData"] = params.get("pagedata")
                    captured_sitekey_dict["callback"] = params.get("callback")
                else:
                    logger.warning("window._tsParams is undefined or empty")

            except Exception as e:
                logger.warning(f"Failed to capture params: {e}")
                return

            # Try 2Captcha
            logger.info("")
            logger.info("=" * 70)
            logger.info("STEP 5: Send to 2Captcha")
            logger.info("=" * 70)

            token = solve_cloudflare_api(page.url, captured_sitekey_dict["value"], captured_sitekey_dict)

            if token:
                logger.info(f"[OK] Token received from 2Captcha: {token[:30]}...")

                # Try to inject token
                logger.info("")
                logger.info("=" * 70)
                logger.info("STEP 6: Inject token")
                logger.info("=" * 70)

                logger.info("Injecting token into page...")
                page.evaluate(f"""
                    () => {{
                        if (window.tsCallback) {{
                            window.tsCallback('{token}');
                            console.log('[INJECT] Token passed to callback');
                        }}
                    }}
                """)
                logger.info("[OK] Token injected")

                # Wait for URL change
                logger.info("")
                logger.info("=" * 70)
                logger.info("STEP 7: Wait for CAPTCHA bypass")
                logger.info("=" * 70)

                logger.info("Waiting for URL to change (indicating CAPTCHA passed)...")
                try:
                    page.wait_for_function(
                        "() => !window.location.href.includes('cf_chl_rt_tk')",
                        timeout=60000
                    )
                    logger.info(f"[OK] URL changed! Current URL: {page.url}")
                    logger.info("[OK][OK][OK] CAPTCHA SUCCESSFULLY BYPASSED [OK][OK][OK]")
                except Exception as e:
                    logger.warning(f"URL didn't change: {e}")
                    logger.info(f"Current URL: {page.url}")

            else:
                logger.error("[FAIL] Failed to get token from 2Captcha")

        except Exception as e:
            logger.error(f"Error in test: {e}")
            import traceback
            logger.error(traceback.format_exc())

        finally:
            logger.info("")
            logger.info("Closing browser...")
            browser.close()
            logger.info("[OK] Browser closed")


if __name__ == "__main__":
    logger.info(f"CAPTCHA_API_KEY configured: {bool(CAPTCHA_API_KEY)}")
    test_captcha_flow()
