# Format Converter - Auto-Detect & Convert Credentials

Automatically detect and convert **any credential format** to SMTP format for use with AutoPilot/SuperPilot.

## Supported Input Formats

✅ **Email:Password**
```
user@gmail.com:password123
admin@company.com:secretpass
```

✅ **SMTP:Password**
```
smtp.gmail.com:mypassword
mail.server.com:pass123
```

✅ **Username:Password** (Basic)
```
user123:password456
admin:pass789
```

✅ **Standard SMTP Format**
```
smtp.gmail.com:587:user@gmail.com:password
mail.server.com:25:admin@company.com:secretpass
```

✅ **Email Only**
```
test@domain.com
user@gmail.com
```

✅ **Mixed Format** (All in one file)
```
# Comments are ignored
user@gmail.com:pass123
smtp.outlook.com:password
admin@domain.com:secret
mail.server.com:25:user@domain.com:pass
```

---

## Quick Start

### 1. Detect Format
See what formats are in your file:
```bash
python3 format_converter.py combos.txt --detect
```

Output:
```
Format Detection Results:
  SMTP (host:port:user:pass):  12
  Email:Password:              45
  SMTP:Password:               8
  User:Password:               2
  Unknown:                     3
  Total:                       70
```

### 2. Convert & Save
Convert to SMTP format:
```bash
python3 format_converter.py combos.txt --output converted.txt
```

Creates `converted.txt` in standard format:
```
smtp.gmail.com:587:user@gmail.com:pass
smtp-mail.outlook.com:587:admin@company.com:secret
```

### 3. Use with AutoPilot/SuperPilot
```bash
python3 superpilot.py converted.txt --threads 10
```

---

## Usage Examples

### Convert Email:Password List
```bash
python3 format_converter.py emails_and_passwords.txt --output smtp_format.txt
```

### Convert Mixed Format File
```bash
python3 format_converter.py mixed_combos.txt --output clean.txt
```

### Check What Formats Are in File (No Conversion)
```bash
python3 format_converter.py suspicious_list.txt --detect
```

### Use Custom SMTP Port
```bash
python3 format_converter.py combos.txt --output converted.txt --port 465
```

### Via Batch File
```
RUN-CONVERTER.bat combos.txt --output converted.txt
RUN-CONVERTER.bat combos.txt --detect
```

---

## How It Works

### Format Detection

The converter automatically identifies:

1. **Standard SMTP** (host:port:user:pass)
   - Already correct format
   - Used as-is

2. **Email:Password**
   - Extracts domain: `user@gmail.com` → `gmail.com`
   - Looks up SMTP server: `smtp.gmail.com:587`
   - Combines: `smtp.gmail.com:587:user@gmail.com:password`

3. **SMTP:Password**
   - Extracts SMTP host
   - Assumes default port (587 or 465)
   - ⚠️ Username remains "unknown" (may fail)

4. **Username:Password**
   - No domain info
   - ⚠️ Marked with warning
   - Will likely fail

5. **Email Only**
   - Password missing
   - ⚠️ Will definitely fail

### Known SMTP Servers

Automatically maps domains to SMTP servers:

```
gmail.com         → smtp.gmail.com:587
outlook.com       → smtp-mail.outlook.com:587
hotmail.com       → smtp-mail.outlook.com:587
yahoo.com         → smtp.mail.yahoo.com:465
aol.com           → smtp.aol.com:465
icloud.com        → smtp.mail.icloud.com:587
protonmail.com    → smtp.protonmail.com:587
zoho.com          → smtp.zoho.com:465
```

### Fallback Behavior

If domain not recognized:
- Uses `smtp.{domain}` as host
- Uses port 587 by default
- May or may not work

---

## Output Format

All converted credentials follow standard format:
```
host:port:user:password
smtp.gmail.com:587:user@gmail.com:mypass
```

Ready to use with:
- AutoPilot: `python3 autopilot.py converted.txt`
- SuperPilot: `python3 superpilot.py converted.txt`
- Web Dashboard: Upload to Mass Mailer

---

## Tips & Tricks

### 1. Clean Your List First
Remove duplicates and empty lines:
```bash
sort combos.txt | uniq > cleaned.txt
python3 format_converter.py cleaned.txt --output final.txt
```

### 2. Check for Problems
```bash
python3 format_converter.py your_list.txt --detect
```
Look for high "Unknown" count - may indicate bad format.

### 3. Separate Good from Bad
Before converting, check:
```bash
# Count each format
grep "@" combos.txt | wc -l    # Email:pass entries
grep "smtp" combos.txt | wc -l # SMTP entries
```

### 4. Use Different Ports
```bash
# For port 465 (SSL)
python3 format_converter.py combos.txt --output converted.txt --port 465

# For port 25 (Plain)
python3 format_converter.py combos.txt --output converted.txt --port 25
```

---

## Examples

### Example 1: Basic Email:Password
**Input:**
```
user1@gmail.com:password123
user2@outlook.com:secret456
```

**Output (converted):**
```
smtp.gmail.com:587:user1@gmail.com:password123
smtp-mail.outlook.com:587:user2@outlook.com:secret456
```

### Example 2: Mixed Format
**Input:**
```
# Gmail users
user@gmail.com:pass123
admin@gmail.com:secret

# SMTP format
mail.company.com:25:user@company.com:pass456

# Yahoo
yahoo@yahoo.com:pass789
```

**Output (converted):**
```
smtp.gmail.com:587:user@gmail.com:pass123
smtp.gmail.com:587:admin@gmail.com:secret
mail.company.com:25:user@company.com:pass456
smtp.mail.yahoo.com:465:yahoo@yahoo.com:pass789
```

### Example 3: Corporate Email
**Input:**
```
john.smith@company.com:JohnPass123
jane.doe@company.com:JanePass456
admin@company.com:AdminPassword
```

**Output (converted):**
```
smtp.company.com:587:john.smith@company.com:JohnPass123
smtp.company.com:587:jane.doe@company.com:JanePass456
smtp.company.com:587:admin@company.com:AdminPassword
```

---

## Workflow

### Before AutoPilot/SuperPilot:
```
Your List → Format Converter → Converted List → SuperPilot
```

### Example:
```bash
# 1. You have mixed format list
# 2. Detect format
python3 format_converter.py mixed.txt --detect

# 3. Convert it
python3 format_converter.py mixed.txt --output clean.txt

# 4. Use with SuperPilot
python3 superpilot.py clean.txt --threads 10

# 5. Get results
# → superpilot_working_*.csv (working accounts)
# → superpilot_report_*.html (report)
```

---

## Troubleshooting

### "Unknown format"
The converter couldn't identify the format. Check:
- Is it email:pass or smtp:pass?
- Any special characters?
- Line endings correct (Unix vs Windows)?

### "User remaining unknown"
Happens when input is `smtp.host.com:password` without username.
**Solution:** Add username to input or use email:password format.

### "Password unknown"
Input only had email address.
**Solution:** Make sure password is after colon: `email@domain.com:password`

### "Too many warnings"
Many entries couldn't be fully converted.
**Solution:**
1. Check input format
2. Use --detect to see breakdown
3. Clean list first (remove bad entries)

---

## Integration with AutoPilot/SuperPilot

After conversion, you can immediately use:

```bash
# Quick test
python3 superpilot.py converted.txt --iterations 1

# Full test with warmup
python3 superpilot.py converted.txt --threads 10 --warmup 60

# Get results
# Check: superpilot_working_*.csv
```

---

**Format Converter makes credential prep easy!** 🚀

No more manual reformatting. Drop any format in, get standard SMTP out.
