import argparse
import signal
import sys
import threading

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    GREEN  = Fore.GREEN
    RED    = Fore.RED
    YELLOW = Fore.YELLOW
    CYAN   = Fore.CYAN
    RESET  = Style.RESET_ALL
except ImportError:
    GREEN = RED = YELLOW = CYAN = RESET = ""

BANNER = f"""{CYAN}
  ███╗   ███╗ █████╗ ██╗██╗     ███████╗██████╗
  ████╗ ████║██╔══██╗██║██║     ██╔════╝██╔══██╗
  ██╔████╔██║███████║██║██║     █████╗  ██████╔╝
  ██║╚██╔╝██║██╔══██║██║██║     ██╔══╝  ██╔══██╗
  ██║ ╚═╝ ██║██║  ██║██║███████╗███████╗██║  ██║
  ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚═╝  ╚═╝
{RESET}"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mailer",
        description="Bulk HTML mailer with SMTP/subject/letter rotation",
    )
    p.add_argument("--smtps",      metavar="FILE", required=True,
                   help="SMTP credentials file (host|port|user|pass per line)")
    p.add_argument("--recipients", metavar="FILE", required=True,
                   help="Recipients file (one email per line)")
    p.add_argument("--subjects",   metavar="FILE", default="data/subjects.txt",
                   help="Subjects file (default: data/subjects.txt)")
    p.add_argument("--from-names", metavar="FILE", default="data/from_names.txt",
                   dest="from_names",
                   help="From-names file (default: data/from_names.txt)")
    p.add_argument("--letters",    metavar="DIR",  default="data/letters",
                   help="HTML letters folder (default: data/letters)")
    p.add_argument("--threads",      metavar="N",    type=int,   default=None,
                   help="Thread count (overrides config)")
    p.add_argument("--delay",        metavar="SECS", type=float, default=None,
                   help="Delay between sends in seconds (overrides config)")
    p.add_argument("--retries",      metavar="N",    type=int,   default=None,
                   help="Retry attempts per recipient on failure (overrides config)")
    p.add_argument("--rate-limit",   metavar="N",    type=float, default=None,
                   dest="rate_limit",
                   help="Max sends per second globally, 0=unlimited (overrides config)")
    p.add_argument("--domain-limit", metavar="N",    type=int,   default=None,
                   dest="domain_limit",
                   help="Max sends per domain per minute, 0=unlimited (overrides config)")
    p.add_argument("--attach",       metavar="FILE", nargs="*",  default=None,
                   help="Files to attach to every email")
    p.add_argument("--pre-check",    action="store_true", dest="pre_check",
                   help="Test all SMTPs before sending, keep only valid ones")
    p.add_argument("--config",       metavar="FILE", default="config/config.json",
                   help="Config JSON file (default: config/config.json)")
    p.add_argument("--no-banner",    action="store_true",
                   help="Skip ASCII banner")
    return p


def _print_progress(snapshot: dict):
    sent    = snapshot["sent"]
    failed  = snapshot["failed"]
    skipped = snapshot["skipped"]
    total   = snapshot["total"]
    elapsed = snapshot["elapsed"]
    pct     = snapshot["percent"]

    bar_width = 20
    filled = int(bar_width * pct / 100)
    bar = "█" * filled + "░" * (bar_width - filled)

    line = (
        f"\r  [{CYAN}{bar}{RESET}] {pct:5.1f}%  "
        f"{GREEN}Sent:{sent:<5}{RESET}"
        f"{RED}Fail:{failed:<5}{RESET}"
        f"{YELLOW}Skip:{skipped:<5}{RESET}"
        f"/{total}  {elapsed:.1f}s  "
    )
    sys.stdout.write(line)
    sys.stdout.flush()


def main():
    from .core.config import ensure_dirs, load_config, setup_logging
    from .core.mailer import run_campaign
    from .core.smtp_checker import check_smtps

    ensure_dirs()

    parser = build_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    if args.threads is not None:
        config["threads"] = max(1, min(args.threads, 100))
    if args.delay is not None:
        config["delay_seconds"] = max(0.0, args.delay)
    if args.retries is not None:
        config["retries"] = max(0, min(args.retries, 10))
    if args.rate_limit is not None:
        config["rate_per_second"] = max(0.0, args.rate_limit)
    if args.domain_limit is not None:
        config["domain_limit_per_minute"] = max(0, args.domain_limit)

    log = setup_logging(config["log_file"], config["log_level"])
    # Silence all handlers so log messages don't interrupt the \r progress line.
    # Errors still reach the log file because the FileHandler is kept in setup_logging.
    for h in log.handlers:
        h.setLevel(9999)

    if not args.no_banner:
        print(BANNER)

    pause_event = threading.Event()
    pause_event.set()
    stop_event = threading.Event()

    def _sigint_handler(sig, frame):
        print(f"\n{YELLOW}Stopping... waiting for workers to finish.{RESET}")
        stop_event.set()
        pause_event.set()

    signal.signal(signal.SIGINT, _sigint_handler)

    smtps_path = args.smtps

    if args.pre_check:
        print(f"\n  {CYAN}Pre-checking SMTPs...{RESET}")
        _checked = [0]
        _valid_count = [0]

        def _check_progress(checked, total, valid):
            _checked[0] = checked
            _valid_count[0] = valid
            bar_w = 20
            pct = checked / total * 100 if total else 0
            filled = int(bar_w * pct / 100)
            bar = "█" * filled + "░" * (bar_w - filled)
            sys.stdout.write(
                f"\r  [{CYAN}{bar}{RESET}] {pct:5.1f}%  "
                f"{GREEN}Valid:{valid:<5}{RESET}/{checked}  "
            )
            sys.stdout.flush()

        try:
            valid_lines = check_smtps(
                smtps_path,
                threads=min(config.get("threads", 10), 30),
                timeout=config.get("smtp_timeout", 10),
                save_valid=True,
                progress_callback=_check_progress,
            )
        except (FileNotFoundError, ValueError) as e:
            print(f"\n{RED}SMTP check error: {e}{RESET}")
            sys.exit(1)

        out_path = str(smtps_path) + ".checked.txt" if not smtps_path.endswith(".checked.txt") \
            else smtps_path
        print(f"\n  {GREEN}SMTP check done — {len(valid_lines)} valid → {out_path}{RESET}\n")

        if not valid_lines:
            print(f"{RED}No valid SMTPs found. Aborting.{RESET}")
            sys.exit(1)
        smtps_path = out_path

    print(f"  {CYAN}SMTPs     :{RESET} {smtps_path}")
    print(f"  {CYAN}Recipients:{RESET} {args.recipients}")
    print(f"  {CYAN}Threads   :{RESET} {config['threads']}")
    print(f"  {CYAN}Delay     :{RESET} {config['delay_seconds']}s")
    print(f"  {CYAN}Retries   :{RESET} {config['retries']}")
    if config["rate_per_second"]:
        print(f"  {CYAN}Rate limit:{RESET} {config['rate_per_second']}/s")
    if config["domain_limit_per_minute"]:
        print(f"  {CYAN}Domain lim:{RESET} {config['domain_limit_per_minute']}/min")
    if args.attach:
        print(f"  {CYAN}Attachments:{RESET} {', '.join(args.attach)}")
    print()

    try:
        stats = run_campaign(
            recipients_path=args.recipients,
            smtps_path=smtps_path,
            subjects_path=args.subjects,
            from_names_path=args.from_names,
            letters_folder=args.letters,
            config=config,
            pause_event=pause_event,
            stop_event=stop_event,
            attachments=args.attach or [],
            progress_callback=_print_progress,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"\n{RED}Error: {e}{RESET}")
        sys.exit(1)

    snap = stats.snapshot()
    print(f"\n\n{'─'*50}")
    print(f"  {GREEN}Sent   : {snap['sent']}{RESET}")
    print(f"  {RED}Failed : {snap['failed']}{RESET}")
    print(f"  {YELLOW}Skipped: {snap['skipped']}{RESET}")
    print(f"  Elapsed: {snap['elapsed']:.1f}s")
    if snap["reasons"]:
        print(f"  Failure breakdown: {snap['reasons']}")
    print(f"{'─'*50}")
    print(f"  Results : {config['results_file']}")
    print(f"  Report  : results/report_<timestamp>.txt")
