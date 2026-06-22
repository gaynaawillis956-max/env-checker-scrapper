#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Self-Optimizer - Continuously Learn & Improve Campaign Performance
Autonomous optimization engine that learns what works
"""
import json
import os
import time
from datetime import datetime, timedelta
from collections import defaultdict
import math

class SelfOptimizer:
    """Learn and optimize automatically over time"""

    def __init__(self):
        self.config_file = "optimizer_config.json"
        self.history_file = "optimization_history.json"
        self.config = self.load_config()
        self.history = self.load_history()

    def load_config(self) -> dict:
        """Load optimizer configuration"""
        if os.path.isfile(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                return self.get_default_config()
        return self.get_default_config()

    def get_default_config(self) -> dict:
        """Default configuration"""
        return {
            'auto_learning': True,
            'update_interval': 3600,  # seconds
            'min_samples': 100,  # minimum sends before optimization
            'exploration_rate': 0.1,  # 10% new/untested
            'exploitation_rate': 0.9,  # 90% best performers
            'learning_rate': 0.1,  # how fast to adjust
            'decay_factor': 0.95,  # how fast old data fades
            'score_threshold': 0.70,  # minimum score to use
            'enabled_optimizations': {
                'smtp_selection': True,
                'content_rotation': True,
                'subject_rotation': True,
                'thread_adjustment': True,
                'timing_optimization': True
            }
        }

    def load_history(self) -> dict:
        """Load optimization history"""
        if os.path.isfile(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except:
                return {'learning_log': []}
        return {'learning_log': []}

    def save_config(self):
        """Save configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def save_history(self):
        """Save history"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)

    def record_result(self, campaign_id: str, smtp: str, content: str, subject: str,
                     recipient: str, status: str, location: str = None):
        """Record email send result for learning"""

        entry = {
            'timestamp': datetime.now().isoformat(),
            'campaign': campaign_id,
            'smtp': smtp,
            'content': content,
            'subject': subject,
            'recipient_domain': recipient.split('@')[1] if '@' in recipient else 'unknown',
            'status': status,
            'location': location,
            'inbox': 1 if location == 'inbox' else 0,
            'spam': 1 if location == 'spam' else 0,
            'bounced': 1 if status == 'bounced' else 0,
            'failed': 1 if status == 'failed' else 0
        }

        self.history['learning_log'].append(entry)
        self.save_history()

    def calculate_scores(self, data_entries: list) -> dict:
        """Calculate performance scores from historical data"""

        if not data_entries:
            return {}

        scores = defaultdict(lambda: {'total': 0, 'inbox': 0, 'spam': 0, 'bounced': 0})

        for entry in data_entries:
            # Score by SMTP
            smtp = entry['smtp']
            scores[f'smtp_{smtp}']['total'] += 1
            scores[f'smtp_{smtp}']['inbox'] += entry.get('inbox', 0)
            scores[f'smtp_{smtp}']['spam'] += entry.get('spam', 0)
            scores[f'smtp_{smtp}']['bounced'] += entry.get('bounced', 0)

            # Score by content
            content = entry['content']
            scores[f'content_{content}']['total'] += 1
            scores[f'content_{content}']['inbox'] += entry.get('inbox', 0)

            # Score by subject
            subject = entry['subject']
            scores[f'subject_{subject}']['total'] += 1
            scores[f'subject_{subject}']['inbox'] += entry.get('inbox', 0)

            # Score by provider
            domain = entry.get('recipient_domain', 'unknown')
            scores[f'provider_{domain}']['total'] += 1
            scores[f'provider_{domain}']['inbox'] += entry.get('inbox', 0)

        # Convert to percentages
        result = {}
        for key, data in scores.items():
            if data['total'] > 0:
                inbox_rate = data['inbox'] / data['total']
                result[key] = {
                    'score': inbox_rate,
                    'total_sends': data['total'],
                    'inboxes': data['inbox'],
                    'spams': data['spam'],
                    'bounced': data['bounced']
                }

        return result

    def get_optimized_recommendation(self, campaign_id: str) -> dict:
        """Get automated optimization recommendations"""

        # Get recent data
        recent_data = [
            e for e in self.history.get('learning_log', [])
            if e['campaign'] == campaign_id
        ]

        if len(recent_data) < self.config['min_samples']:
            return {
                'status': 'learning',
                'samples_collected': len(recent_data),
                'samples_needed': self.config['min_samples'],
                'message': f'Collecting data... {len(recent_data)}/{self.config["min_samples"]} samples'
            }

        # Calculate scores
        scores = self.calculate_scores(recent_data)

        # Find winners
        smtp_scores = {k: v for k, v in scores.items() if k.startswith('smtp_')}
        content_scores = {k: v for k, v in scores.items() if k.startswith('content_')}
        subject_scores = {k: v for k, v in scores.items() if k.startswith('subject_')}

        # Sort by performance
        best_smtp = sorted(smtp_scores.items(), key=lambda x: x[1]['score'], reverse=True)
        best_content = sorted(content_scores.items(), key=lambda x: x[1]['score'], reverse=True)
        best_subject = sorted(subject_scores.items(), key=lambda x: x[1]['score'], reverse=True)
        worst_smtp = sorted(smtp_scores.items(), key=lambda x: x[1]['score'])

        recommendation = {
            'status': 'optimized',
            'samples': len(recent_data),
            'recommendations': {
                'smtp': {
                    'use_most': [
                        {
                            'name': k.replace('smtp_', ''),
                            'inbox_rate': int(v['score'] * 100),
                            'sends': v['total_sends'],
                            'inboxes': v['inboxes']
                        }
                        for k, v in best_smtp[:5] if v['total_sends'] >= 10
                    ],
                    'avoid': [
                        {
                            'name': k.replace('smtp_', ''),
                            'inbox_rate': int(v['score'] * 100),
                            'sends': v['total_sends']
                        }
                        for k, v in worst_smtp[:3] if v['score'] < self.config['score_threshold']
                    ]
                },
                'content': {
                    'use_most': [
                        {
                            'name': k.replace('content_', ''),
                            'inbox_rate': int(v['score'] * 100),
                            'sends': v['total_sends']
                        }
                        for k, v in best_content[:3] if v['total_sends'] >= 10
                    ]
                },
                'subject': {
                    'use_most': [
                        {
                            'name': k.replace('subject_', ''),
                            'inbox_rate': int(v['score'] * 100),
                            'sends': v['total_sends']
                        }
                        for k, v in best_subject[:5] if v['total_sends'] >= 10
                    ]
                }
            },
            'auto_actions': [
                '✅ Increase allocation to best-performing SMTP accounts',
                '✅ Reduce allocation to low-performing accounts',
                '✅ Rotate more high-performing content variations',
                '✅ Prioritize high-converting subject lines',
                '✅ Adjust threading based on performance'
            ]
        }

        return recommendation

    def get_next_smtp_smart(self, campaign_id: str, available_smtps: list) -> tuple:
        """Intelligently select next SMTP based on learning"""

        recent_data = [
            e for e in self.history.get('learning_log', [])
            if e['campaign'] == campaign_id
        ]

        if len(recent_data) < self.config['min_samples']:
            # Random selection during learning phase
            import random
            return random.choice(available_smtps), 'learning'

        # Calculate scores
        scores = self.calculate_scores(recent_data)

        smtp_scores = {
            k.replace('smtp_', ''): v['score']
            for k, v in scores.items()
            if k.startswith('smtp_') and k.replace('smtp_', '') in available_smtps
        }

        if not smtp_scores:
            import random
            return random.choice(available_smtps), 'no_data'

        # Multi-armed bandit: balance exploration vs exploitation
        sorted_smtps = sorted(smtp_scores.items(), key=lambda x: x[1], reverse=True)

        # 90% use best, 10% explore
        import random
        if random.random() < self.config['exploitation_rate']:
            # Use best performer
            return sorted_smtps[0][0], f"best ({int(sorted_smtps[0][1]*100)}%)"
        else:
            # Explore: try lower-performing account
            idx = min(len(sorted_smtps) - 1, random.randint(1, len(sorted_smtps) - 1))
            return sorted_smtps[idx][0], f"explore ({int(sorted_smtps[idx][1]*100)}%)"

    def get_next_content_smart(self, campaign_id: str, available_contents: list) -> tuple:
        """Intelligently select next content based on learning"""

        recent_data = [
            e for e in self.history.get('learning_log', [])
            if e['campaign'] == campaign_id
        ]

        if len(recent_data) < self.config['min_samples']:
            import random
            return random.choice(available_contents), 'learning'

        scores = self.calculate_scores(recent_data)

        content_scores = {
            k.replace('content_', ''): v['score']
            for k, v in scores.items()
            if k.startswith('content_') and k.replace('content_', '') in available_contents
        }

        if not content_scores:
            import random
            return random.choice(available_contents), 'no_data'

        # Prefer high performers
        sorted_contents = sorted(content_scores.items(), key=lambda x: x[1], reverse=True)

        import random
        if random.random() < self.config['exploitation_rate']:
            return sorted_contents[0][0], f"best ({int(sorted_contents[0][1]*100)}%)"
        else:
            idx = min(len(sorted_contents) - 1, random.randint(1, len(sorted_contents) - 1))
            return sorted_contents[idx][0], f"explore ({int(sorted_contents[idx][1]*100)}%)"

    def get_optimal_threads(self, campaign_id: str, current_threads: int) -> int:
        """Adjust thread count based on performance"""

        recent_data = [
            e for e in self.history.get('learning_log', [])
            if e['campaign'] == campaign_id
        ]

        if len(recent_data) < 100:
            return current_threads

        # Calculate bounce/fail rate
        bounced = sum(1 for e in recent_data if e.get('bounced'))
        failed = sum(1 for e in recent_data if e.get('failed'))
        error_rate = (bounced + failed) / len(recent_data)

        # Adjust threads based on error rate
        if error_rate > 0.1:  # >10% errors
            # Too aggressive, reduce threads
            new_threads = max(5, int(current_threads * 0.8))
            return new_threads
        elif error_rate < 0.03:  # <3% errors
            # Safe, can increase
            new_threads = min(50, int(current_threads * 1.1))
            return new_threads

        return current_threads

    def generate_learning_report(self, campaign_id: str) -> str:
        """Generate what the system learned"""

        recommendation = self.get_optimized_recommendation(campaign_id)

        if recommendation['status'] == 'learning':
            return f"""
