#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Subject Line Rotator - Create & Manage Email Subject Lines
Rotate subject lines to improve inbox delivery
"""
import json
import os
from pathlib import Path

class SubjectRotator:
    """Manage and rotate email subject lines"""

    def __init__(self):
        self.subjects_dir = "email_subjects"
        self.subjects_file = "subjects.json"
        os.makedirs(self.subjects_dir, exist_ok=True)
        self.subjects = self.load_subjects()

    def load_subjects(self) -> dict:
        """Load subjects from file"""
        if os.path.isfile(self.subjects_file):
            try:
                with open(self.subjects_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {'campaigns': {}}
        return {'campaigns': {}}

    def save_subjects(self):
        """Save subjects to file"""
        with open(self.subjects_file, 'w', encoding='utf-8') as f:
            json.dump(self.subjects, f, indent=2, ensure_ascii=False)

    def create_campaign(self, campaign_name: str, subjects: list) -> bool:
        """Create subject campaign"""
        if 'campaigns' not in self.subjects:
            self.subjects['campaigns'] = {}

        if campaign_name in self.subjects['campaigns']:
            print(f"  ⚠️  Campaign '{campaign_name}' already exists")
            return False

        self.subjects['campaigns'][campaign_name] = {
            'name': campaign_name,
            'subjects': subjects,
            'count': len(subjects),
            'created': str(Path(self.subjects_dir) / f"{campaign_name}.txt")
        }

        # Save subject file
        with open(os.path.join(self.subjects_dir, f"{campaign_name}.txt"), 'w', encoding='utf-8') as f:
            f.write('\n'.join(subjects) + '\n')

        self.save_subjects()
        return True

    def get_campaign(self, campaign_name: str) -> list:
        """Get subjects from campaign"""
        if campaign_name in self.subjects.get('campaigns', {}):
            return self.subjects['campaigns'][campaign_name].get('subjects', [])
        return []

    def list_campaigns(self) -> list:
        """List all campaigns"""
        result = []
        for name, data in self.subjects.get('campaigns', {}).items():
            result.append({
                'name': name,
                'count': data.get('count', 0),
                'subjects': data.get('subjects', [])
            })
        return result

    def delete_campaign(self, campaign_name: str) -> bool:
        """Delete a campaign"""
        if campaign_name in self.subjects.get('campaigns', {}):
            del self.subjects['campaigns'][campaign_name]
            self.save_subjects()
            # Delete file
            try:
                os.remove(os.path.join(self.subjects_dir, f"{campaign_name}.txt"))
            except:
                pass
            return True
        return False

    def generate_sample_campaigns(self):
        """Create sample subject line campaigns"""
        campaigns = {
            'Urgency-Based': [
                '⏰ Last Chance - Limited Time Offer',
                '🚨 Don\'t Miss Out - Expires Soon',
                '⚡ Final Hours to Claim Your Spot',
                '🔥 Urgent: Time-Sensitive Opportunity',
                '⏳ Ending Tonight - Act Now',
            ],
            'Value-Focused': [
                '💰 Save Big On Your Next Order',
                '📈 Increase Your Revenue By 300%',
                '✨ Unlock Premium Features Free',
                '🎁 Exclusive Bonus Inside',
                '💎 VIP Access Granted',
            ],
            'Curiosity-Driven': [
                '👀 You Won\'t Believe What Happens Next',
                '❓ The Truth About [Topic] Revealed',
                '🔍 This Might Surprise You',
                '💭 What You\'re Missing',
                '📢 Industry Insider Secret',
            ],
            'Social-Proof': [
                '✅ 10,000+ Happy Customers Say...',
                '⭐ See Why Everyone Is Switching',
                '👥 Join Our Growing Community',
                '📊 What Top Performers Are Doing',
                '🏆 Award-Winning Solution',
            ],
            'Personal': [
                'Hi [Name], Quick Question',
                'Your Account Requires Attention',
                '[Name], We Miss You',
                'Important Update About Your Account',
                'A Personalized Offer Just For You',
            ],
            'Question-Based': [
                'Can I Ask You Something?',
                'What\'s Stopping Your Growth?',
                'Ready For Your Next Level?',
                'Interested In Making More Money?',
                'Want To Solve This Problem?',
            ]
        }

        for campaign_name, subjects in campaigns.items():
            self.create_campaign(campaign_name, subjects)

        print("✓ Sample subject campaigns created!")
        for name in campaigns:
            print(f"  • {name} ({len(campaigns[name])} subjects)")

    def add_subject(self, campaign_name: str, subject: str) -> bool:
        """Add subject to existing campaign"""
        if campaign_name not in self.subjects.get('campaigns', {}):
            return False

        self.subjects['campaigns'][campaign_name]['subjects'].append(subject)
        self.subjects['campaigns'][campaign_name]['count'] = len(self.subjects['campaigns'][campaign_name]['subjects'])
        self.save_subjects()
        return True


def interactive_menu():
    """Interactive subject manager"""
    rotator = SubjectRotator()

    while True:
        print("\n" + "="*70)
        print("  📧 SUBJECT LINE ROTATOR")
        print("="*70)
        print("\n  What do you want to do?\n")
        print("  [1] Create sample campaigns")
        print("  [2] Create custom campaign")
        print("  [3] List all campaigns")
        print("  [4] View campaign subjects")
        print("  [5] Add subject to campaign")
        print("  [6] Delete campaign")
        print("  [7] Export for Mass Mailer")
        print("  [8] Exit")
        print()

        choice = input("  → Choose (1-8): ").strip()

        if choice == "1":
            rotator.generate_sample_campaigns()

        elif choice == "2":
            campaign_name = input("\n  Campaign name: ").strip()
            print("  Enter subjects (one per line, empty line to finish):")
            subjects = []
            while True:
                subj = input("    > ").strip()
                if not subj:
                    break
                subjects.append(subj)

            if subjects:
                if rotator.create_campaign(campaign_name, subjects):
                    print(f"\n  ✓ Campaign '{campaign_name}' created with {len(subjects)} subjects!")
                else:
                    print(f"\n  ❌ Failed to create campaign")

        elif choice == "3":
            print()
            campaigns = rotator.list_campaigns()
            if campaigns:
                print("  All Campaigns:\n")
                for i, c in enumerate(campaigns, 1):
                    print(f"  [{i}] {c['name']}")
                    print(f"      Subjects: {c['count']}")
                    print()
            else:
                print("  No campaigns yet.")

        elif choice == "4":
            campaign_name = input("\n  Campaign name: ").strip()
            subjects = rotator.get_campaign(campaign_name)
            if subjects:
                print(f"\n  Subjects in '{campaign_name}':\n")
                for i, s in enumerate(subjects, 1):
                    print(f"  [{i}] {s}")
            else:
                print(f"\n  ❌ Campaign not found")

        elif choice == "5":
            campaign_name = input("\n  Campaign name: ").strip()
            subject = input("  New subject: ").strip()
            if rotator.add_subject(campaign_name, subject):
                print(f"  ✓ Subject added!")
            else:
                print(f"  ❌ Campaign not found")

        elif choice == "6":
            campaign_name = input("\n  Campaign name to delete: ").strip()
            if rotator.delete_campaign(campaign_name):
                print(f"  ✓ Campaign deleted!")
            else:
                print(f"  ❌ Campaign not found")

        elif choice == "7":
            campaign_name = input("\n  Campaign name to export: ").strip()
            subjects = rotator.get_campaign(campaign_name)
            if subjects:
                filename = f"{campaign_name}_subjects.txt"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(subjects))
                print(f"  ✓ Exported to: {filename}")
                print(f"    Use this in Mass Mailer config as mail_subject")
            else:
                print(f"  ❌ Campaign not found")

        elif choice == "8":
            print("\n  Goodbye!\n")
            break

        else:
            print("  ❌ Invalid choice")


if __name__ == "__main__":
    interactive_menu()
