#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Account Manager - Auto-save working accounts and suggest strategies
Tracks IMAP/SMTP status and recommends usage patterns
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict

class AccountManager:
    """Manage and track email accounts"""

    def __init__(self):
        self.working_file = "working_accounts.json"
        self.accounts = self.load_accounts()

    def load_accounts(self) -> List[Dict]:
        """Load existing working accounts"""
        if os.path.isfile(self.working_file):
            try:
                with open(self.working_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_accounts(self):
        """Save accounts to file"""
        with open(self.working_file, 'w', encoding='utf-8') as f:
            json.dump(self.accounts, f, indent=2, ensure_ascii=False)

    def add_account(self, email: str, password: str, provider: str,
                   can_send: bool, can_receive: bool, test_date: str = None) -> bool:
        """Add or update account"""
        if not test_date:
            test_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Check if already exists
        for account in self.accounts:
            if account['email'] == email:
                account['password'] = password
                account['provider'] = provider
                account['can_send'] = can_send
                account['can_receive'] = can_receive
                account['last_tested'] = test_date
                account['test_count'] = account.get('test_count', 0) + 1
                self.save_accounts()
                return True

        # Add new
        self.accounts.append({
            'email': email,
            'password': password,
            'provider': provider,
            'can_send': can_send,
            'can_receive': can_receive,
            'created': test_date,
            'last_tested': test_date,
            'test_count': 1,
            'notes': ''
        })
        self.save_accounts()
        return True

    def get_working_senders(self) -> List[Dict]:
        """Get accounts that can send"""
        return [a for a in self.accounts if a.get('can_send')]

    def get_working_receivers(self) -> List[Dict]:
        """Get accounts that can receive"""
        return [a for a in self.accounts if a.get('can_receive')]

    def get_fully_working(self) -> List[Dict]:
        """Get accounts that can send and receive"""
        return [a for a in self.accounts if a.get('can_send') and a.get('can_receive')]

    def export_smtp_list(self, filename: str = "working_smtp.txt"):
        """Export working senders as SMTP list"""
        working = self.get_working_senders()
        if working:
            with open(filename, 'w', encoding='utf-8') as f:
                for account in working:
                    # Try to extract SMTP from provider config
                    host = self.get_smtp_host(account['provider'])
                    port = self.get_smtp_port(account['provider'])
                    f.write(f"{host}:{port}:{account['email']}:{account['password']}\n")
            return True
        return False

    @staticmethod
    def get_smtp_host(provider: str) -> str:
        """Get SMTP host for provider"""
        hosts = {
            'Gmail': 'smtp.gmail.com',
            'Outlook': 'smtp-mail.outlook.com',
            'Yahoo': 'smtp.mail.yahoo.com',
            'AOL': 'smtp.aol.com',
            'ProtonMail': 'smtp.protonmail.com',
            'Zoho': 'smtp.zoho.com',
            'iCloud': 'smtp.mail.icloud.com',
        }
        return hosts.get(provider, 'smtp.unknown.com')

    @staticmethod
    def get_smtp_port(provider: str) -> int:
        """Get SMTP port for provider"""
        ports = {
            'Gmail': 587,
            'Outlook': 587,
            'Yahoo': 465,
            'AOL': 465,
            'ProtonMail': 587,
            'Zoho': 465,
            'iCloud': 587,
        }
        return ports.get(provider, 587)

    def generate_report(self) -> str:
        """Generate strategy report"""
        senders = self.get_working_senders()
        receivers = self.get_working_receivers()
        fully_working = self.get_fully_working()

        report = "\n" + "="*70 + "\n"
        report += "ACCOUNT STRATEGY REPORT\n"
        report += "="*70 + "\n\n"

        # Summary
        report += "SUMMARY:\n"
        report += f"  Total Accounts Saved:   {len(self.accounts)}\n"
        report += f"  Can Send:               {len(senders)}\n"
        report += f"  Can Receive:            {len(receivers)}\n"
        report += f"  Fully Working (both):   {len(fully_working)}\n\n"

        # Fully working accounts
        if fully_working:
            report += "✓ FULLY WORKING ACCOUNTS (Use for sending):\n"
            report += "-" * 70 + "\n"
            for account in fully_working:
                report += f"  {account['email']} ({account['provider']})\n"
                report += f"    Last tested: {account['last_tested']}\n"
            report += "\n"

        # Send-only accounts
        send_only = [a for a in senders if not a.get('can_receive')]
        if send_only:
            report += "📤 SEND-ONLY ACCOUNTS (Can send, can't receive):\n"
            report += "-" * 70 + "\n"
            for account in send_only:
                report += f"  {account['email']} ({account['provider']})\n"
            report += "\n"

        # Receive-only accounts
        receive_only = [a for a in receivers if not a.get('can_send')]
        if receive_only:
            report += "📥 RECEIVE-ONLY ACCOUNTS (Can receive, can't send):\n"
            report += "-" * 70 + "\n"
            for account in receive_only:
                report += f"  {account['email']} ({account['provider']})\n"
            report += "\n"

        # Recommendations
        report += "💡 RECOMMENDATIONS:\n"
        report += "-" * 70 + "\n"

        if len(fully_working) >= 3:
            report += f"  ✓ You have {len(fully_working)} fully-working accounts\n"
            report += f"    → Use for rotating sending (avoid rate limits)\n"
            report += f"    → Use multiple in parallel for scale\n"
            report += f"    → Good for campaigns\n\n"
        elif len(fully_working) >= 1:
            report += f"  ✓ You have {len(fully_working)} fully-working account(s)\n"
            report += f"    → Good for basic sending\n"
            report += f"    → Test more accounts to increase capacity\n\n"
        else:
            report += f"  ⚠️  No fully-working accounts yet\n"
            report += f"    → Test more accounts\n"
            report += f"    → Check if Gmail/Outlook need app passwords\n\n"

        if len(senders) >= 1:
            report += f"  ✓ You have {len(senders)} sending account(s)\n"
            if len(senders) >= 10:
                report += f"    → Excellent! Can send with rotation\n"
                report += f"    → Use 5-10 accounts in parallel\n"
                report += f"    → Rotate to avoid bans\n"
            elif len(senders) >= 5:
                report += f"    → Good! Can send with some rotation\n"
                report += f"    → Use 3-5 accounts in rotation\n"
            elif len(senders) >= 2:
                report += f"    → Basic sending possible\n"
                report += f"    → Rotate between accounts\n"
            report += "\n"

        # Strategy
        report += "🎯 SUGGESTED STRATEGY:\n"
        report += "-" * 70 + "\n"

        if len(fully_working) >= 3:
            report += "  ROTATION STRATEGY (3+ accounts):\n"
            report += "    1. Send 5-10 emails from account 1\n"
            report += "    2. Wait 30-60 seconds\n"
            report += "    3. Send 5-10 emails from account 2\n"
            report += "    4. Repeat with account 3\n"
            report += "    → Prevents rate limiting\n"
            report += "    → Better deliverability\n"
        elif len(fully_working) >= 1:
            report += "  WARMUP STRATEGY (1+ account):\n"
            report += "    1. Start with small batches (5-10 emails)\n"
            report += "    2. Wait 60 seconds between batches\n"
            report += "    3. Gradually increase batch size\n"
            report += "    4. Monitor for blocking\n"

        if len(senders) >= 5 and len(fully_working) < 1:
            report += "\n  SENDING STRATEGY (No receive, but can send):\n"
            report += "    1. Use for outbound campaigns\n"
            report += "    2. Create separate receiving account\n"
            report += "    3. Rotate sending accounts\n"

        report += "\n" + "="*70 + "\n"

        return report

    def suggest_usage(self) -> Dict:
        """Suggest how many accounts to use"""
        senders = self.get_working_senders()
        fully_working = self.get_fully_working()

        suggestion = {
            'total_accounts': len(self.accounts),
            'sendable': len(senders),
            'fully_working': len(fully_working),
            'recommendation': ''
        }

        if len(fully_working) == 0:
            suggestion['recommendation'] = 'Test more accounts. Add Gmail/Outlook with app passwords.'
            suggestion['suggested_threads'] = 1
            suggestion['suggested_rotation'] = False
        elif len(fully_working) == 1:
            suggestion['recommendation'] = 'You have 1 working account. Single sending only.'
            suggestion['suggested_threads'] = 1
            suggestion['suggested_rotation'] = False
        elif len(fully_working) < 5:
            suggestion['recommendation'] = f'Rotate {len(fully_working)} accounts. Add more for better throughput.'
            suggestion['suggested_threads'] = len(fully_working)
            suggestion['suggested_rotation'] = True
        elif len(fully_working) < 10:
            suggestion['recommendation'] = f'Good! Use all {len(fully_working)} accounts with rotation.'
            suggestion['suggested_threads'] = min(5, len(fully_working))
            suggestion['suggested_rotation'] = True
        else:
            suggestion['recommendation'] = f'Excellent! {len(fully_working)} accounts. Use 5-10 in parallel rotation.'
            suggestion['suggested_threads'] = 10
            suggestion['suggested_rotation'] = True

        return suggestion

    def print_strategy(self):
        """Print strategy recommendations"""
        print(self.generate_report())
        suggestion = self.suggest_usage()

        print("\n" + "="*70)
        print("QUICK RECOMMENDATION:")
        print("="*70)
        print(f"  {suggestion['recommendation']}")
        print(f"\n  Use {suggestion['suggested_threads']} threads")
        if suggestion['suggested_rotation']:
            print(f"  Enable rotation: YES")
        else:
            print(f"  Enable rotation: NO (single account)")
        print("="*70 + "\n")


def main():
    """Test account manager"""
    import argparse

    parser = argparse.ArgumentParser(description="Email Account Manager")
    parser.add_argument("--add", nargs=4, metavar=('EMAIL', 'PASSWORD', 'PROVIDER', 'STATUS'),
                       help="Add account (status: fully_working/send_only/receive_only)")
    parser.add_argument("--report", action="store_true", help="Show strategy report")
    parser.add_argument("--export", help="Export SMTP list to file")
    parser.add_argument("--list", action="store_true", help="List all accounts")
    parser.add_argument("--suggest", action="store_true", help="Suggest usage strategy")

    args = parser.parse_args()

    manager = AccountManager()

    if args.add:
        email, password, provider, status = args.add
        can_send = status in ['fully_working', 'send_only']
        can_receive = status in ['fully_working', 'receive_only']
        manager.add_account(email, password, provider, can_send, can_receive)
        print(f"✓ Added: {email}")

    if args.list:
        print(f"\nTotal accounts: {len(manager.accounts)}\n")
        for account in manager.accounts:
            status = "✓" if (account.get('can_send') and account.get('can_receive')) else \
                     "📤" if account.get('can_send') else \
                     "📥" if account.get('can_receive') else "✗"
            print(f"  {status} {account['email']} ({account['provider']})")
        print()

    if args.report:
        manager.print_strategy()

    if args.export:
        if manager.export_smtp_list(args.export):
            print(f"✓ Exported {len(manager.get_working_senders())} accounts to {args.export}")
        else:
            print("✗ No working accounts to export")

    if args.suggest:
        suggestion = manager.suggest_usage()
        print(f"\nSuggestion: {suggestion['recommendation']}")
        print(f"Threads: {suggestion['suggested_threads']}")
        print(f"Rotation: {suggestion['suggested_rotation']}\n")


if __name__ == "__main__":
    main()
