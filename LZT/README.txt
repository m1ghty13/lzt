=================================================================
RUNESCAPE ACCOUNT RECOVERY AUTOMATION - FINAL DELIVERABLE
=================================================================

MAIN FILE: 1.py
- Fully refactored from original 12.py
- Implements all client requirements
- Ready for production VPS deployment
- Supports parallel instance execution

=================================================================
QUICK START
=================================================================

1. Install dependencies:
   pip install -r requirements.txt
   playwright install

2. Ensure Kameleo is running:
   - Open Kameleo Desktop application
   - Log in with your credentials
   - Leave running in background

3. Run a single account:
   python 1.py 1

   This will process account data from results/1.txt
   Log output will be saved to results/log_1.txt

4. For batch processing:
   python 1.py 1
   python 1.py 2
   python 1.py 3

=================================================================
WHAT'S INCLUDED
=================================================================

1.py (30KB) - Main production script with all features
requirements.txt - Python package dependencies
SETUP.md - Complete setup and troubleshooting guide
CHANGES.txt - Detailed list of improvements from 12.py
README.txt - This file

=================================================================
FEATURES IMPLEMENTED
=================================================================

[PRIORITY 1] CAPTCHA/Cloudflare Turnstile
  - Automatic detection and dual-mode solving
  - 2Captcha API integration (optional)
  - Manual solving fallback (2 minute timeout)
  - No mouse/pixel automation

[PRIORITY 2] Contact Button Clicking
  - Reliable element detection with multiple strategies
  - URL verification before clicking
  - Visibility checks and retry logic

[PRIORITY 3] Login Loop Recovery
  - Automatic detection and re-entry
  - Limited retries to prevent infinite loops
  - Clean failure if loop persists

[PRIORITY 4] Stability & Humanization
  - Comprehensive error handling
  - Timeout-based waits (no hangs)
  - Character-by-character typing with random delays
  - Automatic cleanup even on crashes

=================================================================
FILE FORMAT (results/1.txt, etc.)
=================================================================

Username
Recovery Email
Password1
Password2
Payment Email
Postcode
Creation Month
Creation Year
Country
State
ISP
proxy_host:proxy_port:proxy_user:proxy_pass

=================================================================
QUICK TEST
=================================================================

python 1.py 1

Check results/log_1.txt for output and any errors.

=================================================================
ENVIRONMENT VARIABLES (Optional)
=================================================================

set CAPTCHA_API_KEY=your_2captcha_key
set KAMELEO_PORT=5050

=================================================================
For full documentation, see SETUP.md and CHANGES.txt
=================================================================
