import concurrent.futures
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from rate_limiter import DomainThrottle, RateLimiter
from rotator import Rotator
from smtp_client import SMTPSendError, send_email

log = logging.getLogger("mailer_app")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _expand_template(text: str, recipient: str) -> str:
    """Replace all supported placeholders in a template string."""
    name = recipient.split("@")[0] if "@" in recipient else recipient
    domain = recipient.split("@")[1] if "@" in recipient else ""
    now = time.localtime()
    replacements = {
        "{recipient}": recipient,
        "{email}":     recipient,
        "{name}":      name,
        "{domain}":    domain,
        "{date}":      time.strftime("%B %d, %Y", now),
        "{time}":      time.strftime("%H:%M", now),
        "{year}":      time.strftime("%Y", now),
        "{month}":     time.strftime("%B", now),
    }
    for key, val in replacements.items():
        text = text.replace(key, val)
    return text


@dataclass
class MailStats:
    total: int = 0
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    start_time: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _failed_reasons: dict = field(default_factory=dict, repr=False)

    def inc_sent(self):
        with self._lock:
            self.sent += 1

    def inc_failed(self, reason: str = ""):
        with self._lock:
            self.failed += 1
            self._failed_reasons[reason] = self._failed_reasons.get(reason, 0) + 1

    def inc_skipped(self):
        with self._lock:
            self.skipped += 1

    def elapsed(self) -> float:
        return time.time() - self.start_time

    def snapshot(self) -> dict:
        with self._lock:
            done = self.sent + self.failed + self.skipped
            pct = (done / self.total * 100) if self.total else 0.0
            return {
                "total": self.total,
                "sent": self.sent,
                "failed": self.failed,
                "skipped": self.skipped,
                "elapsed": self.elapsed(),
                "percent": pct,
                "reasons": dict(self._failed_reasons),
            }


def load_recipients(path) -> list:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Recipients file not found: {path}")
    seen = set()
    lines = []
    invalid = 0
    raw_count = 0
    for raw in p.read_text(encoding="utf-8").splitlines():
        addr = raw.strip()
        if not addr or addr.startswith("#"):
            continue
        raw_count += 1
        if not _EMAIL_RE.match(addr):
            log.warning("Skipping invalid email address: %r", addr)
            invalid += 1
            continue
        key = addr.lower()
        if key not in seen:
            seen.add(key)
            lines.append(addr)
    if not lines:
        raise ValueError(f"Recipients file is empty or all addresses are invalid: {path}")
    dupes = raw_count - invalid - len(lines)
    if dupes:
        log.info("Deduplicated %d duplicate recipient(s)", dupes)
    if invalid:
        log.info("Skipped %d invalid email address(es)", invalid)
    return lines


def _append_result(results_path: Path, lock: threading.Lock, line: str):
    with lock:
        with results_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def _send_worker(
    recipient: str,
    rotator: Rotator,
    stats: MailStats,
    config: dict,
    results_path: Path,
    results_lock: threading.Lock,
    pause_event: threading.Event,
    stop_event: threading.Event,
    rate_limiter: RateLimiter,
    domain_throttle: DomainThrottle,
    attachments: list,
    progress_callback=None,
):
    if stop_event.is_set():
        stats.inc_skipped()
        return

    pause_event.wait()

    if stop_event.is_set():
        stats.inc_skipped()
        return

    # Global rate limit
    rate_limiter.wait()
    # Per-domain throttle
    domain_throttle.wait(recipient)

    retries = config.get("retries", 1)
    subject   = _expand_template(rotator.next_subject(), recipient)
    from_name = _expand_template(rotator.next_from_name(), recipient)
    html_body = _expand_template(rotator.next_letter(), recipient)
    timeout = config.get("smtp_timeout", 10)

    last_reason = "unknown"
    sent = False
    host = port = user = ""

    for attempt in range(1, retries + 2):
        if stop_event.is_set():
            stats.inc_skipped()
            return
        try:
            host, port, user, password = rotator.next_smtp()
            send_email(
                host, port, user, password,
                recipient, subject, html_body, from_name,
                smtp_timeout=timeout,
                attachments=attachments,
            )
            sent = True
            break
        except SMTPSendError as e:
            last_reason = e.reason
            if attempt <= retries:
                log.warning("Retry %d/%d for %s (reason: %s)", attempt, retries, recipient, e.reason)
        except Exception as e:
            last_reason = "worker_error"
            log.error("ERROR → %s | %s", recipient, e)
            break

    if sent:
        stats.inc_sent()
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        _append_result(results_path, results_lock,
                       f"{ts}|{host}|{port}|{user}|{recipient}|{subject}")
        log.info("SENT  → %s via %s", recipient, user)
    else:
        stats.inc_failed(last_reason)
        log.error("FAIL  → %s | reason: %s", recipient, last_reason)

    if progress_callback:
        try:
            progress_callback(stats.snapshot())
        except Exception:
            pass

    delay = config.get("delay_seconds", 1.0)
    if delay > 0 and not stop_event.is_set():
        time.sleep(delay)


