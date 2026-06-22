# SuperPilot - Advanced SMTP Testing & Automation

**SuperPilot v2.0** - Enterprise-grade SMTP testing with multi-threading, IMAP verification, detailed reports, and advanced automation.

## 🚀 Key Features

✅ **Multi-Threading** - Test 5-10x faster with concurrent connections  
✅ **IMAP Verification** - Verify inboxes are actually accessible  
✅ **Email Sending** - Send test emails from working accounts  
✅ **HTML Reports** - Beautiful dashboards with statistics  
✅ **CSV Export** - Export working accounts for other tools  
✅ **JSON Logs** - Detailed structured data for analysis  
✅ **Retry Logic** - Automatic retries on failure  
✅ **Advanced Stats** - Detailed error categorization  
✅ **Logging** - Complete activity logs for debugging  
✅ **Progress Display** - Real-time countdown and status  

## Quick Start

### Minimal (Default Settings)
```bash
python3 superpilot.py smtps.txt
```

### Recommended (Faster with More Threads)
```bash
python3 superpilot.py smtps.txt --threads 10
```

### Advanced (Full Control)
```bash
python3 superpilot.py smtps.txt \
  --threads 10 \
  --warmup 60 \
  --iterations 5 \
  --test-email mytest@domain.com
```

### Via Batch File
```
Double-click: RUN-SUPERPILOT.bat smtps.txt --threads 10
```

## Input Format

Create `smtps.txt` with credentials:
```
smtp.gmail.com:587:user1@gmail.com:password1
smtp.outlook.com:587:user2@outlook.com:password2
smtp.company.com:25:admin@company.com:secretpass
mail.server.com:465:test@server.com:pass123
```

**Format:** `host:port:username:password`

## Output Files

### 1. **HTML Report** (Visual Dashboard)
```
superpilot_report_20260620_103045.html
```
- Beautiful dark theme
- Statistics cards
- Detailed iteration data
- Working accounts table
- Open in any browser

### 2. **JSON Results** (Raw Data)
```json
{
  "start_time": "2026-06-20T10:30:45.123456",
  "iterations": [
    {
      "iteration": 1,
      "tested": 10,
      "working": 8,
      "verified": 6,
      "sent": 5
    }
  ],
  "working_smtps": [
    {
      "host": "smtp.gmail.com",
      "port": 587,
      "user": "user@gmail.com",
      "pass": "password"
    }
  ]
}
```

### 3. **CSV Export** (For Import)
```
superpilot_working_20260620_103045.csv

host,port,user,pass
smtp.gmail.com,587,user1@gmail.com,password1
smtp.outlook.com,587,user2@outlook.com,password2
```

### 4. **Activity Log** (Debugging)
```
superpilot.log

2026-06-20 10:30:45,123 [INFO] Loaded 10 SMTP credentials
2026-06-20 10:30:46,234 [DEBUG] Testing smtp.gmail.com:587
2026-06-20 10:30:47,345 [DEBUG] SMTP OK: user1@gmail.com
...
```

## Commands & Options

```bash
python3 superpilot.py smtps.txt [options]

Options:
  --test-email EMAIL       Email to use for inbox/send tests
                          (default: test@example.com)

  --threads NUMBER        Concurrent testing threads
                         (default: 5, range: 1-20)

  --warmup SECONDS        Wait between iterations (warmup period)
                         (default: 30 seconds)

  --iterations NUMBER     Total iterations to run
                         (default: 5 iterations)

  --no-report            Skip HTML report generation
                         (saves processing time)
```

## Examples

### Fast Testing (Many Threads)
```bash
python3 superpilot.py smtps.txt --threads 20 --warmup 10 --iterations 2
```
- 20 concurrent threads
- 10 second warmup
- 2 quick iterations
- **Best for:** Initial filtering

### Slow & Careful (Strict Servers)
```bash
python3 superpilot.py smtps.txt --threads 3 --warmup 120 --iterations 5
```
- 3 concurrent threads
- 120 second warmup
- 5 careful iterations
- **Best for:** High-quality, low-ban-rate testing

### High Volume (Many Accounts)
```bash
python3 superpilot.py smtps.txt --threads 15 --iterations 10
```
- 15 threads
- Default 30s warmup
- 10 iterations
- **Best for:** Large lists

### Single Pass
```bash
python3 superpilot.py smtps.txt --iterations 1 --warmup 5
```
- Single pass
- Minimal warmup
- Quick validation
- **Best for:** Rapid checking

## Testing Workflow

**Per Iteration:**

```
1. Test SMTP (Multi-threaded)
   ├─ Connect to each SMTP server
   ├─ Authenticate user/pass
   └─ Result: Working list

2. Verify Inbox (Multi-threaded IMAP)
   ├─ Check IMAP access
   ├─ List mailboxes
   └─ Result: Verified list

3. Send Test Emails (Multi-threaded)
   ├─ Compose email
   ├─ Send from each account
   └─ Result: Successful sends

4. Warmup Period
   └─ Wait N seconds before next iteration
```

