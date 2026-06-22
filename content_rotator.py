#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Content Rotator - Create & Rotate Email Body Variations
Rotate email content to improve inbox delivery
"""
import json
import os
from pathlib import Path

class ContentRotator:
    """Manage and rotate email content variations"""

    def __init__(self):
        self.content_dir = "email_content"
        self.content_file = "content_sets.json"
        os.makedirs(self.content_dir, exist_ok=True)
        self.content_sets = self.load_content()

    def load_content(self) -> dict:
        """Load content from file"""
        if os.path.isfile(self.content_file):
            try:
                with open(self.content_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {'sets': {}}
        return {'sets': {}}

    def save_content(self):
        """Save content to file"""
        with open(self.content_file, 'w', encoding='utf-8') as f:
            json.dump(self.content_sets, f, indent=2, ensure_ascii=False)

    def create_content_set(self, name: str, variations: list) -> bool:
        """Create content set with multiple variations"""
        if 'sets' not in self.content_sets:
            self.content_sets['sets'] = {}

        if name in self.content_sets['sets']:
            print(f"  ⚠️  Content set '{name}' already exists")
            return False

        self.content_sets['sets'][name] = {
            'name': name,
            'variations': variations,
            'count': len(variations),
            'created': Path(self.content_dir) / f"{name}"
        }

        # Save each variation
        for i, content in enumerate(variations, 1):
            variation_file = os.path.join(self.content_dir, f"{name}_v{i}.html")
            with open(variation_file, 'w', encoding='utf-8') as f:
                f.write(content)

        self.save_content()
        return True

    def get_variation(self, set_name: str, index: int) -> str:
        """Get specific variation from set"""
        if set_name not in self.content_sets.get('sets', {}):
            return ''

        variations = self.content_sets['sets'][set_name]['variations']
        if not variations:
            return ''

        return variations[index % len(variations)]

    def list_content_sets(self) -> list:
        """List all content sets"""
        result = []
        for name, data in self.content_sets.get('sets', {}).items():
            result.append({
                'name': name,
                'variations': data.get('count', 0),
                'types': self._analyze_variations(data.get('variations', []))
            })
        return result

    def delete_content_set(self, name: str) -> bool:
        """Delete a content set"""
        if name in self.content_sets.get('sets', {}):
            variations = self.content_sets['sets'][name].get('count', 0)
            del self.content_sets['sets'][name]
            self.save_content()
            # Delete files
            for i in range(1, variations + 1):
                try:
                    os.remove(os.path.join(self.content_dir, f"{name}_v{i}.html"))
                except:
                    pass
            return True
        return False

    def _analyze_variations(self, variations: list) -> str:
        """Analyze variation types"""
        if not variations:
            return 'empty'
        first = str(variations[0])[:50]
        if '<html' in first.lower() or '<body' in first.lower():
            return 'HTML'
        return 'Text'

    def generate_sample_sets(self):
        """Create sample content variations"""

        # Set 1: Professional variations
        prof_v1 = """<html>
<body style="font-family: Arial, sans-serif;">
  <h2>Hello,</h2>
  <p>I wanted to reach out with an opportunity that might interest you.</p>
  <p>{{MESSAGE}}</p>
  <p>Best regards,<br>The Team</p>
  <p style="font-size: 11px; color: #999;">
    <a href="{{UNSUBSCRIBE_LINK}}">Unsubscribe</a>
  </p>
</body>
</html>"""

        prof_v2 = """<html>
<body style="font-family: Arial, sans-serif;">
  <p>Hi there,</p>
  <p>We thought you might be interested in this:</p>
  <p>{{MESSAGE}}</p>
  <p>Let us know what you think!</p>
  <p>Regards,<br>Our Team</p>
  <p style="font-size: 11px; color: #999;">
    <a href="{{UNSUBSCRIBE_LINK}}">Remove me from this list</a>
  </p>
</body>
</html>"""

        prof_v3 = """<html>
<body style="font-family: Arial, sans-serif;">
  <p>Hello {{NAME}},</p>
  <p>I hope this message finds you well. I'm reaching out because:</p>
  <p>{{MESSAGE}}</p>
  <p>Would love to hear your thoughts.</p>
  <p>Thanks,<br>The Team</p>
  <p style="font-size: 11px; color: #999;">
    <a href="{{UNSUBSCRIBE_LINK}}">Unsubscribe here</a>
  </p>
</body>
</html>"""

        # Set 2: Friendly variations
        friendly_v1 = """<html>
<body style="font-family: Georgia, serif;">
  <p>Hey {{NAME}},</p>
  <p>Quick note - {{MESSAGE}}</p>
  <p>Would appreciate your thoughts!</p>
  <p>Cheers,<br>The Team</p>
  <p style="font-size: 11px; color: #999;">
    <a href="{{UNSUBSCRIBE_LINK}}">Not interested? Unsubscribe</a>
  </p>
</body>
</html>"""

        friendly_v2 = """<html>
<body style="font-family: 'Segoe UI', sans-serif;">
  <p>Hi {{NAME}},</p>
  <p>Thought you'd find this valuable:</p>
  <p>{{MESSAGE}}</p>
  <p>Let me know your thoughts!</p>
  <p>Best,<br>Our Team</p>
  <p style="font-size: 11px; color: #999;">
    <a href="{{UNSUBSCRIBE_LINK}}">Unsubscribe</a>
  </p>
