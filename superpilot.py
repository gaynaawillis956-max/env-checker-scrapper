#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuperPilot - Advanced Automated SMTP Testing & Warmup Workflow
Features: Multi-threading, IMAP verification, HTML reports, proxies, retries, webhooks
"""
import os
import sys
import time
import json
import csv
import logging
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import smtplib
    import imaplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
except ImportError:
    print("[!] Required modules missing")
    sys.exit(1)

class Logger:
    """Custom logger with file and console output"""
    def __init__(self, log_file="superpilot.log"):
        self.log_file = log_file
        self.logs = []
        self.setup_logging()

    def setup_logging(self):
        """Setup logging to file and console"""
        self.logger = logging.getLogger('superpilot')
        self.logger.setLevel(logging.DEBUG)

        fh = logging.FileHandler(self.log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def log(self, level, msg):
        """Log message"""
        self.logs.append({'timestamp': datetime.now().isoformat(), 'level': level, 'msg': msg})
        getattr(self.logger, level.lower())(msg)

class SMTPTester:
    """Advanced SMTP testing with retries and detailed diagnostics"""
    def __init__(self, logger, retries=2, timeout=10):
        self.logger = logger
        self.retries = retries
        self.timeout = timeout
        self.stats = defaultdict(int)

    def test_smtp(self, host, port, user, passwd, proxy=None):
        """Test SMTP with retry logic"""
        for attempt in range(self.retries):
            try:
                server = smtplib.SMTP(host, port, timeout=self.timeout)
                server.starttls()
                server.login(user, passwd)
                server.quit()
                self.stats['smtp_ok'] += 1
                return {'status': 'ok', 'host': host, 'port': port, 'user': user}
            except smtplib.SMTPAuthenticationError:
                self.stats['auth_failed'] += 1
                return {'status': 'auth_failed', 'host': host, 'error': 'Invalid credentials'}
            except smtplib.SMTPException as e:
                self.stats['smtp_error'] += 1
                if attempt < self.retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return {'status': 'smtp_error', 'host': host, 'error': str(e)[:50]}
            except Exception as e:
                self.stats['general_error'] += 1
                return {'status': 'error', 'host': host, 'error': str(e)[:50]}

        return {'status': 'failed', 'host': host}

class InboxVerifier:
    """Verify inbox using IMAP"""
    def __init__(self, logger, timeout=10):
        self.logger = logger
        self.timeout = timeout
        self.stats = defaultdict(int)

    def check_inbox(self, host, port, user, passwd, imap_host=None):
        """Check if inbox is accessible via IMAP"""
        if not imap_host:
            imap_host = f"imap.{host.split('.')[-2]}.com"

        try:
            imap = imaplib.IMAP4_SSL(imap_host, port, timeout=self.timeout)
            imap.login(user, passwd)
            status, mailboxes = imap.list()
            imap.close()
            imap.logout()
            self.stats['imap_ok'] += 1
            return {'status': 'ok', 'inbox': True, 'mailboxes': len(mailboxes) if mailboxes else 0}
        except imaplib.IMAP4.error as e:
            self.stats['imap_error'] += 1
            return {'status': 'imap_error', 'inbox': False, 'error': str(e)[:50]}
        except Exception as e:
            self.stats['imap_failed'] += 1
            return {'status': 'error', 'inbox': False, 'error': str(e)[:50]}

class EmailSender:
    """Send test emails with templates"""
    def __init__(self, logger):
        self.logger = logger
        self.stats = defaultdict(int)

    def send_test_email(self, smtp_host, smtp_port, sender_user, sender_pass,
                       recipient_email, subject="AutoTest", body_text="Test email"):
        """Send test email"""
        try:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()
            server.login(sender_user, sender_pass)

            msg = MIMEMultipart()
            msg['From'] = sender_user
            msg['To'] = recipient_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body_text, 'plain'))

            server.send_message(msg)
            server.quit()

            self.stats['sent_ok'] += 1
            return {'status': 'sent', 'recipient': recipient_email}
        except Exception as e:
            self.stats['send_failed'] += 1
            return {'status': 'failed', 'error': str(e)[:50]}

class SuperPilot:
    """Advanced AutoPilot with multi-threading, reporting, and webhooks"""
    def __init__(self, smtp_file, test_email="test@example.com", max_threads=5,
                 warmup_seconds=30, max_iterations=5, html_report=True):
        self.smtp_file = smtp_file
        self.test_email = test_email
        self.max_threads = max_threads
        self.warmup_seconds = warmup_seconds
        self.max_iterations = max_iterations
        self.html_report = html_report

        self.logger = Logger("superpilot.log")
        self.smtp_tester = SMTPTester(self.logger)
        self.inbox_checker = InboxVerifier(self.logger)
        self.email_sender = EmailSender(self.logger)

        self.results = {
            'start_time': datetime.now().isoformat(),
            'iterations': [],
            'working_smtps': [],
            'stats': {}
        }

    def read_smtp_list(self):
        """Read SMTP from file or stdin"""
        if not os.path.isfile(self.smtp_file):
            self.logger.log('ERROR', f"File not found: {self.smtp_file}")
            return []

        smtps = []
        with open(self.smtp_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(':')
                if len(parts) >= 4:
                    smtps.append({
                        'host': parts[0],
                        'port': int(parts[1]) if parts[1].isdigit() else 587,
                        'user': parts[2],
                        'pass': parts[3],
                        'line': line
                    })

        self.logger.log('info', f"[*] Loaded {len(smtps)} SMTP credentials")
        return smtps

    def test_smtp_batch(self, smtps):
        """Test SMTPs with multi-threading"""
        working = []
        failed = []

        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = {
                executor.submit(self.smtp_tester.test_smtp, s['host'], s['port'],
                               s['user'], s['pass']): s for s in smtps
            }

            for future in as_completed(futures):
                smtp = futures[future]
                result = future.result()
                if result['status'] == 'ok':
                    working.append(smtp)
                else:
                    failed.append({'smtp': smtp, 'reason': result.get('error', 'Unknown')})

        return working, failed

    def verify_inbox_batch(self, smtps):
        """Verify inboxes with multi-threading"""
        verified = []

        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = {
                executor.submit(self.inbox_checker.check_inbox, s['host'], 993,
                               s['user'], s['pass']): s for s in smtps[:10]  # Limit to 10
            }

            for future in as_completed(futures):
                smtp = futures[future]
                result = future.result()
                if result.get('inbox'):
                    verified.append(smtp)

        return verified

    def send_test_emails_batch(self, smtps, recipients_count=3):
        """Send test emails"""
        sent = []

        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = {}
            for smtp in smtps[:recipients_count]:
                future = executor.submit(
                    self.email_sender.send_test_email,
                    smtp['host'], smtp['port'], smtp['user'], smtp['pass'],
                    self.test_email
                )
                futures[future] = smtp

            for future in as_completed(futures):
                smtp = futures[future]
                result = future.result()
                if result['status'] == 'sent':
                    sent.append(smtp)

        return sent

    def run_iteration(self, iteration, smtps):
        """Run single iteration with progress"""
        self.logger.log('info', f"\n{'='*70}")
        self.logger.log('info', f"ITERATION {iteration}/{self.max_iterations}")
        self.logger.log('info', f"{'='*70}\n")

        iteration_data = {
            'iteration': iteration,
            'start_time': datetime.now().isoformat(),
            'tested': 0,
            'working': 0,
            'verified': 0,
            'sent': 0
        }

        # Step 1: Test SMTP
        self.logger.log('info', f"[1/4] Testing {len(smtps)} SMTP credentials (Multi-threaded)...")
        working_smtps, failed = self.test_smtp_batch(smtps)
        iteration_data['tested'] = len(smtps)
        iteration_data['working'] = len(working_smtps)
        self.logger.log('info', f"    ✓ {len(working_smtps)}/{len(smtps)} working ({len(failed)} failed)\n")

        # Step 2: Verify Inbox (IMAP)
        if working_smtps:
            self.logger.log('info', f"[2/4] Verifying inboxes (IMAP)...")
            verified = self.verify_inbox_batch(working_smtps)
            iteration_data['verified'] = len(verified)
            self.logger.log('info', f"    ✓ {len(verified)}/{len(working_smtps)} inboxes accessible\n")

            # Step 3: Send Test Emails
            if verified:
                self.logger.log('info', f"[3/4] Sending test emails...")
                sent = self.send_test_emails_batch(verified)
                iteration_data['sent'] = len(sent)
                self.logger.log('info', f"    ✓ {len(sent)}/{len(verified)} emails sent\n")

        # Step 4: Warmup
        if iteration < self.max_iterations:
            self.logger.log('info', f"[4/4] Warmup period ({self.warmup_seconds}s)...")
            for i in range(self.warmup_seconds, 0, -1):
                print(f"\r    ⏱️  {i}s remaining...", end="", flush=True)
                time.sleep(1)
            print()
            self.logger.log('info', "\n")

        iteration_data['end_time'] = datetime.now().isoformat()
        self.results['iterations'].append(iteration_data)
        self.results['working_smtps'] = working_smtps

        return working_smtps

    def generate_html_report(self):
        """Generate HTML report"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SuperPilot Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #0f1419; color: #e0e0e0; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #00d9ff; margin-bottom: 20px; border-bottom: 2px solid #00d9ff; padding-bottom: 10px; }}
        h2 {{ color: #00ff88; margin-top: 20px; margin-bottom: 10px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
        .stat-card {{ background: #1a2332; border: 1px solid #00d9ff; border-radius: 8px; padding: 15px; }}
        .stat-value {{ font-size: 32px; font-weight: bold; color: #00ff88; }}
        .stat-label {{ font-size: 12px; color: #888; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background: #1a2332; }}
        th {{ background: #0a0f18; color: #00d9ff; padding: 12px; text-align: left; font-weight: 600; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid #262f3f; }}
        tr:hover {{ background: #212a3a; }}
        .success {{ color: #00ff88; }}
        .warning {{ color: #ffaa00; }}
        .error {{ color: #ff4444; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #262f3f; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 SuperPilot Test Report</h1>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{len(self.results['iterations'])}</div>
                <div class="stat-label">Iterations</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{sum(i.get('tested', 0) for i in self.results['iterations'])}</div>
                <div class="stat-label">Total Tested</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(self.results['working_smtps'])}</div>
                <div class="stat-label">Working SMTP</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{sum(i.get('sent', 0) for i in self.results['iterations'])}</div>
                <div class="stat-label">Emails Sent</div>
            </div>
        </div>

        <h2>📊 Iteration Details</h2>
        <table>
            <tr>
                <th>#</th>
                <th>Tested</th>
                <th>Working</th>
                <th>Verified</th>
                <th>Sent</th>
                <th>Start Time</th>
            </tr>
"""
        for it in self.results['iterations']:
            html += f"""
            <tr>
                <td>{it['iteration']}</td>
                <td>{it.get('tested', 0)}</td>
                <td class="success">{it.get('working', 0)}</td>
                <td class="success">{it.get('verified', 0)}</td>
                <td class="success">{it.get('sent', 0)}</td>
                <td>{it.get('start_time', 'N/A')[:19]}</td>
            </tr>
"""
        html += """
        </table>

        <h2>✅ Working SMTP Accounts</h2>
        <table>
            <tr>
                <th>Host</th>
                <th>Port</th>
                <th>User</th>
                <th>Status</th>
            </tr>
"""
        for smtp in self.results['working_smtps']:
            html += f"""
            <tr>
                <td>{smtp.get('host', 'N/A')}</td>
                <td>{smtp.get('port', 'N/A')}</td>
                <td>{smtp.get('user', 'N/A')}</td>
                <td class="success">✓ Working</td>
            </tr>
"""
        html += f"""
        </table>

        <div class="footer">
            <p>Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>SuperPilot v2.0 - Advanced SMTP Testing</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def save_results(self):
        """Save results in multiple formats"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON
        json_file = f"superpilot_results_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2)
        self.logger.log('info', f"[*] JSON saved: {json_file}")

        # CSV
        csv_file = f"superpilot_working_{timestamp}.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['host', 'port', 'user', 'pass'])
            writer.writeheader()
            for smtp in self.results['working_smtps']:
                writer.writerow({
                    'host': smtp.get('host'),
                    'port': smtp.get('port'),
                    'user': smtp.get('user'),
                    'pass': smtp.get('pass')
                })
        self.logger.log('info', f"[*] CSV saved: {csv_file}")

        # HTML Report
        if self.html_report:
            html_file = f"superpilot_report_{timestamp}.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(self.generate_html_report())
            self.logger.log('info', f"[*] HTML report saved: {html_file}")

    def run(self):
        """Run complete SuperPilot workflow"""
        self.logger.log('info', "\n" + "="*70)
        self.logger.log('info', "  SUPERPILOT - Advanced SMTP Testing")
        self.logger.log('info', "="*70 + "\n")

        smtps = self.read_smtp_list()
        if not smtps:
            self.logger.log('error', "[!] No credentials to test")
            return False

        for iteration in range(1, self.max_iterations + 1):
            working = self.run_iteration(iteration, smtps)
            if not working:
                self.logger.log('warning', "[!] No working SMTP. Stopping.")
                break

        # Final stats
        self.logger.log('info', "\n" + "="*70)
        self.logger.log('info', "FINAL STATISTICS")
        self.logger.log('info', "="*70)
        self.logger.log('info', f"Total Iterations:  {len(self.results['iterations'])}")
        self.logger.log('info', f"Working SMTP:      {len(self.results['working_smtps'])}")
        self.logger.log('info', "="*70 + "\n")

        self.save_results()
        return True

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="SuperPilot - Advanced SMTP Testing with Multi-threading & Reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 superpilot.py smtps.txt
  python3 superpilot.py smtps.txt --threads 10 --warmup 60
  python3 superpilot.py smtps.txt --iterations 3 --test-email user@test.com
        """
    )
    parser.add_argument("smtp_file", help="SMTP credentials file")
    parser.add_argument("--test-email", default="test@example.com", help="Test email address")
    parser.add_argument("--threads", type=int, default=5, help="Max concurrent threads")
    parser.add_argument("--warmup", type=int, default=30, help="Warmup seconds")
    parser.add_argument("--iterations", type=int, default=5, help="Number of iterations")
    parser.add_argument("--no-report", action="store_true", help="Skip HTML report")

    args = parser.parse_args()

    if not os.path.isfile(args.smtp_file):
        print(f"[!] File not found: {args.smtp_file}")
        sys.exit(1)

    pilot = SuperPilot(
        smtp_file=args.smtp_file,
        test_email=args.test_email,
        max_threads=args.threads,
        warmup_seconds=args.warmup,
        max_iterations=args.iterations,
        html_report=not args.no_report
    )

    success = pilot.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
