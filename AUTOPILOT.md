# AutoPilot - Automated SMTP Testing & Warmup Workflow

Automatically test SMTP credentials, validate inboxes, and send emails with built-in warmup periods.

## Workflow Overview

```
Iteration 1:
  ├─ Test SMTP credentials (host:port:user:pass)
  ├─ Filter working SMTP accounts
  ├─ Test inbox functionality (send test email)
  └─ Warmup period (30 seconds)

Iteration 2-5:
  └─ Repeat...

Results:
  └─ Save working SMTPs to JSON
```

## Quick Start

### Step 1: Prepare SMTP List

Create a file `smtps.txt` with credentials in this format:
```
smtp.gmail.com:587:user1@gmail.com:password1
smtp.outlook.com:587:user2@outlook.com:password2
smtp.company.com:25:admin@company.com:securepass
```

Format: `host:port:username:password`

### Step 2: Run AutoPilot

**Simple (default settings):**
```bash
python3 autopilot.py smtps.txt
```

**With custom options:**
```bash
python3 autopilot.py smtps.txt --warmup 60 --iterations 3 --test-email user@example.com
```

**Or use the batch file:**
```
Double-click: RUN-AUTOPILOT.bat smtps.txt
```

## Options

```
--test-email EMAIL       Email address to use for inbox testing
                        (default: test@example.com)

--warmup SECONDS        Wait time between iterations (let SMTP warm up)
                        (default: 30 seconds)

--iterations NUMBER     Number of test cycles to run
                        (default: 5 iterations)
```

## Examples

### Fast Testing (10 second warmup, 3 iterations)
```bash
python3 autopilot.py smtps.txt --warmup 10 --iterations 3
```

### Slow & Careful (2 minute warmup, 5 iterations)
```bash
python3 autopilot.py smtps.txt --warmup 120 --iterations 5
```

### Custom Test Email
```bash
python3 autopilot.py smtps.txt --test-email mytest@domain.com
```

## What Happens

### Per Iteration:
1. **Test SMTP Credentials**
   - Connects to each SMTP server
   - Verifies username/password
   - Filters out failed ones
   - Delay: 0.5s between each

2. **Test Inbox Functionality**
   - Sends test email from working SMTP
   - Verifies email can be sent
   - Tests first 3 working accounts
   - Delay: 1s between each

3. **Warmup Period**
   - Waits N seconds before next iteration
   - Gives SMTP servers time to "warm up"
   - Prevents rate limiting
   - Countdown timer shown

## Output

Real-time output shows:
```
============================================================
ITERATION 1/5
============================================================

[*] Step 1: Testing SMTP credentials...
  Testing: smtp.gmail.com:587
    ✓ SMTP OK
  Testing: smtp.outlook.com:587
    ✓ SMTP OK
    
    Result: 2/3 SMTP credentials working

[*] Step 2: Testing inbox functionality...
  Testing inbox: user1@gmail.com
    ✓ Inbox OK - Email sent
    
    Result: 1/2 inboxes working

[*] Step 3: Warmup period (30s)...
    Waiting: 30s...
    Waiting: 29s...
    ...
```

## Results File

After completion, results are saved to `autopilot_results.json`:

```json
{
  "timestamp": "2026-06-20 10:30:45",
  "stats": {
    "tested": 15,
    "working": 12,
    "inbox_ok": 8,
    "sent": 8,
    "failed": 4
  },
  "working_smtps": [
    {
      "host": "smtp.gmail.com",
      "port": 587,
      "user": "user1@gmail.com",
      "pass": "password1"
    },
    ...
  ]
}
```

## Use Cases

### 1. Initial SMTP Validation
Test a large list of credentials quickly:
```bash
python3 autopilot.py all_smtps.txt --iterations 1 --warmup 5
```

### 2. Account Warmup (Prevent Blocking)
Gradually warm up accounts before mass sending:
```bash
python3 autopilot.py smtps.txt --warmup 60 --iterations 10
```

### 3. Reliability Testing
Find which accounts are stable:
```bash
python3 autopilot.py smtps.txt --warmup 120 --iterations 5
```

### 4. One-Time Check
Quick validation without warmup:
```bash
python3 autopilot.py smtps.txt --warmup 1 --iterations 1
```

## Tips & Tricks

### Slow Down to Avoid Rate Limits
```bash
python3 autopilot.py smtps.txt --warmup 180  # 3 min between iterations
```

### Test with Different Email
```bash
python3 autopilot.py smtps.txt --test-email backup@company.com
```

### Run Many Iterations
```bash
python3 autopilot.py smtps.txt --iterations 20  # Many cycles
```

## Troubleshooting

### All tests failing?
- Check SMTP credentials format: `host:port:user:pass`
- Verify credentials are correct
- Check firewall/network access
- Some servers might block automated access

### Need more warmup time?
- Increase `--warmup` value
- Try 120-300 seconds for stricter servers

### Want faster results?
- Decrease `--warmup` to 10-30 seconds
- Reduce `--iterations` to 2-3

## Integration with Web Dashboard

After AutoPilot completes:
1. Check `autopilot_results.json` for working SMTPs
2. Open web dashboard: `http://127.0.0.1:5000`
3. Go to **Mass Mailer** tab
4. Upload the working SMTPs list
5. Configure email body
6. Click **START**

## Advanced: Custom Workflow

To modify the workflow, edit `autopilot.py`:
- Change test delay times (line 80, 91)
- Modify SMTP testing logic (line 76)
- Add webhook notifications
- Custom email body for testing

---

**AutoPilot makes SMTP testing fast and automatic!** 🚀