## Understanding Statistics

**Iteration Output:**
```
[1/4] Testing 10 SMTP credentials (Multi-threaded)...
    ✓ 8/10 working (2 failed)

[2/4] Verifying inboxes (IMAP)...
    ✓ 6/8 inboxes accessible

[3/4] Sending test emails...
    ✓ 5/6 emails sent

[4/4] Warmup period (30s)...
```

**Final Report:**
- **Iterations:** Number of test cycles
- **Total Tested:** Sum of SMTP accounts tested
- **Working SMTP:** Accounts that passed SMTP authentication
- **Emails Sent:** Total successful email sends

## Use Cases

### 1️⃣ Initial Filter (Fast)
```bash
python3 superpilot.py accounts.txt --threads 15 --iterations 1 --warmup 5
```
Quickly filter dead accounts from a large list.

### 2️⃣ Account Warmup (Prevent Blocking)
```bash
python3 superpilot.py accounts.txt --threads 5 --iterations 20 --warmup 60
```
Gradually warm up accounts before mass campaigns to prevent rate limiting.

### 3️⃣ Reliability Testing (High Quality)
```bash
python3 superpilot.py accounts.txt --threads 3 --iterations 10 --warmup 120
```
Find most stable accounts through repeated testing.

### 4️⃣ Validation Before Campaign
```bash
python3 superpilot.py accounts.txt --iterations 1
```
Quick validation before using accounts in mass mailer.

## Advanced Features

### Multi-Threading Performance
- **5 threads:** ~200 accounts/minute
- **10 threads:** ~400 accounts/minute
- **15 threads:** ~600 accounts/minute

> Increase threads for faster testing, decrease for stricter servers.

### Retry Mechanism
- Automatic retries on failure
- Exponential backoff (2^attempt seconds)
- Detailed error categorization

### IMAP Verification
- Checks inbox accessibility
- Verifies mailbox existence
- Confirms account is not suspended

### Email Sending Tests
- Composes proper email messages
- Tests SMTP send capability
- Verifies MIME formatting

## Troubleshooting

### All Accounts Failing?
```bash
# Check network connectivity
# Verify account credentials format: host:port:user:pass
# Try fewer threads: --threads 1
```

### Rate Limited by Server?
```bash
# Increase warmup time
python3 superpilot.py smtps.txt --warmup 300  # 5 minutes

# Reduce threads
python3 superpilot.py smtps.txt --threads 2
```

### Too Slow?
```bash
# Increase threads
python3 superpilot.py smtps.txt --threads 20

# Reduce iterations
python3 superpilot.py smtps.txt --iterations 1

# Skip HTML report
python3 superpilot.py smtps.txt --no-report
```

### Memory Issues?
```bash
# Reduce threads
python3 superpilot.py smtps.txt --threads 3

# Reduce list size
# Test smaller batches
```

## Integration with Web Dashboard

After SuperPilot completes:

1. **Check HTML Report**
   ```
   Open: superpilot_report_*.html
   ```

2. **Export Working Accounts**
   ```
   superpilot_working_*.csv
   ```

3. **Use in Mass Mailer**
   - Open Web Dashboard: `http://127.0.0.1:5000`
   - Go to **Mass Mailer**
   - Upload the CSV file
   - Configure email
   - Click **START**

## Performance Tips

1. **Balance Speed vs Accuracy**
   - 20 threads = fast but more rejections
   - 3 threads = slow but higher quality

2. **Warmup for Reputation**
   - Use 60-300 second warmup
   - Prevents immediate bans

3. **Retry on Failures**
   - Built-in retry logic
   - Usually finds transient issues

4. **Monitor Progress**
   - Watch real-time output
   - Check superpilot.log
   - Review HTML report

## Command-Line Tips

### Run in Background (Linux/Mac)
```bash
nohup python3 superpilot.py smtps.txt > output.log 2>&1 &
```

### Save Full Output
```bash
python3 superpilot.py smtps.txt 2>&1 | tee superpilot_full_output.txt
```

### Run Multiple Files in Sequence
```bash
python3 superpilot.py list1.txt && python3 superpilot.py list2.txt
```

## System Requirements

- Python 3.7+
- 100MB disk space
- 500MB RAM (for 10+ threads)
- Network access

## What Gets Logged

- SMTP test results (pass/fail/reason)
- IMAP verification status
- Email send results
- Thread execution times
- Error details and codes
- Statistics per iteration

---

**SuperPilot - Test smarter, faster, better!** 🚀

Questions? Check `superpilot.log` for details.
