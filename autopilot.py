#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoPilot - Automated SMTP Testing & Warmup Workflow
Tests SMTP → Upload → Check Inbox → Send → Repeat with Warmup
"""
import os
import sys
import time
import json
import subprocess
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smtp_client import test_smtp, send_email
from mailer import MailStats

class AutoPilot:
    def __init__(self, smtp_list_file, test_email=None, warmup_seconds=30, max_iterations=5):
        """
        Initialize AutoPilot

        Args:
            smtp_list_file: Path to file with SMTP creds (format: host:port:user:pass)
            test_email: Email to test inbox functionality
            warmup_seconds: Seconds to wait between iterations (let SMTP warm up)
            max_iterations: Max number of iterations
        """
        self.smtp_list_file = smtp_list_file
        self.test_email = test_email or "test@example.com"
        self.warmup_seconds = warmup_seconds
        self.max_iterations = max_iterations
        self.working_smtps = []
        self.stats = {
            "tested": 0,
            "working": 0,
            "inbox_ok": 0,
            "sent": 0,
            "failed": 0
        }

    def read_smtp_list(self):
        """Read SMTP credentials from file"""
        if not os.path.isfile(self.smtp_list_file):
            print(f"[!] File not found: {self.smtp_list_file}")
            return []

        smtps = []
        with open(self.smtp_list_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Expected format: host:port:user:pass
                parts = line.split(':')
                if len(parts) >= 4:
                    smtps.append({
                        'host': parts[0],
                        'port': int(parts[1]) if parts[1].isdigit() else 587,
                        'user': parts[2],
                        'pass': parts[3]
                    })

        print(f"[*] Loaded {len(smtps)} SMTP credentials")
        return smtps

    def test_smtp_credential(self, smtp):
        """Test single SMTP credential"""
        try:
            print(f"  Testing: {smtp['host']}:{smtp['port']}")
            result = test_smtp(
                smtp['host'],
                smtp['port'],
                smtp['user'],
                smtp['pass']
            )
            if result:
                print(f"    ✓ SMTP OK")
                return True
        except Exception as e:
            print(f"    ✗ Failed: {str(e)[:50]}")
        return False

    def test_inbox_functionality(self, smtp):
        """Test inbox by sending test email"""
        try:
            print(f"  Testing inbox: {smtp['user']}")
            result = send_email(
                smtp_host=smtp['host'],
                smtp_port=smtp['port'],
                smtp_user=smtp['user'],
                smtp_pass=smtp['pass'],
                sender_email=smtp['user'],
                recipient_email=self.test_email,
                subject="AutoPilot Test",
                body="This is an automated test email"
            )
            if result:
                print(f"    ✓ Inbox OK - Email sent")
                return True
        except Exception as e:
            print(f"    ✗ Inbox failed: {str(e)[:50]}")
        return False

    def run_iteration(self, iteration, smtps):
        """Run one iteration of the workflow"""
        print(f"\n{'='*60}")
        print(f"ITERATION {iteration}/{self.max_iterations}")
        print(f"{'='*60}\n")

        iteration_working = 0
        iteration_inbox = 0

        # Step 1: Test SMTP credentials
        print("[*] Step 1: Testing SMTP credentials...")
        for smtp in smtps:
            self.stats["tested"] += 1
            if self.test_smtp_credential(smtp):
                self.stats["working"] += 1
                iteration_working += 1
                self.working_smtps.append(smtp)
            time.sleep(0.5)  # Small delay between tests

        print(f"\n    Result: {iteration_working}/{len(smtps)} SMTP credentials working\n")

        # Step 2: Test inbox functionality
        if self.working_smtps:
            print("[*] Step 2: Testing inbox functionality...")
            for smtp in self.working_smtps[:3]:  # Test first 3
                if self.test_inbox_functionality(smtp):
                    self.stats["inbox_ok"] += 1
                    iteration_inbox += 1
                    self.stats["sent"] += 1
                time.sleep(1)  # Wait between inbox tests

            print(f"\n    Result: {iteration_inbox}/{len(self.working_smtps)} inboxes working\n")

        # Step 3: Warmup period
        if iteration < self.max_iterations:
            print(f"[*] Step 3: Warmup period ({self.warmup_seconds}s)...")
            for i in range(self.warmup_seconds, 0, -1):
                print(f"\r    Waiting: {i}s...", end="", flush=True)
                time.sleep(1)
            print("\n")

        return iteration_working, iteration_inbox

    def run(self):
        """Run the complete AutoPilot workflow"""
        print("\n" + "="*60)
        print("  MAILTOOLS AUTOPILOT")
        print("="*60 + "\n")

        # Read SMTP credentials
        smtps = self.read_smtp_list()
        if not smtps:
            print("[!] No credentials to test")
            return False

        # Run iterations
        for iteration in range(1, self.max_iterations + 1):
            working, inbox = self.run_iteration(iteration, smtps)

            if working == 0:
                print("[!] No working SMTP found. Stopping.")
                break

        # Final stats
        print(f"\n{'='*60}")
        print("FINAL STATISTICS")
        print(f"{'='*60}")
        print(f"Total Tested:      {self.stats['tested']}")
        print(f"Working SMTP:      {self.stats['working']}")
        print(f"Working Inbox:     {self.stats['inbox_ok']}")
        print(f"Emails Sent:       {self.stats['sent']}")
        print(f"{'='*60}\n")

        # Save results
        self.save_results()
        return True

    def save_results(self):
        """Save results to JSON file"""
        output_file = "autopilot_results.json"
        results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stats": self.stats,
            "working_smtps": self.working_smtps
        }

        try:
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"[*] Results saved to: {output_file}")
        except Exception as e:
            print(f"[!] Failed to save results: {e}")

def main():
    import argparse

    parser = argparse.ArgumentParser(description="AutoPilot SMTP Testing Workflow")
    parser.add_argument("smtp_file", help="SMTP credentials file (host:port:user:pass)")
    parser.add_argument("--test-email", default="test@example.com", help="Email for inbox testing")
    parser.add_argument("--warmup", type=int, default=30, help="Warmup seconds between iterations")
    parser.add_argument("--iterations", type=int, default=5, help="Number of iterations")

    args = parser.parse_args()

    # Check if file exists
    if not os.path.isfile(args.smtp_file):
        print(f"[!] File not found: {args.smtp_file}")
        sys.exit(1)

    # Create and run AutoPilot
    autopilot = AutoPilot(
        smtp_list_file=args.smtp_file,
        test_email=args.test_email,
        warmup_seconds=args.warmup,
        max_iterations=args.iterations
    )

    success = autopilot.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
