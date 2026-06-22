#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Template Rotator - Rotate HTML & Text Templates
Avoid spam filters by rotating email content
"""
import json
import os
import random
from pathlib import Path
from typing import List, Dict

class TemplateRotator:
    """Manage and rotate email templates"""

    def __init__(self):
        self.templates_dir = "email_templates"
        self.templates_file = "templates.json"
        os.makedirs(self.templates_dir, exist_ok=True)
        self.templates = self.load_templates()
        self.rotation_index = {}

    def load_templates(self) -> Dict:
        """Load templates from file"""
        if os.path.isfile(self.templates_file):
            try:
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {'html': [], 'text': []}
        return {'html': [], 'text': []}

    def save_templates(self):
        """Save templates to file"""
        with open(self.templates_file, 'w', encoding='utf-8') as f:
            json.dump(self.templates, f, indent=2, ensure_ascii=False)

    def add_html_template(self, name: str, subject: str, html_content: str) -> bool:
        """Add HTML email template"""
        if 'html' not in self.templates:
            self.templates['html'] = []

        self.templates['html'].append({
            'name': name,
            'subject': subject,
            'content': html_content,
            'type': 'html',
            'created': str(Path(self.templates_dir) / f"{name}.html")
        })

        # Save HTML file
        with open(os.path.join(self.templates_dir, f"{name}.html"), 'w', encoding='utf-8') as f:
            f.write(html_content)

        self.save_templates()
        return True

    def add_text_template(self, name: str, subject: str, text_content: str) -> bool:
        """Add plain text email template"""
        if 'text' not in self.templates:
            self.templates['text'] = []

        self.templates['text'].append({
            'name': name,
            'subject': subject,
            'content': text_content,
            'type': 'text',
            'created': str(Path(self.templates_dir) / f"{name}.txt")
        })

        # Save text file
        with open(os.path.join(self.templates_dir, f"{name}.txt"), 'w', encoding='utf-8') as f:
            f.write(text_content)

        self.save_templates()
        return True

    def get_next_template(self, template_type: str = 'html'):
        """Get next template in rotation"""
        templates = self.templates.get(template_type, [])
        if not templates:
            return None

        key = f"{template_type}_index"
        if key not in self.rotation_index:
            self.rotation_index[key] = 0

        # Get current template
        current = templates[self.rotation_index[key]]

        # Increment for next time
        self.rotation_index[key] = (self.rotation_index[key] + 1) % len(templates)

        return current

    def get_random_template(self, template_type: str = 'html'):
        """Get random template (for variety)"""
        templates = self.templates.get(template_type, [])
        if not templates:
            return None
        return random.choice(templates)

    def list_templates(self, template_type: str = None) -> List[Dict]:
        """List all templates"""
        if template_type:
            return self.templates.get(template_type, [])

        result = []
        for ttype in ['html', 'text']:
            for template in self.templates.get(ttype, []):
                result.append(template)
        return result

    def delete_template(self, name: str) -> bool:
        """Delete a template"""
        for ttype in ['html', 'text']:
            templates = self.templates.get(ttype, [])
            for i, t in enumerate(templates):
                if t['name'] == name:
                    del templates[i]
                    self.save_templates()
                    # Delete file
                    try:
                        os.remove(os.path.join(self.templates_dir, f"{name}.{ttype[0]}"))
                    except:
                        pass
                    return True
        return False

    def generate_sample_templates(self):
        """Create sample templates"""
        # Sample HTML
        html1 = """<html>
<body style="font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px;">
  <div style="background-color: white; padding: 30px; border-radius: 8px; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #333; margin-bottom: 20px;">Hello {{NAME}},</h2>

    <p style="color: #666; line-height: 1.6; margin-bottom: 15px;">
      We have an exciting opportunity for you. Check out what we've prepared.
    </p>

    <p style="color: #666; line-height: 1.6; margin-bottom: 15px;">
      {{MESSAGE}}
    </p>

    <p style="color: #999; font-size: 12px; margin-top: 30px;">
      Best regards,<br>
      The Team
    </p>
  </div>
</body>
</html>"""

        html2 = """<html>
<body style="font-family: 'Segoe UI', Tahoma, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; margin: 0;">
  <div style="background-color: white; padding: 40px; border-radius: 12px; max-width: 600px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
    <h1 style="color: #667eea; margin-top: 0;">Great News!</h1>

    <p style="color: #555; line-height: 1.8; font-size: 16px;">
      {{MESSAGE}}
    </p>

    <div style="background-color: #f0f4ff; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #667eea;">
      <p style="color: #667eea; margin: 0; font-weight: bold;">Important:</p>
      <p style="color: #666; margin: 5px 0 0 0;">This is a time-sensitive opportunity.</p>
    </div>

    <p style="color: #999; font-size: 11px; margin-top: 30px; text-align: center;">
      © 2026 Your Company
    </p>
  </div>
