#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Mass Mailer with Template Support
Straightforward email sending with rotating templates
"""
import sys
import os
import time
import smtplib
import configparser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from concurrent.futures import ThreadPoolExecutor, as_completed
import socket
import ssl

class SimpleMailer:
    """Simple mass mailer"""

    def __init__(self, config_file):
        self.config = configparser.ConfigParser()
        self.config.read(config_file, encoding='utf-8')
        self.section = 'madcatmailer'
        self.sent_count = 0
        self.failed_count = 0
        self.total_count = 0

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

    def send_email(self, smtp_parts, to_email, subject, body):
        """Send single email"""
        try:
            # Parse SMTP: host:port:user:pass
            if ':' in smtp_parts:
                parts = smtp_parts.split(':')
                if len(parts) >= 4:
                    host = parts[0]
                    port = int(parts[1])
                    user = parts[2]
                    passwd = parts[3]
                else:
                    return False, "Invalid SMTP format"
            else:
                return False, "Invalid SMTP format"

            # Prepare message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.get_config('mail_from', user)
            msg['To'] = to_email
            msg['Subject'] = subject

            # Add reply-to if configured
            reply_to = self.get_config('mail_reply_to', '').strip()
            if reply_to:
                msg['Reply-To'] = reply_to

            # Body (detect HTML or plain text)
            msg.attach(MIMEText(body, 'html' if body.strip().startswith('<') else 'plain'))

            # Attachments
            attachments = self.get_config('attachment_files', '').strip()
            if attachments:
                for att_path in [a.strip() for a in attachments.split(';') if a.strip()]:
                    if os.path.isfile(att_path):
                        try:
                            with open(att_path, 'rb') as attachment:
                                part = MIMEBase('application', 'octet-stream')
                                part.set_payload(attachment.read())
                            encoders.encode_base64(part)
                            part.add_header('Content-Disposition', f'attachment; filename= {os.path.basename(att_path)}')
                            msg.attach(part)
                        except:
                            pass

            # Send
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

            return True, "Sent"

        except smtplib.SMTPAuthenticationError:
            return False, "Auth failed"
        except smtplib.SMTPException as e:
            return False, str(e)
        except Exception as e:
            return False, str(e)

    def run(self):
        """Run mailer"""
        print("\n" + "="*70)
        print("  📧 SIMPLE MAILER - Template Supported")
        print("="*70 + "\n")

        # Load config
        smtps_file = self.get_config('smtps_list_file', '').strip()
        mails_file = self.get_config('mails_list_file', '').strip()
        subject = self.get_config('mail_subject', 'Hello').strip()
        body_file = self.get_config('mail_body', '').strip()

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

        if not smtps or not mails or not body:
            print(f"  ❌ Empty data:")
            print(f"     • SMTP accounts: {len(smtps)}")
            print(f"     • Recipient emails: {len(mails)}")
            print(f"     • Body length: {len(body)}")
            return False

        self.total_count = len(mails)

        print(f"  📋 Configuration:")
        print(f"     • SMTP accounts: {len(smtps)}")
        print(f"     • Recipients: {len(mails)}")
        print(f"     • Subject: {subject[:50]}...")
        print(f"     • Body length: {len(body)} chars")
        print()

        # Send emails
        threads = int(self.get_config('threads_count', '5'))
        print(f"  🚀 Sending with {threads} threads...\n")

        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {}
            for i, to_email in enumerate(mails):
                smtp = smtps[i % len(smtps)]  # Rotate SMTP accounts
                future = executor.submit(self.send_email, smtp, to_email, subject, body)
                futures[future] = (i + 1, to_email)

            for future in as_completed(futures):
                idx, email = futures[future]
                success, msg = future.result()

                if success:
                    self.sent_count += 1
                    status = "✓"
                else:
                    self.failed_count += 1
                    status = "✗"

                # Progress
                pct = int(self.sent_count / self.total_count * 100) if self.total_count > 0 else 0
                print(f"  [{idx:5d}/{self.total_count}] {status} {email:40s} [{pct}%]")

        print()
        print("="*70)
        print(f"  ✅ COMPLETED")
        print("="*70)
        print(f"  Sent:    {self.sent_count}")
        print(f"  Failed:  {self.failed_count}")
        print(f"  Total:   {self.total_count}")
        print()
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nUsage: python3 simple_mailer.py [config_file]\n")
        sys.exit(1)

    config_file = sys.argv[1]
    if not os.path.isfile(config_file):
        print(f"\n❌ Config file not found: {config_file}\n")
        sys.exit(1)

    mailer = SimpleMailer(config_file)
    success = mailer.run()
    sys.exit(0 if success else 1)
