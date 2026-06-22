# Auto-Save & Strategy Integration

The **Account Manager** now auto-saves all working accounts and suggests usage strategies.

## Quick Summary

```
Test Accounts → Auto-Saved → Get Strategy → Use Smartly
```

## What Gets Auto-Saved

✅ Email address  
✅ Password  
✅ Provider (Gmail, Outlook, Yahoo, etc)  
✅ Can Send? (SMTP works)  
✅ Can Receive? (IMAP works)  
✅ Test date & time  
✅ Test count (how many times tested)  

**File:** `working_accounts.json` (automatically created)

## Strategy Suggestions

After testing, you get:

```
✓ You have 5 fully-working accounts
  → Use for rotating sending (avoid rate limits)
  → Use multiple in parallel for scale

📤 Send-Only Accounts: 3
  → Can send, can't receive

📥 Receive-Only Accounts: 1
  → Can receive, can't send

Suggested Usage:
- Use 5 accounts with rotation
- Rotate every 5-10 emails
- Wait 30-60 seconds between rotations
- Prevents rate limiting & bans
```

## Usage Commands

### Save Account Manually
```bash
python3 account_manager.py \
  --add user@gmail.com "apppass" Gmail fully_working
```

### View All Accounts
```bash
python3 account_manager.py --list
```

### Get Strategy Report
```bash
python3 account_manager.py --report
```

### Export as SMTP List
```bash
python3 account_manager.py --export working_smtp.txt
```

### Get Quick Suggestion
```bash
python3 account_manager.py --suggest
```

## Integration with SuperPilot

After testing:

```bash
# Test accounts (auto-saves results)
python3 superpilot.py combos.txt

# Get strategy
python3 account_manager.py --report

# Export for Mass Mailer
python3 account_manager.py --export smtp_list.txt

# Use in Mass Mailer
python3 superpilot.py smtp_list.txt --threads 5
```

## Rotation Strategies

### With 1-2 Accounts
```
Single account: Send 10 emails → Wait 60s → Send 10 more
```

### With 3-5 Accounts
```
Rotation:
  Send 5 from A → Wait 30s
  Send 5 from B → Wait 30s
  Send 5 from C → Wait 30s
  Repeat...
```

### With 10+ Accounts
```
Parallel:
  5 threads × 2 emails each
  All at once, then wait 60s
  Rotate through all 10
```

## File Structure

```
working_accounts.json
[
  {
    "email": "user@gmail.com",
    "password": "app_password",
    "provider": "Gmail",
    "can_send": true,
    "can_receive": true,
    "created": "2026-06-20 10:30:00",
    "last_tested": "2026-06-20 10:30:00",
    "test_count": 1
  },
  ...
]
```

## Workflow

```
1. Browser Dashboard
   → Upload SMTP list
   → Test (shows results)

2. Auto-Save
   → Account Manager saves working ones
   → Tracks send/receive status

3. Get Suggestion
   → Run: python3 account_manager.py --report
   → Shows which accounts to use
   → How many threads recommended
   → Whether to rotate or not

4. Use Smart
   → Export: python3 account_manager.py --export
   → Use in SuperPilot/Mass Mailer
   → Implement rotation strategy
```

## Examples

### Example 1: Gmail Testing
```bash
# Test 1 Gmail
python3 multi_deliverability.py user@gmail.com "apppass"
# Result: ✓ Fully Working

# Account auto-saved to working_accounts.json

# Get suggestion
python3 account_manager.py --suggest
# Output: You have 1 working account. Single sending only.
```

### Example 2: Multiple Accounts
```bash
# Test multiple
python3 multi_deliverability.py user1@gmail.com "pass1"
python3 multi_deliverability.py user2@outlook.com "pass2"
python3 multi_deliverability.py user3@yahoo.com "pass3"

# Get strategy
python3 account_manager.py --report
# Output: Rotation strategy for 3 accounts

# Export and use
python3 account_manager.py --export working_smtp.txt
python3 superpilot.py working_smtp.txt --threads 3
```

### Example 3: Optimize Sending
```bash
# Know how many accounts you have
python3 account_manager.py --list
# Shows: 5 fully working, 3 send-only

# Get usage suggestion
python3 account_manager.py --suggest
# Shows: Use 5 threads, rotation: YES

# Run optimized
python3 superpilot.py accounts.txt --threads 5 --warmup 30
```

## Benefits

✅ **Auto-Save** - Never lose working accounts  
✅ **Smart Suggestions** - Know exactly how to use them  
✅ **Rotation Support** - Avoid bans with rotation strategy  
✅ **Scale Ready** - Use 1-100+ accounts efficiently  
✅ **Export Ready** - Instant SMTP list for other tools  
✅ **Persistent** - Accounts saved forever  

## Next Steps

1. **Test accounts** (via Browser, Deliverability Checker, or SuperPilot)
2. **Check what you have** → `python3 account_manager.py --list`
3. **Get strategy** → `python3 account_manager.py --report`
4. **Export** → `python3 account_manager.py --export smtp.txt`
5. **Use smartly** → Follow the rotation suggestion