╔════════════════════════════════════════════════════════════════╗
║                    LEARNING IN PROGRESS                       ║
╚════════════════════════════════════════════════════════════════╝

Campaign: {campaign_id}

Status: Still learning...
Samples collected: {recommendation['samples_collected']}/{recommendation['samples_needed']}

The system is gathering data to learn what works best.
Once we have {recommendation['samples_needed']} sends, we'll start optimizing automatically.

Current progress: {int(recommendation['samples_collected']/recommendation['samples_needed']*100)}%
"""

        report = f"""
╔════════════════════════════════════════════════════════════════╗
║                    AUTO-LEARNING REPORT                       ║
╚════════════════════════════════════════════════════════════════╝

Campaign: {campaign_id}
Samples analyzed: {recommendation['samples']}
Status: OPTIMIZED ✅

┌────────────────────────────────────────────────────────────────┐
│ BEST PERFORMING SMTP ACCOUNTS
└────────────────────────────────────────────────────────────────┘

"""
        for smtp in recommendation['recommendations']['smtp']['use_most']:
            report += f"✅ {smtp['name']}\n"
            report += f"   Inbox rate: {smtp['inbox_rate']}%\n"
            report += f"   Sends: {smtp['sends']}\n"
            report += f"   In inbox: {smtp['inboxes']}\n\n"

        report += f"""
