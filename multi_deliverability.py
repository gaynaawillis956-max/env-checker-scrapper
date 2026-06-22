#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Provider Deliverability Checker
Supports: Gmail, Outlook, Yahoo, IMAP, ProtonMail, Zoho, and more
"""
import imaplib
import smtplib
import ssl
import json
import time
from typing import Dict, List, Tuple

class DeliverabilityChecker:
    """Test email account deliverability across multiple providers"""

    PROVIDERS = {
        'gmail': {
            'imap_host': 'imap.gmail.com',
            'imap_port': 993,
            'smtp_host': 'smtp.gmail.com',
            'smtp_port': 587,
            'requires_app_password': True,
            'name': 'Gmail'
        },
        'outlook': {
            'imap_host': 'imap-mail.outlook.com',
            'imap_port': 993,
            'smtp_host': 'smtp-mail.outlook.com',
            'smtp_port': 587,
            'requires_app_password': False,
            'name': 'Outlook/Microsoft 365'
        },
        'hotmail': {
            'imap_host': 'imap-mail.outlook.com',
            'imap_port': 993,
            'smtp_host': 'smtp-mail.outlook.com',
            'smtp_port': 587,
            'requires_app_password': False,
            'name': 'Hotmail'
        },
        'yahoo': {
            'imap_host': 'imap.mail.yahoo.com',
            'imap_port': 993,
            'smtp_host': 'smtp.mail.yahoo.com',
            'smtp_port': 465,
            'requires_app_password': True,
            'name': 'Yahoo Mail'
        },
        'aol': {
            'imap_host': 'imap.aol.com',
            'imap_port': 993,
            'smtp_host': 'smtp.aol.com',
            'smtp_port': 465,
            'requires_app_password': True,
            'name': 'AOL Mail'
        },
        'protonmail': {
            'imap_host': 'imap.protonmail.com',
            'imap_port': 993,
            'smtp_host': 'smtp.protonmail.com',
            'smtp_port': 587,
            'requires_app_password': False,
            'name': 'ProtonMail'
        },
        'zoho': {
            'imap_host': 'imap.zoho.com',
            'imap_port': 993,
            'smtp_host': 'smtp.zoho.com',
            'smtp_port': 465,
            'requires_app_password': False,
            'name': 'Zoho Mail'
        },
        'icloud': {
            'imap_host': 'imap.mail.icloud.com',
            'imap_port': 993,
            'smtp_host': 'smtp.mail.icloud.com',
            'smtp_port': 587,
            'requires_app_password': True,
            'name': 'iCloud'
        },
        'office365': {
            'imap_host': 'outlook.office365.com',
            'imap_port': 993,
            'smtp_host': 'smtp.office365.com',
            'smtp_port': 587,
            'requires_app_password': False,
            'name': 'Office 365'
        }
    }

    @staticmethod
    def detect_provider(email: str) -> Tuple[str, Dict]:
        """Auto-detect email provider from address"""
        domain = email.split('@')[1].lower()

        # Check known domains
        domain_map = {
            'gmail.com': 'gmail',
            'outlook.com': 'outlook',
            'outlook.co.uk': 'outlook',
            'hotmail.com': 'hotmail',
            'hotmail.co.uk': 'hotmail',
            'yahoo.com': 'yahoo',
            'yahoo.co.uk': 'yahoo',
            'aol.com': 'aol',
            'protonmail.com': 'protonmail',
            'protonmailplus.com': 'protonmail',
            'zoho.com': 'zoho',
            'icloud.com': 'icloud',
            'mac.com': 'icloud',
            'office365.com': 'office365',
        }

        if domain in domain_map:
            provider = domain_map[domain]
            return provider, DeliverabilityChecker.PROVIDERS[provider]

        return None, None

    @staticmethod
    def test_imap(host: str, port: int, email: str, password: str, timeout: int = 10) -> Dict:
        """Test IMAP connection"""
        try:
            context = ssl.create_default_context()
            imap = imaplib.IMAP4_SSL(host, port, timeout=timeout, ssl_context=context)
            imap.login(email, password)

            # Get mailbox stats
            status, response = imap.status('INBOX', '(MESSAGES UNSEEN)')
            imap.close()
            imap.logout()

            return {
                'status': 'ok',
                'service': 'IMAP',
                'host': host,
                'port': port,
                'accessible': True
            }
        except imaplib.IMAP4.error as e:
            return {
                'status': 'auth_failed',
                'service': 'IMAP',
                'error': str(e)[:50]
            }
        except Exception as e:
            return {
                'status': 'error',
                'service': 'IMAP',
                'error': str(e)[:50]
            }

    @staticmethod
    def test_smtp(host: str, port: int, email: str, password: str, timeout: int = 10) -> Dict:
        """Test SMTP connection"""
        try:
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=timeout)
            else:
                server = smtplib.SMTP(host, port, timeout=timeout)
                server.starttls()

            server.login(email, password)
            server.quit()

            return {
                'status': 'ok',
                'service': 'SMTP',
                'host': host,
                'port': port,
                'sendable': True
            }
        except smtplib.SMTPAuthenticationError:
            return {
                'status': 'auth_failed',
                'service': 'SMTP',
                'error': 'Invalid credentials'
            }
        except Exception as e:
            return {
                'status': 'error',
                'service': 'SMTP',
                'error': str(e)[:50]
            }

    @staticmethod
    def test_account(email: str, password: str, provider: str = None) -> Dict:
        """Test complete email account deliverability"""
        result = {
            'email': email,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'tests': {}
        }

        # Auto-detect provider
        if not provider:
            provider, _ = DeliverabilityChecker.detect_provider(email)

        if not provider or provider not in DeliverabilityChecker.PROVIDERS:
            result['status'] = 'unknown_provider'
            result['error'] = f'Provider not recognized'
            return result

        config = DeliverabilityChecker.PROVIDERS[provider]
        result['provider'] = config['name']
        result['requires_app_password'] = config['requires_app_password']

        # Test IMAP
        imap_result = DeliverabilityChecker.test_imap(
            config['imap_host'],
            config['imap_port'],
            email,
            password
        )
        result['tests']['imap'] = imap_result

        # Test SMTP
        smtp_result = DeliverabilityChecker.test_smtp(
            config['smtp_host'],
            config['smtp_port'],
            email,
            password
        )
        result['tests']['smtp'] = smtp_result

        # Overall status
        imap_ok = imap_result['status'] == 'ok'
        smtp_ok = smtp_result['status'] == 'ok'

        if imap_ok and smtp_ok:
            result['status'] = 'fully_working'
            result['can_receive'] = True
            result['can_send'] = True
        elif imap_ok:
            result['status'] = 'partial_working'
            result['can_receive'] = True
            result['can_send'] = False
        elif smtp_ok:
            result['status'] = 'partial_working'
            result['can_receive'] = False
            result['can_send'] = True
        else:
            result['status'] = 'not_working'
            result['can_receive'] = False
            result['can_send'] = False

        return result

    @staticmethod
    def test_batch(accounts: List[Dict]) -> List[Dict]:
        """Test multiple accounts"""
        results = []
        for account in accounts:
            result = DeliverabilityChecker.test_account(
                account['email'],
                account['password'],
                account.get('provider')
            )
            results.append(result)
            time.sleep(1)  # Small delay between tests

        return results

    @staticmethod
    def generate_report(results: List[Dict]) -> str:
        """Generate text report"""
        report = "\n" + "="*70 + "\n"
        report += "DELIVERABILITY TEST REPORT\n"
        report += "="*70 + "\n\n"

        stats = {
            'total': len(results),
            'fully_working': sum(1 for r in results if r.get('status') == 'fully_working'),
            'partial_working': sum(1 for r in results if r.get('status') == 'partial_working'),
            'not_working': sum(1 for r in results if r.get('status') == 'not_working'),
            'unknown': sum(1 for r in results if r.get('status') == 'unknown_provider')
        }

        report += f"SUMMARY:\n"
        report += f"  Total Tested:      {stats['total']}\n"
        report += f"  Fully Working:     {stats['fully_working']} (Can send & receive)\n"
        report += f"  Partial Working:   {stats['partial_working']} (Can send OR receive)\n"
        report += f"  Not Working:       {stats['not_working']} (Cannot send or receive)\n"
        report += f"  Unknown Provider:  {stats['unknown']}\n\n"

        report += "DETAILED RESULTS:\n"
        report += "-"*70 + "\n"

        for result in results:
            email = result['email']
            status = result.get('status', 'unknown')
            provider = result.get('provider', 'Unknown')

            status_icon = {
                'fully_working': '✓',
                'partial_working': '~',
                'not_working': '✗',
                'unknown_provider': '?'
            }.get(status, '?')

            report += f"\n{status_icon} {email}\n"
            report += f"  Provider: {provider}\n"

            if 'tests' in result:
                imap = result['tests'].get('imap', {})
                smtp = result['tests'].get('smtp', {})

                report += f"  IMAP: {imap.get('status', 'unknown')}"
                if imap.get('error'):
                    report += f" ({imap['error']})"
                report += "\n"

                report += f"  SMTP: {smtp.get('status', 'unknown')}"
                if smtp.get('error'):
                    report += f" ({smtp['error']})"
                report += "\n"

        report += "\n" + "="*70 + "\n"
        return report


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Multi-Provider Email Deliverability Checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported Providers:
  - Gmail (requires app password)
  - Outlook/Microsoft 365
  - Yahoo Mail (requires app password)
  - AOL (requires app password)
  - ProtonMail
  - Zoho Mail
  - iCloud (requires app password)
  - Generic IMAP servers

Examples:
  python3 multi_deliverability.py test@gmail.com "app_password"
  python3 multi_deliverability.py test@outlook.com "password" --provider outlook
  python3 multi_deliverability.py test@custom.com "password" \\
    --imap imap.custom.com --smtp smtp.custom.com
        """
    )

    parser.add_argument("email", help="Email address to test")
    parser.add_argument("password", help="Email password or app password")
    parser.add_argument("--provider", help="Force provider (gmail, outlook, yahoo, etc)")
    parser.add_argument("--imap", help="Custom IMAP host (overrides provider)")
    parser.add_argument("--imap-port", type=int, default=993, help="IMAP port")
    parser.add_argument("--smtp", help="Custom SMTP host (overrides provider)")
    parser.add_argument("--smtp-port", type=int, default=587, help="SMTP port")
    parser.add_argument("--timeout", type=int, default=10, help="Connection timeout")

    args = parser.parse_args()

    # Custom servers
    if args.imap or args.smtp:
        provider = None
        if args.provider:
            provider = args.provider

        result = DeliverabilityChecker.test_account(args.email, args.password, provider)

        if args.imap:
            result['tests']['imap'] = DeliverabilityChecker.test_imap(
                args.imap, args.imap_port, args.email, args.password, args.timeout
            )

        if args.smtp:
            result['tests']['smtp'] = DeliverabilityChecker.test_smtp(
                args.smtp, args.smtp_port, args.email, args.password, args.timeout
            )
    else:
        result = DeliverabilityChecker.test_account(args.email, args.password, args.provider)

    # Print results
    print(json.dumps(result, indent=2))

    # Print summary
    status = result.get('status', 'unknown')
    provider = result.get('provider', 'Unknown')

    print(f"\n{'='*70}")
    print(f"Result: {status.upper()}")
    print(f"Provider: {provider}")

    if status == 'fully_working':
        print("✓ Account can SEND and RECEIVE emails")
    elif status == 'partial_working':
        can_send = result.get('can_send', False)
        can_receive = result.get('can_receive', False)
        if can_send:
            print("~ Account can SEND but NOT RECEIVE")
        else:
            print("~ Account can RECEIVE but NOT SEND")
    else:
        print("✗ Account CANNOT send or receive emails")

    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
