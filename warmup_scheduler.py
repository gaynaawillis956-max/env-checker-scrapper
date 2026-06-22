#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Warmup Scheduler - Gradually Warm Up SMTP Accounts
Build sender reputation before large campaigns
"""
import json
import os
from datetime import datetime, timedelta

class WarmupScheduler:
    """Manage SMTP account warmup schedules"""

    def __init__(self):
        self.warmup_file = "warmup_schedule.json"
        self.schedule = self.load_schedule()

    def load_schedule(self) -> dict:
        """Load warmup schedule"""
        if os.path.isfile(self.warmup_file):
            try:
                with open(self.warmup_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {'accounts': {}}
        return {'accounts': {}}

    def save_schedule(self):
        """Save schedule"""
        with open(self.warmup_file, 'w', encoding='utf-8') as f:
            json.dump(self.schedule, f, indent=2, ensure_ascii=False)

    def create_warmup_plan(self, smtp_account: str, days: int = 14) -> dict:
        """Create warmup plan for account"""
        if 'accounts' not in self.schedule:
            self.schedule['accounts'] = {}

        plan = {
            'account': smtp_account,
            'started': datetime.now().isoformat(),
            'days': days,
            'stages': self._generate_stages(days),
            'current_stage': 0,
            'emails_sent': 0,
            'status': 'warmup'
        }

        self.schedule['accounts'][smtp_account] = plan
        self.save_schedule()
        return plan

    def _generate_stages(self, days: int) -> list:
        """Generate warmup stages"""
        # Typical warmup: gradually increase daily volume
        stages = []
        start_date = datetime.now()

        stage_configs = [
            {'day': 1, 'emails_per_day': 10, 'description': 'Day 1: Send 10 emails (test)'},
            {'day': 2, 'emails_per_day': 25, 'description': 'Day 2: Send 25 emails'},
            {'day': 3, 'emails_per_day': 50, 'description': 'Day 3: Send 50 emails'},
            {'day': 4, 'emails_per_day': 100, 'description': 'Day 4: Send 100 emails'},
            {'day': 5, 'emails_per_day': 150, 'description': 'Day 5: Send 150 emails'},
            {'day': 6, 'emails_per_day': 250, 'description': 'Day 6: Send 250 emails'},
            {'day': 7, 'emails_per_day': 500, 'description': 'Week 1 complete: Send 500 emails'},
            {'day': 8, 'emails_per_day': 750, 'description': 'Day 8: Send 750 emails'},
            {'day': 9, 'emails_per_day': 1000, 'description': 'Day 9: Send 1000 emails'},
            {'day': 10, 'emails_per_day': 1500, 'description': 'Day 10: Send 1500 emails'},
            {'day': 11, 'emails_per_day': 2000, 'description': 'Day 11: Send 2000 emails'},
            {'day': 12, 'emails_per_day': 3000, 'description': 'Day 12: Send 3000 emails'},
            {'day': 13, 'emails_per_day': 5000, 'description': 'Day 13: Send 5000 emails'},
            {'day': 14, 'emails_per_day': 10000, 'description': 'Day 14 (Ready): Send 10,000+ emails'},
        ]

        for config in stage_configs:
            if config['day'] <= days:
                stage_date = start_date + timedelta(days=config['day'] - 1)
                stages.append({
                    'day': config['day'],
                    'date': stage_date.strftime('%Y-%m-%d'),
                    'emails_per_day': config['emails_per_day'],
                    'description': config['description'],
                    'status': 'pending'
                })

        return stages

    def get_current_stage(self, smtp_account: str) -> dict:
        """Get current warmup stage"""
        if smtp_account not in self.schedule.get('accounts', {}):
            return None

        plan = self.schedule['accounts'][smtp_account]
        current = plan['stages'][plan['current_stage']]
        return {
            'stage': plan['current_stage'] + 1,
            'date': current['date'],
            'daily_limit': current['emails_per_day'],
            'description': current['description'],
            'emails_sent_today': plan['emails_sent'],
            'ready_for_next': plan['emails_sent'] >= current['emails_per_day']
        }

    def should_send(self, smtp_account: str) -> tuple:
        """Check if account is ready to send"""
        if smtp_account not in self.schedule.get('accounts', {}):
            return True, "Not in warmup"  # Not warmed up, but can send anyway

        plan = self.schedule['accounts'][smtp_account]
        if plan['status'] != 'warmup':
            return True, "Warmup complete"

        current_stage = plan['stages'][plan['current_stage']]
        today = datetime.now().strftime('%Y-%m-%d')

        if current_stage['date'] > today:
            return False, f"Not ready until {current_stage['date']}"

        if plan['emails_sent'] >= current_stage['emails_per_day']:
            # Move to next stage
            if plan['current_stage'] + 1 < len(plan['stages']):
                plan['current_stage'] += 1
                plan['emails_sent'] = 0
                self.save_schedule()
                return True, f"Stage {plan['current_stage'] + 1} started"
            else:
                plan['status'] = 'complete'
                self.save_schedule()
                return True, "Warmup complete - ready for full campaigns!"

        return True, f"{current_stage['emails_per_day'] - plan['emails_sent']} emails left in stage"

    def record_send(self, smtp_account: str):
        """Record email sent"""
        if smtp_account in self.schedule.get('accounts', {}):
            self.schedule['accounts'][smtp_account]['emails_sent'] += 1
            self.save_schedule()

    def list_accounts(self) -> list:
        """List all warmup accounts"""
        result = []
        for account, plan in self.schedule.get('accounts', {}).items():
            current = plan['stages'][plan['current_stage']]
            result.append({
                'account': account,
                'stage': plan['current_stage'] + 1,
                'total_stages': len(plan['stages']),
                'status': plan['status'],
                'emails_sent_today': plan['emails_sent'],
                'daily_limit': current['emails_per_day']
            })
        return result

    def get_recommendations(self) -> str:
        """Get warmup recommendations"""
        text = """