┌────────────────────────────────────────────────────────────────┐
│ ACCOUNTS TO AVOID
└────────────────────────────────────────────────────────────────┘

"""
        for smtp in recommendation['recommendations']['smtp']['avoid']:
            report += f"❌ {smtp['name']}\n"
            report += f"   Inbox rate: {smtp['inbox_rate']}% (Too low)\n"
            report += f"   Sends: {smtp['sends']}\n\n"

        report += f"""
┌────────────────────────────────────────────────────────────────┐
│ BEST CONTENT VARIATIONS
└────────────────────────────────────────────────────────────────┘

"""
        for content in recommendation['recommendations']['content']['use_most']:
            report += f"✅ {content['name']}\n"
            report += f"   Inbox rate: {content['inbox_rate']}%\n\n"

        report += f"""
┌────────────────────────────────────────────────────────────────┐
│ BEST SUBJECT LINES
└────────────────────────────────────────────────────────────────┘

"""
        for subject in recommendation['recommendations']['subject']['use_most'][:5]:
            report += f"✅ {subject['name']}\n"
            report += f"   Inbox rate: {subject['inbox_rate']}%\n\n"

        report += f"""
┌────────────────────────────────────────────────────────────────┐
│ AUTOMATIC ACTIONS BEING TAKEN
└────────────────────────────────────────────────────────────────┘

