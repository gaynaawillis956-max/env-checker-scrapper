# Multi-Provider Deliverability Checker

Test email accounts across **ALL major providers** - Gmail, Outlook, Yahoo, IMAP, and more!

## 🌍 Supported Providers

✅ **Gmail** - Requires app password  
✅ **Outlook / Microsoft 365** - Standard password  
✅ **Hotmail** - Standard password  
✅ **Yahoo Mail** - Requires app password  
✅ **AOL** - Requires app password  
✅ **ProtonMail** - Standard password  
✅ **Zoho Mail** - Standard password  
✅ **iCloud** - Requires app password  
✅ **Custom IMAP/SMTP** - Any server  

---

## Quick Start

### Test Gmail Account
```bash
python3 multi_deliverability.py user@gmail.com "16char_app_password"
```

### Test Outlook Account
```bash
python3 multi_deliverability.py user@outlook.com "password"
```

### Test Yahoo Account
```bash
python3 multi_deliverability.py user@yahoo.com "app_password"
```

### Test Custom IMAP Server
```bash
python3 multi_deliverability.py user@custom.com "password" \
  --imap imap.custom.com --smtp smtp.custom.com
```

### Via Batch File
```
RUN-DELIVERABILITY.bat user@gmail.com "app_password"
```

---

## What It Tests

Each account is tested for:

### ✉️ **IMAP (Receiving)**
- Can connect to IMAP server
- Can authenticate
- Can access inbox
- **Can:** Receive emails ✓

### 📤 **SMTP (Sending)**
- Can connect to SMTP server
- Can authenticate
- Can send emails
- **Can:** Send emails ✓

### 📊 **Results**
- **✓ Fully Working** - Can send AND receive
- **~ Partial Working** - Can send OR receive (not both)
- **✗ Not Working** - Cannot send or receive
- **? Unknown** - Provider not recognized

---

## Setup by Provider

### 1️⃣ Gmail (App Password)

**Required:** App Password (not regular password)

**Steps:**
1. Go to: **myaccount.google.com/security**
2. Turn ON **2-Step Verification**
3. Go to: **myaccount.google.com/apppasswords**
4. Select: Mail → Windows PC
5. Generate & copy 16-char password
6. Use password in checker

**Command:**
```bash
python3 multi_deliverability.py yourname@gmail.com "sixteen_char_pass"
```

---

### 2️⃣ Outlook / Microsoft 365

**Required:** Regular password (no app password needed)

**Steps:**
1. Use your regular Outlook password

**Command:**
```bash
python3 multi_deliverability.py you@outlook.com "password"
```

---

### 3️⃣ Yahoo Mail (App Password)

**Required:** App Password

**Steps:**
1. Go to: **account.yahoo.com**
2. Click **Account Security**
3. Generate **App Password**
4. Copy password
5. Use in checker

**Command:**
```bash
python3 multi_deliverability.py yourname@yahoo.com "app_password"
```

---

### 4️⃣ AOL Mail (App Password)

**Required:** App Password

**Steps:**
1. Go to: **myaccount.aol.com**
2. Click **Security**
3. Generate **App Password**
4. Use in checker

**Command:**
```bash
python3 multi_deliverability.py yourname@aol.com "app_password"
```

---

### 5️⃣ iCloud (App Password)

**Required:** App Password

**Steps:**
1. Go to: **appleid.apple.com**
2. Click **App Passwords**
3. Generate password for Mail
4. Use in checker

**Command:**
```bash
python3 multi_deliverability.py yourname@icloud.com "app_password"
```

---

### 6️⃣ ProtonMail (Standard Password)

**Required:** Regular password

**Command:**
```bash
python3 multi_deliverability.py yourname@protonmail.com "password"
```

---

### 7️⃣ Zoho Mail (Standard Password)

**Required:** Regular password

**Command:**
```bash
python3 multi_deliverability.py yourname@zoho.com "password"
```

---

### 8️⃣ Custom IMAP/SMTP Server

**For enterprise or custom email:**

```bash
python3 multi_deliverability.py user@company.com "password" \
  --imap imap.company.com \
  --smtp smtp.company.com \
  --imap-port 993 \
  --smtp-port 587
```

---

## Output Example

```
{
  "email": "test@gmail.com",
  "provider": "Gmail",
  "status": "fully_working",
  "can_send": true,
  "can_receive": true,
  "tests": {
    "imap": {
      "status": "ok",
      "service": "IMAP",
      "accessible": true
    },
    "smtp": {
      "status": "ok",
      "service": "SMTP",
      "sendable": true
    }
  }
}

======================================================================
Result: FULLY_WORKING
Provider: Gmail
✓ Account can SEND and RECEIVE emails
======================================================================
```

---

## Common Issues & Fixes