</body>
</html>"""

        friendly_v3 = """<html>
<body style="font-family: 'Courier New', monospace;">
  <p>Hello {{NAME}},</p>
  <p>Wanted to share something with you:</p>
  <p>{{MESSAGE}}</p>
  <p>Looking forward to hearing from you!</p>
  <p>Thanks,<br>Team</p>
  <p style="font-size: 11px; color: #999;">
    <a href="{{UNSUBSCRIBE_LINK}}">Remove from mailing list</a>
  </p>
</body>
</html>"""

        # Set 3: Minimalist variations
        minimal_v1 = """<html><body>
<p>Hi {{NAME}},</p>
<p>{{MESSAGE}}</p>
<p>Regards,<br>Team</p>
<hr style="margin: 20px 0; border: none; border-top: 1px solid #ccc;">
<p style="font-size: 10px; color: #999;"><a href="{{UNSUBSCRIBE_LINK}}">Unsubscribe</a></p>
</body></html>"""

        minimal_v2 = """<html><body>
<p>Hello {{NAME}},</p>
<p>{{MESSAGE}}</p>
<p>Thanks,<br>The Team</p>
<p style="margin-top: 20px; font-size: 10px; color: #999;">
<a href="{{UNSUBSCRIBE_LINK}}">Don't want this? Unsubscribe</a>
</p>
</body></html>"""

        minimal_v3 = """<html><body>
<p>{{NAME}},</p>
<p>{{MESSAGE}}</p>
<p>Cheers</p>
<p style="margin-top: 30px; font-size: 10px; color: #ccc; border-top: 1px solid #eee; padding-top: 10px;">
<a href="{{UNSUBSCRIBE_LINK}}">Unsubscribe from these emails</a>
</p>
</body></html>"""

        # Create sets
        self.create_content_set('Professional', [prof_v1, prof_v2, prof_v3])
        self.create_content_set('Friendly', [friendly_v1, friendly_v2, friendly_v3])
        self.create_content_set('Minimalist', [minimal_v1, minimal_v2, minimal_v3])

        print("✓ Sample content sets created!")
        print("  • Professional (3 variations)")
        print("  • Friendly (3 variations)")
        print("  • Minimalist (3 variations)")


def interactive_menu():
    """Interactive content manager"""
    rotator = ContentRotator()

    while True:
        print("\n" + "="*70)
        print("  📧 CONTENT ROTATOR - Email Body Variations")
        print("="*70)
        print("\n  What do you want to do?\n")
        print("  [1] Create sample content sets")
        print("  [2] Create custom content set")
        print("  [3] List all content sets")
        print("  [4] View content set variations")
        print("  [5] Delete content set")
        print("  [6] Export for Mass Mailer")
        print("  [7] Exit")
        print()

        choice = input("  → Choose (1-7): ").strip()

        if choice == "1":
            rotator.generate_sample_sets()

        elif choice == "2":
            set_name = input("\n  Content set name: ").strip()
            print("  Enter variations (one per input, empty line to finish):")
            variations = []
            while True:
                print(f"  Variation {len(variations) + 1}:")
                lines = []
                print("  (paste content, then Ctrl+D or Ctrl+Z+Enter):")
                while True:
                    try:
                        line = input("    ")
                        lines.append(line)
                    except EOFError:
                        break
                if lines:
                    variations.append("\n".join(lines))
                else:
                    break

            if variations:
                if rotator.create_content_set(set_name, variations):
                    print(f"\n  ✓ Content set '{set_name}' created with {len(variations)} variations!")
                else:
                    print(f"\n  ❌ Failed to create content set")

        elif choice == "3":
            print()
            sets = rotator.list_content_sets()
            if sets:
                print("  All Content Sets:\n")
                for i, s in enumerate(sets, 1):
                    print(f"  [{i}] {s['name']}")
                    print(f"      Variations: {s['variations']}")
                    print()
            else:
                print("  No content sets yet.")

        elif choice == "4":
            set_name = input("\n  Content set name: ").strip()
            content_set = rotator.content_sets.get('sets', {}).get(set_name)
            if content_set:
                print(f"\n  Variations in '{set_name}':\n")
                for i, content in enumerate(content_set['variations'], 1):
                    preview = content[:80].replace('\n', ' ')
                    print(f"  [{i}] {preview}...")
            else:
                print(f"\n  ❌ Content set not found")

        elif choice == "5":
            set_name = input("\n  Content set name to delete: ").strip()
            if rotator.delete_content_set(set_name):
                print(f"  ✓ Content set deleted!")
            else:
                print(f"  ❌ Content set not found")

        elif choice == "6":
            set_name = input("\n  Content set name to export: ").strip()
            content_set = rotator.content_sets.get('sets', {}).get(set_name)
            if content_set:
                # Export as multiple files or one combined
                filename = f"{set_name}_content.txt"
                with open(filename, 'w', encoding='utf-8') as f:
                    for i, content in enumerate(content_set['variations'], 1):
                        f.write(f"=== VARIATION {i} ===\n")
                        f.write(content)
                        f.write("\n\n")
                print(f"  ✓ Exported to: {filename}")
                print(f"    Use variations in Mass Mailer config")
            else:
                print(f"  ❌ Content set not found")

        elif choice == "7":
            print("\n  Goodbye!\n")
            break

        else:
            print("  ❌ Invalid choice")


if __name__ == "__main__":
    interactive_menu()