╔══════════════════════════════════════════════════════════════════╗
║           📈 EMAIL WARMUP SCHEDULE - BEST PRACTICES              ║
╚══════════════════════════════════════════════════════════════════╝

NEW ACCOUNT WARMUP (14 Days)
──────────────────────────────────────────────────────────────────

Day 1-3:    Light sending (10-50 emails/day)
            • Test with small list
            • Check for bounces/spam
            • Low volume signals "human" sender

Day 4-7:    Moderate sending (100-500 emails/day)
            • Build reputation
            • Monitor delivery rate
            • Check inbox vs spam ratio

Day 8-10:   Heavier sending (750-1500 emails/day)
            • Good reputation developing
            • Most accounts ready now
            • Continue monitoring

Day 11-14:  Full sending (2000-10000 emails/day)
            • Account fully warmed
            • Ready for large campaigns
            • Can send high volumes

WHY WARMUP?
──────────────────────────────────────────────────────────────────

New SMTP accounts have:
  ❌ No sender history
  ❌ No reputation with ISPs
  ❌ Higher spam filter scores
  ❌ Lower inbox delivery rate

Warmup fixes this:
  ✅ Builds sender reputation over time
  ✅ ISPs recognize as legitimate sender
  ✅ Establishes sending patterns
  ✅ Improves inbox delivery rate (90%+)

WARM UP BENEFITS
──────────────────────────────────────────────────────────────────

Before warmup:  30-50% inbox delivery rate ❌
After warmup:   90%+ inbox delivery rate ✅

Time investment: 2 weeks
Reputation gain: 6-12 months

DURING WARMUP
──────────────────────────────────────────────────────────────────

DO:
  ✅ Send to engaged recipients
  ✅ Use varied subject lines (3-5)
  ✅ Use varied content (3-5 versions)
  ✅ Monitor bounce rate (<5% is good)
  ✅ Monitor spam complaints (<0.1%)
  ✅ Send consistently daily

DON'T:
  ❌ Send to cold lists
  ❌ Use aggressive subject lines
  ❌ Overload with links/images
  ❌ Send to spam traps
  ❌ Skip days (be consistent)
  ❌ Jump to 10k emails on day 1

MULTI-ACCOUNT WARMUP
──────────────────────────────────────────────────────────────────

Have 5 accounts?
  Day 1:  Account #1: 10 emails
  Day 2:  Account #1: 25 emails   Account #2: 10 emails
  Day 3:  Account #1: 50 emails   Account #2: 25 emails   Acct #3: 10
  ...continue staggered

Result: Staggered warmup = full campaign in ~3 weeks

AFTER WARMUP
──────────────────────────────────────────────────────────────────

Account is ready for:
  • Large campaigns (10,000+ emails/day)
  • Multiple sends per day
  • Bulk mailing