</body>
</html>"""

        # Sample text
        text1 = """Hello {{NAME}},

We wanted to reach out to you with something special.

{{MESSAGE}}

Thank you for your time and consideration.

Best regards,
The Team"""

        text2 = """Hi {{NAME}},

Great news!

{{MESSAGE}}

We look forward to hearing from you soon.

Warm regards,
The Team"""

        # Add samples
        self.add_html_template("Professional-Blue", "Important Update", html1)
        self.add_html_template("Modern-Gradient", "Exciting Opportunity", html2)
        self.add_text_template("Formal-Letter", "Hello", text1)
        self.add_text_template("Friendly-Letter", "Great News", text2)

        print("✓ Sample templates created!")
        print("  • Professional-Blue (HTML)")
        print("  • Modern-Gradient (HTML)")
        print("  • Formal-Letter (Text)")
        print("  • Friendly-Letter (Text)")

    def rotate_for_campaign(self, recipient_count: int) -> List[Dict]:
        """Get templates for a campaign (rotate across recipients)"""
        html_templates = self.templates.get('html', [])
        text_templates = self.templates.get('text', [])

        if not html_templates or not text_templates:
            return []

        result = []
        for i in range(recipient_count):
            html_idx = i % len(html_templates)
            text_idx = i % len(text_templates)
            result.append({
                'recipient_num': i + 1,
                'html': html_templates[html_idx],
                'text': text_templates[text_idx]
            })

        return result


def interactive_menu():
    """Interactive template manager"""
    rotator = TemplateRotator()

    while True:
        print("\n" + "="*60)
        print("  📧 EMAIL TEMPLATE ROTATOR")
        print("="*60)
        print("\n  What do you want to do?\n")
        print("  [1] Create sample templates")
        print("  [2] Add HTML template")
        print("  [3] Add text template")
        print("  [4] List all templates")
        print("  [5] Get next template (rotation)")
        print("  [6] Delete template")
        print("  [7] Generate rotation for campaign")
        print("  [8] Exit")
        print()

        choice = input("  → Choose (1-8): ").strip()

        if choice == "1":
            rotator.generate_sample_templates()

        elif choice == "2":
            name = input("\n  Template name: ").strip()
            subject = input("  Email subject: ").strip()
            print("  HTML content (paste, then Ctrl+D or Ctrl+Z+Enter when done):")
            lines = []
            while True:
                try:
                    line = input()
                    lines.append(line)
                except EOFError:
                    break
            html = "\n".join(lines)
            if rotator.add_html_template(name, subject, html):
                print(f"\n  ✓ HTML template '{name}' saved!")

        elif choice == "3":
            name = input("\n  Template name: ").strip()
            subject = input("  Email subject: ").strip()
            print("  Text content (paste, then Ctrl+D or Ctrl+Z+Enter when done):")
            lines = []
            while True:
                try:
                    line = input()
                    lines.append(line)
                except EOFError:
                    break
            text = "\n".join(lines)
            if rotator.add_text_template(name, subject, text):
                print(f"\n  ✓ Text template '{name}' saved!")

        elif choice == "4":
            print("\n  All Templates:\n")
            templates = rotator.list_templates()
            if templates:
                for i, t in enumerate(templates, 1):
                    ttype = t.get('type', 'unknown').upper()
                    print(f"  [{i}] {t['name']} ({ttype})")
                    print(f"      Subject: {t['subject']}")
            else:
                print("  No templates yet. Create some first!")

        elif choice == "5":
            print("\n  Next HTML template:")
            html = rotator.get_next_template('html')
            if html:
                print(f"    Name: {html['name']}")
                print(f"    Subject: {html['subject']}")
            print("\n  Next Text template:")
            text = rotator.get_next_template('text')
            if text:
                print(f"    Name: {text['name']}")
                print(f"    Subject: {text['subject']}")

        elif choice == "6":
            name = input("\n  Template name to delete: ").strip()
            if rotator.delete_template(name):
                print(f"  ✓ Template '{name}' deleted!")
            else:
                print(f"  ❌ Template not found")

        elif choice == "7":
            count = int(input("\n  Number of recipients: ").strip())
            rotation = rotator.rotate_for_campaign(count)
            print(f"\n  Rotation for {count} recipients:\n")
            for item in rotation[:5]:  # Show first 5
                print(f"  Recipient {item['recipient_num']}: {item['html']['name']} (HTML) + {item['text']['name']} (Text)")
            if len(rotation) > 5:
                print(f"  ... and {len(rotation) - 5} more")

        elif choice == "8":
            print("\n  Goodbye!\n")
            break

        else:
            print("  ❌ Invalid choice")


if __name__ == "__main__":
    interactive_menu()
