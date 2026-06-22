#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Format Converter - Automatically detect and convert credential formats
Supports: email:pass, smtp:pass, host:port:user:pass, combos, mixed formats
"""
import re
from typing import List, Dict, Tuple

class FormatConverter:
    """Detect and convert various credential formats"""

    COMMON_SMTP_HOSTS = {
        'gmail': ('smtp.gmail.com', 587),
        'outlook': ('smtp-mail.outlook.com', 587),
        'hotmail': ('smtp-mail.outlook.com', 587),
        'yahoo': ('smtp.mail.yahoo.com', 465),
        'aol': ('smtp.aol.com', 465),
        'icloud': ('smtp.mail.icloud.com', 587),
        'protonmail': ('smtp.protonmail.com', 587),
        'zoho': ('smtp.zoho.com', 465),
        'sendgrid': ('smtp.sendgrid.net', 587),
        'mailgun': ('smtp.mailgun.org', 587),
    }

    @staticmethod
    def detect_format(line: str) -> Tuple[str, Dict]:
        """
        Detect credential format and return (format_type, parsed_data)

        Returns:
            Tuple of (format_name, dict with parsed data)
        """
        line = line.strip()

        # Format 1: host:port:user:pass (SMTP)
        if line.count(':') == 3:
            parts = line.split(':')
            if parts[1].isdigit():
                return 'smtp_full', {
                    'host': parts[0],
                    'port': int(parts[1]),
                    'user': parts[2],
                    'pass': parts[3],
                    'original': line
                }

        # Format 2: email:password
        if line.count(':') == 1:
            email, password = line.split(':')
            if '@' in email:
                domain = email.split('@')[1]
                return 'email_pass', {
                    'email': email,
                    'pass': password,
                    'domain': domain,
                    'original': line
                }
            # Could be username:pass for known domains
            else:
                return 'user_pass', {
                    'user': email,
                    'pass': password,
                    'original': line
                }

        # Format 3: smtp_host:password
        if line.count(':') == 1 and 'smtp' in line.lower():
            parts = line.split(':')
            return 'smtp_pass', {
                'host': parts[0],
                'pass': parts[1],
                'original': line
            }

        # Format 4: Just email
        if '@' in line and ':' not in line:
            return 'email_only', {
                'email': line,
                'original': line
            }

        return 'unknown', {'original': line}

    @staticmethod
    def convert_to_smtp(line: str, fallback_port: int = 587) -> Dict:
        """
        Convert any format to standard SMTP format
        host:port:user:pass
        """
        format_type, data = FormatConverter.detect_format(line)

        # Already in correct format
        if format_type == 'smtp_full':
            return data

        # Email:password - guess SMTP server
        elif format_type == 'email_pass':
            email = data['email']
            domain = data['domain']
            password = data['pass']

            # Try to find SMTP server from domain
            for key, (smtp_host, smtp_port) in FormatConverter.COMMON_SMTP_HOSTS.items():
                if key.lower() in domain.lower():
                    return {
                        'host': smtp_host,
                        'port': smtp_port,
                        'user': email,
                        'pass': password,
                        'format_detected': 'email:pass',
                        'original': line
                    }

            # If not found, use generic SMTP settings
            return {
                'host': f'smtp.{domain}',
                'port': fallback_port,
                'user': email,
                'pass': password,
                'format_detected': 'email:pass (guessed)',
                'original': line
            }

        # SMTP host:password
        elif format_type == 'smtp_pass':
            return {
                'host': data['host'],
                'port': fallback_port,
                'user': 'unknown',
                'pass': data['pass'],
                'format_detected': 'smtp:pass',
                'original': line,
                'warning': 'Username unknown - may fail'
            }

        # Username:password (needs more info)
        elif format_type == 'user_pass':
            return {
                'host': 'smtp.unknown.com',
                'port': fallback_port,
                'user': data['user'],
                'pass': data['pass'],
                'format_detected': 'user:pass',
                'original': line,
                'warning': 'Domain unknown - may fail'
            }

        # Just email
        elif format_type == 'email_only':
            return {
                'host': 'smtp.unknown.com',
                'port': fallback_port,
                'user': data['email'],
                'pass': 'unknown',
                'format_detected': 'email_only',
                'original': line,
                'warning': 'Password unknown - will fail'
            }

        return {'error': 'Unknown format', 'original': line}

    @staticmethod
    def convert_file(input_file: str, fallback_port: int = 587) -> List[Dict]:
        """
        Convert entire file to SMTP format
        Returns list of SMTP credentials
        """
        results = []
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                converted = FormatConverter.convert_to_smtp(line, fallback_port)
                if 'error' not in converted:
                    results.append(converted)

        return results

    @staticmethod
    def print_detection_stats(input_file: str) -> Dict:
        """Print format detection statistics"""
        stats = {
            'smtp_full': 0,
            'email_pass': 0,
            'smtp_pass': 0,
            'user_pass': 0,
            'email_only': 0,
            'unknown': 0,
            'total': 0,
            'with_warnings': 0
        }

        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                format_type, _ = FormatConverter.detect_format(line)
                stats[format_type] += 1
                stats['total'] += 1

        return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Credential Format Converter")
    parser.add_argument("input_file", help="Input credentials file")
    parser.add_argument("--output", help="Output file (optional)")
    parser.add_argument("--detect", action="store_true", help="Just detect format")
    parser.add_argument("--port", type=int, default=587, help="Default SMTP port")

    args = parser.parse_args()

    # Detect formats
    if args.detect:
        print(f"\n[*] Analyzing {args.input_file}...\n")
        stats = FormatConverter.print_detection_stats(args.input_file)

        print(f"Format Detection Results:")
        print(f"  SMTP (host:port:user:pass):  {stats['smtp_full']}")
        print(f"  Email:Password:              {stats['email_pass']}")
        print(f"  SMTP:Password:               {stats['smtp_pass']}")
        print(f"  User:Password:               {stats['user_pass']}")
        print(f"  Email Only:                  {stats['email_only']}")
        print(f"  Unknown:                     {stats['unknown']}")
        print(f"  Total:                       {stats['total']}\n")
        return

    # Convert formats
    print(f"\n[*] Converting {args.input_file}...\n")
    converted = FormatConverter.convert_file(args.input_file, args.port)

    print(f"✓ Converted {len(converted)} credentials\n")

    # Show first few
    for i, cred in enumerate(converted[:3]):
        print(f"  [{i+1}] {cred['host']}:{cred['port']}")
        print(f"      User: {cred['user']}")
        if cred.get('warning'):
            print(f"      ⚠ {cred['warning']}")

    if len(converted) > 3:
        print(f"  ... and {len(converted) - 3} more\n")

    # Save output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            for cred in converted:
                f.write(f"{cred['host']}:{cred['port']}:{cred['user']}:{cred['pass']}\n")
        print(f"✓ Saved to: {args.output}\n")


if __name__ == "__main__":
    main()
