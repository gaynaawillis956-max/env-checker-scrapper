"""Email preview functionality - render final email as it will be sent."""

import re
from pathlib import Path


def expand_template(text: str, recipient: str) -> str:
    """Expand template variables in text for a specific recipient."""
    import time

    name = recipient.split("@")[0] if "@" in recipient else recipient
    domain = recipient.split("@")[1] if "@" in recipient else ""
    now = time.localtime()

    replacements = {
        "{recipient}": recipient,
        "{email}": recipient,
        "{name}": name,
        "{domain}": domain,
        "{date}": time.strftime("%B %d, %Y", now),
        "{time}": time.strftime("%H:%M", now),
        "{year}": time.strftime("%Y", now),
        "{month}": time.strftime("%B", now),
    }

    result = text
    for key, val in replacements.items():
        result = result.replace(key, val)
    return result


class EmailPreview:
    """Generate preview of email as it will be sent to a recipient."""

    def __init__(self, subject_template: str, letter_template: str, from_name_template: str):
        self.subject_template = subject_template
        self.letter_template = letter_template
        self.from_name_template = from_name_template

    def preview_for_recipient(self, recipient: str) -> dict:
        """Generate preview for specific recipient."""
        return {
            "recipient": recipient,
            "subject": expand_template(self.subject_template, recipient),
            "from_name": expand_template(self.from_name_template, recipient),
            "body_html": expand_template(self.letter_template, recipient),
        }

    def validate_template_variables(self) -> list:
        """Check for undefined template variables."""
        # Find all {variables} in templates
        pattern = r'\{([^}]+)\}'

        supported_vars = {
            "recipient", "email", "name", "domain",
            "date", "time", "year", "month"
        }

        found_vars = set()
        for template in [self.subject_template, self.from_name_template, self.letter_template]:
            matches = re.findall(pattern, template)
            found_vars.update(matches)

        undefined = found_vars - supported_vars
        return list(undefined) if undefined else []

    @staticmethod
    def validate_html(html: str) -> tuple:
        """Validate HTML is well-formed (basic check)."""
        issues = []

        # Check for matching tags
        open_tags = re.findall(r'<(\w+)[^>]*>', html)
        close_tags = re.findall(r'</(\w+)>', html)

        # Self-closing tags that don't need closing
        self_closing = {'br', 'hr', 'img', 'input', 'link', 'meta'}

        for tag in open_tags:
            if tag.lower() not in self_closing:
                if close_tags.count(tag) != open_tags.count(tag):
                    issues.append(f"Mismatched <{tag}> tag")

        # Check for common issues
        if '<body>' in html.lower() and '</body>' not in html.lower():
            issues.append("Missing closing </body> tag")
        if '<html>' in html.lower() and '</html>' not in html.lower():
            issues.append("Missing closing </html> tag")

        return (len(issues) == 0, issues)


def load_templates_from_files(
    subjects_file: str,
    from_names_file: str,
    letters_folder: str,
    subject_idx: int = 0,
    from_name_idx: int = 0,
    letter_idx: int = 0,
) -> tuple:
    """Load templates from files and get specific ones by index."""

    # Load subjects
    subjects = []
    if Path(subjects_file).exists():
        with open(subjects_file, 'r', encoding='utf-8') as f:
            subjects = [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith('#')
            ]
    subject = subjects[subject_idx % len(subjects)] if subjects else "Hello"

    # Load from-names
    from_names = []
    if Path(from_names_file).exists():
        with open(from_names_file, 'r', encoding='utf-8') as f:
            from_names = [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith('#')
            ]
    from_name = from_names[from_name_idx % len(from_names)] if from_names else "Sender"

    # Load letters
    letters = list(Path(letters_folder).glob("*.html"))
    if letters:
        letter_file = letters[letter_idx % len(letters)]
        letter = letter_file.read_text(encoding='utf-8')
    else:
        letter = "<html><body><p>Hello {recipient}</p></body></html>"

    return subject, from_name, letter