### ❌ "auth_failed"
**Problem:** Wrong password or credentials

**Fix:**
- Verify email address spelling
- Verify password/app-password is correct
- Make sure 2-Step Verification is ON (if using Gmail)
- Regenerate app password

### ❌ "IMAP: error"
**Problem:** Can't receive emails

**Possible causes:**
- IMAP disabled in account settings
- Firewall/security blocking IMAP
- Wrong IMAP server address
- Account suspension

**Fix:**
- Enable IMAP in account settings
- Check firewall rules
- Verify IMAP server address

### ❌ "SMTP: error"
**Problem:** Can't send emails

**Possible causes:**
- SMTP disabled
- Wrong SMTP port (use 587 or 465)
- Rate limiting
- Account suspension

**Fix:**
- Enable SMTP in account settings
- Try different port (587 for TLS, 465 for SSL)
- Check account is not suspended

### ❌ "unknown_provider"
**Problem:** Provider not auto-detected

**Fix:**
- Specify provider manually: `--provider gmail`
- Or use custom IMAP/SMTP: `--imap imap.xxx.com`

---

## Batch Testing

Test multiple accounts from a file:

**accounts.txt:**
```
test1@gmail.com:app_password1
test2@outlook.com:regular_password
test3@yahoo.com:app_password3
```

**Bash script (test_accounts.sh):**
```bash
#!/bin/bash
while IFS=':' read email password; do
  echo "Testing $email..."
  python3 multi_deliverability.py "$email" "$password"
  sleep 2
done < accounts.txt
```

**Or use SuperPilot after checking:**
```bash
python3 superpilot.py smtp_list.txt --threads 5
```

---

## Integration with Web Dashboard

After testing accounts:

1. **Check Results** - See which accounts work
2. **Get CSV** - Export working accounts
3. **Use in Mass Mailer** - Upload to web dashboard
4. **Send Campaigns** - Use tested accounts

---

## Command Reference

```bash
python3 multi_deliverability.py EMAIL PASSWORD [OPTIONS]

Options:
  --provider PROVIDER      Specify provider (gmail, outlook, yahoo, etc)
  --imap HOST             Custom IMAP server
  --imap-port PORT        IMAP port (default: 993)
  --smtp HOST             Custom SMTP server
  --smtp-port PORT        SMTP port (default: 587)
  --timeout SECONDS       Connection timeout (default: 10)
```

### Examples

**Auto-detect Gmail:**
```bash
python3 multi_deliverability.py test@gmail.com "apppass"
```

**Force provider:**
```bash
python3 multi_deliverability.py test@customdomain.com "pass" --provider outlook
```

**Custom IMAP only:**
```bash
python3 multi_deliverability.py user@company.com "pass" --imap imap.company.com
```

**Custom ports:**
```bash
python3 multi_deliverability.py user@server.com "pass" \
  --imap imap.server.com --imap-port 9993 \
  --smtp smtp.server.com --smtp-port 2587
```

---

## Status Codes

| Status | Meaning | Next Step |
|--------|---------|-----------|
| fully_working | IMAP + SMTP OK | Use for sending |
| partial_working | Either IMAP or SMTP | Investigate failure |
| not_working | Both failed | Check password/settings |
| auth_failed | Wrong credentials | Fix password |
| unknown_provider | Can't detect provider | Use --provider flag |

---

## Tips & Tricks

### 1. Test Before Bulk Sending
```bash
# Test one account first
python3 multi_deliverability.py test@gmail.com "apppass"

# If working, use in campaigns
python3 superpilot.py accounts.txt --threads 10
```

### 2. Find Working Accounts
```bash
# Test multiple, keep working ones
python3 multi_deliverability.py account1@gmail.com "pass1"
python3 multi_deliverability.py account2@outlook.com "pass2"
python3 multi_deliverability.py account3@yahoo.com "pass3"

# Use working ones in Mass Mailer
```

### 3. Verify After Changes
```bash
# Test after changing password/settings
python3 multi_deliverability.py updated@gmail.com "newpass"
```

### 4. Debug Issues
```bash
# Add custom server info for testing
python3 multi_deliverability.py user@company.com "pass" \
  --imap imap.company.com --smtp smtp.company.com --timeout 30
```

---

## Troubleshooting Checklist

- [ ] Email address spelled correctly
- [ ] Password/app-password correct
- [ ] 2-Step Verification enabled (if required)
- [ ] App passwords enabled
- [ ] IMAP/SMTP enabled in account settings
- [ ] Not rate-limited or suspended
- [ ] Firewall allows connections
- [ ] Correct port (587 or 465)
- [ ] Provider name correct

---

**Multi-Deliverability Checker - Test any email, any provider!** 🌍

Questions? Check the output JSON for detailed error messages.
