# 📧 Email Template Rotation - Quick Start

Template rotation helps avoid spam filters by sending different email versions to different recipients. Perfect for mass campaigns.

## Features

✓ **HTML Templates** - Create beautiful email templates with styling  
✓ **Text Templates** - Plain text letter templates  
✓ **Auto Rotation** - Automatically cycle through templates  
✓ **Web Interface** - Select templates directly in Mass Mailer  
✓ **Template Variables** - Use `{{NAME}}`, `{{MESSAGE}}` in templates  

---

## Quick Start: 3 Steps

### Step 1️⃣ - Create Templates

Run the template manager:

```bash
python3 template_rotator.py
# OR use the batch file:
MANAGE-TEMPLATES.bat
```

Choose **[1] Create sample templates** to get started with examples.

### Step 2️⃣ - View Available Templates

In the template manager, choose **[4] List all templates**

You'll see:
```
[1] Professional-Blue (HTML)
    Subject: Important Update
[2] Modern-Gradient (HTML)
    Subject: Exciting Opportunity
[3] Formal-Letter (TEXT)
    Subject: Hello
[4] Friendly-Letter (TEXT)
    Subject: Great News
```

### Step 3️⃣ - Use in Mass Mailer

When you use the **Web Dashboard** (http://127.0.0.1:5000):

1. Go to **Mass Mailer** tab
2. Upload SMTP accounts
3. Enter recipient emails
4. **NEW:** Select a template from "Use Template" dropdown
5. Or paste custom HTML/text in "Email Body"
6. Click **Send**

---

## Creating Your Own Templates

### HTML Template Example

```html
<html>
<body style="font-family: Arial, sans-serif; background: white; padding: 20px;">
  <h2>Hello {{NAME}},</h2>
  
  <p>{{MESSAGE}}</p>
  
  <p>Best regards,<br>Your Company</p>
</body>
</html>
```

### Text Template Example

```
Hello {{NAME}},

{{MESSAGE}}

Best regards,
Your Company
```

**Available Variables:**
- `{{NAME}}` - Recipient name (if provided)
- `{{MESSAGE}}` - Custom message content

---

## Template Rotation How It Works

```
Recipients:    [email1@...] [email2@...] [email3@...] [email4@...]
               
Templates:     [Template A] [Template B] [Template A] [Template B]
               (cycles automatically)
```

If you have 2 HTML templates and 2 text templates, they rotate in order:
- Email 1 → Template A (HTML) + Template A (Text)
- Email 2 → Template B (HTML) + Template B (Text)
- Email 3 → Template A (HTML) + Template A (Text)
- Email 4 → Template B (HTML) + Template B (Text)

---

## Template Manager Commands

### Add HTML Template
```bash
python3 template_rotator.py
# Choose [2] Add HTML template
# Enter: name, subject, HTML content
```

### Add Text Template
```bash
python3 template_rotator.py
# Choose [3] Add text template
# Enter: name, subject, text content
```

### List Templates
```bash
python3 template_rotator.py
# Choose [4] List all templates
```

### Delete Template
```bash
python3 template_rotator.py
# Choose [6] Delete template
# Enter template name
```

### Get Next in Rotation
```bash
python3 template_rotator.py
# Choose [5] Get next template (rotation)
# Shows which template will be used next
```

---

## Files Created

When you create templates, these files are created:

```
email_templates/           ← All template HTML/text files
  ├── Professional-Blue.html
  ├── Modern-Gradient.html
  ├── Formal-Letter.txt
  └── Friendly-Letter.txt

templates.json            ← Template metadata (names, subjects, etc.)
```

**Backup these folders if you create custom templates!**

---

## Using Templates in Web Dashboard

### Via Web UI (Easiest)

1. **Open:** http://127.0.0.1:5000
2. **Tab:** "Mass Mailer"
3. **Upload SMTP list** (accounts)
4. **Enter recipient emails**
5. **Select template** from "Use Template" dropdown
6. **Click Send**

### Via CLI (Advanced)

```bash
python3 template_rotator.py
# Creates templates.json in root directory

# Then in Mass Mailer config:
python3 simple_mailer.py config.txt
```

---

## Rotation Statistics

Example: 3 templates, 100 recipients

```
Email #1  → Template 1 (HTML) + Template 1 (Text)
Email #2  → Template 2 (HTML) + Template 2 (Text)
Email #3  → Template 3 (HTML) + Template 3 (Text)
Email #4  → Template 1 (HTML) + Template 1 (Text)  ← Cycles back
...
Email #100 → Template 1 (HTML) + Template 1 (Text)
```

With more templates = **less detection risk** ✓

---

## Tips

✅ **Create 3-5 templates** minimum for campaigns  
✅ **Vary subject lines** in different templates  
✅ **Test templates** before large sends  
✅ **Monitor** if templates trigger spam filters  
✅ **Keep templates** similar in tone/content (not drastically different)  

---

## Troubleshooting

### Templates Not Showing?

1. Check `templates.json` exists
2. Check `email_templates/` folder has files
3. Run: `python3 template_rotator.py` → [1] Create sample templates

### Template Not Loading?

1. Check template name is correct (case-sensitive)
2. Check template file exists in `email_templates/` folder
3. Try selecting a different template

### "Use Template" Dropdown Empty?

1. Create templates first: `MANAGE-TEMPLATES.bat`
2. Refresh the web page (F5)
3. Check browser console for errors

---

## Next Steps

1. ✓ **Create sample templates:** `MANAGE-TEMPLATES.bat`
2. ✓ **View templates:** Template manager [4]
3. ✓ **Send test email:** Web Dashboard → Mass Mailer
4. ✓ **Monitor delivery:** Check recipient email

---

**Questions?** Check the main README.md or test manually first!