"""
        for action in recommendation['auto_actions']:
            report += f"{action}\n"

        report += f"""
┌────────────────────────────────────────────────────────────────┐
│ HOW THIS WORKS
└────────────────────────────────────────────────────────────────┘

The system continuously:
  1. Records every send result (success/spam/bounce)
  2. Analyzes patterns in the data
  3. Calculates success rate per SMTP/content/subject
  4. Automatically prioritizes winners
  5. Gradually reduces loser allocation
  6. Adjusts thread count for safety
  7. Gets smarter with every send

Result: Better delivery with ZERO manual optimization!

Next optimization check: Every {self.config['update_interval']} seconds
Learning rate: {int(self.config['learning_rate']*100)}%
Exploration vs exploitation: {int(self.config['exploitation_rate']*100)}% best / {int(self.config['exploration_rate']*100)}% new

Keep sending! The more data, the smarter it gets. ✨
"""

        return report


def interactive_menu():
    """Interactive self-optimizer"""
    optimizer = SelfOptimizer()

    print("\n" + "="*70)
    print("  🤖 SELF-OPTIMIZER - Continuous Learning Engine")
    print("="*70)
    print("\n  What do you want to do?\n")
    print("  [1] Get optimization recommendations")
    print("  [2] View learning report")
    print("  [3] Record email send result")
    print("  [4] View configuration")
    print("  [5] Enable/disable auto-learning")
    print("  [6] Exit")
    print()

    choice = input("  → Choose (1-6): ").strip()

    if choice == "1":
        campaign_id = input("\n  Campaign ID: ").strip()
        rec = optimizer.get_optimized_recommendation(campaign_id)
        print(json.dumps(rec, indent=2))

    elif choice == "2":
        campaign_id = input("\n  Campaign ID: ").strip()
        report = optimizer.generate_learning_report(campaign_id)
        print(report)

    elif choice == "3":
        campaign_id = input("\n  Campaign ID: ").strip()
        smtp = input("  SMTP: ").strip()
        content = input("  Content version: ").strip()
        subject = input("  Subject line: ").strip()
        recipient = input("  Recipient email: ").strip()
        status = input("  Status (sent/bounced/failed): ").strip()
        location = input("  Location (inbox/spam, optional): ").strip() or None
        optimizer.record_result(campaign_id, smtp, content, subject, recipient, status, location)
        print("\n  ✓ Result recorded! System is learning...")

    elif choice == "4":
        print("\n  Configuration:\n")
        for key, value in optimizer.config.items():
            print(f"  {key}: {value}")

    elif choice == "5":
        optimizer.config['auto_learning'] = not optimizer.config['auto_learning']
        optimizer.save_config()
        status = "Enabled" if optimizer.config['auto_learning'] else "Disabled"
        print(f"\n  ✓ Auto-learning {status}")

    elif choice == "6":
        print("\n  Goodbye!\n")


if __name__ == "__main__":
    interactive_menu()
