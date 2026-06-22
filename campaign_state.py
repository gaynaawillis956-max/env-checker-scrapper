"""Campaign state persistence for recovery and resume functionality."""

import json
import logging
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict

log = logging.getLogger("mailer_app")


@dataclass
class CampaignState:
    """Tracks campaign progress for recovery/resume capability."""

    campaign_id: str = ""
    start_time: float = 0.0
    last_save_time: float = 0.0
    total_recipients: int = 0
    sent_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    sent_addresses: list = field(default_factory=list)  # Track what was actually sent
    failed_addresses: dict = field(default_factory=dict)  # {address: failure_reason}
    skipped_addresses: list = field(default_factory=list)

    @property
    def progress_percent(self) -> float:
        """Calculate current progress percentage."""
        if self.total_recipients <= 0:
            return 0.0
        processed = self.sent_count + self.failed_count + self.skipped_count
        return (processed / self.total_recipients) * 100

    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time since campaign start."""
        if self.start_time <= 0:
            return 0.0
        return time.time() - self.start_time

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CampaignState":
        """Load from dict."""
        return cls(**data)


def save_campaign_state(state: CampaignState, results_dir: Path) -> Path:
    """Save campaign state to JSON file for recovery."""
    results_dir.mkdir(parents=True, exist_ok=True)
    state_file = results_dir / f"campaign_state_{state.campaign_id}.json"

    try:
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, indent=2)
        state.last_save_time = time.time()
        log.debug(f"Campaign state saved: {state_file}")
        return state_file
    except Exception as e:
        log.warning(f"Could not save campaign state: {e}")
        return None


def load_campaign_state(campaign_id: str, results_dir: Path) -> CampaignState:
    """Load campaign state from JSON file."""
    state_file = results_dir / f"campaign_state_{campaign_id}.json"

    if not state_file.exists():
        return None

    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        state = CampaignState.from_dict(data)
        log.info(f"Loaded campaign state: {campaign_id} (progress: {state.progress_percent:.1f}%)")
        return state
    except Exception as e:
        log.warning(f"Could not load campaign state: {e}")
        return None


def delete_campaign_state(campaign_id: str, results_dir: Path) -> bool:
    """Delete campaign state file (after successful completion)."""
    state_file = results_dir / f"campaign_state_{campaign_id}.json"

    if not state_file.exists():
        return True

    try:
        state_file.unlink()
        log.debug(f"Campaign state deleted: {campaign_id}")
        return True
    except Exception as e:
        log.warning(f"Could not delete campaign state: {e}")
        return False


def list_pending_campaigns(results_dir: Path) -> list:
    """List all incomplete campaigns that can be resumed."""
    results_dir.mkdir(parents=True, exist_ok=True)

    pending = []
    for state_file in results_dir.glob("campaign_state_*.json"):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            state = CampaignState.from_dict(data)
            if state.progress_percent < 100:
                pending.append(state)
        except Exception as e:
            log.debug(f"Could not load pending campaign {state_file}: {e}")

    # Sort by most recent
    pending.sort(key=lambda s: s.last_save_time, reverse=True)
    return pending