def run_campaign(
    recipients_path,
    smtps_path,
    subjects_path,
    from_names_path,
    letters_folder,
    config: dict,
    pause_event: threading.Event,
    stop_event: threading.Event,
    attachments: list = None,
    selected_subjects: list = None,
    selected_letters: list = None,
    progress_callback=None,
    completion_callback=None,
) -> MailStats:
    recipients = load_recipients(recipients_path)
    rotator = Rotator(smtps_path, subjects_path, from_names_path, letters_folder,
                      selected_subjects=selected_subjects, selected_letters=selected_letters)

    stats = MailStats(total=len(recipients))
    results_path = Path(config.get("results_file", "results/sent.txt"))
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_lock = threading.Lock()

    rate_limiter = RateLimiter(config.get("rate_per_second", 0))
    domain_throttle = DomainThrottle(config.get("domain_limit_per_minute", 0))

    log.info(
        "Campaign start — %d recipients, %d SMTPs, %d threads",
        len(recipients), rotator.smtp_count(), config.get("threads", 10),
    )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=config.get("threads", 10)
    ) as executor:
        futures = {
            executor.submit(
                _send_worker, recipient, rotator, stats, config,
                results_path, results_lock, pause_event, stop_event,
                rate_limiter, domain_throttle, attachments or [],
                progress_callback,
            ): recipient
            for recipient in recipients
        }
        for future in concurrent.futures.as_completed(futures):
            exc = future.exception()
            if exc:
                log.error("Unhandled worker error for %s: %s", futures[future], exc)

    elapsed = stats.elapsed()
    log.info(
        "Campaign done — sent=%d failed=%d skipped=%d elapsed=%.1fs",
        stats.sent, stats.failed, stats.skipped, elapsed,
    )

    _write_report(stats, config)

    if completion_callback:
        try:
            completion_callback(stats)
        except Exception:
            pass

    return stats


def _write_report(stats: MailStats, config: dict):
    """Write a plain-text summary report to results/report_<timestamp>.txt."""
    try:
        snap = stats.snapshot()
        ts = time.strftime("%Y%m%d_%H%M%S")
        report_dir = Path(config.get("results_file", "results/sent.txt")).parent
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"report_{ts}.txt"

        sep = "=" * 52
        lines = [
            sep,
            f"  Campaign Report  -  {time.strftime('%Y-%m-%d %H:%M:%S')}",
            sep,
            f"  Total recipients : {snap['total']}",
            f"  Sent successfully: {snap['sent']}",
            f"  Failed           : {snap['failed']}",
            f"  Skipped          : {snap['skipped']}",
            f"  Elapsed          : {snap['elapsed']:.1f}s",
        ]
        if snap["total"] and snap["elapsed"]:
            rate = snap["sent"] / snap["elapsed"]
            lines.append(f"  Throughput       : {rate:.2f} sent/s")
        if snap["reasons"]:
            lines.append("")
            lines.append("  Failure breakdown:")
            for reason, count in sorted(snap["reasons"].items(), key=lambda x: -x[1]):
                lines.append(f"    {reason:<30} {count}")
        lines.append(sep)

        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log.info("Report saved → %s", report_path)
    except Exception as e:
        log.warning("Could not write report: %s", e)
