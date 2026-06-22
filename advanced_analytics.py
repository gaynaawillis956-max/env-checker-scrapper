#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Analytics - Track Performance per SMTP, Provider, Content
Detailed campaign metrics and insights
"""
import json
import os
import re
from datetime import datetime
from collections import defaultdict

class AdvancedAnalytics:
    """Track and analyze campaign performance"""

    def __init__(self):
        self.analytics_dir = "campaign_analytics"
        self.analytics_file = "analytics.json"
        os.makedirs(self.analytics_dir, exist_ok=True)
        self.data = self.load_analytics()

    def load_analytics(self) -> dict:
        """Load analytics data"""
        if os.path.isfile(self.analytics_file):
            try:
                with open(self.analytics_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {'campaigns': {}}
        return {'campaigns': {}}

    def save_analytics(self):
        """Save analytics"""
        with open(self.analytics_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def create_campaign_analytics(self, campaign_id: str, campaign_info: dict) -> dict:
        """Create analytics record for campaign"""
        if 'campaigns' not in self.data:
            self.data['campaigns'] = {}

        analytics = {
            'campaign_id': campaign_id,
            'info': campaign_info,
            'created': datetime.now().isoformat(),
            'metrics': {
                'total_sent': 0,
                'inbox': 0,
                'spam': 0,
                'bounced': 0,
                'failed': 0,
                'open_tracked': 0,
                'click_tracked': 0,
            },
            'by_smtp': defaultdict(lambda: {'sent': 0, 'inbox': 0, 'spam': 0, 'bounced': 0}),
            'by_provider': defaultdict(lambda: {'sent': 0, 'inbox': 0, 'spam': 0}),
            'by_content': defaultdict(lambda: {'sent': 0, 'inbox': 0, 'spam': 0}),
            'by_subject': defaultdict(lambda: {'sent': 0, 'inbox': 0, 'spam': 0}),
            'bounce_reasons': defaultdict(int),
            'top_performers': [],
            'worst_performers': []
        }

        self.data['campaigns'][campaign_id] = analytics
        self.save_analytics()
        return analytics

    def record_send(self, campaign_id: str, email: str, smtp: str, subject: str,
                   content_version: str, status: str, location: str = None):
        """Record individual send"""
        if campaign_id not in self.data.get('campaigns', {}):
            return False

        campaign = self.data['campaigns'][campaign_id]

        # Extract provider from email
        provider = self.extract_provider(email)

        # Update metrics
        campaign['metrics']['total_sent'] += 1
        if status == 'sent':
            if location == 'inbox':
                campaign['metrics']['inbox'] += 1
            elif location == 'spam':
                campaign['metrics']['spam'] += 1
        elif status == 'bounced':
            campaign['metrics']['bounced'] += 1
        else:
            campaign['metrics']['failed'] += 1

        # Update by_smtp
        campaign['by_smtp'][smtp]['sent'] += 1
        if location == 'inbox':
            campaign['by_smtp'][smtp]['inbox'] += 1
        elif location == 'spam':
            campaign['by_smtp'][smtp]['spam'] += 1

        # Update by_provider
        campaign['by_provider'][provider]['sent'] += 1
        if location == 'inbox':
            campaign['by_provider'][provider]['inbox'] += 1
        elif location == 'spam':
            campaign['by_provider'][provider]['spam'] += 1

        # Update by_content
        campaign['by_content'][content_version]['sent'] += 1
        if location == 'inbox':
            campaign['by_content'][content_version]['inbox'] += 1

        # Update by_subject
        campaign['by_subject'][subject]['sent'] += 1
        if location == 'inbox':
            campaign['by_subject'][subject]['inbox'] += 1

        self.save_analytics()
        return True

    def extract_provider(self, email: str) -> str:
        """Extract email provider"""
        if '@' not in email:
            return 'unknown'

        domain = email.split('@')[1].lower()

        if 'gmail' in domain or 'google' in domain:
            return 'Gmail'
        elif 'outlook' in domain or 'hotmail' in domain or 'microsoft' in domain:
            return 'Outlook'
        elif 'yahoo' in domain:
            return 'Yahoo'
        elif 'aol' in domain:
            return 'AOL'
        elif 'proton' in domain:
            return 'ProtonMail'
        elif 'zoho' in domain:
            return 'Zoho'
        else:
            return domain

    def get_campaign_report(self, campaign_id: str) -> str:
        """Generate comprehensive campaign report"""
        if campaign_id not in self.data.get('campaigns', {}):
            return "Campaign not found"

        campaign = self.data['campaigns'][campaign_id]
        metrics = campaign['metrics']

        # Calculate rates
        total = metrics['total_sent']
        inbox_rate = int(metrics['inbox'] / total * 100) if total > 0 else 0
        spam_rate = int(metrics['spam'] / total * 100) if total > 0 else 0

        # Get best/worst SMTP
        by_smtp_list = [(smtp, data) for smtp, data in campaign['by_smtp'].items()]
        by_smtp_list.sort(key=lambda x: x[1]['inbox'] / max(1, x[1]['sent']), reverse=True)

        # Get best/worst content
        by_content_list = [(content, data) for content, data in campaign['by_content'].items()]
        by_content_list.sort(key=lambda x: x[1]['inbox'] / max(1, x[1]['sent']), reverse=True)

        report = f"""
