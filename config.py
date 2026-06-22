import json
import logging
from pathlib import Path

DEFAULT_CONFIG = {
    "threads": 10,
    "delay_seconds": 1.0,
    "smtp_timeout": 10,
    "retries": 1,
    "rate_per_second": 0,
    "domain_limit_per_minute": 0,
    "log_level": "INFO",
    "results_file": "results/sent.txt",
    "log_file": "logs/app.log",
}

REQUIRED_DIRS = [
    "data/letters",
    "logs",
    "results",
    "config",
    "data",
]


def load_config(path: str = "config/config.json") -> dict:
    cfg = dict(DEFAULT_CONFIG)
    p = Path(path)
    if p.exists():
        try:
            with p.open("r", encoding="utf-8") as f:
                file_cfg = json.load(f)
            cfg.update(file_cfg)
        except Exception as e:
            logging.warning("Could not load config from %s: %s — using defaults", path, e)
    return cfg


def ensure_dirs() -> None:
    for d in REQUIRED_DIRS:
        Path(d).mkdir(parents=True, exist_ok=True)


def setup_logging(log_file: str, level: str) -> logging.Logger:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger("mailer_app")
    if logger.handlers:
        return logger
    logger.setLevel(numeric)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.ERROR)
    fh.setFormatter(fmt)

    sh = logging.StreamHandler()
    sh.setLevel(numeric)
    sh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger
