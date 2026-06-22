#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive Setup & Troubleshooting Wizard
Simple menu-driven interface for everything
"""
import os
import sys
import subprocess
import json
from pathlib import Path

class Wizard:
    """Interactive wizard for setup and troubleshooting"""

    def __init__(self):
        self.clear_screen()
        self.main_menu()

    def clear_screen(self):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(self, title):
        """Print nice header"""
        print("\n" + "="*60)
        print(f"  {title}")
        print("="*60 + "\n")

    def print_menu(self, options):
        """Print menu options"""
        for i, option in enumerate(options, 1):
            print(f"  [{i}] {option}")
        print()

    def get_choice(self, max_option):
        """Get user choice"""
        while True:
            try:
                choice = int(input("  → Choose: "))
                if 1 <= choice <= max_option:
                    return choice
                print(f"  Please enter 1-{max_option}")
            except ValueError:
                print("  Please enter a number")

    def main_menu(self):
        """Main menu"""
        while True:
            self.clear_screen()
            self.print_header("📧 UNIFIED MAIL TOOLS - WIZARD")

            print("What do you want to do?\n")
            options = [
                "🚀 Test SMTP Accounts (SuperPilot)",
                "📝 Convert Credential Format",
                "✉️  Check Email Deliverability",
                "📊 View Results & Reports",
                "❓ Troubleshoot Issues",
                "⚙️  Configuration & Setup",
                "❌ Exit"
            ]
            self.print_menu(options)

            choice = self.get_choice(len(options))

            if choice == 1:
                self.superpilot_menu()
            elif choice == 2:
                self.converter_menu()
            elif choice == 3:
                self.deliverability_menu()
            elif choice == 4:
                self.results_menu()
            elif choice == 5:
                self.troubleshoot_menu()
            elif choice == 6:
                self.config_menu()
            elif choice == 7:
                self.clear_screen()
                print("Goodbye! 👋\n")
                sys.exit(0)

    def superpilot_menu(self):
        """SuperPilot testing"""
        self.clear_screen()
        self.print_header("🚀 SUPERPILOT - TEST SMTP ACCOUNTS")

        print("Choose test type:\n")
        options = [
            "Fast Test (15 threads, 2 iterations, 10s warmup)",
            "Normal Test (10 threads, 5 iterations, 30s warmup)",
            "Careful Test (5 threads, 10 iterations, 2min warmup)",
            "Custom Settings",
            "Back to Main Menu"
        ]
        self.print_menu(options)

        choice = self.get_choice(len(options))

        if choice == 1:
            self.run_superpilot("--threads 15 --warmup 10 --iterations 2")
        elif choice == 2:
            self.run_superpilot("--threads 10 --warmup 30 --iterations 5")
        elif choice == 3:
            self.run_superpilot("--threads 5 --warmup 120 --iterations 10")
        elif choice == 4:
            self.custom_superpilot()
        # else: back to main

    def run_superpilot(self, args):
        """Run SuperPilot"""
        self.clear_screen()
        self.print_header("🧪 RUNNING SUPERPILOT TEST")

        file_path = input("  Enter SMTP list filename (e.g., smtps.txt): ").strip()

        if not os.path.isfile(file_path):
            print(f"\n  ❌ File not found: {file_path}")
            input("  Press Enter to continue...")
            return

        print(f"\n  Starting test of {file_path}...\n")
        os.system(f"python3 superpilot.py {file_path} {args}")
        input("\n  Press Enter to continue...")

    def custom_superpilot(self):
        """Custom SuperPilot settings"""
        self.clear_screen()
        self.print_header("⚙️  CUSTOM SUPERPILOT SETTINGS")

        file_path = input("  SMTP list file: ").strip()
        threads = input("  Threads (1-20, default 10): ").strip() or "10"
        warmup = input("  Warmup seconds (default 30): ").strip() or "30"
        iterations = input("  Iterations (default 5): ").strip() or "5"

        args = f"--threads {threads} --warmup {warmup} --iterations {iterations}"
        self.run_superpilot(args)

    def converter_menu(self):
        """Format converter"""
        self.clear_screen()
        self.print_header("📝 FORMAT CONVERTER")

        print("Convert your credential file to SMTP format\n")
        options = [
            "Detect Format (just show what's in file)",
            "Convert & Save",
            "Back to Main Menu"
        ]
        self.print_menu(options)

        choice = self.get_choice(len(options))

        if choice == 1:
            file_path = input("  File to analyze: ").strip()
            if os.path.isfile(file_path):
                os.system(f"python3 format_converter.py {file_path} --detect")
            else:
                print(f"  ❌ File not found: {file_path}")
            input("  Press Enter to continue...")
        elif choice == 2:
            file_path = input("  Input file: ").strip()
            output_file = input("  Output file (default: converted.txt): ").strip() or "converted.txt"
            if os.path.isfile(file_path):
                os.system(f"python3 format_converter.py {file_path} --output {output_file}")
                print(f"\n  ✓ Saved to: {output_file}")
            else:
                print(f"  ❌ File not found: {file_path}")
            input("  Press Enter to continue...")

    def deliverability_menu(self):
        """Deliverability checker"""
        self.clear_screen()
        self.print_header("✉️  CHECK EMAIL DELIVERABILITY")

        print("Test if email can send AND receive\n")
        options = [
            "Gmail Account",
            "Outlook Account",
            "Yahoo Account",
            "Other Provider (IMAP/SMTP)",
            "Back to Main Menu"
        ]
        self.print_menu(options)

        choice = self.get_choice(len(options))

        if choice == 1:
            email = input("  Gmail address: ").strip()
            password = input("  App password (16 chars): ").strip()
            os.system(f'python3 multi_deliverability.py "{email}" "{password}"')
            input("  Press Enter to continue...")
        elif choice == 2:
            email = input("  Outlook address: ").strip()
            password = input("  Password: ").strip()
            os.system(f'python3 multi_deliverability.py "{email}" "{password}" --provider outlook')
            input("  Press Enter to continue...")
        elif choice == 3:
            email = input("  Yahoo address: ").strip()
            password = input("  App password: ").strip()
            os.system(f'python3 multi_deliverability.py "{email}" "{password}" --provider yahoo')
            input("  Press Enter to continue...")
        elif choice == 4:
            email = input("  Email address: ").strip()
            password = input("  Password: ").strip()
            imap = input("  IMAP server (e.g., imap.company.com): ").strip()
            smtp = input("  SMTP server (e.g., smtp.company.com): ").strip()
            os.system(f'python3 multi_deliverability.py "{email}" "{password}" --imap {imap} --smtp {smtp}')
            input("  Press Enter to continue...")

    def results_menu(self):
        """View results"""
        self.clear_screen()
        self.print_header("📊 VIEW RESULTS & REPORTS")

        print("Recent results files:\n")

        # List HTML reports
        html_files = sorted([f for f in os.listdir('.') if f.startswith('superpilot_report_') and f.endswith('.html')])
        csv_files = sorted([f for f in os.listdir('.') if f.startswith('superpilot_working_') and f.endswith('.csv')])

        if html_files:
            print("  HTML Reports (for browser):")
            for f in html_files[-3:]:
                print(f"    • {f}")

        if csv_files:
            print("\n  CSV Files (for import):")
            for f in csv_files[-3:]:
                print(f"    • {f}")

        if not html_files and not csv_files:
            print("  No results files found yet.")
            print("  Run a test first to generate reports!")

        input("\n  Press Enter to continue...")

    def troubleshoot_menu(self):
        """Troubleshooting"""
        self.clear_screen()
        self.print_header("❓ TROUBLESHOOTING")

        print("What's the problem?\n")
        options = [
            "SuperPilot/AutoPilot won't run",
            "Can't connect to SMTP",
            "Can't connect to IMAP",
            "Gmail says invalid credentials",
            "Outlook says invalid credentials",
            "Too slow (want faster)",
            "Too fast (want slower/safer)",
            "Not sure what went wrong",
            "Back to Main Menu"
        ]
        self.print_menu(options)

        choice = self.get_choice(len(options))

        if choice == 1:
            self.troubleshoot_wont_run()
        elif choice == 2:
            self.troubleshoot_smtp()
        elif choice == 3:
            self.troubleshoot_imap()
        elif choice == 4:
            self.troubleshoot_gmail_creds()
        elif choice == 5:
            self.troubleshoot_outlook_creds()
        elif choice == 6:
            self.troubleshoot_slow()
        elif choice == 7:
            self.troubleshoot_fast()
        elif choice == 8:
            self.troubleshoot_unknown()

    def troubleshoot_wont_run(self):
        """Troubleshoot won't run"""
        self.clear_screen()
        self.print_header("🔧 SUPERPILOT WON'T RUN")

        print("Checking...\n")

        # Check Python
        result = os.system("python3 --version >nul 2>&1")
        if result != 0:
            print("  ❌ Python 3 not installed!")
            print("  ✓ Solution: Install Python 3.8+ from python.org")
            input("  Press Enter to continue...")
            return

        print("  ✓ Python 3 found")

        # Check dependencies
        print("  ✓ Checking dependencies...")
        result = os.system("python3 -c \"import smtplib\" 2>nul")
        if result != 0:
            print("  ⚠️  Some dependencies missing")
            print("  ✓ Solution: Run 'pip install colorama flask psutil'")
            input("  Press Enter to continue...")
            return

        print("  ✓ All dependencies OK")

        # Check file
        if not os.path.isfile("superpilot.py"):
            print("  ❌ superpilot.py not found!")
            print("  ✓ Solution: Make sure you're in the unified-mailer folder")
            input("  Press Enter to continue...")
            return

        print("  ✓ superpilot.py found")

        print("\n  ✅ Everything looks OK!")
        print("  Did you provide an SMTP list file?")
        print("  Example: python3 superpilot.py smtps.txt")
        input("  Press Enter to continue...")

    def troubleshoot_smtp(self):
        """SMTP connection issues"""
        self.clear_screen()
        self.print_header("🔧 CAN'T CONNECT TO SMTP")

        print("Common causes & fixes:\n")
        print("  1. WRONG PORT")
        print("     • Try 587 (TLS)")
        print("     • Or try 465 (SSL)")
        print("     • Or try 25 (plain)\n")

        print("  2. WRONG CREDENTIALS")
        print("     • Verify email address")
        print("     • Verify password/app-password")
        print("     • Gmail needs app password (not regular)\n")

        print("  3. FIREWALL/SECURITY")
        print("     • Check firewall allows SMTP")
        print("     • Check antivirus not blocking\n")

        print("  4. ACCOUNT SUSPENDED")
        print("     • Check email is not suspended")
        print("     • Try logging in via web browser\n")

        print("  5. RATE LIMITED")
        print("     • Wait a few minutes")
        print("     • Try again with fewer threads")

        input("\n  Press Enter to continue...")

    def troubleshoot_imap(self):
        """IMAP connection issues"""
        self.clear_screen()
        self.print_header("🔧 CAN'T CONNECT TO IMAP")

        print("Common causes & fixes:\n")

        print("  1. IMAP NOT ENABLED")
        print("     • Gmail: Enable IMAP in Settings")
        print("     • Outlook: May need app password")
        print("     • Yahoo: Check account settings\n")

        print("  2. WRONG CREDENTIALS")
        print("     • Verify password/app-password")
        print("     • Gmail needs app password\n")

        print("  3. FIREWALL BLOCKING")
        print("     • Check port 993 (IMAP-SSL) is open")
        print("     • Check firewall rules\n")

        print("  4. ACCOUNT ISSUE")
        print("     • Try logging in via web")
        print("     • Check account isn't suspended")

        input("\n  Press Enter to continue...")

    def troubleshoot_gmail_creds(self):
        """Gmail credentials"""
        self.clear_screen()
        self.print_header("🔧 GMAIL - INVALID CREDENTIALS")

        print("Gmail requires APP PASSWORD (not regular password)\n")
        print("Steps:\n")
        print("  1. Go to: myaccount.google.com/security")
        print("  2. Enable 2-Step Verification (if not already on)")
        print("  3. Go to: myaccount.google.com/apppasswords")
        print("  4. Select: Mail → Windows PC")
        print("  5. Click Generate")
        print("  6. Copy the 16-character password")
        print("  7. Use that password in SuperPilot\n")

        print("Important:")
        print("  • Use the 16-char password (not your regular password)")
        print("  • Ignore spaces in the password")
        print("  • Don't share this password")

        input("\n  Press Enter to continue...")

    def troubleshoot_outlook_creds(self):
        """Outlook credentials"""
        self.clear_screen()
        self.print_header("🔧 OUTLOOK - INVALID CREDENTIALS")

        print("Outlook usually works with regular password\n")
        print("Try these:\n")
        print("  1. Use REGULAR password (not app password)")
        print("  2. Make sure account is NOT suspended")
        print("  3. Try logging in via web first")
        print("  4. If 2FA enabled, might need app password")
        print("  5. Try different port (587 or 465)")

        input("\n  Press Enter to continue...")

    def troubleshoot_slow(self):
        """Want faster"""
        self.clear_screen()
        self.print_header("🔧 MAKE IT FASTER")

        print("How to speed up testing:\n")
        print("  1. INCREASE THREADS")
        print("     • Default: 10 threads")
        print("     • Faster: 15-20 threads")
        print("     • Command: --threads 20\n")

        print("  2. REDUCE WARMUP")
        print("     • Default: 30 seconds")
        print("     • Faster: 5-10 seconds")
        print("     • Command: --warmup 10\n")

        print("  3. FEWER ITERATIONS")
        print("     • Default: 5 iterations")
        print("     • Faster: 1-2 iterations")
        print("     • Command: --iterations 1\n")

        print("  FASTEST: python3 superpilot.py file.txt")
        print("           --threads 20 --warmup 5 --iterations 1")

        input("\n  Press Enter to continue...")

    def troubleshoot_fast(self):
        """Want slower/safer"""
        self.clear_screen()
        self.print_header("🔧 MAKE IT SLOWER (SAFER)")

        print("How to avoid rate limiting/bans:\n")
        print("  1. REDUCE THREADS")
        print("     • Default: 10 threads")
        print("     • Safer: 3-5 threads")
        print("     • Command: --threads 3\n")

        print("  2. INCREASE WARMUP")
        print("     • Default: 30 seconds")
        print("     • Safer: 60-120 seconds")
        print("     • Command: --warmup 120\n")

        print("  3. MORE ITERATIONS")
        print("     • Default: 5 iterations")
        print("     • Safer: 10-20 iterations")
        print("     • Command: --iterations 10\n")

        print("  SAFEST: python3 superpilot.py file.txt")
        print("          --threads 3 --warmup 120 --iterations 10")

        input("\n  Press Enter to continue...")

    def troubleshoot_unknown(self):
        """Not sure"""
        self.clear_screen()
        self.print_header("❓ TROUBLESHOOTING WIZARD")

        print("Let me ask some questions:\n")

        print("1. What tool are you using?")
        options = ["SuperPilot", "Format Converter", "Deliverability Checker", "Not sure"]
        self.print_menu(options)
        tool = self.get_choice(len(options))

        print("\n2. What's the error message? (type it or press Enter for no message)")
        error = input("  > ").strip()

        print("\n3. What did you try to do?")
        print("     a) Test SMTP accounts")
        print("     b) Convert credential file")
        print("     c) Check if email works")
        print("     d) Something else")
        action = self.get_choice(4)

        print("\n📋 Summary of your issue:")
        print(f"  Tool: {['SuperPilot', 'Converter', 'Deliverability', 'Unknown'][tool-1]}")
        print(f"  Action: {['Test SMTP', 'Convert', 'Check email', 'Other'][action-1]}")
        if error:
            print(f"  Error: {error}")

        print("\n💡 Recommendations:")
        print("  1. Check file path is correct")
        print("  2. Make sure file has correct format")
        print("  3. Verify credentials are correct")
        print("  4. Try single account first")
        print("  5. Check Python version: python3 --version")
        print("  6. Check dependencies installed")

        input("\n  Press Enter to continue...")

    def config_menu(self):
        """Configuration"""
        self.clear_screen()
        self.print_header("⚙️  SETUP & CONFIGURATION")

        print("What do you need help with?\n")
        options = [
            "Install Dependencies",
            "Create SMTP List File",
            "Setup Gmail App Password",
            "Setup Outlook App Password",
            "Setup Yahoo App Password",
            "Setup Custom IMAP Server",
            "Check System Status",
            "Back to Main Menu"
        ]
        self.print_menu(options)

        choice = self.get_choice(len(options))

        if choice == 1:
            self.install_dependencies()
        elif choice == 2:
            self.create_smtp_file()
        elif choice == 3:
            print("\n  Go to: myaccount.google.com/security")
            print("  Enable 2-Step Verification")
            print("  Go to: myaccount.google.com/apppasswords")
            print("  Select Mail → Windows PC")
            print("  Copy the 16-character password")
        elif choice == 4:
            print("\n  Outlook usually works with regular password")
            print("  If 2FA enabled, might need app password")
            print("  Check account.microsoft.com/security")
        elif choice == 5:
            print("\n  Go to: account.yahoo.com")
            print("  Click Account Security")
            print("  Generate App Password")
            print("  Copy password")
        elif choice == 6:
            print("\n  Get IMAP/SMTP from your email provider")
            print("  Usually in email settings/security")
        elif choice == 7:
            self.check_status()

        if choice < 7:
            input("\n  Press Enter to continue...")

    def install_dependencies(self):
        """Install dependencies"""
        self.clear_screen()
        self.print_header("📦 INSTALL DEPENDENCIES")

        print("Installing required packages...\n")

        packages = ["colorama", "flask", "psutil", "requests", "dnspython"]

        for pkg in packages:
            print(f"  Installing {pkg}...", end="", flush=True)
            result = os.system(f"python3 -m pip install {pkg} -q")
            if result == 0:
                print(" ✓")
            else:
                print(" ❌")

        print("\n  ✅ Installation complete!")

    def create_smtp_file(self):
        """Create SMTP list"""
        self.clear_screen()
        self.print_header("📝 CREATE SMTP LIST FILE")

        filename = input("  Filename (default: smtps.txt): ").strip() or "smtps.txt"

        print("  Format: host:port:user:password")
        print("  Example: smtp.gmail.com:587:user@gmail.com:apppass")
        print("  (Press Ctrl+D when done on Linux/Mac, or Ctrl+Z then Enter on Windows)\n")

        lines = []
        print("  Enter credentials (one per line):")
        while True:
            try:
                line = input("  > ").strip()
                if line:
                    lines.append(line)
            except EOFError:
                break

        if lines:
            with open(filename, 'w') as f:
                f.write('\n'.join(lines))
            print(f"\n  ✓ Saved {len(lines)} entries to {filename}")
        else:
            print("  No entries added")

    def check_status(self):
        """Check system status"""
        self.clear_screen()
        self.print_header("✅ SYSTEM STATUS")

        print("Checking system...\n")

        # Python
        result = os.system("python3 --version")
        if result == 0:
            print("  ✓ Python 3 installed\n")
        else:
            print("  ❌ Python 3 NOT found\n")

        # Files
        files = ["superpilot.py", "autopilot.py", "format_converter.py", "multi_deliverability.py"]
        print("  Files:")
        for f in files:
            if os.path.isfile(f):
                print(f"    ✓ {f}")
            else:
                print(f"    ❌ {f} missing")

        print()


def main():
    """Start wizard"""
    try:
        Wizard()
    except KeyboardInterrupt:
        print("\n\nExit (Ctrl+C)\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
