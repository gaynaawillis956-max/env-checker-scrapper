"""
Recipient list operations — merge, filter, deduplicate, sample.
"""
import logging
import re
from pathlib import Path

log = logging.getLogger("mailer_app")


def merge_recipients(*file_paths) -> list:
    """Merge multiple recipient files, deduplicate, return combined list."""
    seen = set()
    lines = []
    for path in file_paths:
        p = Path(path)
        if not p.exists():
            log.warning("File not found (skipping): %s", path)
            continue
        for raw in p.read_text(encoding="utf-8").splitlines():
            addr = raw.strip()
            if not addr or addr.startswith("#"):
                continue
            key = addr.lower()
            if key not in seen:
                seen.add(key)
                lines.append(addr)
    log.info("Merged %d files → %d unique recipients", len(file_paths), len(lines))
    return lines


def filter_by_domain(recipients: list, pattern: str) -> list:
    """
    Filter recipients by domain pattern.
    pattern = 'gmail.com' → only @gmail.com
    pattern = '*.co.uk' → @*.co.uk
    pattern = '^(?!.*test)' → negative: exclude domains with 'test'
    """
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except Exception as e:
        log.error("Invalid filter pattern: %s", e)
        return recipients

    filtered = []
    for addr in recipients:
        if "@" not in addr:
            continue
        domain = addr.split("@")[1]
        if regex.search(domain):
            filtered.append(addr)
    log.info("Domain filter '%s' → %d/%d recipients", pattern, len(filtered), len(recipients))
    return filtered


def sample_recipients(recipients: list, count: int) -> list:
    """Return first N recipients for testing."""
    sampled = recipients[:count]
    log.info("Sampled %d/%d recipients", len(sampled), len(recipients))
    return sampled


def save_recipients(recipients: list, path) -> None:
    """Save recipients list to file, one per line."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(recipients) + "\n", encoding="utf-8")
    log.info("Saved %d recipients → %s", len(recipients), path)