But continue best practices:
  • Rotate subjects/content
  • Monitor bounce rate
  • Watch complaint rate
  • Maintain warm reputation

RECOMMENDED WARMUP PARAMETERS
──────────────────────────────────────────────────────────────────

Recipients:     Warm, engaged list (NOT cold list)
Content:        Professional, not spammy
Frequency:      Once per day (consistent)
Subject lines:  Rotate 3-5 variations
Email body:     Rotate 2-3 versions
Links:          Keep minimal (1-2 max)
Images:         Text-heavy (80% text, 20% images)

TRACKING WARMUP
──────────────────────────────────────────────────────────────────

Monitor daily:
  • Bounce rate (should be <5%)
  • Spam rate (should be <0.1%)
  • Inbox delivery (should increase daily)
  • Complaint rate (watch for issues)

Use delivery_monitor.py to check:
  python3 delivery_monitor.py
  Enter test accounts to see inbox vs spam

TROUBLESHOOTING DURING WARMUP
──────────────────────────────────────────────────────────────────

High bounce rate (>5%)?
  • Check recipient list quality
  • Use verified/engaged list
  • Remove bounces before next send

Many emails in spam?
  • Change subject lines
  • Reduce aggressive language
  • Add unsubscribe link
  • Reduce number of links

Getting blocked?
  • Slow down sending
  • Reduce daily volume
  • Use different SMTP (rotate accounts)
  • Contact ISP if persists
"""
        return text


def interactive_menu():
    """Interactive warmup scheduler"""
    scheduler = WarmupScheduler()

    while True:
        print("\n" + "="*70)
        print("  📈 WARMUP SCHEDULER - Build SMTP Reputation")
        print("="*70)
        print("\n  What do you want to do?\n")
        print("  [1] Create warmup plan for account")
        print("  [2] View warmup schedule")
        print("  [3] Check current stage")
        print("  [4] View all accounts")
        print("  [5] View warmup guide")
        print("  [6] Exit")
        print()

        choice = input("  → Choose (1-6): ").strip()

        if choice == "1":
            smtp = input("\n  SMTP account (host:port:user:pass): ").strip()
            days = int(input("  Warmup days (default 14): ").strip() or "14")
            plan = scheduler.create_warmup_plan(smtp, days)
            print(f"\n  ✓ Warmup plan created!")
            print(f"    Duration: {days} days")
            print(f"    Stages: {len(plan['stages'])}")

        elif choice == "2":
            smtp = input("\n  SMTP account: ").strip()
            if smtp in scheduler.schedule.get('accounts', {}):
                plan = scheduler.schedule['accounts'][smtp]
                print(f"\n  Warmup Schedule for: {smtp}\n")
                for i, stage in enumerate(plan['stages'], 1):
                    status = "✅" if i <= plan['current_stage'] + 1 else "⏳"
                    print(f"  {status} {stage['description']}")
                    print(f"      Date: {stage['date']}")
                    print(f"      Daily limit: {stage['emails_per_day']}")
            else:
                print("\n  ❌ Account not found")

        elif choice == "3":
            smtp = input("\n  SMTP account: ").strip()
            ready, msg = scheduler.should_send(smtp)
            current = scheduler.get_current_stage(smtp)
            if current:
                print(f"\n  Status: {msg}")
                print(f"  Stage: {current['stage']}")
                print(f"  Date: {current['date']}")
                print(f"  Daily limit: {current['daily_limit']} emails")
                print(f"  Sent today: {current['emails_sent_today']}")
                print(f"  Ready to send: {'YES ✅' if ready else 'NO ⏳'}")

        elif choice == "4":
            print()
            accounts = scheduler.list_accounts()
            if accounts:
                print("  All Warmup Accounts:\n")
                for acc in accounts:
                    status = "✅" if acc['status'] == 'complete' else f"Stage {acc['stage']}/{acc['total_stages']}"
                    print(f"  {acc['account']}")
                    print(f"    Status: {status}")
                    print(f"    Sent today: {acc['emails_sent_today']}/{acc['daily_limit']}")
                    print()
            else:
                print("  No accounts in warmup")

        elif choice == "5":
            print(scheduler.get_recommendations())

        elif choice == "6":
            print("\n  Goodbye!\n")
            break

        else:
            print("  ❌ Invalid choice")


if __name__ == "__main__":
    interactive_menu()
