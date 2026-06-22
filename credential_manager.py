#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Secure Credential Manager
Save passwords once, use forever without re-entering
Simple encryption for local storage
"""
import json
import os
import base64
from datetime import datetime
from pathlib import Path

class CredentialManager:
    """Manage saved credentials securely"""

    def __init__(self):
        self.cred_file = "saved_credentials.json"
        self.credentials = self.load_credentials()
        self.key = self.get_simple_key()

    def get_simple_key(self) -> str:
        """Simple obfuscation key (not cryptographically secure, just basic)"""
        return "unified_mailer_2026"

    def simple_encrypt(self, text: str) -> str:
        """Basic encryption for local storage"""
        try:
            # Simple XOR-based encryption
            result = []
            for i, char in enumerate(text):
                key_char = self.key[i % len(self.key)]
                encrypted = chr(ord(char) ^ ord(key_char))
                result.append(encrypted)
            # Encode to base64 for safe storage
            encrypted_bytes = ''.join(result).encode()
            encoded = base64.b64encode(encrypted_bytes).decode()
            return encoded
        except:
            return text

    def simple_decrypt(self, encrypted: str) -> str:
        """Basic decryption"""
        try:
            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted.encode())
            encrypted_text = encrypted_bytes.decode()
            # Simple XOR-based decryption
            result = []
            for i, char in enumerate(encrypted_text):
                key_char = self.key[i % len(self.key)]
                decrypted = chr(ord(char) ^ ord(key_char))
                result.append(decrypted)
            return ''.join(result)
        except:
            return encrypted

    def load_credentials(self) -> dict:
        """Load saved credentials"""
        if os.path.isfile(self.cred_file):
            try:
                with open(self.cred_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_credentials(self):
        """Save credentials to file"""
        with open(self.cred_file, 'w') as f:
            json.dump(self.credentials, f, indent=2)

    def add_credential(self, email: str, password: str,
                      provider: str = "custom", name: str = "") -> bool:
        """Save a credential"""
        if not email or not password:
            return False

        # Extract provider from email if not provided
        if provider == "custom" and "@" in email:
            domain = email.split("@")[1]
            if "gmail" in domain:
                provider = "Gmail"
            elif "outlook" in domain or "hotmail" in domain:
                provider = "Outlook"
            elif "yahoo" in domain:
                provider = "Yahoo"

        # Encrypt password
        encrypted_password = self.simple_encrypt(password)

        # Save
        self.credentials[email] = {
            "email": email,
            "password": encrypted_password,  # Encrypted
            "provider": provider,
            "name": name or email.split("@")[0],
            "saved_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_used": None
        }

        self.save_credentials()
        return True

    def get_credential(self, email: str) -> dict:
        """Get and decrypt credential"""
        if email not in self.credentials:
            return None

        cred = self.credentials[email].copy()
        # Decrypt password
        cred["password"] = self.simple_decrypt(cred["password"])
        # Update last used
        cred["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.credentials[email] = cred
        self.save_credentials()
        return cred

    def list_credentials(self) -> list:
        """List all saved credentials (passwords hidden)"""
        result = []
        for email, data in self.credentials.items():
            result.append({
                "email": email,
                "provider": data.get("provider", "Unknown"),
                "name": data.get("name", ""),
                "saved": data.get("saved_date", ""),
                "last_used": data.get("last_used", "Never")
            })
        return sorted(result, key=lambda x: x["last_used"], reverse=True)

    def delete_credential(self, email: str) -> bool:
        """Delete a saved credential"""
        if email in self.credentials:
            del self.credentials[email]
            self.save_credentials()
            return True
        return False

    def export_smtp_list(self, filename: str = "my_smtp_list.txt") -> bool:
        """Export all saved credentials as SMTP list"""
        if not self.credentials:
            return False

        with open(filename, 'w') as f:
            for email, data in self.credentials.items():
                password = self.simple_decrypt(data["password"])
                # Guess SMTP server from provider
                provider = data.get("provider", "custom")
                host = self.get_smtp_host(provider)
                port = self.get_smtp_port(provider)
                f.write(f"{host}:{port}:{email}:{password}\n")
        return True

    @staticmethod
    def get_smtp_host(provider: str) -> str:
        """Get SMTP host for provider"""
        hosts = {
            "Gmail": "smtp.gmail.com",
            "Outlook": "smtp-mail.outlook.com",
            "Hotmail": "smtp-mail.outlook.com",
            "Yahoo": "smtp.mail.yahoo.com",
            "AOL": "smtp.aol.com",
            "ProtonMail": "smtp.protonmail.com",
            "Zoho": "smtp.zoho.com",
            "iCloud": "smtp.mail.icloud.com"
        }
        return hosts.get(provider, "smtp.unknown.com")

    @staticmethod
    def get_smtp_port(provider: str) -> int:
        """Get SMTP port for provider"""
        ports = {
            "Gmail": 587,
            "Outlook": 587,
            "Hotmail": 587,
            "Yahoo": 465,
            "AOL": 465,
            "ProtonMail": 587,
            "Zoho": 465,
            "iCloud": 587
        }
        return ports.get(provider, 587)


def interactive_menu():
    """Interactive credential manager menu"""
    manager = CredentialManager()

    while True:
        print("\n" + "="*60)
        print("  📝 CREDENTIAL MANAGER")
        print("="*60)
        print("\n  What do you want to do?\n")
        print("  [1] Add new credential (save password)")
        print("  [2] List saved credentials")
        print("  [3] Get credential (reveal password)")
        print("  [4] Delete credential")
        print("  [5] Export as SMTP list")
        print("  [6] Exit")
        print()

        choice = input("  → Choose (1-6): ").strip()

        if choice == "1":
            print()
            email = input("  Email address: ").strip()
            password = input("  Password/App-password: ").strip()
            provider = input("  Provider (Gmail/Outlook/Yahoo, or press Enter for auto): ").strip() or "custom"
            name = input("  Nickname (optional, press Enter to skip): ").strip()

            if manager.add_credential(email, password, provider, name):
                print("\n  ✓ Credential saved securely!")
            else:
                print("\n  ❌ Failed to save")

        elif choice == "2":
            print()
            creds = manager.list_credentials()
            if creds:
                print("  Saved Credentials (passwords hidden):\n")
                for i, cred in enumerate(creds, 1):
                    print(f"  [{i}] {cred['email']}")
                    print(f"      Provider: {cred['provider']}")
                    print(f"      Name: {cred['name']}")
                    print(f"      Saved: {cred['saved']}")
                    print(f"      Last used: {cred['last_used']}")
                    print()
            else:
                print("  No credentials saved yet")

        elif choice == "3":
            print()
            email = input("  Email to retrieve: ").strip()
            cred = manager.get_credential(email)
            if cred:
                print(f"\n  ✓ Email: {cred['email']}")
                print(f"    Password: {cred['password']}")
                print(f"    Provider: {cred['provider']}")
            else:
                print("  ❌ Credential not found")

        elif choice == "4":
            print()
            email = input("  Email to delete: ").strip()
            if manager.delete_credential(email):
                print("  ✓ Credential deleted")
            else:
                print("  ❌ Credential not found")

        elif choice == "5":
            filename = input("\n  Save as (default: my_smtp_list.txt): ").strip() or "my_smtp_list.txt"
            if manager.export_smtp_list(filename):
                print(f"  ✓ Exported to: {filename}")
            else:
                print("  ❌ No credentials to export")

        elif choice == "6":
            print("\n  Goodbye!\n")
            break

        else:
            print("  ❌ Invalid choice")


def main():
    """CLI interface"""
    import argparse

    parser = argparse.ArgumentParser(description="Secure Credential Manager")
    parser.add_argument("--add", nargs=3, metavar=("EMAIL", "PASSWORD", "PROVIDER"),
                       help="Add credential")
    parser.add_argument("--list", action="store_true", help="List all credentials")
    parser.add_argument("--get", help="Get credential (reveal password)")
    parser.add_argument("--delete", help="Delete credential")
    parser.add_argument("--export", help="Export as SMTP list")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive menu")

    args = parser.parse_args()

    manager = CredentialManager()

    if args.interactive:
        interactive_menu()
        return

    if args.add:
        email, password, provider = args.add
        if manager.add_credential(email, password, provider):
            print(f"✓ Saved: {email}")
        else:
            print("❌ Failed")

    elif args.list:
        creds = manager.list_credentials()
        if creds:
            print("\nSaved Credentials:\n")
            for cred in creds:
                print(f"  {cred['email']} ({cred['provider']})")
                print(f"    Last used: {cred['last_used']}")
        else:
            print("No credentials saved")

    elif args.get:
        cred = manager.get_credential(args.get)
        if cred:
            print(f"Email: {cred['email']}")
            print(f"Password: {cred['password']}")
            print(f"Provider: {cred['provider']}")
        else:
            print("❌ Not found")

    elif args.delete:
        if manager.delete_credential(args.delete):
            print(f"✓ Deleted: {args.delete}")
        else:
            print("❌ Not found")

    elif args.export:
        if manager.export_smtp_list(args.export):
            print(f"✓ Exported to: {args.export}")
        else:
            print("❌ No credentials")

    else:
        # Default: interactive mode
        interactive_menu()


if __name__ == "__main__":
    main()
