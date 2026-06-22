"""
Fast SMTP pre-checker. Tests a list of credentials and returns only the valid ones.
Reuses the same STARTTLS flow as smtp_client so behaviour is consistent.
"""
import concurrent.futures
import logging
import smtplib
import threading
import time
from pathlib import Path

log = logging.getLogger("mailer_app")


def _test_one(line: str, timeout: int) -> tuple:
    """Returns (line, True, None) on success or (line, False, reason) on failure."""
    line = line.strip()
    if not line or line.startswith("#"):
        return line, None, None  # skip
    parts = line.split("|")
    if len(parts) < 4:
        return line, False, "bad_format"
    host, port_str, user, password = parts[0], parts[1], parts[2], parts[3]
    try:
        port = int(port_str)
    except ValueError:
        return line, False, "bad_port"
    server = None
    try:
        server = smtplib.SMTP(host, port, timeout=timeout)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user, password)
        return line, True, None
    except smtplib.SMTPAuthenticationError:
        return line, False, "auth_failed"
    except smtplib.SMTPConnectError:
        return line, False, "connect_failed"
    except smtplib.SMTPServerDisconnected:
        return line, False, "disconnected"
    except smtplib.SMTPException as e:
        return line, False, f"smtp:{e}"
    except (OSError, ValueError) as e:
        return line, False, f"network:{e}"
    except Exception as e:
        return line, False, f"unexpected:{e}"
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


def check_smtps(
    smtps_path,
    threads: int = 20,
    timeout: int = 10,
    save_valid: bool = True,
    progress_callback=None,
    stop_event: threading.Event = None,
) -> list:
    """
    Read smtps_path, test each credential, return list of valid lines.
    Optionally writes valid lines back to smtps_path + '.checked.txt'.
    progress_callback(checked, total, valid_count) called after each result.
    """
    p = Path(smtps_path)
    if not p.exists():
        raise FileNotFoundError(f"SMTP file not found: {smtps_path}")

    lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    total = len(lines)
    valid = []
    checked = 0
    lock = threading.Lock()

    def _worker(line):
        nonlocal checked
        if stop_event and stop_event.is_set():
            return
        result_line, ok, reason = _test_one(line, timeout)
        with lock:
            checked += 1
            if ok:
                valid.append(result_line)
            if progress_callback:
                try:
                    progress_callback(checked, total, len(valid))
                except Exception:
                    pass
        if ok:
            log.info("VALID  %s", result_line.split("|")[2] if "|" in result_line else result_line)
        elif ok is False:
            log.debug("INVALID %s — %s", result_line.split("|")[2] if "|" in result_line else result_line, reason)

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
        futures = [ex.submit(_worker, l) for l in lines]
        concurrent.futures.wait(futures)

    if save_valid and valid:
        out = p.with_suffix(".checked.txt")
        out.write_text("\n".join(valid) + "\n", encoding="utf-8")
        log.info("Saved %d valid SMTPs → %s", len(valid), out)

    log.info("SMTP check done — %d/%d valid", len(valid), total)
    return valid