╔════════════════════════════════════════════════════════════════╗
║                  CAMPAIGN ANALYTICS REPORT                    ║
╚════════════════════════════════════════════════════════════════╝

Campaign ID: {campaign_id}
Created: {campaign['created']}

┌────────────────────────────────────────────────────────────────┐
│ OVERALL METRICS
└────────────────────────────────────────────────────────────────┘

Total Sent:         {metrics['total_sent']}
├─ Inbox:          {metrics['inbox']} ({inbox_rate}%)
├─ Spam:           {metrics['spam']} ({spam_rate}%)
├─ Bounced:        {metrics['bounced']}
└─ Failed:         {metrics['failed']}

Engagement:
├─ Opens (tracked): {metrics['open_tracked']}
└─ Clicks (tracked): {metrics['click_tracked']}

┌────────────────────────────────────────────────────────────────┐
│ TOP PERFORMING SMTP ACCOUNTS
└────────────────────────────────────────────────────────────────┘
"""
        for smtp, data in by_smtp_list[:5]:
            if data['sent'] > 0:
                rate = int(data['inbox'] / data['sent'] * 100)
                report += f"\n{smtp}\n"
                report += f"  Sent: {data['sent']:4d}  Inbox: {data['inbox']:3d}  Spam: {data['spam']:3d}  Rate: {rate}%\n"

        report += f"""
┌────────────────────────────────────────────────────────────────┐
│ EMAIL PROVIDER BREAKDOWN
└────────────────────────────────────────────────────────────────┘
"""
        for provider, data in sorted(campaign['by_provider'].items(), key=lambda x: x[1]['sent'], reverse=True):
            if data['sent'] > 0:
                rate = int(data['inbox'] / data['sent'] * 100)
                report += f"{provider:15s}  Sent: {data['sent']:4d}  Inbox: {data['inbox']:3d}  Spam: {data['spam']:3d}  Rate: {rate}%\n"

        report += f"""
┌────────────────────────────────────────────────────────────────┐
│ BEST PERFORMING CONTENT
└────────────────────────────────────────────────────────────────┘
"""
        for content, data in by_content_list[:3]:
            if data['sent'] > 0:
                rate = int(data['inbox'] / data['sent'] * 100)
                report += f"\n{content}\n"
                report += f"  Sent: {data['sent']:4d}  Inbox: {data['inbox']:3d}  Rate: {rate}%\n"

        report += f"""
┌────────────────────────────────────────────────────────────────┐
│ BEST PERFORMING SUBJECT LINES
└────────────────────────────────────────────────────────────────┘
"""
        subject_list = [(subj, data) for subj, data in campaign['by_subject'].items()]
        subject_list.sort(key=lambda x: x[1]['inbox'] / max(1, x[1]['sent']), reverse=True)
        for subject, data in subject_list[:5]:
            if data['sent'] > 0:
                rate = int(data['inbox'] / data['sent'] * 100)
                subj_preview = subject[:50]
                report += f"{subj_preview:50s}  Sent: {data['sent']:3d}  Rate: {rate}%\n"

        report += f"""
