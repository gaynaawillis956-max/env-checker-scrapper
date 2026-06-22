#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Delivery Monitor - Check Which Emails Go To Inbox vs Spam
Monitor campaign performance and identify problematic SMTP accounts
"""
import imaplib, sys, time, json, threading, re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from email import message_from_bytes

class DeliveryMonitor:
    """Monitor email deliverability (inbox vs spam)"""

    PROVIDERS = {
        'gmail': {'host': 'imap.gmail.com', 'port': 993},
        'outlook': {'host': 'imap-mail.outlook.com', 'port': 993},
        'yahoo': {'host': 'imap.mail.yahoo.com', 'port': 993},
        'protonmail': {'host': 'imap.protonmail.com', 'port': 993},
        'zoho': {'host': 'imap.zoho.com', 'port': 993},
        'aol': {'host': 'imap.aol.com', 'port': 993},
    }

    def __init__(self):
        self.results = {'inbox': [], 'spam': [], 'notfound': [], 'error': []}
        self.lock = threading.Lock()

    def get_provider(self, email: str) -> str:
        """Detect email provider"""
        domain = email.split('@')[1].lower()
        for provider, _ in self.PROVIDERS.items():
            if provider in domain:
                return provider
        if 'gmail' in domain or 'google' in domain:
            return 'gmail'
        if 'outlook' in domain or 'hotmail' in domain or 'microsoft' in domain:
            return 'outlook'
        if 'yahoo' in domain:
            return 'yahoo'
        if 'proton' in domain:
            return 'protonmail'
        if 'zoho' in domain:
            return 'zoho'
        return 'gmail'  # default

    def check_delivery(self, test_email: str, password: str, search_from: str = None,
                      search_subject: str = None, minutes_back: int = 30) -> dict:
        """Check if email from search_from is in inbox or spam"""
        try:
            provider = self.get_provider(test_email)
            config = self.PROVIDERS.get(provider, self.PROVIDERS['gmail'])

            # Connect
            imap = imaplib.IMAP4_SSL(config['host'], config['port'], timeout=10)
            imap.login(test_email, password)

            result = {'email': test_email, 'status': 'error', 'found': False, 'location': None}

            # Build search criteria
            criteria = f'SINCE {(datetime.now() - timedelta(minutes=minutes_back)).strftime("%d-%b-%Y")}'

            if search_from:
                criteria += f' FROM "{search_from}"'
            if search_subject:
                criteria += f' SUBJECT "{search_subject}"'

            # Check Inbox first
            imap.select('INBOX')
            _, inbox_data = imap.search(None, criteria)
            inbox_count = len(inbox_data[0].split()) if inbox_data[0] else 0

            if inbox_count > 0:
                result['status'] = 'success'
                result['found'] = True
                result['location'] = 'INBOX'
                result['count'] = inbox_count
                imap.close()
                imap.logout()
                return result

            # Check Spam/Junk
            for spam_folder in ['[Gmail]/Spam', 'Spam', 'Junk', 'Junk Email', 'Junk Mail']:
                try:
                    imap.select(spam_folder)
                    _, spam_data = imap.search(None, criteria)
                    spam_count = len(spam_data[0].split()) if spam_data[0] else 0

                    if spam_count > 0:
                        result['status'] = 'success'
                        result['found'] = True
                        result['location'] = 'SPAM'
                        result['count'] = spam_count
                        imap.close()
                        imap.logout()
                        return result
                except:
                    continue

            # Not found
            result['status'] = 'success'
            result['found'] = False
            result['location'] = 'NOT_FOUND'

            imap.close()
            imap.logout()
            return result

        except imaplib.IMAP4.error as e:
            return {
                'email': test_email,
                'status': 'error',
                'error': f'IMAP Error: {str(e)[:50]}',
                'found': False
            }
        except Exception as e:
            return {
                'email': test_email,
                'status': 'error',
                'error': f'Error: {str(e)[:50]}',
                'found': False
            }

    def record_result(self, result: dict):
        """Record check result"""
        with self.lock:
            if result['status'] == 'error':
                self.results['error'].append(result)
            elif not result.get('found', False):
                self.results['notfound'].append(result)
            elif result.get('location') == 'INBOX':
                self.results['inbox'].append(result)
            else:
                self.results['spam'].append(result)

    def monitor_campaign(self, test_accounts: list, search_from: str = None,
                        search_subject: str = None, minutes_back: int = 30,
                        max_workers: int = 5) -> dict:
        """Monitor multiple test accounts for campaign delivery"""

        print("\n" + "="*80)
        print("  📧 DELIVERY MONITOR - Checking Where Emails Land")
        print("="*80)
        print()
        print(f"  Monitoring {len(test_accounts)} test accounts")
        if search_from:
            print(f"  Searching for emails FROM: {search_from}")
        if search_subject:
            print(f"  Searching for SUBJECT: {search_subject}")
        print(f"  Time window: Last {minutes_back} minutes")
        print()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for account in test_accounts:
                email, password = account.split(':') if ':' in account else (account, '')
                future = executor.submit(
                    self.check_delivery,
                    email, password, search_from, search_subject, minutes_back
                )
                futures[future] = email

            for i, future in enumerate(as_completed(futures), 1):
                email = futures[future]
                result = future.result()
                self.record_result(result)

                # Print result
                if result['status'] == 'error':
                    status = "❌"
                    msg = result.get('error', 'Unknown error')
                elif not result.get('found'):
                    status = "⏸️"
                    msg = "Email not found"
                elif result.get('location') == 'INBOX':
                    status = "✅"
                    msg = f"INBOX ({result.get('count', 0)})"
                else:
                    status = "🚨"
                    msg = f"SPAM ({result.get('count', 0)})"

                print(f"  [{i}] {status} {email:40s} {msg}")

        # Summary
        self.show_summary()
        return self.results

    def show_summary(self):
        """Show delivery summary"""
        total = len(self.results['inbox']) + len(self.results['spam']) + len(self.results['notfound'])
        inbox_rate = int(len(self.results['inbox']) / total * 100) if total > 0 else 0
        spam_rate = int(len(self.results['spam']) / total * 100) if total > 0 else 0

        print()
        print("="*80)
        print("  📊 DELIVERY REPORT")
        print("="*80)
        print()
        print(f"  ✅ INBOX:     {len(self.results['inbox']):3d} ({inbox_rate:3d}%)")
        print(f"  🚨 SPAM:      {len(self.results['spam']):3d} ({spam_rate:3d}%)")
        print(f"  ⏸️  NOT FOUND: {len(self.results['notfound']):3d}")
        print(f"  ❌ ERRORS:    {len(self.results['error']):3d}")
        print()

        if self.results['spam']:
            print(f"  🚨 ACCOUNTS DELIVERING TO SPAM:")
            for r in self.results['spam'][:5]:
                print(f"     • {r['email']}")
            if len(self.results['spam']) > 5:
                print(f"     ... and {len(self.results['spam']) - 5} more")
            print()

        if self.results['inbox']:
            print(f"  ✅ BEST PERFORMING ACCOUNTS:")
            for r in self.results['inbox'][:5]:
                print(f"     • {r['email']}")
            if len(self.results['inbox']) > 5:
                print(f"     ... and {len(self.results['inbox']) - 5} more")
            print()


def interactive_menu():
    """Interactive delivery monitor"""
    monitor = DeliveryMonitor()

    print("\n" + "="*80)
    print("  📧 DELIVERY MONITOR - Check Campaign Inbox vs Spam")
    print("="*80)
    print()

    # Get test accounts
    print("  Enter test Gmail/email accounts to check (format: email:password)")
    print("  (One per line, empty line to finish):")
    print()
    test_accounts = []
    while True:
        acc = input("    > ").strip()
        if not acc:
            break
        test_accounts.append(acc)

    if not test_accounts:
        print("\n  ❌ No accounts provided\n")
        return

    # Get search criteria
    search_from = input("\n  Search for emails FROM (optional): ").strip() or None
    search_subject = input("  Search for SUBJECT (optional): ").strip() or None
    minutes = int(input("  Check last N minutes (default 30): ").strip() or "30")

    # Monitor
    results = monitor.monitor_campaign(test_accounts, search_from, search_subject, minutes)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"delivery_report_{timestamp}.json"
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"  💾 Report saved: {report_file}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--auto':
        # Auto mode: email password from_email from_password search_from search_subject
        if len(sys.argv) < 5:
            print("\nUsage: python3 delivery_monitor.py --auto email password search_from search_subject\n")
            sys.exit(1)

        monitor = DeliveryMonitor()
        result = monitor.check_delivery(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        print(json.dumps(result, indent=2))
    else:
        interactive_menu()
