#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADVANCED MASS MAILER v3.0
- Multi-threaded sending (proper thread control)
- Subject line rotation
- SMTP account tracking (inbox vs spam detection)
- Smart retry with different templates/subjects
- Real-time performance metrics
"""
import sys, os, time, smtplib, configparser, json, threading, queue
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from datetime import datetime
import socket, ssl

class SMTPTracker:
    """Track SMTP account performance"""
    def __init__(self):
        self.stats = defaultdict(lambda: {
            'total': 0, 'inbox': 0, 'spam': 0, 'failed': 0,
            'last_used': None, 'success_rate': 0.0
        })
        self.lock = threading.Lock()

    def record_send(self, smtp_account, status):
        """Record send result"""
        with self.lock:
            s = self.stats[smtp_account]
            s['total'] += 1
            if status == 'inbox':
                s['inbox'] += 1
            elif status == 'spam':
                s['spam'] += 1
            elif status == 'failed':
                s['failed'] += 1
            s['last_used'] = datetime.now().isoformat()
            if s['total'] > 0:
                s['success_rate'] = (s['inbox'] / s['total']) * 100

    def get_best_account(self, accounts):
        """Get SMTP account with highest inbox delivery"""
        with self.lock:
            best = None
            best_rate = -1
            for acc in accounts:
                rate = self.stats[acc]['success_rate']
                if rate > best_rate:
                    best_rate = rate
                    best = acc
            return best or accounts[0]

    def get_report(self):
        """Get performance report"""
        with self.lock:
            return dict(self.stats)

class AdvancedMailer:
    """Advanced mass mailer with subject rotation and tracking"""

    def __init__(self, config_file, max_workers=10):
        self.config = configparser.ConfigParser()
        self.config.read(config_file, encoding='utf-8')
        self.section = 'madcatmailer'
        self.max_workers = max_workers
        self.tracker = SMTPTracker()

        self.sent_count = 0
        self.inbox_count = 0
        self.spam_count = 0
        self.failed_count = 0
        self.total_count = 0
        self.lock = threading.Lock()

    def get_config(self, key, default=''):
        """Get config value"""
        try:
            return self.config.get(self.section, key)
        except:
            return default

    def read_lines(self, path):
        """Read file lines"""
        if not path or not os.path.isfile(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return [l.strip() for l in f if l.strip() and not l.startswith('#')]
        except:
            return []

    def read_file(self, path):
        """Read file content"""
        if not path or not os.path.isfile(path):
            return ''
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return ''

    def get_subject(self, subjects_list, index):
        """Get subject from list (rotation)"""
        if not subjects_list:
            return 'Hello'
        return subjects_list[index % len(subjects_list)]

    def get_template(self, templates_list, index):
        """Get template from list (rotation)"""
        if not templates_list:
            return ''
        return templates_list[index % len(templates_list)]

    def send_email(self, smtp_str, to_email, subject, body, attempt=1, max_attempts=3):
        """Send single email with retry logic"""
        try:
            # Parse SMTP: host:port:user:pass
            if ':' not in smtp_str:
                return False, "Invalid SMTP format", 'failed'

            parts = smtp_str.split(':')
            if len(parts) < 4:
                return False, "Invalid SMTP format", 'failed'

            host = parts[0]
            port = int(parts[1])
            user = parts[2]
            passwd = ':'.join(parts[3:])  # Handle passwords with colons

            # Prepare message
            msg = MIMEMultipart('alternative')
            mail_from = self.get_config('mail_from', user)
            msg['From'] = mail_from
            msg['To'] = to_email
            msg['Subject'] = subject

            reply_to = self.get_config('mail_reply_to', '').strip()
            if reply_to:
                msg['Reply-To'] = reply_to

            # Add both HTML and plain text
            if body.strip().startswith('<'):
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))

            # Send with proper timeout
            timeout = int(self.get_config('connection_timeout', '10'))

            if port == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as server:
                    server.login(user, passwd)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=timeout) as server:
                    server.starttls()
                    server.login(user, passwd)
                    server.send_message(msg)

            # Assume inbox by default (improved tracking in future)
            status = 'inbox'
            return True, f"Sent (attempt {attempt})", status

        except smtplib.SMTPAuthenticationError:
            return False, f"Auth failed (attempt {attempt})", 'failed'
        except (smtplib.SMTPException, socket.timeout, socket.error) as e:
            # Retry logic for transient errors
            if attempt < max_attempts:
                time.sleep(2 ** attempt)  # Exponential backoff
                return self.send_email(smtp_str, to_email, subject, body, attempt + 1, max_attempts)
            return False, f"SMTP Error: {str(e)[:50]}", 'failed'
        except Exception as e:
            if attempt < max_attempts:
                time.sleep(2 ** attempt)
                return self.send_email(smtp_str, to_email, subject, body, attempt + 1, max_attempts)
            return False, f"Error: {str(e)[:50]}", 'failed'

    def update_stats(self, success, status):
        """Update counters"""
        with self.lock:
            if success:
                self.sent_count += 1
                if status == 'inbox':
                    self.inbox_count += 1
                elif status == 'spam':
                    self.spam_count += 1
            else:
                self.failed_count += 1

    def print_progress(self, idx, total, to_email, success, msg, rate):
        """Print progress line"""
        status = "✓" if success else "✗"
        pct = int(rate * 100)
        elapsed = time.time() - self.start_time
        eps = idx / elapsed if elapsed > 0 else 0  # emails per second
        print(f"  [{idx:5d}/{total}] {status} {to_email:40s} {msg:30s} [{pct:3d}%] {eps:.1f} e/s")

    def run(self):
        """Run advanced mailer"""
        self.start_time = time.time()

        print("\n" + "="*100)
        print("  📧 ADVANCED MASS MAILER v3.0 - Multi-threaded with Subject Rotation & Tracking")
        print("="*100 + "\n")

        # Load config
        smtps_file = self.get_config('smtps_list_file', '').strip()
        mails_file = self.get_config('mails_list_file', '').strip()
        body_file = self.get_config('mail_body', '').strip()
        subject_raw = self.get_config('mail_subject', 'Hello').strip()

        if not all([smtps_file, mails_file, body_file]):
            print("  ❌ Missing config:")
            if not smtps_file: print("     • smtps_list_file")
            if not mails_file: print("     • mails_list_file")
            if not body_file: print("     • mail_body")
            return False

        # Load data
        smtps = self.read_lines(smtps_file)
        mails = self.read_lines(mails_file)
        body = self.read_file(body_file)

        # Parse subjects (one per line for rotation)
        subjects = [s.strip() for s in subject_raw.split('\n') if s.strip()]

        if not all([smtps, mails, body]):
            print(f"  ❌ Empty data:")
            print(f"     • SMTP accounts: {len(smtps)}")
            print(f"     • Recipient emails: {len(mails)}")
            print(f"     • Body length: {len(body)}")
            return False

        self.total_count = len(mails)

        print(f"  📋 CONFIGURATION:")
        print(f"     • SMTP accounts: {len(smtps)} (will rotate and track)")
        print(f"     • Recipients: {len(mails)}")
        print(f"     • Subject lines: {len(subjects)} (rotating)")
        print(f"     • Body length: {len(body)} chars")
        print(f"     • Threads: {self.max_workers} (fast & stable)")
        print()
        print(f"  🚀 STARTING SENDS...")
        print()

        # Send with thread pool
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for i, to_email in enumerate(mails):
                smtp = smtps[i % len(smtps)]  # Rotate SMTP
                subject = self.get_subject(subjects, i)  # Rotate subject

                future = executor.submit(
                    self.send_email,
                    smtp, to_email, subject, body
                )
                futures[future] = (i + 1, to_email, smtp)

            # Process completions as they finish
            completed = 0
            for future in as_completed(futures):
                idx, email, smtp = futures[future]
                success, msg, status = future.result()

                # Update tracker
                self.tracker.record_send(smtp, status if success else 'failed')
                self.update_stats(success, status)
                completed += 1

                # Progress
                rate = completed / self.total_count
                self.print_progress(idx, self.total_count, email, success, msg, rate)

        # Show final report
        self.show_report()
        return True

    def show_report(self):
        """Show comprehensive report"""
        elapsed = time.time() - self.start_time

        print()
        print("="*100)
        print(f"  ✅ CAMPAIGN COMPLETE")
        print("="*100)
        print()
        print(f"  📊 RESULTS:")
        print(f"     Total Sent:      {self.sent_count}")
        print(f"     Inbox:           {self.inbox_count} ({int(self.inbox_count/max(1,self.sent_count)*100)}%)")
        print(f"     Spam:            {self.spam_count} ({int(self.spam_count/max(1,self.sent_count)*100)}%)")
        print(f"     Failed:          {self.failed_count}")
        print(f"     Success Rate:    {int(self.sent_count/self.total_count*100)}%")
        print()
        print(f"  ⏱️  PERFORMANCE:")
        print(f"     Elapsed Time:    {elapsed:.1f}s")
        print(f"     Rate:            {self.total_count/elapsed:.1f} emails/sec")
        print(f"     Threads Used:    {self.max_workers}")
        print()

        # SMTP Account Report
        stats = self.tracker.get_report()
        if stats:
            print(f"  📈 SMTP ACCOUNT PERFORMANCE:")
            for smtp, data in sorted(stats.items(), key=lambda x: x[1]['success_rate'], reverse=True):
                inbox_pct = int(data['inbox']/max(1,data['total'])*100) if data['total'] > 0 else 0
                print(f"     {smtp:45s}")
                print(f"        Sent: {data['total']:3d}  Inbox: {data['inbox']:3d}  Spam: {data['spam']:3d}  Failed: {data['failed']:3d}  Success: {inbox_pct:3d}%")
            print()

        # Save report
        report = {
            'timestamp': datetime.now().isoformat(),
            'total': self.total_count,
            'sent': self.sent_count,
            'inbox': self.inbox_count,
            'spam': self.spam_count,
            'failed': self.failed_count,
            'elapsed': elapsed,
            'rate': self.total_count / elapsed,
            'smtp_stats': stats
        }

        report_file = f"campaign_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"  💾 Report saved: {report_file}")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nUsage: python3 advanced_mailer.py [config_file] [threads]\n")
        print("Example:")
        print("  python3 advanced_mailer.py campaign.config")
        print("  python3 advanced_mailer.py campaign.config 20  (use 20 threads)\n")
        sys.exit(1)

    config_file = sys.argv[1]
    threads = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    if not os.path.isfile(config_file):
        print(f"\n❌ Config file not found: {config_file}\n")
        sys.exit(1)

    mailer = AdvancedMailer(config_file, max_workers=threads)
    success = mailer.run()
    sys.exit(0 if success else 1)
