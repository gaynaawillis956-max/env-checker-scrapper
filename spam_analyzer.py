#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spam Analyzer - Detect Spam Triggers in Email Content
Identify what's making emails go to spam
"""
import re
import sys

class SpamAnalyzer:
    """Analyze email for spam triggers"""

    def __init__(self):
        # Spam trigger patterns
        self.triggers = {
            'urgent_words': [
                r'\b(urgent|urgent|act now|buy now|click here|limited time|expires|deadline|immediate|asap|don\'t wait|hurry|rush|quick decision)\b',
            ],
            'all_caps': r'[A-Z]{3,}',  # 3+ consecutive caps
            'suspicious_links': [
                r'(bit\.ly|tinyurl|short\.link|goo\.gl|ow\.ly)',
                r'http:\/\/',  # non-HTTPS links
            ],
            'excessive_punctuation': r'[!?]{2,}',  # Multiple ! or ?
            'too_many_links': None,  # Checked separately
            'no_unsubscribe': None,  # Checked separately
            'misleading_subject': [
                r'(re:|fwd:|reply)',
                r'\[no-reply\]',
            ],
            'suspicious_sender': [
                r'(noreply|no-reply|donotreply)',
                r'(support|info|admin)@(gmail|yahoo|hotmail)',
            ],
            'excessive_images': None,  # Checked separately
            'poor_formatting': None,  # Checked separately
            'spammy_words': [
                'free', 'win', 'congratulations', 'claim', 'prize', 'bonus',
                'winner', 'cash', 'money', 'bank', 'guarantee', 'risk-free',
                'no credit card', 'limited time', 'act now', 'apply now',
                'click here', 'order now', 'buy now', 'exclusive', 'urgent',
                'viagra', 'casino', 'lottery', 'weight loss', 'work from home'
            ]
        }

    def analyze_subject(self, subject: str) -> dict:
        """Analyze subject line"""
        issues = []
        score = 100

        # Check all caps
        if re.search(r'[A-Z]{5,}', subject):
            issues.append("⚠️  Multiple ALL CAPS words (triggers spam filter)")
            score -= 10

        # Check excessive punctuation
        if re.search(r'[!?]{2,}', subject):
            issues.append("⚠️  Excessive punctuation (!! or ??)")
            score -= 10

        # Check urgent/spammy words
        spammy = ['urgent', 'act now', 'buy now', 'click here', 'limited time', 'expires']
        for word in spammy:
            if word.lower() in subject.lower():
                issues.append(f"⚠️  Contains '{word}' (common spam word)")
                score -= 5

        # Check length
        if len(subject) < 5:
            issues.append("⚠️  Subject too short")
            score -= 5

        if len(subject) > 100:
            issues.append("⚠️  Subject too long (over 100 chars)")
            score -= 5

        return {
            'score': max(0, score),
            'issues': issues,
            'suggestion': 'Subject looks good' if score >= 80 else 'Improve subject line for better delivery'
        }

    def analyze_body(self, body: str) -> dict:
        """Analyze email body"""
        issues = []
        score = 100

        # Count links
        links = re.findall(r'https?://[^\s\)]+', body)
        if len(links) > 5:
            issues.append(f"⚠️  Too many links ({len(links)}) - limit to 3-5")
            score -= 15
        elif len(links) > 0:
            pass  # Links are OK

        # Check HTTP (non-HTTPS)
        if re.search(r'http://', body):
            issues.append("⚠️  Contains non-HTTPS links (http:// instead of https://)")
            score -= 10

        # Check shorteners
        if re.search(r'(bit\.ly|tinyurl|short\.link|goo\.gl|ow\.ly)', body):
            issues.append("⚠️  Contains link shortener (bit.ly, tinyurl, etc)")
            score -= 10

        # Check image ratio
        images = len(re.findall(r'<img[^>]+>', body, re.IGNORECASE))
        if images > 5:
            issues.append(f"⚠️  Too many images ({images}) - text-heavy is better")
            score -= 10

        if images > 0 and len(body) < 200:
            issues.append("⚠️  Image-only or very little text (add more text content)")
            score -= 10

        # Check all caps words
        caps_words = re.findall(r'\b[A-Z]{4,}\b', body)
        if len(caps_words) > 5:
            issues.append(f"⚠️  Too many ALL CAPS words ({len(caps_words)})")
            score -= 10

        # Check excessive punctuation
        if re.search(r'[!?]{2,}', body):
            exclamations = len(re.findall(r'!', body))
            if exclamations > len(body) // 50:  # More than 1 per 50 chars
                issues.append(f"⚠️  Too many exclamation marks ({exclamations})")
                score -= 10

        # Check spammy words
        spammy_words = [
            'free', 'congratulations', 'claim your', 'winner', 'prize',
            'cash', 'money', 'guarantee', 'risk-free', 'no credit card',
            'apply now', 'order now', 'viagra', 'casino', 'lottery'
        ]
        found_spammy = []
        for word in spammy_words:
            if word.lower() in body.lower():
                found_spammy.append(word)

        if found_spammy:
            issues.append(f"⚠️  Contains spammy words: {', '.join(found_spammy)}")
            score -= 5 * len(found_spammy)

        # Check no unsubscribe
        if not re.search(r'unsubscribe|opt-out', body, re.IGNORECASE):
            issues.append("⚠️  No unsubscribe link (required by law)")
            score -= 10

        # Check body length
        text_only = re.sub(r'<[^>]+>', '', body)
        if len(text_only) < 50:
            issues.append("⚠️  Email body too short")
            score -= 10

        return {
            'score': max(0, score),
            'issues': issues,
            'link_count': len(links),
            'image_count': images,
            'suggestion': 'Email content looks good' if score >= 70 else 'Improve email content for better inbox delivery'
        }

    def analyze_headers(self, from_addr: str, reply_to: str = None) -> dict:
        """Analyze email headers"""
        issues = []
        score = 100

        # Check from address
        if 'noreply' in from_addr.lower() or 'no-reply' in from_addr.lower():
            issues.append("⚠️  From address contains 'noreply' (bad for reputation)")
            score -= 15

        if 'support' in from_addr.lower() or 'info' in from_addr.lower():
            issues.append("⚠️  Generic from address (use personal name instead)")
            score -= 5

        # Check free email providers
        free_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com']
        domain = from_addr.split('@')[1] if '@' in from_addr else ''
        if domain.lower() in free_domains:
            issues.append(f"⚠️  Using free email provider ({domain}) - consider company domain")
            score -= 10

        # Check reply-to
        if not reply_to:
            issues.append("⚠️  No Reply-To header set")
            score -= 5

        return {
            'score': max(0, score),
            'issues': issues,
            'from': from_addr,
            'suggestion': 'Headers look good' if score >= 85 else 'Improve email headers for better reputation'
        }

    def get_overall_score(self, subject: str, body: str, from_addr: str, reply_to: str = None) -> dict:
        """Get overall spam score"""
        subject_analysis = self.analyze_subject(subject)
        body_analysis = self.analyze_body(body)
        headers_analysis = self.analyze_headers(from_addr, reply_to)

        # Weight the scores
        overall = (subject_analysis['score'] * 0.25 +
                  body_analysis['score'] * 0.50 +
                  headers_analysis['score'] * 0.25)

        # Determine likelihood
        if overall >= 80:
            likelihood = "✅ High Inbox Delivery (Low Spam Risk)"
            emoji = "✅"
        elif overall >= 60:
            likelihood = "⚠️  Medium Risk (Some Changes Needed)"
            emoji = "⚠️"
        else:
            likelihood = "🚨 High Spam Risk (Major Changes Needed)"
            emoji = "🚨"

        all_issues = []
        all_issues.extend(subject_analysis['issues'])
        all_issues.extend(body_analysis['issues'])
        all_issues.extend(headers_analysis['issues'])

        return {
            'overall_score': int(overall),
            'likelihood': likelihood,
            'emoji': emoji,
            'subject': subject_analysis,
            'body': body_analysis,
            'headers': headers_analysis,
            'all_issues': all_issues,
            'improvements_needed': len(all_issues),
            'recommendations': self.get_recommendations(subject_analysis, body_analysis, headers_analysis)
        }

    def get_recommendations(self, subject_analysis, body_analysis, headers_analysis):
        """Get actionable recommendations"""
        recommendations = []

        if subject_analysis['score'] < 80:
            recommendations.append("• Simplify subject line - avoid urgent/spammy words")
            recommendations.append("• Remove excessive punctuation from subject")
            recommendations.append("• Keep subject under 60 characters")

        if body_analysis['score'] < 70:
            recommendations.append("• Add more text content (less image-heavy)")
            recommendations.append("• Reduce number of links (use max 3-5)")
            recommendations.append("• Add unsubscribe link at bottom")
            recommendations.append("• Remove spammy words (free, congratulations, etc)")

        if headers_analysis['score'] < 85:
            recommendations.append("• Use branded From address (not noreply)")
            recommendations.append("• Set Reply-To header to valid email")
            recommendations.append("• Consider using company domain instead of free email")

        if not recommendations:
            recommendations.append("✅ Email looks great! Ready to send.")

        return recommendations


def interactive_menu():
    """Interactive spam analyzer"""
    analyzer = SpamAnalyzer()

    print("\n" + "="*80)
    print("  📧 SPAM ANALYZER - Check If Your Email Goes to Inbox or Spam")
    print("="*80)
    print()

    # Get email details
    subject = input("  Subject line: ").strip()
    from_addr = input("  From address: ").strip()
    reply_to = input("  Reply-To (optional): ").strip() or None

    print("\n  Email body (paste, then Ctrl+D or Ctrl+Z+Enter):")
    lines = []
    while True:
        try:
            line = input()
            lines.append(line)
        except EOFError:
            break

    body = "\n".join(lines)

    # Analyze
    print("\n" + "="*80)
    print("  🔍 ANALYSIS RESULTS")
    print("="*80)
    print()

    result = analyzer.get_overall_score(subject, body, from_addr, reply_to)

    # Overall score
    print(f"  {result['emoji']} OVERALL INBOX DELIVERY SCORE: {result['overall_score']}/100")
    print(f"     {result['likelihood']}")
    print()

    # Subject analysis
    print(f"  📧 SUBJECT LINE SCORE: {result['subject']['score']}/100")
    if result['subject']['issues']:
        for issue in result['subject']['issues']:
            print(f"     {issue}")
    else:
        print("     ✅ Subject line looks good")
    print()

    # Body analysis
    print(f"  📝 EMAIL BODY SCORE: {result['body']['score']}/100")
    if result['body']['issues']:
        for issue in result['body']['issues']:
            print(f"     {issue}")
    else:
        print("     ✅ Email body looks good")
    print()

    # Headers analysis
    print(f"  🔐 HEADERS SCORE: {result['headers']['score']}/100")
    if result['headers']['issues']:
        for issue in result['headers']['issues']:
            print(f"     {issue}")
    else:
        print("     ✅ Headers look good")
    print()

    # Recommendations
    print(f"  💡 RECOMMENDATIONS ({len(result['recommendations'])} changes)")
    for rec in result['recommendations']:
        print(f"     {rec}")
    print()

    # Save report
    import json
    from datetime import datetime
    report_file = f"spam_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        # Remove functions from result for JSON serialization
        json_result = {k: v for k, v in result.items() if not callable(v)}
        json.dump(json_result, f, indent=2)
    print(f"  💾 Report saved: {report_file}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--batch':
        # Batch mode: analyze from file
        if len(sys.argv) < 4:
            print("\nUsage: python3 spam_analyzer.py --batch subject body from_addr [reply_to]\n")
            sys.exit(1)

        analyzer = SpamAnalyzer()
        result = analyzer.get_overall_score(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else None)
        import json
        print(json.dumps(result, indent=2))
    else:
        interactive_menu()