┌────────────────────────────────────────────────────────────────┐
│ RECOMMENDATIONS
└────────────────────────────────────────────────────────────────┘

Based on this campaign:

1. BEST SMTP ACCOUNTS TO USE:
"""
        for smtp, data in by_smtp_list[:3]:
            if data['sent'] > 0:
                rate = int(data['inbox'] / data['sent'] * 100)
                report += f"   ✅ {smtp} ({rate}% inbox)\n"

        report += f"""
2. CONTENT TO REPLICATE:
"""
        for content, data in by_content_list[:2]:
            if data['sent'] > 0:
                rate = int(data['inbox'] / data['sent'] * 100)
                report += f"   ✅ {content} ({rate}% inbox)\n"

        report += f"""
3. NEXT STEPS:
   • Use high-performing SMTP accounts more often
   • Replicate best-performing content variations
   • Avoid low-performing subject lines
   • Increase warmup time if spam rate >10%
   • A/B test best vs worst performers

"""
        return report

    def export_csv(self, campaign_id: str) -> bool:
        """Export analytics as CSV"""
        if campaign_id not in self.data.get('campaigns', {}):
            return False

        campaign = self.data['campaigns'][campaign_id]
        filename = f"{campaign_id}_analytics.csv"

        with open(filename, 'w') as f:
            f.write("Metric,Value\n")
            metrics = campaign['metrics']
            f.write(f"Total Sent,{metrics['total_sent']}\n")
            f.write(f"Inbox,{metrics['inbox']}\n")
            f.write(f"Spam,{metrics['spam']}\n")
            f.write(f"Bounced,{metrics['bounced']}\n")
            f.write(f"Failed,{metrics['failed']}\n")
            f.write(f"Opens,{metrics['open_tracked']}\n")
            f.write(f"Clicks,{metrics['click_tracked']}\n")

        return True


def interactive_menu():
    """Interactive analytics"""
    analytics = AdvancedAnalytics()

    print("\n" + "="*70)
    print("  📊 ADVANCED ANALYTICS")
    print("="*70)
    print()
    print("  [1] Create new campaign analytics")
    print("  [2] View campaign report")
    print("  [3] Export analytics to CSV")
    print("  [4] Record email send")
    print("  [5] Get recommendations")
    print("  [6] Exit")
    print()

    choice = input("  → Choose (1-6): ").strip()

    if choice == "1":
        campaign_id = input("\n  Campaign ID: ").strip()
        subject = input("  Subject line: ").strip()
        segment = input("  Segment/List: ").strip()
        analytics.create_campaign_analytics(campaign_id, {
            'subject': subject,
            'segment': segment
        })
        print(f"  ✓ Campaign analytics created!")

    elif choice == "2":
        campaign_id = input("\n  Campaign ID: ").strip()
        report = analytics.get_campaign_report(campaign_id)
        print(report)

    elif choice == "3":
        campaign_id = input("\n  Campaign ID: ").strip()
        if analytics.export_csv(campaign_id):
            print(f"  ✓ Exported to: {campaign_id}_analytics.csv")
        else:
            print(f"  ❌ Campaign not found")

    elif choice == "4":
        campaign_id = input("\n  Campaign ID: ").strip()
        email = input("  Email: ").strip()
        smtp = input("  SMTP: ").strip()
        subject = input("  Subject: ").strip()
        content = input("  Content version: ").strip()
        status = input("  Status (sent/bounced/failed): ").strip()
        location = input("  Location (inbox/spam, optional): ").strip() or None
        analytics.record_send(campaign_id, email, smtp, subject, content, status, location)
        print(f"  ✓ Send recorded!")

    elif choice == "5":
        campaign_id = input("\n  Campaign ID: ").strip()
        report = analytics.get_campaign_report(campaign_id)
        print(report)

    elif choice == "6":
        print("\n  Goodbye!\n")


if __name__ == "__main__":
    interactive_menu()
