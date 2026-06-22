import itertools
import logging
import threading
from pathlib import Path

log = logging.getLogger("mailer_app")

FALLBACK_HTML = """\
<!DOCTYPE html>
<html><body>
<p>Hello {recipient},</p>
<p>This is an automated message.</p>
</body></html>
"""


def _load_lines(path, fallback: list) -> list:
    p = Path(path)
    if not p.exists():
        log.warning("File not found: %s — using fallback", path)
        return list(fallback)
    lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    if not lines:
        log.warning("File is empty: %s — using fallback", path)
        return list(fallback)
    return lines


def _load_html_files(folder, fallback_html: str) -> list:
    files = sorted(Path(folder).glob("*.html"))
    if not files:
        log.warning("No .html files in %s — using built-in fallback letter", folder)
        return [fallback_html]
    result = []
    for f in files:
        try:
            result.append(f.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Could not read letter %s: %s", f, e)
    return result if result else [fallback_html]


class Rotator:
    def __init__(self, smtps_path, subjects_path, from_names_path, letters_folder,
                 selected_subjects=None, selected_letters=None):
        smtps = _load_lines(smtps_path, fallback=[])
        if not smtps:
            raise ValueError(f"No SMTP credentials found in: {smtps_path}")

        subjects = _load_lines(subjects_path, fallback=["Hello", "Greetings", "Important Message"])
        if selected_subjects:
            subjects = [s for s in subjects if s in selected_subjects]
            if not subjects:
                subjects = selected_subjects

        names = _load_lines(from_names_path, fallback=["Support Team", "Info", "No Reply"])

        letters = _load_html_files(letters_folder, FALLBACK_HTML)
        if selected_letters:
            # selected_letters are file paths
            letters_dict = {Path(f).read_text(encoding="utf-8"): Path(f).name for f in selected_letters}
            letters = list(letters_dict.keys())
            if not letters:
                letters = _load_html_files(letters_folder, FALLBACK_HTML)

        self._smtp_list = smtps
        self._smtp_cycle = itertools.cycle(smtps)
        self._subject_cycle = itertools.cycle(subjects)
        self._name_cycle = itertools.cycle(names)
        self._letter_cycle = itertools.cycle(letters)

        self._smtp_lock = threading.Lock()
        self._subject_lock = threading.Lock()
        self._name_lock = threading.Lock()
        self._letter_lock = threading.Lock()

    def next_smtp(self) -> tuple:
        with self._smtp_lock:
            raw = next(self._smtp_cycle)
        parts = raw.split("|")
        if len(parts) < 4:
            raise ValueError(f"Invalid SMTP line (expected host|port|user|pass): {raw!r}")
        host, port, user, password = parts[0], int(parts[1]), parts[2], parts[3]
        return host, port, user, password

    def next_subject(self) -> str:
        with self._subject_lock:
            return next(self._subject_cycle)

    def next_from_name(self) -> str:
        with self._name_lock:
            return next(self._name_cycle)

    def next_letter(self) -> str:
        with self._letter_lock:
            return next(self._letter_cycle)

    def smtp_count(self) -> int:
        return len(self._smtp_list)
