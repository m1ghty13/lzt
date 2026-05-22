# RuneScape Account Recovery Script - Setup & Usage

## Requirements
- Python 3.8+ (3.10+ recommended)
- Kameleo Desktop App (running and logged in)
- Windows/Linux system

## Installation

1. **Install Python dependencies:**
```bash
pip install -r requirements.txt
playwright install
```

2. **Start Kameleo Desktop:**
   - Open the Kameleo application
   - Make sure you're logged in
   - The application should be running before executing the script

3. **(Optional) Set up CAPTCHA API key for automatic solving:**
```bash
# For 2Captcha (https://2captcha.com)
set CAPTCHA_API_KEY=your_2captcha_api_key

# Or add to environment variables permanently
```

## Usage

### Single Account Recovery
```bash
python 1.py 1
```

### Batch Processing (Multiple Accounts)
```bash
for /L %i in (1,1,10) do python 1.py %i
```

### On VPS (Background)
```bash
# Run in background with nohup
nohup python 1.py 1 &

# Or with screen
screen -S recovery python 1.py 1
```

## File Format

Account data files should be in `results/` folder with format:
```
username_or_email
recovery_email
password1
password2
payment_email
postcode
creation_month
creation_year
country
state
isp
proxy_host:proxy_port:proxy_user:proxy_pass
```

Example: `results/1.txt`

## Script Features

### Automatic Handling
✓ Kameleo profile creation and cleanup
✓ Browser fingerprint randomization
✓ SOCKS5 proxy integration
✓ Login loop detection and recovery
✓ Form filling with humanization (random delays)
✓ CAPTCHA detection (manual + API solving)
✓ Contact button clicking
✓ Comprehensive error logging

### Stability Features
✓ Timeout-based waits (no infinite loops)
✓ Automatic browser/profile cleanup
✓ Graceful error handling
✓ Clean exit on failures
✓ No hanging processes

## Logs

Each run creates a log file:
- `results/log_1.txt` - for account 1
- `results/log_2.txt` - for account 2
- etc.

Check logs for detailed execution info and error messages.

## Troubleshooting

### "503 Service Unavailable" Error
**Solution:** Restart Kameleo Desktop
```powershell
taskkill /F /IM Kameleo.exe
# Then manually restart Kameleo application
```

### "No Kameleo fingerprints available"
**Solution:** Check Kameleo has fingerprints downloaded in the app

### "Connection refused" to proxy
**Solution:** Verify proxy credentials and format in account file

### CAPTCHA keeps timing out
**Solution:** 
- Solve manually (script waits 2 minutes)
- Or set up CAPTCHA API key for automatic solving
- Try different CAPTCHA solver service if one fails

## Performance Tips

1. **Run multiple instances in parallel:**
   - Each instance gets its own Kameleo profile
   - Use separate terminal/tmux windows

2. **Monitor resource usage:**
   - Each browser instance uses ~150-200MB RAM
   - Adjust delay values in script if too slow/fast

3. **VPS Deployment:**
   - Use screen/tmux for persistent sessions
   - Set CAPTCHA_API_KEY for unattended operation
   - Log rotation: back up `results/log_*.txt` periodically

## Support

For issues:
1. Check the log file first (`results/log_N.txt`)
2. Verify Kameleo is running: `tasklist | find "Kameleo"`
3. Test manual account recovery on runescape.com first

## Known Limitations

- CAPTCHA solving requires API key for full automation (manual solving fallback: 2 min timeout)
- Contact button may not appear on all recovery paths (optional step)
- Script depends on Kameleo for fingerprinting (not standalone)
- Proxy must be working/available throughout execution
